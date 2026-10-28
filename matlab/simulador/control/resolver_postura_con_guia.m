
function resultado = resolver_postura_con_guia( ...
    modelo,pose,opciones)
% RESOLVER_POSTURA_CON_GUIA
%
% Resuelve una postura lingual con FEM no lineal.
%
% MODOS:
% - Directo: una resolucion FEM guiada.
% - Comparativo: postura base + postura guiada.
%
% La postura base tambien se calcula cuando
% existe un objetivo angular relativo.
%
% No modifica la geometria de referencia.
% No realiza simulacion dinamica.

%% 1. OPCIONES

if nargin < 3 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('Opciones invalidas.');
end

opNL = leer(opciones, ...
    'opcionesNoLineales',struct());

factorGuia = leer( ...
    opciones,'factorRigidezGuia',0.25);

factorAngular = leer( ...
    opciones,'factorRigidezAngular',0.20);

activacion = leer(opciones,'activacion',[]);

suavidad = leer( ...
    opciones,'suavidad',struct());

mostrarConsola = leer( ...
    opciones,'mostrarConsola',true);

calcularBaseComparativa = leer( ...
    opciones,'calcularBaseComparativa',false);

if ~isstruct(pose) || ...
        ~isscalar(pose) || ...
        ~isfield(pose,'puntaYZ') || ...
        ~isfield(pose,'objetivos') || ...
        ~isfield(pose,'apice')
    error('Postura incompatible.');
end

%% 2. OBJETIVO FEM PRINCIPAL

objBase = struct();

objBase.puntaYZ = pose.puntaYZ;
objBase.modo = 'prescrito';
objBase.componentes = [true true];

objBase.suavidad = suavidad;

if ~isempty(activacion)
    objBase.activacion = activacion;
end

%% 3. DETERMINAR SI NECESITAMOS POSTURA BASE

deltaAngulo = pose.apice.deltaAngulo_deg;

necesitaBase = ...
    calcularBaseComparativa || ...
    isfinite(deltaAngulo);

estadoBase = [];
thetaBase = NaN;

% Preparar guia sin alterar pose.
guia = pose;

guia.apice.anguloObjetivo_deg = NaN;

%% 4. RESOLUCION BASE OPCIONAL

if necesitaBase

    if mostrarConsola
        fprintf('\nResolviendo postura base...\n');
    end

    estadoBase = resolver_postura_no_lineal( ...
        modelo,objBase,opNL);

    % Orientacion apical en la postura base.
    a = pose.apice.anterior;
    p = pose.apice.posterior;

    pa = a.coef*estadoBase.nodos(a.ids,:);
    pp = p.coef*estadoBase.nodos(p.ids,:);

    vBase = pa-pp;

    thetaBase = atan2d(vBase(2),vBase(1));

    % Convertir cambio angular relativo
    % en orientacion absoluta objetivo.
    if isfinite(deltaAngulo)

        guia.apice.anguloObjetivo_deg = ...
            thetaBase+deltaAngulo;

    end

end

%% 5. GUIADO DISTRIBUIDO

opDistribucion = leer( ...
    opciones,'distribucionGuia', ...
    struct('modo','puntual'));

guia = preparar_guia_distribuida( ...
    modelo.malla,guia,opDistribucion);

%% 6. OBJETIVO GUIADO

objGuia = objBase;

objGuia.guia = guia;

objGuia.factorRigidezGuia = factorGuia;
objGuia.factorRigidezAngular = factorAngular;

%% CONTROL OPCIONAL DE FORMA

if isfield(opciones,'controlForma') && ...
        ~isempty(opciones.controlForma)

    objGuia.controlForma = controlar_forma_lingual( ...
        'preparar',modelo,opciones.controlForma);

end

%% 7. RESOLVER POSTURA FINAL

if mostrarConsola
    fprintf('\nResolviendo postura guiada...\n');
end

estadoGuiado = resolver_postura_no_lineal( ...
    modelo,objGuia,opNL);

%% 8. POSICIONES MATERIALES

n = numel(pose.objetivos);

% NaN indica que no se calculo comparacion.
puntosBase = nan(n,2);

puntosFinal = zeros(n,2);

errores = nan(n,2);

for i = 1:n

    ancla = pose.objetivos(i);

    ids = ancla.ids;
    coef = ancla.coef;

    if ~isempty(estadoBase)

        puntosBase(i,:) = ...
            coef*estadoBase.nodos(ids,:);

    end

    puntosFinal(i,:) = ...
        coef*estadoGuiado.nodos(ids,:);

    meta = ancla.meta;

    mascara = isfinite(meta);

    errores(i,mascara) = ...
        meta(mascara)-puntosFinal(i,mascara);

end

%% 9. ORIENTACION APICAL FINAL

a = pose.apice.anterior;
p = pose.apice.posterior;

pa = a.coef*estadoGuiado.nodos(a.ids,:);
pp = p.coef*estadoGuiado.nodos(p.ids,:);

vFinal = pa-pp;

thetaFinal = atan2d(vFinal(2),vFinal(1));

% La diferencia angular relativa solo tiene
% sentido si se calculo la postura base.

deltaFinal = NaN;
errorAngular = NaN;

if ~isempty(estadoBase)

    deltaFinal = envolver180( ...
        thetaFinal-thetaBase);

    if isfinite(deltaAngulo)

        errorAngular = envolver180( ...
            deltaAngulo-deltaFinal);

    end

end

%% 10. SALIDA COMPATIBLE

resultado.pose = pose;

resultado.estadoBase = estadoBase;
resultado.estado = estadoGuiado;

resultado.puntosBase = puntosBase;
resultado.puntosFinal = puntosFinal;

resultado.erroresPuntos = errores;

resultado.anguloBase_deg = thetaBase;
resultado.anguloFinal_deg = thetaFinal;

resultado.deltaAnguloApice_deg = deltaFinal;
resultado.errorAnguloApice_deg = errorAngular;

%% DIAGNOSTICOS

resultado.diagnostico.Jmin = ...
    estadoGuiado.diagnostico.Jmin;

resultado.diagnostico.energiaGuia = ...
    estadoGuiado.diagnostico.energiaGuia;

resultado.diagnostico.fuerzaGuiaMaxima = ...
    estadoGuiado.diagnostico.fuerzaGuiaMaxima;

resultado.diagnostico.errorPunta = ...
    estadoGuiado.diagnostico.errorControlado;

resultado.diagnostico.convergio = ...
    estadoGuiado.diagnostico.convergio;

if ~isempty(estadoBase)

    resultado.diagnostico.convergio = ...
        resultado.diagnostico.convergio && ...
        estadoBase.diagnostico.convergio;

end

resultado.diagnostico.calculoBase = ...
    ~isempty(estadoBase);

end

%% FUNCIONES LOCALES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end

function a = envolver180(a)

a = mod(a+180,360)-180;

end