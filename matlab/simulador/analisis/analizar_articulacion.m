
function analisis = analizar_articulacion(sistema,simulacion)
% ANALIZAR_ARTICULACION
%
% Calcula distancias sagitales aproximadas entre:
% - Punta lingual y regiones de la cavidad.
% - Dorso lingual y regiones de la cavidad.
%
% Utiliza la superficie inferior preparada
% mediante preparar_contacto_sagital.
%
% No calcula fuerzas ni contacto mecanico.
% Unidades: mm.

%% 1. ENTRADAS

if ~isfield(sistema,'contactoSagital') || ...
        isempty(sistema.contactoSagital)
    error('No existen referencias de contacto sagital.');
end

if ~isfield(simulacion,'lengua') || ...
        ~isfield(simulacion,'estado')
    error('Simulacion lingual invalida.');
end

regiones = sistema.contactoSagital.regiones;

S = simulacion.lengua.sagital;

dorso = [
    S.ySuperior(:), ...
    S.zSuperior(:)
];

punta = reshape( ...
    simulacion.estado.puntaYZ,1,2);

n = numel(regiones);

%% 2. PREPARAR RESULTADOS

plantilla = struct( ...
    'nombre',"", ...
    'distanciaPunta_mm',NaN, ...
    'distanciaDorso_mm',NaN, ...
    'puntoDorsoYZ',[NaN NaN], ...
    'puntoCavidadYZ',[NaN NaN]);

resultados = repmat(plantilla,n,1);

%% 3. ANALIZAR CADA REGION

for i = 1:n

    R = regiones(i);

    resultados(i).nombre = string(R.nombre);

    validos = ...
        R.valido(:) & ...
        isfinite(R.y(:)) & ...
        isfinite(R.zInferior(:));

    if ~any(validos)
        continue
    end

    % Contorno inferior de la region.
    cavidadYZ = [
        R.y(validos), ...
        R.zInferior(validos)
    ];

    %% A. DISTANCIA DE LA PUNTA

    distanciasPunta = hypot( ...
        cavidadYZ(:,1)-punta(1), ...
        cavidadYZ(:,2)-punta(2));

    resultados(i).distanciaPunta_mm = ...
        min(distanciasPunta);

    %% B. DISTANCIA MINIMA DEL DORSO

    distanciaMinima = inf;

    puntoLengua = [NaN NaN];
    puntoCavidad = [NaN NaN];

    for j = 1:size(dorso,1)

        p = dorso(j,:);

        distancias = hypot( ...
            cavidadYZ(:,1)-p(1), ...
            cavidadYZ(:,2)-p(2));

        [d,indice] = min(distancias);

        if d < distanciaMinima

            distanciaMinima = d;

            puntoLengua = p;
            puntoCavidad = cavidadYZ(indice,:);

        end

    end

    resultados(i).distanciaDorso_mm = ...
        distanciaMinima;

    resultados(i).puntoDorsoYZ = puntoLengua;

    resultados(i).puntoCavidadYZ = puntoCavidad;

end

%% 4. REGION MAS CERCANA

distanciasPunta = ...
    [resultados.distanciaPunta_mm];

distanciasDorso = ...
    [resultados.distanciaDorso_mm];

[distPunta,ip] = min(distanciasPunta);
[distDorso,id] = min(distanciasDorso);

%% 5. SALIDA

analisis.regiones = resultados;

analisis.puntaYZ = punta;

analisis.regionCercanaPunta = ...
    resultados(ip).nombre;

analisis.regionCercanaDorso = ...
    resultados(id).nombre;

analisis.distanciaMinimaPunta_mm = distPunta;
analisis.distanciaMinimaDorso_mm = distDorso;

analisis.tipo = ...
    'Proximidad geometrica sagital aproximada';

analisis.contactoMecanico = false;


%% 5B. HOLGURA VERTICAL SAGITAL

