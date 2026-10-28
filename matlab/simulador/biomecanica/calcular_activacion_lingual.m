
function carga = calcular_activacion_lingual(modelo, activacion)
% CALCULAR_ACTIVACION_LINGUAL
% Contracciones distribuidas sobre FEM 2D.
%
% MODO FUNCIONAL:
%   activacion.apice  = [dorsal ventral]
%   activacion.lamina = [dorsal ventral]
%   activacion.cuerpo = [dorsal ventral]
%
% MODO ANTERIOR (COMPATIBILIDAD):
%   activacion.anterior = [dorsal ventral]
%   activacion.central  = [dorsal ventral]
%
% Las intensidades son deformaciones activas
% contractiles adimensionales.
%
% No modifica nodos ni calcula desplazamientos.
% Compatible con FEM lineal y no lineal.
%
% Unidades: mm, N, N/mm^2.

%% 1. VALIDAR ENTRADAS

if nargin < 1 || ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo,'material')
    error('Modelo FEM invalido.');
end

if nargin < 2 || isempty(activacion)
    activacion = struct();
end

if ~isstruct(activacion) || ~isscalar(activacion)
    error('activacion debe ser una estructura escalar.');
end

% Detectar formato de activacion.
tieneFuncional = any(isfield(activacion, ...
    {'apice','lamina','cuerpo'}));

tieneAnterior = any(isfield(activacion, ...
    {'anterior','central'}));

% Tercer modo: parches espaciales localizados.
tieneParches = isfield(activacion,'parches');

nModos = double(tieneFuncional) + ...
    double(tieneAnterior) + double(tieneParches);

if nModos > 1
    error(['No mezcles los modos funcional, ', ...
        'anterior_central y parches.']);
end

%% 2. CONFIGURACION REGIONAL

% Estas coordenadas se mantienen fijas
% respecto a la geometria de reposo.
%
% s = 0: punta
% s = 1: extremo posterior truncado

opRegiones = struct();

opRegiones.limites = ...
    leer(activacion,'limitesRegionales', ...
    [0.12 0.32 0.895]);

opRegiones.anchoTransicion = ...
    leer(activacion,'anchoTransicion',0.08);

opRegiones.exponenteEspesor = ...
    leer(activacion,'exponenteEspesor',2);

% Clasificacion funcional de la malla.
regiones = definir_regiones_funcionales( ...
    modelo.malla,opRegiones);


%% 3. INTENSIDADES DE CONTRACCION

% Inicializar campos para todos los modos.
apice = [0 0];
lamina = [0 0];
cuerpo = [0 0];

anterior = [0 0];
central = [0 0];

parches = struct([]);

if tieneParches

    modo = "parches";

    parches = activacion.parches;

    if ~isstruct(parches) || isempty(parches)
        error('Se requiere un arreglo de parches.');
    end

elseif tieneAnterior

    modo = "anterior_central";

    anterior = leer(activacion,'anterior',[0 0]);
    central = leer(activacion,'central',[0 0]);

    validarContraccion(anterior,'anterior');
    validarContraccion(central,'central');

    anterior = reshape(anterior,1,2);
    central = reshape(central,1,2);

else

    modo = "funcional";

    apice = leer(activacion,'apice',[0 0]);
    lamina = leer(activacion,'lamina',[0 0]);
    cuerpo = leer(activacion,'cuerpo',[0 0]);

    validarContraccion(apice,'apice');
    validarContraccion(lamina,'lamina');
    validarContraccion(cuerpo,'cuerpo');

    apice = reshape(apice,1,2);
    lamina = reshape(lamina,1,2);
    cuerpo = reshape(cuerpo,1,2);

end


%% 4. GEOMETRIA FEM

malla = modelo.malla;

nodos = malla.nodos;
tri = malla.elementos;

N = size(nodos,1);
M = size(tri,1);
nGDL = 2*N;

if ~isequal(size(tri,2),3) || ...
        size(nodos,2) ~= 2
    error('Se requiere una malla triangular 2D.');
end

if size(regiones.elementos.pesos,1) ~= M
    error('Regiones incompatibles con la malla.');
end

%% 5. PESOS DORSALES Y VENTRALES

eta = regiones.elementos.eta;

pesoDorsal = regiones.elementos.pesoDorsal;
pesoVentral = regiones.elementos.pesoVentral;

% Contraccion local:
% a = dorsal*wd + ventral*wv
%
% En el dorso: mayor contribucion dorsal.
% En el vientre: mayor contribucion ventral.


%% 6. DISTRIBUCION LONGITUDINAL

W = regiones.elementos.pesos;

% Columnas:
% 1 Apice
% 2 Lamina
% 3 Cuerpo
% 4 Posterior

aApice = zeros(M,1);
aLamina = zeros(M,1);
aCuerpo = zeros(M,1);

