
function salida = simular_postura_lingual( ...
    modelo,lenguaReposo,postura,opciones)
% SIMULAR_POSTURA_LINGUAL
%
% Simulador general de posturas linguales.
%
% ENTRADAS
%
% modelo:
%   Salida de configurar_biomecanica.
%
% lenguaReposo:
%   Salida de lengua_ideal en reposo.
%
% postura:
%   puntaYZ       [Y Z] mm, coordenadas absolutas
%   anguloApice   cambio angular en grados (NaN = libre)
%   pesoAngulo    peso del objetivo angular
%
%   dorso:
%       [s DeltaZ Peso] o
%       [s Yobjetivo Zobjetivo Peso]
%
%   vientre:
%       misma estructura que dorso
%
%   En el formato de 3 columnas, DeltaZ representa
%   el desplazamiento respecto a la superficie en reposo.
%
%   s=0 corresponde a la punta.
%   s=1 corresponde al extremo posterior truncado.
%
% opciones:
%   Opciones de resolver_postura_con_guia
%
%   mostrarConsola = true
%   validar = true
%
%   visualizacion.graficar = true
%   visualizacion.mostrarCavidad = false
%   visualizacion.carpetaSTL = 'STL'
%   visualizacion.mostrarBase = true
%   visualizacion.mostrarPuntos = true
%   visualizacion.mostrarReposo3D = false
%
% SALIDA
%
%   salida.postura
%   salida.objetivos
%   salida.resultado
%   salida.estado
%   salida.estadoBase
%   salida.lengua
%   salida.validacion
%   salida.resumen
%   salida.graficos
%
% No modifica las mallas originales.
% No realiza simulacion dinamica temporal.

%% =====================================================
% 1. VALIDACION DE ENTRADAS
% ======================================================

if nargin < 4 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

if ~isstruct(postura) || ~isscalar(postura)
    error('postura debe ser una estructura escalar.');
end

if ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo,'material')
    error('Modelo FEM invalido.');
end

if ~isstruct(lenguaReposo) || ...
        ~isfield(lenguaReposo,'sagital') || ...
        ~isfield(lenguaReposo,'malla')
    error('Geometria lingual de reposo invalida.');
end

malla = modelo.malla;

X = malla.nodos;

indicePunta = malla.seguimiento.puntaIndice;

puntaInicial = X(indicePunta,:);

%% =====================================================
% 2. OPCIONES GENERALES
% ======================================================

mostrarConsola = leer( ...
    opciones,'mostrarConsola',true);

hacerValidacion = leer( ...
    opciones,'validar',true);

%% =====================================================
% 3. DEFINICION DE POSTURA
% ======================================================

puntaYZ = leer( ...
    postura,'puntaYZ',puntaInicial);

anguloApice = leer( ...
    postura,'anguloApice',NaN);

pesoAngulo = leer( ...
    postura,'pesoAngulo',1);

dorso = leer( ...
    postura,'dorso',zeros(0,3));

vientre = leer( ...
    postura,'vientre',zeros(0,3));