% Comparacion entre el dorso y la cara inferior
% de cada region, para una misma coordenada Y.
%
% Holgura > 0: lengua debajo de la superficie.
% Holgura = 0: coincidencia vertical.
% Holgura < 0: posible penetracion sagital.

n = numel(regiones);

holguras = repmat(struct( ...
    'nombre',"", ...
    'reposo_mm',NaN, ...
    'final_mm',NaN, ...
    'yCritico_mm',NaN),n,1);

for i = 1:n

    R = regiones(i);

    % Perfil de la lengua deformada.
    [hFinal,yCritico] = calcularHolguraVertical( ...
        R, ...
        S.ySuperior, ...
        S.zSuperior);

    % Perfil de la lengua en reposo.
    [hReposo,~] = calcularHolguraVertical( ...
        R, ...
        sistema.lengua0.sagital.y, ...
        sistema.lengua0.sagital.zSuperior);

    holguras(i).nombre = string(R.nombre);
    holguras(i).reposo_mm = hReposo;
    holguras(i).final_mm = hFinal;
    holguras(i).yCritico_mm = yCritico;

end

analisis.holguras = holguras;

%% 5C. SOLAPAMIENTO GEOMETRICO SAGITAL

% Utilizar las mascaras ya preparadas de la cavidad.
% No representa contacto mecanico ni volumen 3D.

C = sistema.cavidad.sagital;

y = C.y(:)';
z = C.z(:)';

[YY,ZZ] = meshgrid(y,z);

% Poligono de la lengua deformada.
S = simulacion.lengua.sagital;

yFinal = [
    S.ySuperior(:);
    flipud(S.yInferior(:))
    ];

zFinal = [
    S.zSuperior(:);
    flipud(S.zInferior(:))
    ];

% Poligono de la lengua en reposo.
S0 = sistema.lengua0.sagital;

yReposo = [
    S0.y(:);
    flipud(S0.y(:))
    ];

zReposo = [
    S0.zSuperior(:);
    flipud(S0.zInferior(:))
    ];

% Ocupacion de ambos perfiles en la cuadricula.
mascaraFinal = inpolygon( ...
    YY,ZZ,yFinal,zFinal);

mascaraReposo = inpolygon( ...
    YY,ZZ,yReposo,zReposo);

% Area aproximada de cada celda.
areaCelda = abs(mean(diff(y))*mean(diff(z)));

solapamiento = repmat(struct( ...
    'nombre',"", ...
    'areaReposo_mm2',0, ...
    'areaFinal_mm2',0),n,1);

for i = 1:n

    R = sistema.cavidad.regiones(i);

    mascaraRegion = R.mascaraSagital;

    areaReposo = nnz( ...
        mascaraReposo & mascaraRegion)*areaCelda;

    areaFinal = nnz( ...
        mascaraFinal & mascaraRegion)*areaCelda;

    solapamiento(i).nombre = string(R.nombre);

    solapamiento(i).areaReposo_mm2 = areaReposo;
    solapamiento(i).areaFinal_mm2 = areaFinal;

end

analisis.solapamiento = solapamiento;

%% VALIDACION GEOMETRICA SAGITAL

areas = [solapamiento.areaFinal_mm2];

% Resolucion de la cuadricula sagital.
Sref = sistema.cavidad.sagital;

dy = abs(mean(diff(Sref.y)));
dz = abs(mean(diff(Sref.z)));

areaCelda = dy*dz;

% Tolerancia numerica exploratoria:
% tres celdas de la cuadricula.
tolerancia = 3*areaCelda;

analisis.validacionGeometrica = struct();

analisis.validacionGeometrica.areaCelda_mm2 = ...
    areaCelda;

analisis.validacionGeometrica.tolerancia_mm2 = ...
    tolerancia;

analisis.validacionGeometrica.areaMaxima_mm2 = ...
    max(areas);

analisis.validacionGeometrica.regionesInterferidas = ...
    string({solapamiento(areas > tolerancia).nombre});

