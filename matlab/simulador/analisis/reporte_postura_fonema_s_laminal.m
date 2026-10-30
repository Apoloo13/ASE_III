
function salida = reporte_postura_fonema_s_laminal()
% Reporte geometrico y FEM de una candidata /s/ laminal.
% No constituye validacion clinica ni simulacion acustica.

raiz = fileparts(fileparts(mfilename('fullpath')));
addpath(raiz);

for carpeta = {'geometria','biomecanica','control','analisis', ...
               'visualizacion','secuencias'}
    addpath(fullfile(raiz,carpeta{1}));
end

cfg = configuracion_orofacial();

% Registro geometrico provisional.
cfg.geometria.lengua.desplazamientoGlobal = [0 3 0];

sistema = preparar_sistema_orofacial(cfg);
postura = definir_postura_fonema_s_laminal(sistema);

op = cfg.simulacion;
op.mostrarConsola = false;

sim = simular_postura_lingual( ...
    sistema.modeloFEM,sistema.lengua0,postura,op);

analisis = analizar_articulacion(sistema,sim);
V = sim.validacion;

%% 1. COORDENADAS MATERIALES

M = sistema.malla;
X0 = M.nodos;

ids = M.frontera.superior(:);

yPunta0 = X0(M.seguimiento.puntaIndice,1);
L = yPunta0-min(X0(:,1));

s = (yPunta0-X0(ids,1))/L;

[s,ord] = sort(s);
ids = ids(ord);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);
PF = sim.estado.nodos(ids,:);

%% 2. REFERENCIA ALVEOLAR

R = sistema.contactoSagital.regiones;

iA = find(strcmpi( ...
    string({R.nombre}),'Alveolar'),1);

assert(~isempty(iA),'No se encontro la region alveolar.');

A = puntos_superiores(R(iA));

assert(size(A,1)>=2, ...
    'Contorno alveolar insuficiente.');

%% 3. DISTANCIAS SOBRE LA LENGUA

sEval = linspace(0.04,0.29,180)';

Q0 = interp1(s,P0,sEval,'linear');
QF = interp1(s,PF,sEval,'linear');

