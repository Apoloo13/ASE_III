
function regiones = definir_regiones_funcionales(malla, opciones)
% DEFINIR_REGIONES_FUNCIONALES
% Identifica regiones funcionales de la lengua FEM 2D.
%
% Regiones:
%   1 - Apice
%   2 - Lamina
%   3 - Cuerpo
%   4 - Posterior
%
% Utiliza pesos continuos entre 0 y 1.
% La suma de los cuatro pesos es 1.
%
% Entradas:
%   malla    : salida de crear_malla_lengua
%   opciones : configuracion opcional
%
% Salida:
%   regiones : pesos, posiciones y clasificaciones
%
% No modifica la malla ni calcula deformaciones.

%% 1. CONFIGURACION

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

% Limites longitudinales normalizados.
% s = 0 en punta, s = 1 en extremo posterior.
%
% Apice/Lamina     : s = 0.12
% Lamina/Cuerpo    : s = 0.32
% Cuerpo/Posterior : s = 0.76

limites = opcion(opciones, ...
    'limites',[0.12 0.32 0.895]);

anchoTransicion = opcion( ...
    opciones,'anchoTransicion',0.08);

% Control de distribucion dorsal/ventral.
exponenteEspesor = opcion( ...
    opciones,'exponenteEspesor',2);

validateattributes(limites,{'numeric'}, ...
    {'vector','numel',3,'real','finite','>',0,'<',1});

validateattributes(anchoTransicion,{'numeric'}, ...
    {'scalar','real','finite','positive','<',1});

validateattributes(exponenteEspesor,{'numeric'}, ...
    {'scalar','real','finite','>=',1,'<=',6});

limites = reshape(limites,1,3);

if any(diff(limites) <= anchoTransicion)
    error('Las transiciones regionales se superponen.');
end

if limites(1) <= anchoTransicion/2 || ...
        limites(3) >= 1-anchoTransicion/2
    error('Las transiciones exceden los extremos.');
end

nombres = ["Apice","Lamina","Cuerpo","Posterior"];

%% 2. OBTENER MALLA

if ~isstruct(malla) || ...
        ~isfield(malla,'nodos') || ...
        ~isfield(malla,'elementos') || ...
        ~isfield(malla,'referencia') || ...
        ~isfield(malla,'seguimiento')
    error('Estructura de malla invalida.');
end

nodos = malla.nodos;
tri = malla.elementos;

N = size(nodos,1);
M = size(tri,1);

if size(nodos,2) ~= 2 || ...
        size(tri,2) ~= 3 || ...
        any(~isfinite(nodos(:))) || ...
        any(~isfinite(tri(:))) || ...
        any(tri(:) < 1) || ...
        any(tri(:) > N) || ...
        any(tri(:) ~= round(tri(:)))
    error('Geometria FEM invalida.');
end

%% 3. IDENTIFICAR COLUMNAS Y PUNTA

niveles = malla.referencia.nivelesEspesor;
yColumnas = malla.referencia.yColumnas(:);

nColumnas = numel(yColumnas);

indicePunta = malla.seguimiento.puntaIndice;

% Compatible con nuestra malla estructurada:
% cinco niveles por columna y punta unica.

if N ~= nColumnas*niveles+1 || ...
        indicePunta ~= N
    error('Numeracion de malla incompatible.');
end

if niveles < 2 || any(diff(yColumnas) <= 0)
    error('Columnas de referencia invalidas.');
end

idxInferiores = ...
    (0:nColumnas-1)'*niveles+1;

idxSuperiores = idxInferiores+niveles-1;

if any(abs(nodos(idxInferiores,1)-yColumnas) > 1e-8) || ...
        any(abs(nodos(idxSuperiores,1)-yColumnas) > 1e-8)
    error('Orden de nodos incompatible con las columnas.');
end

yPunta = nodos(indicePunta,1);
yPosterior = yColumnas(1);

