
function [lengua3D, mapa] = reconstruir_lengua_3d( ...
    lengua0, malla, estado, mapa)
% RECONSTRUIR_LENGUA_3D
% Transfiere los desplazamientos FEM 2D a la lengua 3D.
%
% Entradas:
%   lengua0 : geometria original de lengua_ideal
%   malla   : salida de crear_malla_lengua
%   estado  : salida de resolver_postura_lengua
%   mapa    : correspondencia precalculada (opcional)
%
% Salidas:
%   lengua3D : geometria tridimensional deformada
%   mapa     : correspondencia reutilizable en otras posturas
%
% Se conserva X. No modifica la geometria original.
% No dibuja figuras ni requiere toolboxes adicionales.

%% 1. VALIDACION

if ~isstruct(lengua0) || ...
        ~isfield(lengua0,'malla') || ...
        ~isfield(lengua0,'sagital')
    error('lengua0 debe proceder de lengua_ideal.');
end

if ~isstruct(malla) || ...
        ~isfield(malla,'nodos') || ...
        ~isfield(malla,'elementos')
    error('La malla FEM no es valida.');
end

if ~isstruct(estado) || ~isfield(estado,'nodos')
    error('El estado FEM no es valido.');
end

if ~isequal(size(estado.nodos),size(malla.nodos)) || ...
        any(~isfinite(estado.nodos(:)))
    error('El estado no coincide con la malla FEM.');
end

X0 = lengua0.malla.X;
Y0 = lengua0.malla.Y;
Z0 = lengua0.malla.Z;

if ~isequal(size(X0),size(Y0),size(Z0))
    error('Las dimensiones de la superficie 3D no coinciden.');
end

y0 = lengua0.sagital.y(:);
zSup0 = lengua0.sagital.zSuperior(:);
zInf0 = lengua0.sagital.zInferior(:);

if numel(y0) ~= numel(zSup0) || ...
        numel(y0) ~= numel(zInf0)
    error('El perfil sagital es inconsistente.');
end

%% 2. PREPARAR CORRESPONDENCIA

% El mapa se calcula una vez y se reutiliza.
if nargin < 4 || isempty(mapa)

    mapa = prepararMapa(lengua0,malla);

else

    if ~isstruct(mapa) || ...
            ~isfield(mapa,'nodosReferencia') || ...
            ~isfield(mapa,'elementosReferencia') || ...
            ~isfield(mapa,'YReferencia') || ...
            ~isfield(mapa,'ZReferencia') || ...
            ~isfield(mapa,'indices') || ...
            ~isfield(mapa,'pesos') || ...
            ~isfield(mapa,'nSuperficie') || ...
            ~isfield(mapa,'nPerfil')
        error('El mapa de interpolacion es invalido.');
    end

    if ~isequal(mapa.nodosReferencia,malla.nodos) || ...
            ~isequal(mapa.elementosReferencia,malla.elementos) || ...
            ~isequal(mapa.YReferencia,Y0) || ...
            ~isequal(mapa.ZReferencia,Z0) || ...
            mapa.nPerfil ~= numel(y0)
        error('El mapa no corresponde a la geometria actual.');
    end

end

%% 3. DESPLAZAMIENTOS NODALES FEM

uNodal = estado.nodos - malla.nodos;

indices = mapa.indices;
pesos = mapa.pesos;

% Interpolacion baricentrica de las dos componentes.
uPuntos = zeros(size(indices,1),2);

for j = 1:3

    uPuntos = uPuntos + ...
        pesos(:,j).*uNodal(indices(:,j),:);

end

%% 4. RECONSTRUCCION DE SUPERFICIE 3D

nSuperficie = mapa.nSuperficie;
nPerfil = mapa.nPerfil;

idxSuperficie = 1:nSuperficie;

uY = reshape( ...
    uPuntos(idxSuperficie,1),size(Y0));

uZ = reshape( ...
    uPuntos(idxSuperficie,2),size(Z0));

X = X0;
Y = Y0 + uY;
Z = Z0 + uZ;

%% 5. RECONSTRUCCION SAGITAL

idxSuperior = nSuperficie + (1:nPerfil);

idxInferior = nSuperficie + nPerfil + ...
    (1:nPerfil);

ySuperior = y0 + uPuntos(idxSuperior,1);
zSuperior = zSup0 + uPuntos(idxSuperior,2);

yInferior = y0 + uPuntos(idxInferior,1);
zInferior = zInf0 + uPuntos(idxInferior,2);

%% 6. PUNTA Y NUEVE MARCADORES

indicePunta = malla.seguimiento.puntaIndice;
indicesCostillas = malla.seguimiento.costillasIndices;

puntaFinal = estado.nodos(indicePunta,:);

costillasFinales = ...
    estado.nodos(indicesCostillas,:);

centros = lengua0.costillas.centros;
centros(:,2:3) = costillasFinales;

%% 7. ESTRUCTURA DE SALIDA

lengua3D = lengua0;

lengua3D.malla.X = X;
lengua3D.malla.Y = Y;
lengua3D.malla.Z = Z;

% sagital.y conserva las coordenadas de referencia.
% Las curvas deformadas usan sus Y independientes.
lengua3D.sagital.yReferencia = ...
    lengua0.sagital.y;

lengua3D.sagital.ySuperior = ...
    reshape(ySuperior,size(lengua0.sagital.y));

lengua3D.sagital.zSuperior = ...
    reshape(zSuperior,size(lengua0.sagital.zSuperior));