D = hypot( ...
    QF(:,1)-A(:,1)', ...
    QF(:,2)-A(:,2)');

[dPerfil,idxA] = min(D,[],2);

% Region anterior y laminal central.
maskAnt = sEval>=0.04 & sEval<=0.12;
maskCent = sEval>=0.16 & sEval<=0.29;

indAnt = find(maskAnt);
indCent = find(maskCent);

[DAnt,j] = min(dPerfil(maskAnt));
iAnt = indAnt(j);

[DCent,j] = min(dPerfil(maskCent));
iCent = indCent(j);

pAnt = QF(iAnt,:);
pAlvAnt = A(idxA(iAnt),:);

pCent = QF(iCent,:);
pAlvCent = A(idxA(iCent),:);

%% 4. ORIENTACION LAMINAL

Qang0 = interp1(s,P0,[0.16;0.29],'linear');
QangF = interp1(s,PF,[0.16;0.29],'linear');

v0 = Qang0(1,:)-Qang0(2,:);
vF = QangF(1,:)-QangF(2,:);

theta0 = atan2d(v0(2),v0(1));
thetaF = atan2d(vF(2),vF(1));

dTheta = atan2d( ...
    sind(thetaF-theta0), ...
    cosd(thetaF-theta0));

%% 5. METRICAS

met = struct();

met.DAnterior_mm = DAnt;
met.DCentral_mm = DCent;

met.sAnterior = sEval(iAnt);
met.sCentral = sEval(iCent);

met.anguloInicial_deg = theta0;
met.anguloFinal_deg = thetaF;
met.cambioAngular_deg = dTheta;

met.GreenMax = sim.resumen.GreenMax;
met.Jmin = sim.resumen.Jmin;
met.Jmax = sim.resumen.Jmax;

met.cumpleCriteriosFEM = ...
    V.criterios.cumpleCriteriosExploratorios;

met.sinSolapamientoBandas = ...
    analisis.validacionGeometrica.sinSolapamiento;

%% 6. RESUMEN NUMERICO

fprintf('\n===== /s/ LAMINAL: GEOMETRIA MEDIDA =====\n');

fprintf(['Referencia lingual Y: +3 mm ', ...
    '(registro provisional)\n']);

fprintf(['Distancia anterior a alveolar superior: ', ...
    '%.3f mm (s=%.3f)\n'],DAnt,sEval(iAnt));

fprintf(['Distancia central a alveolar superior: ', ...
    '%.3f mm (s=%.3f)\n'],DCent,sEval(iCent));

fprintf('Angulo laminal: %.2f grados\n',thetaF);

fprintf('Cambio respecto al reposo: %+.2f grados\n', ...
    dTheta);

fprintf('\n===== /s/ LAMINAL: FEM =====\n');

fprintf('GreenMax: %.4f (limite %.4f)\n', ...
    met.GreenMax,V.limites.GreenMax);

fprintf('Jmin: %.4f (limite %.4f)\n', ...
    met.Jmin,V.limites.Jmin);

fprintf('Elementos invertidos: %d\n', ...
    V.global.elementosInvertidos);

fprintf('Cruces del contorno: %d\n', ...
    V.contorno.numeroCruces);

fprintf('Elementos fuera de Green: %d\n', ...
    V.global.elementosFueraGreen);

fprintf('Elementos fuera de J: %d\n', ...
    V.global.elementosFueraJ);

fprintf('Cumple criterios FEM: %d\n', ...
    met.cumpleCriteriosFEM);

fprintf(['Sin solapamiento con franjas regionales: ', ...
    '%d\n'],met.sinSolapamientoBandas);

fprintf(['Nota: los criterios FEM son exploratorios. ', ...
    'No certifican una constriccion funcional.\n']);

%% 7. FIGURAS 1 Y 5: SAGITAL Y 3D

g = visualizar_sistema_orofacial( ...
    sistema,sim,analisis,cfg.visualizacion);

% Contorno superior de las referencias anatomicas.
for k = 1:numel(R)

    B = puntos_superiores(R(k));

    if ~isempty(B)

        plot(g.axSagital,B(:,1),B(:,2), ...
            'k-','LineWidth',1.35, ...
            'HandleVisibility','off');

    end
end

title(g.axSagital, ...
    '/s/ laminal - postura y referencias anatomicas');

title(g.ax3D, ...
    '/s/ laminal - reconstruccion superficial 3D');

rotate3d(g.figura3D,'on');

%% 8. FIGURA 2: DISTANCIAS Y ORIENTACION

figZoom = figure('Color','w', ...
    'Name','/s/ - Distancias anatomicas');

ax = axes('Parent',figZoom);
hold(ax,'on');

dibujar_bandas(ax,R);

% Contorno superior.
for k = 1:numel(R)

    B = puntos_superiores(R(k));

    if ~isempty(B)

        plot(ax,B(:,1),B(:,2),'k-', ...
            'LineWidth',1.5, ...
            'HandleVisibility','off');

    end
end

S0 = sistema.lengua0.sagital;
S = sim.lengua.sagital;

plot(ax,S0.y,S0.zSuperior,'k--', ...
    'LineWidth',1.3, ...
    'DisplayName','Dorso de referencia');

plot(ax,S.ySuperior,S.zSuperior,'r-', ...
    'LineWidth',2.4, ...
    'DisplayName','Dorso final');

plot(ax,S.yInferior,S.zInferior, ...
    'Color',[0.55 0.23 0.48], ...
    'LineWidth',1.4, ...
    'DisplayName','Vientre final');

% Distancias medidas.
dibujar_distancia(ax,pAnt,pAlvAnt, ...
    sprintf('D anterior = %.2f mm',DAnt), ...
    [0.0 0.55 0.75]);

dibujar_distancia(ax,pCent,pAlvCent, ...
    sprintf('D central = %.2f mm',DCent), ...
    [0.7 0.15 0.7]);

% Cuerda de orientacion.
plot(ax,QangF(:,1),QangF(:,2),'m--', ...
    'LineWidth',1.9, ...
    'DisplayName','Cuerda de orientacion');

text(ax,mean(QangF(:,1))-1, ...
    mean(QangF(:,2))+1, ...
    sprintf('Angulo = %.1f grados',thetaF), ...
    'BackgroundColor','w', ...
    'FontSize',10);

plot(ax,sim.estado.puntaYZ(1), ...
    sim.estado.puntaYZ(2),'ro', ...
    'MarkerFaceColor','r', ...
    'MarkerSize',8, ...
    'HandleVisibility','off');

set(ax,'XDir','reverse');

axis(ax,'equal');
grid(ax,'on');

xlim(ax,[-18 12]);
ylim(ax,[-3 20]);

xlabel(ax,'Y (mm)');
ylabel(ax,'Z (mm)');

title(ax,'/s/: distancias al contorno superior alveolar');
legend(ax,'Location','best');

%% 9. EVIDENCIA GEOMETRICA INTERACTIVA

evi = struct();

evi.regiones = R;

evi.S0 = sistema.lengua0.sagital;
evi.S = sim.lengua.sagital;

evi.s = s;
evi.P0 = P0;
evi.PF = PF;

evi.punta = sim.estado.puntaYZ;

evi.pAnt = pAnt;
evi.pAlvAnt = pAlvAnt;

evi.pCent = pCent;
evi.pAlvCent = pAlvCent;

evi.DAnt = DAnt;
evi.DCent = DCent;

evi.thetaF = thetaF;
evi.dTheta = dTheta;

evi.cumpleFEM = met.cumpleCriteriosFEM;

figArt = visualizar_evidencia_s_laminal(evi);

%% 10. EVALUACION MECANICA DE LA POSTURA

figFEM = figure( ...
    'Color','w', ...
    'Name','/s/ - Evaluacion FEM', ...
    'NumberTitle','off', ...
    'Units','pixels', ...
    'Position',[100 100 1250 610]);

M = sistema.malla;

tri = M.elementos;
XF = sim.estado.nodos;

G = V.elementos.GreenMax(:);
J = V.elementos.J(:);

centros = V.elementos.centros;

limG = V.limites.GreenMax;

fueraG = find(G>limG);

fueraJ = find( ...
    J<V.limites.Jmin | ...
    J>V.limites.Jmax);

%% 1. MAPA DE DEFORMACION

ax = axes( ...
    'Parent',figFEM, ...
    'Units','normalized', ...
    'Position',[0.07 0.20 0.63 0.67]);

hold(ax,'on');

patch(ax, ...
    'Faces',tri, ...
    'Vertices',XF, ...
    'FaceVertexCData',G, ...
    'FaceColor','flat', ...
    'EdgeColor','none');

colormap(ax,parula(256));

cb = colorbar(ax);
cb.Label.String = 'Deformacion Green-Lagrange';

caxis(ax,[0 max(limG,1.05*max(G))]);

% Elementos que superan el criterio Green.
if ~isempty(fueraG)

    plot(ax, ...
        centros(fueraG,1), ...
        centros(fueraG,2), ...
        'rx','MarkerSize',10, ...
        'LineWidth',2);

end

% Elemento con mayor deformacion.
[gMax,ig] = max(G);

plot(ax, ...
    centros(ig,1),centros(ig,2), ...
    'wo','MarkerEdgeColor','k', ...
    'MarkerSize',9, ...
    'LineWidth',1.5);

set(ax,'XDir','reverse');

axis(ax,'equal');
grid(ax,'on');

xlim(ax,[-25 12]);
ylim(ax,[-4 12]);

xlabel(ax,'Y (mm)');
ylabel(ax,'Z (mm)');

title(ax,'Donde se concentra la deformacion');

%% 2. ESTADO NUMERICO

cumple = V.criterios.cumpleCriteriosExploratorios;

if cumple
    estado = 'CUMPLE';
    colorEstado = [0.10 0.50 0.20];
else
    estado = 'NO CUMPLE';
    colorEstado = [0.75 0.15 0.15];
end

panel = uipanel( ...
    'Parent',figFEM, ...
    'Units','normalized', ...
    'Position',[0.76 0.15 0.22 0.72], ...
    'Title','Evaluacion del FEM', ...
    'FontSize',11, ...
    'FontWeight','bold');

uicontrol(panel, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.83 0.86 0.10], ...
    'String',estado, ...
    'ForegroundColor',colorEstado, ...
    'BackgroundColor','w', ...
    'FontSize',14, ...
    'FontWeight','bold');