longitud = yPunta-yPosterior;

if longitud <= 0
    error('Longitud lingual invalida.');
end

%% 4. COORDENADA LONGITUDINAL NORMALIZADA

% Posicion de todos los nodos.
sNodos = (yPunta-nodos(:,1))/longitud;

% Centroides de los elementos.
centroides = ( ...
    nodos(tri(:,1),:) + ...
    nodos(tri(:,2),:) + ...
    nodos(tri(:,3),:))/3;

sElementos = ...
    (yPunta-centroides(:,1))/longitud;

if any(sNodos < -1e-8 | sNodos > 1+1e-8)
    error('Nodos fuera del intervalo longitudinal.');
end

sNodos = max(0,min(1,sNodos));
sElementos = max(0,min(1,sElementos));

%% 5. PESOS FUNCIONALES LONGITUDINALES

pesosNodos = calcularPesos( ...
    sNodos,limites,anchoTransicion);

pesosElementos = calcularPesos( ...
    sElementos,limites,anchoTransicion);

% Cada fila:
% [Apice Lamina Cuerpo Posterior]

%% 6. COORDENADA A TRAVES DEL ESPESOR

% Contornos inferior y superior de la malla FEM.
zInferior = nodos(idxInferiores,2);
zSuperior = nodos(idxSuperiores,2);

if any(zSuperior <= zInferior)
    error('Secciones linguales de espesor invalido.');
end

% Agregar la punta como extremo comun.
yPerfil = [
    yColumnas;
    yPunta
];

zPerfilInferior = [
    zInferior;
    nodos(indicePunta,2)
];

zPerfilSuperior = [
    zSuperior;
    nodos(indicePunta,2)
];

% Coordenada eta:
% 0 = superficie inferior
% 1 = superficie superior

etaNodos = zeros(N,1);

regulares = (1:N-1)';

% Para nodos regulares, utilizar sus columnas.
etaNodos(regulares) = ...
    (nodos(regulares,2) - ...
    interp1(yColumnas,zInferior, ...
    nodos(regulares,1),'linear')) ./ ...
    (interp1(yColumnas,zSuperior, ...
    nodos(regulares,1),'linear') - ...
    interp1(yColumnas,zInferior, ...
    nodos(regulares,1),'linear'));

% La punta tiene espesor nulo.
etaNodos(indicePunta) = 0.5;

% Posiciones de los centroides.
yE = centroides(:,1);
zE = centroides(:,2);

zInfE = interp1( ...
    yPerfil,zPerfilInferior,yE,'linear');

zSupE = interp1( ...
    yPerfil,zPerfilSuperior,yE,'linear');

espesorE = zSupE-zInfE;

if any(espesorE <= 0)
    error('Espesor elemental invalido.');
end

etaElementos = (zE-zInfE)./espesorE;

if any(etaNodos < -1e-6 | etaNodos > 1+1e-6) || ...
        any(etaElementos < -1e-6 | ...
            etaElementos > 1+1e-6)
    error('Posiciones fuera del espesor lingual.');
end

etaNodos = max(0,min(1,etaNodos));
etaElementos = max(0,min(1,etaElementos));

%% 7. DISTRIBUCION DORSAL Y VENTRAL

% Mantiene la convencion utilizada anteriormente
% por calcular_activacion_lingual.

pesoDorsalN = etaNodos.^exponenteEspesor;
pesoVentralN = (1-etaNodos).^exponenteEspesor;

pesoDorsalE = etaElementos.^exponenteEspesor;
pesoVentralE = (1-etaElementos).^exponenteEspesor;

%% 8. CLASIFICACION DOMINANTE

% Clasificacion para visualizacion y seguimiento.
% Las activaciones futuras utilizaran los pesos
% continuos, no las etiquetas discretas.

[~,claseNodos] = max(pesosNodos,[],2);
[~,claseElementos] = max(pesosElementos,[],2);