lengua3D.sagital.yInferior = ...
    reshape(yInferior,size(lengua0.sagital.y));

lengua3D.sagital.zInferior = ...
    reshape(zInferior,size(lengua0.sagital.zInferior));

lengua3D.punta = [
    lengua0.punta(1), puntaFinal
];

lengua3D.costillas.centros = centros;

lengua3D.costillas.desplazamientos = ...
    uNodal(indicesCostillas,2)';

lengua3D.costillas.desplazamientosYZ = ...
    uNodal(indicesCostillas,:);

lengua3D.fem.desplazamientos = uNodal;
lengua3D.fem.nodos = estado.nodos;

lengua3D.fem.desplazamientoMaximoSuperficie = ...
    max(hypot(uY(:),uZ(:)));

% Los identificadores graficos heredados no se actualizan aqui.

end

%% FUNCION LOCAL: CORRESPONDENCIA FEM

function mapa = prepararMapa(lengua0,malla)

Y = lengua0.malla.Y;
Z = lengua0.malla.Z;

y0 = lengua0.sagital.y(:);
zSup0 = lengua0.sagital.zSuperior(:);
zInf0 = lengua0.sagital.zInferior(:);

nSuperficie = numel(Y);
nPerfil = numel(y0);

% Consultas: superficie 3D, contorno superior e inferior.
consultaY = [
    Y(:);
    y0;
    y0
];

consultaZ = [
    Z(:);
    zSup0;
    zInf0
];

%% A. PERFILES DE REFERENCIA FEM

niveles = malla.referencia.nivelesEspesor;
nColumnas = numel(malla.referencia.yColumnas);

idxInf = (0:nColumnas-1)'*niveles + 1;
idxSup = idxInf + niveles - 1;

nodos = malla.nodos;

indicePunta = malla.seguimiento.puntaIndice;

yFEM = [
    nodos(idxInf,1);
    nodos(indicePunta,1)
];

zInfFEM = [
    nodos(idxInf,2);
    nodos(indicePunta,2)
];

zSupFEM = [
    nodos(idxSup,2);
    nodos(indicePunta,2)
];

%% B. POSICION NORMALIZADA EN EL ESPESOR

nConsultas = numel(consultaY);

indices = repmat(indicePunta,nConsultas,3);

pesos = zeros(nConsultas,3);
pesos(:,1) = 1;

% La punta es un unico nodo material.
esPunta = abs(consultaY-yFEM(end)) < 1e-11;

idx = find(~esPunta);

yQ = consultaY(idx);
zQ = consultaZ(idx);

if any(yQ < yFEM(1)-1e-9) || ...
        any(yQ > yFEM(end)+1e-9)
    error('Hay puntos fuera del intervalo longitudinal FEM.');
end

zSupOriginal = interp1( ...
    y0,zSup0,yQ,'pchip');

zInfOriginal = interp1( ...
    y0,zInf0,yQ,'pchip');

espesorOriginal = zSupOriginal-zInfOriginal;

if any(espesorOriginal <= 0)
    error('Espesor de referencia invalido.');
end

eta = (zQ-zInfOriginal)./espesorOriginal;

tolerancia = 1e-6;

if any(eta < -tolerancia | ...
        eta > 1+tolerancia)
    error('Hay puntos fuera del espesor original.');
end

% Ajuste numerico solo para buscar los elementos.
eta = min(max(eta,1e-10),1-1e-10);

%% C. PROYECCION AL DOMINIO TRIANGULAR FEM

% La geometria FEM aproxima los perfiles curvos
% mediante segmentos rectos.

zInfConsulta = interp1( ...
    yFEM,zInfFEM,yQ,'linear');

zSupConsulta = interp1( ...
    yFEM,zSupFEM,yQ,'linear');

zConsultaFEM = zInfConsulta + ...
    eta.*(zSupConsulta-zInfConsulta);

TR = triangulation(malla.elementos,malla.nodos);

[idTri,pesosTri] = pointLocation( ...
    TR,[yQ,zConsultaFEM]);

% Recuperacion ante errores numericos en fronteras.
fallos = isnan(idTri);

if any(fallos)

    yCorregido = min(max( ...
        yQ(fallos),yFEM(1)+1e-9), ...
        yFEM(end)-1e-9);

    etaCorregido = min(max( ...
        eta(fallos),1e-7),1-1e-7);

    zInfCorregido = interp1( ...
        yFEM,zInfFEM,yCorregido,'linear');

    zSupCorregido = interp1( ...
        yFEM,zSupFEM,yCorregido,'linear');

    zCorregido = zInfCorregido + ...
        etaCorregido.*( ...
        zSupCorregido-zInfCorregido);

    [idNuevo,pesosNuevos] = pointLocation( ...
        TR,[yCorregido,zCorregido]);

    idTri(fallos) = idNuevo;
    pesosTri(fallos,:) = pesosNuevos;

end

if any(isnan(idTri))
    error(['No se pudo asociar toda la superficie ', ...
        'a los elementos FEM.']);
end

indices(idx,:) = malla.elementos(idTri,:);
pesos(idx,:) = pesosTri;

%% D. ALMACENAR CORRESPONDENCIA

mapa.indices = indices;
mapa.pesos = pesos;

mapa.nSuperficie = nSuperficie;
mapa.nPerfil = nPerfil;

mapa.nodosReferencia = malla.nodos;
mapa.elementosReferencia = malla.elementos;

mapa.YReferencia = Y;
mapa.ZReferencia = Z;

end