validateattributes(puntaYZ,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

validateattributes(pesoAngulo,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

if ~isnumeric(anguloApice) || ...
        ~isscalar(anguloApice) || ...
        ~isreal(anguloApice) || ...
        isinf(anguloApice)
    error('anguloApice debe ser un escalar o NaN.');
end

puntaYZ = reshape(puntaYZ,1,2);

%% =====================================================
% 4. CONVERTIR OBJETIVOS REGIONALES
% ======================================================

config = struct();

config.puntaYZ = puntaYZ;

config.deltaAnguloApice_deg = anguloApice;

config.pesoAngulo = pesoAngulo;

config.dorso = convertirObjetivos( ...
    malla,'dorso',dorso);

config.vientre = convertirObjetivos( ...
    malla,'vientre',vientre);

%% =====================================================
% 5. CONSTRUIR OBJETIVOS ARTICULATORIOS
% ======================================================

objetivos = definir_postura_lingual( ...
    malla,config);

% Si no se solicita control angular apical,
% conservarlo explicitamente desactivado.

if isnan(anguloApice)
    objetivos.apice.deltaAngulo_deg = NaN;
end

%% =====================================================
% 6. RESOLVER FEM
% ======================================================

if mostrarConsola

    fprintf('\n===== SIMULADOR LINGUAL =====\n');

    fprintf('Nodos FEM: %d\n',size(X,1));

    fprintf('Elementos: %d\n', ...
        size(malla.elementos,1));

    fprintf('Punta objetivo: [%.3f %.3f] mm\n', ...
        puntaYZ);

    fprintf('Objetivos dorsales: %d\n', ...
        size(config.dorso,1));

    fprintf('Objetivos ventrales: %d\n', ...
        size(config.vientre,1));

end


%% CONFIGURAR CONTROL ADICIONAL DE FORMA

opSolucion = opciones;

opSolucion.controlForma = struct();

opSolucion.controlForma.curvaturaApical = ...
    leer(postura,'curvaturaApical',0);

opSolucion.controlForma.curvaturaLaminal = ...
    leer(postura,'curvaturaLaminal',0);

opSolucion.controlForma.anguloLamina = ...
    leer(postura,'anguloLamina',NaN);

opSolucion.controlForma.factorRigidezCurvatura = ...
    leer(opciones,'factorRigidezCurvatura',0.20);

opSolucion.controlForma.factorRigidezAngularLamina = ...
    leer(opciones,'factorRigidezAngularLamina',0.15);

opSolucion.controlForma.longitudReferencia = 3.0;

%% RESOLVER

resultado = resolver_postura_con_guia( ...
    modelo,objetivos,opSolucion);


estado = resultado.estado;

estadoBase = resultado.estadoBase;


%% =====================================================
% 7. RECONSTRUCCION 3D Y SAGITAL
% ======================================================

% Reconstruir exclusivamente la postura final.
[lenguaFinal,~] = reconstruir_lengua_3d( ...
    lenguaReposo,malla,estado,[]);

% La comparacion base, cuando exista, se
% reconstruye desde el visualizador externo.
lenguaBase = [];

%% =====================================================
% 8. VALIDACION MECANICA
% ======================================================

validacion = [];

if hacerValidacion

    opVal = struct();

    opVal.graficar = false;
    opVal.mostrarConsola = false;

    opVal.nombrePostura = 'Postura general';

    validacion = validar_deformacion_lingual( ...
        modelo,estado,opVal);

end

%% =====================================================
% 9. RESUMEN NUMERICO
% ======================================================

resumen = struct();

resumen.puntaInicial = puntaInicial;
resumen.puntaObjetivo = puntaYZ;
resumen.puntaFinal = estado.puntaYZ;

resumen.errorPunta_mm = norm( ...
    estado.puntaYZ-puntaYZ);

resumen.nObjetivosDorsales = ...
    size(config.dorso,1);

resumen.nObjetivosVentrales = ...
    size(config.vientre,1);

% Errores finitos de los objetivos regionales.
errores = [];

if isfield(resultado,'erroresPuntos')

    errores = abs(resultado.erroresPuntos(:));

    errores = errores(isfinite(errores));

end

if ~isempty(errores)

    resumen.errorMedio_mm = mean(errores);
    resumen.errorMaximo_mm = max(errores);

else

    resumen.errorMedio_mm = NaN;
    resumen.errorMaximo_mm = NaN;

end

if ~isempty(validacion)

    resumen.Jmin = validacion.global.Jmin;
    resumen.Jmax = validacion.global.Jmax;

    resumen.GreenMax = ...
        validacion.global.GreenMax;

    resumen.lambdaMax = ...
        validacion.global.lambdaMax;

    resumen.crucesContorno = ...
        validacion.contorno.numeroCruces;

    resumen.cumpleCriteriosExploratorios = ...
        validacion.criterios.cumpleCriteriosExploratorios;

else

    resumen.Jmin = NaN;
    resumen.Jmax = NaN;

    resumen.GreenMax = NaN;
    resumen.lambdaMax = NaN;

    resumen.crucesContorno = NaN;
    resumen.cumpleCriteriosExploratorios = false;

end

if isfield(estado,'diagnostico')

    d = estado.diagnostico;

    resumen.residuoFEM = leer( ...
        d,'residuoEquilibrio',NaN);

    resumen.rmsCurvatura = leer( ...
        d,'rmsCambioCurvatura',NaN);

    resumen.energiaSuavidad = leer( ...
        d,'energiaSuavidad',NaN);

else

    resumen.residuoFEM = NaN;
    resumen.rmsCurvatura = NaN;
    resumen.energiaSuavidad = NaN;

end

%% =====================================================
% 10. RESULTADOS GRAFICOS
% ======================================================

% Los graficos se generan externamente mediante
% visualizar_sistema_orofacial.
%
% Se conserva la estructura para compatibilidad.

graficos = struct( ...
    'figura3D',[], ...
    'ax3D',[], ...
    'figuraSagital',[], ...
    'axSagital',[], ...
    'cavidad',[]);

%% =====================================================
% 11. ESTRUCTURA DE SALIDA
% ======================================================

salida.postura = postura;

salida.objetivos = objetivos;
salida.configuracion = config;

salida.resultado = resultado;

salida.estado = estado;
salida.estadoBase = estadoBase;

salida.lengua = lenguaFinal;
salida.lenguaBase = lenguaBase;

salida.validacion = validacion;
salida.resumen = resumen;

salida.graficos = graficos;

%% =====================================================
% 12. INFORME FINAL
% ======================================================

if mostrarConsola

    fprintf('\n===== RESULTADOS DE POSTURA =====\n');

    fprintf('Punta objetivo: [%.4f %.4f] mm\n', ...
        puntaYZ);

    fprintf('Punta final: [%.4f %.4f] mm\n', ...
        estado.puntaYZ);

    fprintf('Error punta: %.6f mm\n', ...
        resumen.errorPunta_mm);

    fprintf('Error medio objetivos: %.5f mm\n', ...
        resumen.errorMedio_mm);

    fprintf('Error maximo objetivos: %.5f mm\n', ...
        resumen.errorMaximo_mm);

    fprintf('J minimo: %.6f\n',resumen.Jmin);

    fprintf('Green maximo: %.6f\n', ...
        resumen.GreenMax);

    fprintf('RMS curvatura: %.6f 1/mm\n', ...
        resumen.rmsCurvatura);

    fprintf('Cruces contorno: %.0f\n', ...
        resumen.crucesContorno);

    if hacerValidacion

        if resumen.cumpleCriteriosExploratorios

            fprintf(['Estado: cumple criterios ', ...
                'numericos exploratorios.\n']);

        else

            warning(['La postura requiere revision ', ...
                'de los criterios numericos.']);

        end

    end

    fprintf('\nSIMULACION FINALIZADA.\n');

end

end

%% =====================================================
% FUNCION LOCAL: CONVERSION DE OBJETIVOS
% ======================================================

function objetivos = convertirObjetivos( ...
    malla,superficie,datos)

% Formato:
%   [s DeltaZ Peso]
%
% O alternativamente:
%   [s Yobjetivo Zobjetivo Peso]

if isempty(datos)

    objetivos = zeros(0,4);
    return

end

if ~isnumeric(datos) || ~ismatrix(datos) || ...
        ~ismember(size(datos,2),[3 4])

    error(['Los objetivos deben tener ', ...
        'tres o cuatro columnas.']);

end

s = datos(:,1);

if any(~isfinite(s)) || ...
        any(s <= 0) || any(s >= 1)

    error('Los valores s deben estar entre 0 y 1.');

end

if size(datos,2) == 3

    deltaZ = datos(:,2);
    pesos = datos(:,3);

    if any(~isfinite(deltaZ))

        error('DeltaZ debe contener valores finitos.');

    end

    zReferencia = alturaReferencia( ...
        malla,superficie,s);

    zObjetivo = zReferencia+deltaZ;

    objetivos = [
        s
        ];

    objetivos = [ ...
        s, ...
        nan(size(s)), ...
        zObjetivo, ...
        pesos];

else

    objetivos = datos;

    pesos = datos(:,4);

    if any(isinf(datos(:,2:3)),'all') || ...
            any(all(isnan(datos(:,2:3)),2))

        error('Objetivos Y,Z invalidos.');

    end

end

if any(~isfinite(pesos)) || any(pesos < 0)

    error('Pesos de objetivos invalidos.');

end

end

%% =====================================================
% FUNCION LOCAL: ALTURA EN REPOSO
% ======================================================

function z = alturaReferencia(malla,superficie,s)

switch lower(string(superficie))

    case "dorso"

        ids = malla.frontera.superior(:);

    case "vientre"

        ids = malla.frontera.inferior(:);

    otherwise

        error('Superficie lingual desconocida.');

end

X = malla.nodos;

indicePunta = malla.seguimiento.puntaIndice;

yPunta = X(indicePunta,1);
yPosterior = min(X(:,1));

L = yPunta-yPosterior;

sNodos = (yPunta-X(ids,1))/L;

[sNodos,orden] = sort(sNodos);

zNodos = X(ids(orden),2);

z = interp1( ...
    sNodos,zNodos,s,'pchip');

if any(~isfinite(z))

    error('No se pudo interpolar el objetivo.');

end

end

%% =====================================================
% FUNCION LOCAL: LEER OPCIONES
% ======================================================

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)

    valor = s.(nombre);

else

    valor = defecto;

end

end