indicesNodos = cell(1,4);
indicesElementos = cell(1,4);

for i = 1:4

    indicesNodos{i} = find(claseNodos == i);
    indicesElementos{i} = find(claseElementos == i);

end

%% 9. AREAS DE REFERENCIA POR REGION

p1 = nodos(tri(:,1),:);
p2 = nodos(tri(:,2),:);
p3 = nodos(tri(:,3),:);

areas = 0.5*( ...
    (p2(:,1)-p1(:,1)).*(p3(:,2)-p1(:,2)) - ...
    (p2(:,2)-p1(:,2)).*(p3(:,1)-p1(:,1)));

if any(areas <= 0)
    error('Elementos FEM invertidos.');
end

areasRegionales = sum( ...
    pesosElementos.*areas,1);

%% 10. VERIFICACIONES

errorPesosNodos = max(abs( ...
    sum(pesosNodos,2)-1));

errorPesosElementos = max(abs( ...
    sum(pesosElementos,2)-1));

if errorPesosNodos > 1e-10 || ...
        errorPesosElementos > 1e-10
    error('Los pesos funcionales no suman uno.');
end

if any(pesosNodos(:) < -1e-12) || ...
        any(pesosElementos(:) < -1e-12)
    error('Se detectaron pesos regionales negativos.');
end

%% 11. ESTRUCTURA DE SALIDA

regiones.nombres = nombres;

regiones.configuracion.limites = limites;
regiones.configuracion.anchoTransicion = ...
    anchoTransicion;

regiones.configuracion.exponenteEspesor = ...
    exponenteEspesor;

regiones.referencia.yPunta = yPunta;
regiones.referencia.yPosterior = yPosterior;
regiones.referencia.longitud = longitud;

regiones.referencia.yLimites = ...
    yPunta-longitud*limites;

% Datos nodales.
regiones.nodos.s = sNodos;
regiones.nodos.eta = etaNodos;

regiones.nodos.pesos = pesosNodos;
regiones.nodos.clase = claseNodos;
regiones.nodos.etiquetas = nombres(claseNodos);

regiones.nodos.pesoDorsal = pesoDorsalN;
regiones.nodos.pesoVentral = pesoVentralN;

% Datos elementales.
regiones.elementos.s = sElementos;
regiones.elementos.eta = etaElementos;

regiones.elementos.pesos = pesosElementos;
regiones.elementos.clase = claseElementos;
regiones.elementos.etiquetas = nombres(claseElementos);

regiones.elementos.pesoDorsal = pesoDorsalE;
regiones.elementos.pesoVentral = pesoVentralE;

regiones.elementos.centroides = centroides;

% Indices por region.
regiones.indicesNodos = indicesNodos;
regiones.indicesElementos = indicesElementos;

% Diagnostico.
regiones.diagnostico.nNodos = N;
regiones.diagnostico.nElementos = M;

regiones.diagnostico.areasRegionales = ...
    areasRegionales;

regiones.diagnostico.errorPesosNodos = ...
    errorPesosNodos;

regiones.diagnostico.errorPesosElementos = ...
    errorPesosElementos;

end

%% FUNCION LOCAL: PESOS CONTINUOS

function W = calcularPesos(s,limites,ancho)

s = s(:);

% Tres transiciones longitudinales.
q1 = suave((s-limites(1))/ancho+0.5);
q2 = suave((s-limites(2))/ancho+0.5);
q3 = suave((s-limites(3))/ancho+0.5);

% Particion de unidad:
% Apice + Lamina + Cuerpo + Posterior = 1

W = [
    1-q1, ...
    q1-q2, ...
    q2-q3, ...
    q3
];

end

%% FUNCION LOCAL: SMOOTHSTEP

function q = suave(x)

x = max(0,min(1,x));

q = x.^2.*(3-2*x);

end

%% FUNCION LOCAL: OPCIONES

function valor = opcion(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