texto = {
    sprintf('Green: %.4f / %.4f',gMax,limG)
    sprintf('Fuera de Green: %d elementos', ...
        V.global.elementosFueraGreen)
    ' '
    sprintf('J: %.4f a %.4f',min(J),max(J))
    sprintf('Intervalo permitido: %.2f a %.2f', ...
        V.limites.Jmin,V.limites.Jmax)
    sprintf('Fuera de J: %d elementos', ...
        V.global.elementosFueraJ)
    ' '
    sprintf('Estiramiento: %.3f a %.3f', ...
        V.global.lambdaMin,V.global.lambdaMax)
    sprintf('Fuera de estiramiento: %d', ...
        V.global.elementosFueraLambda)
    ' '
    sprintf('Elementos invertidos: %d', ...
        V.global.elementosInvertidos)
    sprintf('Cruces del contorno: %d', ...
        V.contorno.numeroCruces)
};

uicontrol(panel, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.15 0.87 0.65], ...
    'String',texto, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

uicontrol(panel, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.025 0.88 0.11], ...
    'String',{ ...
        'Circulo: deformacion maxima.', ...
        'X roja: limite Green excedido.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',9);

uicontrol(figFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.92 0.88 0.055], ...
    'String','Evaluacion biomecanica de la postura /s/', ...
    'BackgroundColor','w', ...
    'FontSize',15, ...
    'FontWeight','bold');