analisis.validacionGeometrica.sinSolapamiento = ...
    all(areas <= tolerancia);

%% 6. MOSTRAR RESULTADOS

fprintf('\n===== ANALISIS ARTICULATORIO =====\n');

fprintf('%-15s %12s %12s\n', ...
    'Region','Punta (mm)','Dorso (mm)');

for i = 1:n

    fprintf('%-15s %12.3f %12.3f\n', ...
        char(resultados(i).nombre), ...
        resultados(i).distanciaPunta_mm, ...
        resultados(i).distanciaDorso_mm);

end

fprintf('\nRegion cercana a punta: %s\n', ...
    char(analisis.regionCercanaPunta));

fprintf('Region cercana a dorso: %s\n', ...
    char(analisis.regionCercanaDorso));


%% INFORME DE HOLGURAS

fprintf('\n===== HOLGURA VERTICAL SAGITAL =====\n');

fprintf('%-15s %12s %12s %12s\n', ...
    'Region','Reposo','Final','Y critico');

for i = 1:numel(holguras)

    H = holguras(i);

    fprintf('%-15s %12.3f %12.3f %12.3f\n', ...
        char(H.nombre), ...
        H.reposo_mm, ...
        H.final_mm, ...
        H.yCritico_mm);

    if isfinite(H.final_mm) && H.final_mm < 0

        fprintf('  -> Posible penetracion sagital.\n');

    end

end

%% INFORME DE SOLAPAMIENTO

fprintf('\n===== SOLAPAMIENTO SAGITAL =====\n');

fprintf('%-15s %15s %15s\n', ...
    'Region','Reposo (mm2)','Final (mm2)');

for i = 1:numel(analisis.solapamiento)

    R = analisis.solapamiento(i);

    fprintf('%-15s %15.3f %15.3f\n', ...
        char(R.nombre), ...
        R.areaReposo_mm2, ...
        R.areaFinal_mm2);

end

fprintf('\nANALISIS FINALIZADO.\n');

end


function [holguraMinima,yCritico] = ...
    calcularHolguraVertical(R,yLengua,zLengua)
% Compara alturas en la misma coordenada Y.
% Soporta perfiles linguales no monotonicos.
% No representa contacto mecanico ni distancia 3D.

holguraMinima = NaN;
yCritico = NaN;

yL = yLengua(:);
zL = zLengua(:);

validos = R.valido(:) & ...
    isfinite(R.y(:)) & ...
    isfinite(R.zInferior(:));

yC = R.y(validos);
zC = R.zInferior(validos);

if isempty(yC) || numel(yL) < 2
    return
end

% Segmentos del dorso lingual.
y1 = yL(1:end-1);
y2 = yL(2:end);

z1 = zL(1:end-1);
z2 = zL(2:end);

dy = y2-y1;

mejorHolgura = inf;

for k = 1:numel(yC)

    y = yC(k);

    % Buscar cruces del perfil con Y constante.
    cruza = ...
        ((y1 <= y & y2 > y) | ...
        (y2 <= y & y1 > y)) & ...
        abs(dy) > 1e-12;

    alturas = [];

    if any(cruza)

        t = (y-y1(cruza))./dy(cruza);

        alturas = z1(cruza) + ...
            t.*(z2(cruza)-z1(cruza));

    end

    % Incluir vertices exactamente sobre el corte.
    vertices = abs(yL-y) < 1e-9;

    alturas = [alturas;zL(vertices)];

    if isempty(alturas)
        continue
    end

    % Si hay varias intersecciones, utilizar la
    % altura dorsal mayor como criterio conservador.
    zDorso = max(alturas);

    holgura = zC(k)-zDorso;

    if holgura < mejorHolgura

        mejorHolgura = holgura;
        yCritico = y;

    end

end

if isfinite(mejorHolgura)
    holguraMinima = mejorHolgura;
end

end
