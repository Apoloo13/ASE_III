
function cavidad = cavidad_oral(carpetaSTL, puntaReposo, ax3D, axSagital)
% Importa la cavidad oral y sus regiones en un sistema de referencia comun.
% El origen corresponde a la punta de la lengua en reposo.
% La visualizacion es opcional y no crea figuras nuevas.

%% 1. CONFIGURACION
if nargin < 1 || isempty(carpetaSTL)
    carpetaSTL = "STL";
end

if nargin < 2 || isempty(puntaReposo)
    puntaReposo = [0, 23.5, -1.15];
end

if nargin < 3
    ax3D = [];
end

if nargin < 4
    axSagital = [];
end

validateattributes(puntaReposo, {'numeric'}, ...
    {'vector','numel',3,'finite'});

puntaReposo = reshape(puntaReposo, 1, 3);

archivos = [
    "region_dental.stl"
    "region_alveolar.stl"
    "region_prepalatal.stl"
    "region_mediopalatal.stl"
];

nombres = [
    "Dental"
    "Alveolar"
    "Prepalatal"
    "Mediopalatal"
];

archivoCompleto = fullfile(carpetaSTL, "cavidad_completa.stl");

colores = lines(numel(archivos));
alphaRegiones = 0.65;
alphaCompleta = 0.08;

% Rotacion: [X,Y,Z] original -> [X,-Z,Y]
rotacion = [
    1  0  0
    0  0  1
    0 -1  0
];

%% 2. IMPORTACION DE MALLAS
n = numel(archivos);

regiones = repmat(struct( ...
    'nombre', "", ...
    'caras', [], ...
    'puntos', [], ...
    'color', [], ...
    'corteSagital', [], ...
    'mascaraSagital', []), n, 1);

for i = 1:n

    ruta = fullfile(carpetaSTL, archivos(i));

    if ~isfile(ruta)
        error("No se encontro el archivo: %s", ruta);
    end

    TR = stlread(ruta);

    regiones(i).nombre = nombres(i);
    regiones(i).caras = TR.ConnectivityList;
    regiones(i).puntos = TR.Points * rotacion;
    regiones(i).color = colores(i,:);

end

existeCompleta = isfile(archivoCompleto);

if existeCompleta

    TR = stlread(archivoCompleto);

    completa.caras = TR.ConnectivityList;
    completa.puntos = TR.Points * rotacion;

    referencia = completa.puntos;

else

    completa = [];

    referencia = vertcat(regiones.puntos);

    warning(['No se encontro cavidad_completa.stl. ', ...
        'La sombra sagital completa no estara disponible.']);

end

%% 3. SISTEMA DE COORDENADAS
% Primero se conserva el centrado anterior de la cavidad.
% Despues se traslada el origen hasta la punta en reposo.

limiteMin = min(referencia, [], 1);
limiteMax = max(referencia, [], 1);

centroAnterior = (limiteMin + limiteMax)/2;
traslacion = centroAnterior + puntaReposo;

for i = 1:n
    regiones(i).puntos = regiones(i).puntos - traslacion;
end

if existeCompleta
    completa.puntos = completa.puntos - traslacion;
end

%% 4. CORTES SAGITALES EN X = 0

for i = 1:n

    regiones(i).corteSagital = cortarSagital( ...
        regiones(i).caras, regiones(i).puntos);

end

if existeCompleta

    corteCompleto = cortarSagital( ...
        completa.caras, completa.puntos);

    puntosReferencia = completa.puntos;

else

    corteCompleto = zeros(0,4);
    puntosReferencia = vertcat(regiones.puntos);

end

% Malla 2D destinada a representar las secciones.
ySagital = linspace( ...
    min(puntosReferencia(:,2)), ...
    max(puntosReferencia(:,2)), 450);

zSagital = linspace( ...
    min(puntosReferencia(:,3)), ...
    max(puntosReferencia(:,3)), 350);

mascaraCompleta = mascaraSeccion( ...
    corteCompleto, ySagital, zSagital);

etiquetasSagitales = zeros( ...
    numel(zSagital), numel(ySagital), 'uint8');

