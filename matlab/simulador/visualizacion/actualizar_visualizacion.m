
function g = actualizar_visualizacion( ...
    g,sistema,simulacion,analisis)
% ACTUALIZAR_VISUALIZACION
%
% Actualiza las figuras existentes del sistema.
% No crea figuras, no ejecuta FEM y no importa STL.
%
% Actualiza:
%   - Superficie 3D
%   - Dorso y vientre sagitales
%   - Punta y costillas
%   - Objetivos materiales
%   - Comparacion base, si existe
%   - Marcadores de interferencia
%
% La cavidad oral permanece fija.

if nargin < 4
    analisis = [];
end

%% 1. COMPROBAR GRAFICOS

if ~isstruct(g) || ...
        ~isgraphics(g.ax3D,'axes') || ...
        ~isgraphics(g.axSagital,'axes')

    error('Los ejes del sistema no son validos.');

end

L = simulacion.lengua.malla;
S = simulacion.lengua.sagital;
estado = simulacion.estado;

p = estado.puntaYZ;

%% 2. SUPERFICIE 3D

set(g.superficie3D, ...
    'XData',L.X, ...
    'YData',L.Y, ...
    'ZData',L.Z);

set(g.punta3D, ...
    'XData',0, ...
    'YData',p(1), ...
    'ZData',p(2));

%% 3. PERFILES SAGITALES

set(g.dorso, ...
    'XData',S.ySuperior, ...
    'YData',S.zSuperior);

set(g.vientre, ...
    'XData',S.yInferior, ...
    'YData',S.zInferior);

set(g.puntaSagital, ...
    'XData',p(1), ...
    'YData',p(2));

%% 4. MARCADORES DE COSTILLAS

if isfield(estado,'costillasYZ')

    C = estado.costillasYZ;

    if ~isempty(g.costillas3D) && ...
            isgraphics(g.costillas3D)

        set(g.costillas3D, ...
            'XData',zeros(size(C,1),1), ...
            'YData',C(:,1), ...
            'ZData',C(:,2));

    end

    if ~isempty(g.costillasSagital) && ...
            isgraphics(g.costillasSagital)

        set(g.costillasSagital, ...
            'XData',C(:,1), ...
            'YData',C(:,2));

    end

end

%% 5. OBJETIVOS MATERIALES

if ~isempty(g.objetivos) && ...
        isgraphics(g.objetivos)

    Q = zeros(0,2);

    if isfield(simulacion.resultado,'puntosFinal')

        Q = simulacion.resultado.puntosFinal;

    end

    set(g.objetivos, ...
        'XData',Q(:,1), ...
        'YData',Q(:,2));

end

%% 6. POSTURA BASE OPCIONAL

if ~isempty(g.base) && isgraphics(g.base)

    if ~isempty(simulacion.estadoBase)

        [lenguaBase,~] = reconstruir_lengua_3d( ...
            sistema.lengua0, ...
            sistema.malla, ...
            simulacion.estadoBase,[]);

        SB = lenguaBase.sagital;

        set(g.base, ...
            'XData',SB.ySuperior, ...
            'YData',SB.zSuperior, ...
            'Visible','on');

    else

        set(g.base, ...
            'XData',NaN, ...
            'YData',NaN, ...
            'Visible','off');

    end

end

%% 7. BORRAR MARCADORES ANTERIORES

% Solo se borran los marcadores de interferencia.
% No se elimina la cavidad ni la lengua.

if ~isempty(g.interferencias)

    validos = isgraphics(g.interferencias);

    delete(g.interferencias(validos));

end

g.interferencias = gobjects(0,1);

%% 8. DIBUJAR INTERFERENCIAS ACTUALES

if g.mostrarPenetraciones && ...
        ~isempty(analisis) && ...
        isfield(analisis,'holguras') && ...
        ~isempty(sistema.contactoSagital)

    for i = 1:numel(analisis.holguras)

        H = analisis.holguras(i);

        if ~isfinite(H.final_mm) || ...
                H.final_mm >= -0.10
            continue
        end

        R = sistema.contactoSagital.regiones(i);

        validos = R.valido(:) & ...
            isfinite(R.y(:)) & ...
            isfinite(R.zInferior(:));

        if nnz(validos) < 2
            continue
        end

        zOral = interp1( ...
            R.y(validos), ...
            R.zInferior(validos), ...
            H.yCritico_mm,'linear',NaN);

        if ~isfinite(zOral)
            continue
        end

        zLengua = zOral-H.final_mm;

        % Segmento de interferencia.
        h1 = plot(g.axSagital, ...
            [H.yCritico_mm H.yCritico_mm], ...
            [zOral zLengua], ...
            'r--','LineWidth',2, ...
            'HandleVisibility','off');

        % Punto de superficie oral.
        h2 = plot(g.axSagital, ...
            H.yCritico_mm,zOral, ...
            'ro','MarkerSize',6, ...
            'MarkerFaceColor','y', ...
            'HandleVisibility','off');

        % Punto de superficie lingual.
        h3 = plot(g.axSagital, ...
            H.yCritico_mm,zLengua, ...
            'ro','MarkerSize',6, ...
            'MarkerFaceColor','r', ...
            'HandleVisibility','off');

        g.interferencias = [
            g.interferencias;
            h1;h2;h3
        ];

    end

end

%% 9. ACTUALIZAR FIGURAS

drawnow limitrate;

end