uicontrol(figFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.04 0.88 0.07], ...
    'String',{ ...
        'El mapa muestra deformacion geometrica, no esfuerzo muscular.', ...
        'Green mide la deformacion; J comprueba cambios locales de area e inversion.', ...
        'Los limites son criterios numericos exploratorios del modelo, no umbrales clinicos.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

%% 11. SALIDA

salida = struct();

salida.cfg = cfg;
salida.sistema = sistema;
salida.postura = postura;

salida.sim = sim;
salida.analisis = analisis;
salida.metricas = met;

salida.figuras = struct( ...
    'sagital',g.figuraSagital, ...
    'zoom',figZoom, ...
    'articulatoria',figArt, ...
    'FEM',figFEM, ...
    'tridimensional',g.figura3D);

end

%% FUNCIONES AUXILIARES

function A = puntos_superiores(R)

ok = R.valido(:) & ...
    isfinite(R.y(:)) & ...
    isfinite(R.zSuperior(:));

A = [R.y(ok),R.zSuperior(ok)];

end

function dibujar_bandas(ax,R)

for k = 1:numel(R)

    r = R(k);

    ok = r.valido(:) & ...
        isfinite(r.y(:)) & ...
        isfinite(r.zInferior(:)) & ...
        isfinite(r.zSuperior(:));

    y = r.y(ok);
    zi = r.zInferior(ok);
    zs = r.zSuperior(ok);

    if numel(y)<2
        continue;
    end

    patch(ax, ...
        [y;flipud(y)], ...
        [zi;flipud(zs)], ...
        r.color, ...
        'FaceAlpha',0.18, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

end

end

function dibujar_distancia(ax,p,q,etiqueta,color)

plot(ax, ...
    [p(1) q(1)], ...
    [p(2) q(2)],'-', ...
    'Color',color, ...
    'LineWidth',2.4, ...
    'HandleVisibility','off');

plot(ax, ...
    [p(1) q(1)], ...
    [p(2) q(2)],'o', ...
    'Color',color, ...
    'MarkerFaceColor',color, ...
    'MarkerSize',5, ...
    'HandleVisibility','off');

centro = (p+q)/2;

text(ax,centro(1)-0.5,centro(2)+0.45, ...
    etiqueta, ...
    'Color',color, ...
    'BackgroundColor','w', ...
    'FontSize',10);

end

function formato_fem(ax)

set(ax,'XDir','reverse');

axis(ax,'equal');
axis(ax,'tight');
grid(ax,'on');

xlabel(ax,'Y (mm)');
ylabel(ax,'Z (mm)');

end