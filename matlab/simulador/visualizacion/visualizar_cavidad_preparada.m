
function graficos = visualizar_cavidad_preparada( ...
    cavidad,ax3D,axSagital)
% VISUALIZAR_CAVIDAD_PREPARADA
%
% Representa la cavidad oral previamente importada.
%
% No lee archivos STL.
% No transforma coordenadas.
% No genera nuevas figuras.
%
% Utiliza los mismos ejes de la lengua deformada.
%
% ENTRADAS:
%   cavidad   : salida de cavidad_oral
%   ax3D      : eje tridimensional existente
%   axSagital : eje sagital existente
%
% SALIDA:
%   graficos  : identificadores graficos de cavidad

%% 1. VALIDACION

if ~isstruct(cavidad) || ...
        ~isfield(cavidad,'regiones') || ...
        ~isfield(cavidad,'sagital')
    error('Cavidad oral no preparada.');
end

if ~isgraphics(ax3D,'axes') || ...
        ~isgraphics(axSagital,'axes')
    error('Se requieren ejes graficos validos.');
end

n = numel(cavidad.regiones);

graficos = struct();

graficos.completa3D = [];
graficos.regiones3D = cell(n,1);
graficos.imagenSagital = [];
graficos.contornosSagitales = cell(n,1);
graficos.leyendaRegiones = gobjects(n,1);

%% 2. VISUALIZACION 3D

hold(ax3D,'on');

% Cavidad completa, como referencia transparente.

if ~isempty(cavidad.completa)

    C = cavidad.completa;

    graficos.completa3D = patch( ...
        'Parent',ax3D, ...
        'Faces',C.caras, ...
        'Vertices',C.puntos, ...
        'FaceColor',[0.65 0.70 0.75], ...
        'FaceAlpha',0.04, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

end

% Regiones anatomicas.

for i = 1:n

    R = cavidad.regiones(i);

    graficos.regiones3D{i} = patch( ...
        'Parent',ax3D, ...
        'Faces',R.caras, ...
        'Vertices',R.puntos, ...
        'FaceColor',R.color, ...
        'FaceAlpha',0.30, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

end

axis(ax3D,'equal');
axis(ax3D,'vis3d');

grid(ax3D,'on');

xlabel(ax3D,'X (mm)');
ylabel(ax3D,'Y (mm)');
zlabel(ax3D,'Z (mm)');

title(ax3D,'Lengua y cavidad oral - 3D');

%% 3. PREPARAR REPRESENTACION SAGITAL

hold(axSagital,'on');

S = cavidad.sagital;

y = S.y;
z = S.z;

ny = numel(y);
nz = numel(z);

% Color de referencia de cavidad completa.
rgb = repmat( ...
    reshape([0.72 0.75 0.78],1,1,3), ...
    nz,ny);

alpha = 0.07*double(S.mascaraCompleta);

% Superponer regiones con colores individuales.

for i = 1:n

    R = cavidad.regiones(i);

    mascara = R.mascaraSagital;

    if ~isequal(size(mascara),[nz ny])
        error('Mascara sagital incompatible.');
    end

    for canal = 1:3

        capa = rgb(:,:,canal);

        capa(mascara) = R.color(canal);

        rgb(:,:,canal) = capa;

    end

    alpha(mascara) = 0.25;

end

%% 4. DIBUJAR LAS REGIONES SAGITALES

graficos.imagenSagital = image( ...
    axSagital, ...
    'XData',[y(1) y(end)], ...
    'YData',[z(1) z(end)], ...
    'CData',rgb, ...
    'AlphaData',alpha, ...
    'AlphaDataMapping','none', ...
    'HandleVisibility','off');

% Colocar la imagen debajo de los perfiles
% linguales ya dibujados.

uistack(graficos.imagenSagital,'bottom');

%% 5. CONTORNOS ANATOMICOS

for i = 1:n

    R = cavidad.regiones(i);

    segmentos = R.corteSagital;

    if isempty(segmentos)
        continue
    end

    numero = size(segmentos,1);

    yy = reshape([ ...
        segmentos(:,1), ...
        segmentos(:,3), ...
        nan(numero,1)]',[],1);

    zz = reshape([ ...
        segmentos(:,2), ...
        segmentos(:,4), ...
        nan(numero,1)]',[],1);

    graficos.contornosSagitales{i} = plot( ...
        axSagital,yy,zz, ...
        'Color',R.color, ...
        'LineWidth',1.0, ...
        'HandleVisibility','off');

    % Identificador para la leyenda.
    graficos.leyendaRegiones(i) = plot( ...
        axSagital,NaN,NaN, ...
        '-', ...
        'Color',R.color, ...
        'LineWidth',2, ...
        'DisplayName',char(R.nombre));

end

%% 6. FORMATO FINAL

set(axSagital, ...
    'XDir','reverse', ...
    'YDir','normal');

axis(axSagital,'equal');

grid(axSagital,'on');

xlabel(axSagital,'Y (mm)');
ylabel(axSagital,'Z (mm)');

title(axSagital, ...
    'Lengua y cavidad oral - Plano sagital');

legend(axSagital,'show','Location','best');

end