aAnterior = zeros(M,1);
aCentral = zeros(M,1);

if modo == "parches"

    % Activacion espacial localizada.
    % No modifica la geometria ni impone
    % desplazamientos a los nodos.

    aTotal = activarParches( ...
        parches, ...
        regiones.elementos.s, ...
        regiones.elementos.eta, ...
        opRegiones.exponenteEspesor);

elseif modo == "funcional"

    aApice = W(:,1).*( ...
        apice(1)*pesoDorsal + ...
        apice(2)*pesoVentral);

    aLamina = W(:,2).*( ...
        lamina(1)*pesoDorsal + ...
        lamina(2)*pesoVentral);

    aCuerpo = W(:,3).*( ...
        cuerpo(1)*pesoDorsal + ...
        cuerpo(2)*pesoVentral);

    aTotal = aApice+aLamina+aCuerpo;

else

    % Compatibilidad con el modelo original.
    s = regiones.elementos.s;

    wAnterior = ventana( ...
        s,0.00,0.38,0.07);

    wCentral = ventana( ...
        s,0.22,0.76,0.07);

    aAnterior = wAnterior.*( ...
        anterior(1)*pesoDorsal + ...
        anterior(2)*pesoVentral);

    aCentral = wCentral.*( ...
        central(1)*pesoDorsal + ...
        central(2)*pesoVentral);

    aTotal = aAnterior+aCentral;

end

if any(~isfinite(aTotal)) || any(aTotal < 0)
    error('Distribucion activa invalida.');
end

if max(aTotal) > 0.05
    warning(['Contraccion local superior al 5%%. ', ...
        'Revisar estabilidad mecanica.']);
end


%% 7. DIRECCION LOCAL LONGITUDINAL

% La contraccion sigue la tangente del perfil
% medio de la lengua en reposo.

niveles = malla.referencia.nivelesEspesor;

nColumnas = ...
    numel(malla.referencia.yColumnas);

indicePunta = malla.seguimiento.puntaIndice;

if N ~= nColumnas*niveles+1 || ...
        indicePunta ~= N
    error('Numeracion nodal incompatible.');
end

idxInf = (0:nColumnas-1)'*niveles+1;
idxSup = idxInf+niveles-1;

yPerfil = [
    nodos(idxInf,1);
    nodos(indicePunta,1)
];

zCentro = [
    (nodos(idxInf,2)+nodos(idxSup,2))/2;
    nodos(indicePunta,2)
];

% Pendiente local del perfil medio.
pendientes = gradient(zCentro,yPerfil);

yElementos = ...
    regiones.elementos.centroides(:,1);

pendienteE = interp1( ...
    yPerfil,pendientes,yElementos,'linear');

norma = sqrt(1+pendienteE.^2);

tY = 1./norma;
tZ = pendienteE./norma;

%% 8. DEFORMACION ACTIVA ELEMENTAL

% Contraccion longitudinal:
%
% epsilon* = -a (t tensor t)
%
% Voigt: [epsYY epsZZ gammaYZ]

deformacionActiva = [
    -aTotal.*tY.^2, ...
    -aTotal.*tZ.^2, ...
    -2*aTotal.*tY.*tZ
];


%% 9. PROPIEDADES MECANICAS

Dreferencia = modelo.material.D;
Ereferencia = modelo.material.E;
espesor = modelo.material.espesor;

if isfield(modelo.material,'Eelementos')
    Eelementos = modelo.material.Eelementos(:);
else
    Eelementos = Ereferencia*ones(M,1);
end

if numel(Eelementos) ~= M || ...
        any(~isfinite(Eelementos)) || ...
        any(Eelementos <= 0)
    error('Propiedades elementales invalidas.');
end

if ~isequal(size(Dreferencia),[3 3]) || ...
        any(~isfinite(Dreferencia(:))) || ...
        Ereferencia <= 0 || espesor <= 0
    error('Propiedades constitutivas invalidas.');
end

%% 10. FUERZAS NODALES EQUIVALENTES

indicesGDL = zeros(M,6);
valoresF = zeros(M,6);