for i = 1:n

    mascara = mascaraSeccion( ...
        regiones(i).corteSagital, ySagital, zSagital);

    regiones(i).mascaraSagital = mascara;
    etiquetasSagitales(mascara) = uint8(i);

end

%% 5. ESTRUCTURA DE SALIDA

cavidad.regiones = regiones;
cavidad.completa = completa;

cavidad.sistema.rotacion = rotacion;
cavidad.sistema.centroAnterior = centroAnterior;
cavidad.sistema.puntaReposo = puntaReposo;
cavidad.sistema.traslacion = traslacion;

cavidad.sagital.y = ySagital;
cavidad.sagital.z = zSagital;
cavidad.sagital.corteCompleto = corteCompleto;
cavidad.sagital.mascaraCompleta = mascaraCompleta;
cavidad.sagital.etiquetas = etiquetasSagitales;

cavidad.graficos.completa3D = [];
cavidad.graficos.regiones3D = cell(n,1);
cavidad.graficos.sombraSagital = [];

%% 6. VISUALIZACION 3D

if ~isempty(ax3D)

    if ~isgraphics(ax3D, 'axes')
        error('ax3D debe ser un eje grafico valido.');
    end

    hold(ax3D, 'on');

    if existeCompleta

        cavidad.graficos.completa3D = patch( ...
            'Parent', ax3D, ...
            'Faces', completa.caras, ...
            'Vertices', completa.puntos, ...
            'FaceColor', [0.65 0.70 0.75], ...
            'FaceAlpha', alphaCompleta, ...
            'EdgeColor', 'none', ...
            'DisplayName', 'Cavidad completa');

    end

    for i = 1:n

        cavidad.graficos.regiones3D{i} = patch( ...
            'Parent', ax3D, ...
            'Faces', regiones(i).caras, ...
            'Vertices', regiones(i).puntos, ...
            'FaceColor', regiones(i).color, ...
            'FaceAlpha', alphaRegiones, ...
            'EdgeColor', 'none', ...
            'DisplayName', regiones(i).nombre);

    end

    axis(ax3D, 'equal');
    axis(ax3D, 'vis3d');
    grid(ax3D, 'on');

    xlabel(ax3D, 'X (mm)');
    ylabel(ax3D, 'Y (mm)');
    zlabel(ax3D, 'Z (mm)');

    title(ax3D, 'Cavidad oral - 3D');

    view(ax3D, 3);
    camlight(ax3D, 'headlight');
    lighting(ax3D, 'gouraud');

end

%% 7. VISUALIZACION SAGITAL 2D

