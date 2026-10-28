
function contacto = preparar_contacto_sagital(cavidad, opciones)
% PREPARAR_CONTACTO_SAGITAL
% Extrae los contornos inferiores de las regiones anatomicas.
%
% Entrada:
%   cavidad : salida de cavidad_oral.m
%   opciones.pasoY : resolucion longitudinal (mm)
%
% Salida:
%   contacto.regiones(i).y
%   contacto.regiones(i).zInferior
%   contacto.regiones(i).zSuperior
%   contacto.regiones(i).valido
%
% Unidades: mm.
% Geometria fija, sin fuerzas de contacto ni deformacion.
%
% IMPORTANTE:
% El contorno inferior es un candidato de contacto.
% Su validez anatomica debe comprobarse visualmente.

%% 1. CONFIGURACION

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

if ~isstruct(cavidad) || ...
        ~isfield(cavidad,'regiones') || ...
        ~isfield(cavidad,'sistema') || ...
        ~isfield(cavidad,'completa')
    error('La cavidad oral no es valida.');
end

% Exigimos el STL completo para conservar el
% sistema de referencia reproducible.
if isempty(cavidad.completa)
    error(['Se requiere cavidad_completa.stl ', ...
        'para conservar el centrado original.']);
end

if isfield(opciones,'pasoY')
    pasoY = opciones.pasoY;
else
    pasoY = 0.10;
end

validateattributes(pasoY,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',1});

%% 2. PREPARAR ESTRUCTURA

nRegiones = numel(cavidad.regiones);

regiones = repmat(struct( ...
    'nombre',"", ...
    'y',[], ...
    'zInferior',[], ...
    'zSuperior',[], ...
    'valido',[], ...
    'color',[]),nRegiones,1);

%% 3. EXTRAER CONTORNOS SAGITALES

for i = 1:nRegiones

    region = cavidad.regiones(i);
    segmentos = region.corteSagital;

    if isempty(segmentos) || size(segmentos,2) ~= 4
        error('Region %d sin corte sagital valido.',i);
    end

    segmentos = segmentos( ...
        all(isfinite(segmentos),2),:);

    if isempty(segmentos)
        error('Region %d sin segmentos finitos.',i);
    end

    % Segmentos [Y1 Z1 Y2 Z2].
    y1 = segmentos(:,1);
    z1 = segmentos(:,2);
    y2 = segmentos(:,3);
    z2 = segmentos(:,4);

    yMin = min([y1;y2]);
    yMax = max([y1;y2]);

    if yMax <= yMin
        error('Region %d sin extension longitudinal.',i);
    end

    nMuestras = max(2,ceil((yMax-yMin)/pasoY)+1);

    yMuestras = linspace( ...
        yMin,yMax,nMuestras)';

    zInferior = nan(nMuestras,1);
    zSuperior = nan(nMuestras,1);

    %% 4. INTERSECCION CON Y CONSTANTE

    for j = 1:nMuestras

        y = yMuestras(j);

        % Convencion semiabierta: evita duplicar
        % intersecciones sobre vertices compartidos.
        cruza = ...
            (y1 <= y & y2 > y) | ...
            (y2 <= y & y1 > y);

        if ~any(cruza)
            continue
        end

        t = (y-y1(cruza))./ ...
            (y2(cruza)-y1(cruza));

        alturas = z1(cruza) + t.* ...
            (z2(cruza)-z1(cruza));

        % Envolventes verticales de la seccion.
        zInferior(j) = min(alturas);
        zSuperior(j) = max(alturas);

    end

    valido = isfinite(zInferior) & ...
        isfinite(zSuperior);

    if nnz(valido) < 2
        error('No se obtuvo contorno de region %d.',i);
    end

    %% 5. ALMACENAR RESULTADOS

    regiones(i).nombre = string(region.nombre);
    regiones(i).y = yMuestras;
    regiones(i).zInferior = zInferior;
    regiones(i).zSuperior = zSuperior;
    regiones(i).valido = valido;
    regiones(i).color = region.color;

end

%% 6. SALIDA

contacto.regiones = regiones;
contacto.nRegiones = nRegiones;

contacto.pasoY = pasoY;
contacto.sistema = cavidad.sistema;

contacto.tipo = ...
    'Envolvente inferior sagital de regiones STL';

contacto.contactoActivo = false;

contacto.limitaciones = ...
    'No incluye fuerzas, normales ni contacto 3D';

end