for e = 1:M

    ids = tri(e,:);
    p = nodos(ids,:);

    y = p(:,1);
    z = p(:,2);

    dobleArea = ...
        (y(2)-y(1))*(z(3)-z(1)) - ...
        (y(3)-y(1))*(z(2)-z(1));

    A = dobleArea/2;

    if A <= 1e-10
        error('Elemento %d invalido.',e);
    end

    b = [
        z(2)-z(3);
        z(3)-z(1);
        z(1)-z(2)
    ]/dobleArea;

    c = [
        y(3)-y(2);
        y(1)-y(3);
        y(2)-y(1)
    ]/dobleArea;

    B = [
        b(1),0,b(2),0,b(3),0;
        0,c(1),0,c(2),0,c(3);
        c(1),b(1),c(2),b(2),c(3),b(3)
    ];

    Dlocal = Dreferencia*(Eelementos(e)/Ereferencia);

    epsilon = deformacionActiva(e,:)';

    fe = espesor*A*(B'*Dlocal*epsilon);

    gdl = reshape([2*ids-1;2*ids],1,[]);

    indicesGDL(e,:) = gdl;
    valoresF(e,:) = fe';

end

% Ensamblaje global.
f = accumarray( ...
    indicesGDL(:),valoresF(:), ...
    [nGDL 1],@sum,0);

%% 11. EQUILIBRIO DE FUERZAS ACTIVAS

fNodal = reshape(f,2,[])';

resultante = sum(fNodal,1);

momento = sum( ...
    nodos(:,1).*fNodal(:,2) - ...
    nodos(:,2).*fNodal(:,1));

%% 12. SALIDA

carga.f = f;
carga.fuerzasNodales = fNodal;

carga.modo = modo;
carga.parametros = activacion;

carga.deformacionActiva = ...
    deformacionActiva;

carga.intensidad = aTotal;

% Nuevas intensidades funcionales.
carga.intensidadApice = aApice;
carga.intensidadLamina = aLamina;
carga.intensidadCuerpo = aCuerpo;

% Compatibilidad con el modelo anterior.
carga.intensidadAnterior = aAnterior;
carga.intensidadCentral = aCentral;

% Distribucion funcional utilizada.
carga.regiones.s = regiones.elementos.s;
carga.regiones.eta = eta;

carga.regiones.nombres = regiones.nombres;
carga.regiones.pesos = W;

carga.regiones.pesoDorsal = pesoDorsal;
carga.regiones.pesoVentral = pesoVentral;

carga.regiones.limites = ...
    regiones.configuracion.limites;

% Diagnostico.
carga.diagnostico.maxContraccion = ...
    max(aTotal);

carga.diagnostico.fuerzaNodalMaxima = ...
    max(vecnorm(fNodal,2,2));

carga.diagnostico.resultante = resultante;

carga.diagnostico.momentoResultante = ...
    momento;

end

%% FUNCIONES LOCALES

function validarContraccion(a,nombre)

validateattributes(a,{'numeric'}, ...
    {'vector','numel',2,'real','finite', ...
    '>=',0,'<=',0.10}, ...
    mfilename,nombre);

end

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end

function w = ventana(s,inicio,fin,delta)

entrada = suave((s-inicio)/delta);
salida = suave((fin-s)/delta);

w = entrada.*salida;

end

function q = suave(x)

x = max(0,min(1,x));

q = x.^2.*(3-2*x);

end


%% FUNCION LOCAL: CONTRACCIONES ESPACIALES

function a = activarParches(parches,s,eta,exponente)

% Cada parche aplica una contraccion localizada:
%
% centro:     posicion longitudinal normalizada
% radio:      semiancho de la zona de accion
% capa:       dorsal o ventral
% intensidad: contraccion maxima nominal
%
% Distribucion:
% - Longitudinal: ventana cosenoidal compacta
% - Espesor: distribucion dorsal o ventral
%
% Las contribuciones se suman por elemento.

s = s(:);
eta = eta(:);

if numel(s) ~= numel(eta)
    error('Coordenadas de parche incompatibles.');
end

a = zeros(numel(s),1);

for k = 1:numel(parches)

    p = parches(k);

    campos = { ...
        'centro','radio','capa','intensidad'};

    if ~all(isfield(p,campos))
        error('Parche %d incompleto.',k);
    end

    validateattributes(p.centro,{'numeric'}, ...
        {'scalar','real','finite','>=',0,'<=',1});

    validateattributes(p.radio,{'numeric'}, ...
        {'scalar','real','finite','>',0,'<=',0.30});

    validateattributes(p.intensidad,{'numeric'}, ...
        {'scalar','real','finite','>=',0,'<=',0.10});

    % Distancia relativa al centro del parche.
    xi = (s-p.centro)/p.radio;

    mascara = abs(xi) < 1;

    pesoLongitudinal = zeros(size(s));

    % Ventana con valor y pendiente nulos
    % en los extremos de la zona activa.
    pesoLongitudinal(mascara) = ...
        0.5*(1+cos(pi*xi(mascara)));

    capa = lower(string(p.capa));

    if ~isscalar(capa)
        error('Capa del parche %d invalida.',k);
    end

    switch capa

        case "dorsal"

            pesoEspesor = eta.^exponente;

        case "ventral"

            pesoEspesor = (1-eta).^exponente;

        otherwise

            error('Capa desconocida en parche %d.',k);

    end

    a = a + p.intensidad.* ...
        pesoLongitudinal.*pesoEspesor;

end

end
