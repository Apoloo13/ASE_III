
function graficos = visualizar_sistema_orofacial( ...
    sistema,simulacion,analisis,op)
% VISUALIZAR_SISTEMA_OROFACIAL
%
% Inicializa las figuras del sistema orofacial.
% No ejecuta el FEM ni importa archivos STL.
%
% Las figuras se crean una sola vez.
% Despues se actualizan mediante:
% actualizar_visualizacion.m

if nargin < 4 || isempty(op)
    op = struct();
end

%% 1. CREAR FIGURAS

fig3D = figure( ...
    'Name','Sistema orofacial - 3D', ...
    'NumberTitle','off', ...
    'Color','w', ...
    'Position',[100 100 1100 730]);

ax3D = axes('Parent',fig3D);
hold(ax3D,'on');

figSagital = figure( ...
    'Name','Sistema orofacial - Sagital', ...
    'NumberTitle','off', ...
    'Color','w', ...
    'Position',[250 140 1080 700]);

axSagital = axes('Parent',figSagital);
hold(axSagital,'on');

%% 2. CAVIDAD ORAL

gCavidad = [];

if leer(op,'mostrarCavidad',true) && ...
        ~isempty(sistema.cavidad)

    gCavidad = visualizar_cavidad_preparada( ...
        sistema.cavidad,ax3D,axSagital);

end

%% 3. LENGUA EN REPOSO - 3D

if leer(op,'mostrarReposo3D',false)

    L0 = sistema.lengua0.malla;

    surf(ax3D,L0.X,L0.Y,L0.Z, ...
        'FaceColor',[0.65 0.65 0.65], ...
        'FaceAlpha',0.12, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

end

%% 4. SUPERFICIE LINGUAL 3D

L = simulacion.lengua.malla;

hSuperficie = surf(ax3D, ...
    L.X,L.Y,L.Z, ...
    'FaceColor',[0.82 0.40 0.52], ...
    'FaceAlpha',0.96, ...
    'EdgeColor','none', ...
    'DisplayName','Lengua deformada');

p = simulacion.estado.puntaYZ;

hPunta3D = plot3(ax3D, ...
    0,p(1),p(2),'ro', ...
    'MarkerSize',8, ...
    'MarkerFaceColor','r', ...
    'DisplayName','Punta');

hCostillas3D = gobjects(0);

if leer(op,'mostrarPuntos',true)

    C = simulacion.estado.costillasYZ;

    hCostillas3D = plot3(ax3D, ...
        zeros(size(C,1),1), ...
        C(:,1),C(:,2),'o', ...
        'MarkerSize',5, ...
        'MarkerFaceColor',[1 0.85 0.20], ...
        'MarkerEdgeColor','k', ...
        'HandleVisibility','off');

end

axis(ax3D,'equal');
axis(ax3D,'vis3d');
grid(ax3D,'on');

xlabel(ax3D,'X (mm)');
ylabel(ax3D,'Y (mm)');
zlabel(ax3D,'Z (mm)');

title(ax3D,'Lengua y cavidad oral - 3D');

view(ax3D,[-60 25]);
camlight(ax3D,'headlight');
lighting(ax3D,'gouraud');

legend(ax3D,[hSuperficie hPunta3D], ...
    'Location','best');

%% 5. PERFIL EN REPOSO

S0 = sistema.lengua0.sagital;

hReposo = plot(axSagital, ...
    S0.y,S0.zSuperior, ...
    'k--','LineWidth',1.2, ...
    'DisplayName','Dorso en reposo');

%% 6. POSTURA BASE OPCIONAL

hBase = [];

if leer(op,'mostrarBase',false) && ...
        ~isempty(simulacion.estadoBase)

    [lenguaBase,~] = reconstruir_lengua_3d( ...
        sistema.lengua0, ...
        sistema.malla, ...
        simulacion.estadoBase,[]);

    SB = lenguaBase.sagital;

    hBase = plot(axSagital, ...
        SB.ySuperior,SB.zSuperior, ...
        'Color',[0.20 0.45 0.90], ...
        'LineWidth',1.4, ...
        'DisplayName','Solo punta');

end

%% 7. DORSO Y VIENTRE

S = simulacion.lengua.sagital;

hDorso = plot(axSagital, ...
    S.ySuperior,S.zSuperior, ...
    'Color',[0.86 0.12 0.22], ...
    'LineWidth',2.2, ...
    'DisplayName','Dorso final');

hVientre = plot(axSagital, ...
    S.yInferior,S.zInferior, ...
    'Color',[0.62 0.22 0.48], ...
    'LineWidth',1.8, ...
    'DisplayName','Vientre final');

hPuntaSagital = plot(axSagital, ...
    p(1),p(2),'ro', ...
    'MarkerSize',8, ...
    'MarkerFaceColor','r', ...
    'HandleVisibility','off');

%% 8. MARCADORES SAGITALES

hCostillasSagital = gobjects(0);
hObjetivos = gobjects(0);

if leer(op,'mostrarPuntos',true)

    C = simulacion.estado.costillasYZ;

    hCostillasSagital = plot(axSagital, ...
        C(:,1),C(:,2),'o', ...
        'MarkerSize',5, ...
        'MarkerFaceColor',[1 0.85 0.20], ...
        'MarkerEdgeColor','k', ...
        'HandleVisibility','off');

    % Crear un unico objeto actualizable
    % para los objetivos materiales.
    hObjetivos = plot(axSagital, ...
        NaN,NaN,'x', ...
        'Color',[0.10 0.10 0.10], ...
        'MarkerSize',6, ...
        'LineWidth',1.1, ...
        'HandleVisibility','off');

end

%% 9. FORMATO SAGITAL

set(axSagital, ...
    'XDir','reverse', ...
    'YDir','normal');

axis(axSagital,'equal');
grid(axSagital,'on');

xlabel(axSagital,'Y (mm)');
ylabel(axSagital,'Z (mm)');

title(axSagital, ...
    'Lengua y cavidad oral - Plano sagital');

hLeyenda = [hReposo hDorso hVientre];

if ~isempty(hBase)
    hLeyenda = [hReposo hBase hDorso hVientre];
end

if ~isempty(gCavidad)

    hRegiones = gCavidad.leyendaRegiones;
    hRegiones = hRegiones(isgraphics(hRegiones));

    hLeyenda = [hLeyenda hRegiones(:)'];

end

legend(axSagital,hLeyenda,'Location','best');

%% 10. REGISTRAR IDENTIFICADORES

graficos = struct();

graficos.figura3D = fig3D;
graficos.ax3D = ax3D;

graficos.figuraSagital = figSagital;
graficos.axSagital = axSagital;

graficos.superficie3D = hSuperficie;
graficos.punta3D = hPunta3D;
graficos.costillas3D = hCostillas3D;

graficos.reposo = hReposo;
graficos.base = hBase;

graficos.dorso = hDorso;
graficos.vientre = hVientre;

graficos.puntaSagital = hPuntaSagital;
graficos.costillasSagital = hCostillasSagital;
graficos.objetivos = hObjetivos;

graficos.cavidad = gCavidad;

graficos.mostrarPenetraciones = ...
    leer(op,'mostrarPenetraciones',true);

graficos.interferencias = gobjects(0,1);

%% 11. REPRESENTAR PRIMERA POSTURA

graficos = actualizar_visualizacion( ...
    graficos,sistema,simulacion,analisis);

end

%% FUNCION LOCAL

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end