if ~isempty(axSagital)

    if ~isgraphics(axSagital, 'axes')
        error('axSagital debe ser un eje grafico valido.');
    end

    hold(axSagital, 'on');

    ny = numel(ySagital);
    nz = numel(zSagital);

    % Sombra del corte completo.
    rgb = repmat( ...
        reshape([0.70 0.73 0.77], 1,1,3), nz,ny);

    transparencia = 0.12 * double(mascaraCompleta);

    % Las regiones coloreadas tienen prioridad visual.
    for i = 1:n

        mascara = regiones(i).mascaraSagital;

        for canal = 1:3

            capa = rgb(:,:,canal);
            capa(mascara) = regiones(i).color(canal);
            rgb(:,:,canal) = capa;

        end

        transparencia(mascara) = 0.50;

    end

    cavidad.graficos.sombraSagital = image( ...
        axSagital, ...
        'XData', [ySagital(1), ySagital(end)], ...
        'YData', [zSagital(1), zSagital(end)], ...
        'CData', rgb, ...
        'AlphaData', transparencia);

    % Dibujar los contornos seccionados de cada region.
    for i = 1:n

        segmentos = regiones(i).corteSagital;

        if isempty(segmentos)
            continue
        end

        numero = size(segmentos,1);

        yy = reshape([ ...
            segmentos(:,1), segmentos(:,3), ...
            nan(numero,1)]', [], 1);

        zz = reshape([ ...
            segmentos(:,2), segmentos(:,4), ...
            nan(numero,1)]', [], 1);

        plot(axSagital, yy, zz, ...
            'Color', regiones(i).color, ...
            'LineWidth', 1.0);

    end

    axis(axSagital, 'equal');
    grid(axSagital, 'on');

    set(axSagital, ...
        'XDir', 'reverse', ...
        'YDir', 'normal');

    xlabel(axSagital, 'Y (mm)');
    ylabel(axSagital, 'Z (mm)');

    title(axSagital, 'Plano sagital medio - X = 0');

end

end


%% FUNCION LOCAL: INTERSECCION DE MALLA CON PLANO X = 0

function segmentos = cortarSagital(caras, puntos)

numeroTriangulos = size(caras,1);

intersecciones = nan(numeroTriangulos,3,2);
validas = false(numeroTriangulos,3);

aristas = [1 2; 2 3; 3 1];
tolerancia = 1e-9;

for e = 1:3

    A = puntos(caras(:,aristas(e,1)),:);
    B = puntos(caras(:,aristas(e,2)),:);

    dA = A(:,1);
    dB = B(:,1);

    cruza = (dA.*dB < 0) | ...
        (abs(dA) <= tolerancia & abs(dB) > tolerancia) | ...
        (abs(dB) <= tolerancia & abs(dA) > tolerancia);

    denominador = dA - dB;

    cruza = cruza & abs(denominador) > tolerancia;

    indices = find(cruza);

    t = dA(indices) ./ denominador(indices);

    intersecciones(indices,e,1) = ...
        A(indices,2) + t .* (B(indices,2)-A(indices,2));

    intersecciones(indices,e,2) = ...
        A(indices,3) + t .* (B(indices,3)-A(indices,3));

    validas(:,e) = cruza;

end

% Elegir los dos puntos distintos de cada triangulo.
pares = [1 2; 1 3; 2 3];

distanciaMaxima = -inf(numeroTriangulos,1);
seleccion = zeros(numeroTriangulos,1);

for k = 1:3

    a = pares(k,1);
    b = pares(k,2);

    dy = intersecciones(:,a,1)-intersecciones(:,b,1);
    dz = intersecciones(:,a,2)-intersecciones(:,b,2);

    distancia = dy.^2 + dz.^2;

    distancia(~(validas(:,a) & validas(:,b))) = -inf;

    actualizar = distancia > distanciaMaxima;

    distanciaMaxima(actualizar) = distancia(actualizar);
    seleccion(actualizar) = k;

end

indicesValidos = find( ...
    isfinite(distanciaMaxima) & ...
    distanciaMaxima > tolerancia^2);

segmentos = zeros(numel(indicesValidos),4);

for k = 1:3

    filas = find(seleccion(indicesValidos) == k);
    indices = indicesValidos(filas);

    a = pares(k,1);
    b = pares(k,2);

    segmentos(filas,:) = [ ...
        intersecciones(indices,a,1), ...
        intersecciones(indices,a,2), ...
        intersecciones(indices,b,1), ...
        intersecciones(indices,b,2)];

end

end


%% FUNCION LOCAL: MASCARA DEL CORTE SAGITAL

function mascara = mascaraSeccion(segmentos, valoresY, valoresZ)

mascara = false(numel(valoresZ), numel(valoresY));

if isempty(segmentos)
    return
end

y1 = segmentos(:,1);
z1 = segmentos(:,2);
y2 = segmentos(:,3);
z2 = segmentos(:,4);

% Relleno por pares de intersecciones sobre cada columna Y.
for j = 1:numel(valoresY)

    y = valoresY(j);

    cruces = (y1 <= y & y2 > y) | ...
             (y2 <= y & y1 > y);

    if ~any(cruces)
        continue
    end

    alturas = z1(cruces) + ...
        (y-y1(cruces)) .* ...
        (z2(cruces)-z1(cruces)) ./ ...
        (y2(cruces)-y1(cruces));

    alturas = sort(alturas);

    % Un numero impar de cruces indica un contorno incompleto.
    if mod(numel(alturas),2) ~= 0
        continue
    end

    for k = 1:2:numel(alturas)

        mascara(:,j) = mascara(:,j) | ...
            (valoresZ(:) >= alturas(k) & ...
             valoresZ(:) <= alturas(k+1));

    end

end

end
