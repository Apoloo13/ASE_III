
function salida = reporte_postura_fonema_t()
% REPORTE_POSTURA_FONEMA_T
% Reporte geometrico, articulatorio y FEM de /t/.
% Reproduce T5 (0.83) con referencia Y+3 y Z+1 mm.
%
% La coincidencia sagital no implica contacto 3D
% ni validacion clinica completa.

%% 1. INICIALIZACION

raiz = fileparts(fileparts(mfilename('fullpath')));

addpath(raiz);

carpetas = { ...
    'geometria','biomecanica','control', ...
    'analisis','visualizacion','secuencias'};

for k = 1:numel(carpetas)
    addpath(fullfile(raiz,carpetas{k}));
end

cfg = configuracion_orofacial();

% Registro especifico para esta postura de /t/.
% No modifica la configuracion general del proyecto.
cfg.geometria.lengua.desplazamientoGlobal = [0 3 1];

% Las franjas coloreadas son referencias auxiliares.
% No interpretarlas como superficies fisicas de contacto.
cfg.visualizacion.mostrarPenetraciones = false;

sistema = preparar_sistema_orofacial(cfg);

postura = definir_postura_fonema_t_cierre(sistema);

op = cfg.simulacion;
op.mostrarConsola = false;

sim = simular_postura_lingual( ...
    sistema.modeloFEM,sistema.lengua0,postura,op);

analisis = analizar_articulacion(sistema,sim);
V = sim.validacion;

%% 2. COORDENADAS MATERIALES

M = sistema.malla;

X0 = M.nodos;
XF = sim.estado.nodos;

ids = M.frontera.superior(:);

yp = X0(M.seguimiento.puntaIndice,1);
L = yp-min(X0(:,1));

s = (yp-X0(ids,1))/L;

[s,ord] = sort(s);
ids = ids(ord);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);
PF = XF(ids,:);

%% 3. REFERENCIAS ANATOMICAS

R = sistema.contactoSagital.regiones;
nombres = string({R.nombre});

iD = find(strcmpi(nombres,'Dental'),1);
iA = find(strcmpi(nombres,'Alveolar'),1);

assert(~isempty(iD) && ~isempty(iA), ...
    'No se encontraron las regiones dentoalveolares.');

D = puntos_superiores_t(R(iD));
A = puntos_superiores_t(R(iA));

%% 4. MEDICION DE CIERRE SAGITAL

sEval = linspace(0,0.30,301)';

Q = interp1(s,PF,sEval,'linear');

ds = hypot(diff(Q(:,1)),diff(Q(:,2)));

contornos = {D,A};

gap = nan(1,2);
sMin = nan(1,2);

pLengua = nan(2,2);
pTecho = nan(2,2);

longitudProxima = zeros(1,2);
penetracion = zeros(1,2);

% Tolerancias geometricas exploratorias.
tolCerca = 0.15;
tolPen = 0.10;

for r = 1:2

    C = contornos{r};

    zTecho = interp1( ...
        C(:,1),C(:,2),Q(:,1),'linear',NaN);

    h = zTecho-Q(:,2);

    validos = find(isfinite(h));

    assert(~isempty(validos), ...
        'No existe correspondencia longitudinal.');

    [gap(r),j] = min(h(validos));

    indice = validos(j);

    sMin(r) = sEval(indice);

    pLengua(r,:) = Q(indice,:);
    pTecho(r,:) = [Q(indice,1),zTecho(indice)];

    cerca = isfinite(h) & abs(h)<=tolCerca;

    longitudProxima(r) = sum( ...
        ds.*(cerca(1:end-1) & cerca(2:end)));

    penetracion(r) = max(0,-gap(r));

end

sinPenetracion = all(penetracion<=tolPen);

%% 5. MORFOLOGIA ANTERIOR Y POSTERIOR

% Direccion de la elevacion anterior.
sOrientacion = [0.02;0.12];

Qang0 = interp1(s,P0,sOrientacion,'linear');
QangF = interp1(s,PF,sOrientacion,'linear');

v0 = Qang0(2,:)-Qang0(1,:);
vF = QangF(2,:)-QangF(1,:);

% Angulo respecto a la direccion longitudinal posterior.
theta0 = atan2d(v0(2),-v0(1));
thetaF = atan2d(vF(2),-vF(1));

cambioAngular = mod(thetaF-theta0+180,360)-180;

% Diagnostico de movimiento posterior.
sPost = linspace(0.30,0.90,151)';

Ppost0 = interp1(s,P0,sPost,'linear');
PpostF = interp1(s,PF,sPost,'linear');

deltaPost = PpostF-Ppost0;

magPost = hypot(deltaPost(:,1),deltaPost(:,2));

RMSposterior = sqrt(mean(magPost.^2));
maxPosterior = max(magPost);

%% 6. METRICAS DEL REPORTE

met = struct();

met.gapDental_mm = gap(1);
met.gapAlveolar_mm = gap(2);

met.sDental = sMin(1);
met.sAlveolar = sMin(2);

met.longitudDental_mm = longitudProxima(1);
met.longitudAlveolar_mm = longitudProxima(2);

met.penetracionDental_mm = penetracion(1);
met.penetracionAlveolar_mm = penetracion(2);

met.sinPenetracionSignificativa = sinPenetracion;

met.anguloAnterior_deg = thetaF;
met.cambioAngular_deg = cambioAngular;

met.RMSposterior_mm = RMSposterior;
met.desplazamientoPosteriorMax_mm = maxPosterior;

met.GreenMax = V.global.GreenMax;
met.Jmin = V.global.Jmin;
met.Jmax = V.global.Jmax;
met.lambdaMin = V.global.lambdaMin;
met.lambdaMax = V.global.lambdaMax;

met.cumpleFEM = ...
    V.criterios.cumpleCriteriosExploratorios;

% La siguiente medida se refiere solamente a
% las franjas auxiliares coloreadas.
met.sinSolapamientoFranjas = ...
    analisis.validacionGeometrica.sinSolapamiento;

%% 7. RESULTADOS NUMERICOS

fprintf('\n===== /t/ - GEOMETRIA ARTICULATORIA =====\n');

fprintf('Registro lingual: Y +3.00 mm, Z +1.00 mm\n');
fprintf('Configuracion: T5, factor 0.83\n');

fprintf('Gap dental superior: %.4f mm\n',gap(1));
fprintf('Gap alveolar superior: %.4f mm\n',gap(2));

fprintf('Posicion material dental: s = %.4f\n',sMin(1));
fprintf('Posicion material alveolar: s = %.4f\n',sMin(2));

fprintf('Longitud proxima dental: %.4f mm\n', ...
    longitudProxima(1));

fprintf('Longitud proxima alveolar: %.4f mm\n', ...
    longitudProxima(2));

fprintf('Penetracion significativa: %d\n', ...
    ~sinPenetracion);

fprintf('Angulo anterior: %.2f grados\n',thetaF);
fprintf('Cambio angular anterior: %+.2f grados\n', ...
    cambioAngular);

fprintf('Desplazamiento RMS posterior: %.3f mm\n', ...
    RMSposterior);

fprintf('\n===== /t/ - FEM =====\n');

fprintf('GreenMax: %.4f / %.4f\n', ...
    V.global.GreenMax,V.limites.GreenMax);

fprintf('Jmin: %.4f / %.4f\n', ...
    V.global.Jmin,V.limites.Jmin);

fprintf('Jmax: %.4f / %.4f\n', ...
    V.global.Jmax,V.limites.Jmax);

fprintf('LambdaMin: %.4f / %.4f\n', ...
    V.global.lambdaMin,V.limites.lambdaMin);

fprintf('Elementos invertidos: %d\n', ...
    V.global.elementosInvertidos);

fprintf('Cruces del contorno: %d\n', ...
    V.contorno.numeroCruces);

fprintf('Cumple FEM: %d\n',met.cumpleFEM);

fprintf('Solapamiento con franjas auxiliares: %d\n', ...
    ~met.sinSolapamientoFranjas);

fprintf(['Nota: el contacto se aproxima en 2D ', ...
    'y no se resuelve mecanicamente.\n']);

if ~met.cumpleFEM || ~sinPenetracion
    warning('La postura /t/ requiere revision.');
end

if abs(met.GreenMax-0.17848)>0.005 || ...
        abs(met.lambdaMin-0.80189)>0.005

    warning(['Los resultados difieren de T5 (0.83). ', ...
        'Revisar configuracion y objetivos.']);

end

%% 8. FIGURAS 1 Y 5: SAGITAL Y 3D

g = visualizar_sistema_orofacial( ...
    sistema,sim,analisis,cfg.visualizacion);

% Superponer el limite superior completo
% de las cuatro regiones anatomicas.
for k = 1:numel(R)

    C = puntos_superiores_t(R(k));

    if ~isempty(C)

        plot(g.axSagital,C(:,1),C(:,2), ...
            'k-','LineWidth',1.3, ...
            'HandleVisibility','off');

    end

end

title(g.axSagital, ...
    '/t/ - postura apico-dentoalveolar y cavidad');

title(g.ax3D, ...
    '/t/ - reconstruccion superficial tridimensional');

rotate3d(g.figura3D,'on');

%% 9. FIGURA 2: ZONA ANTERIOR Y MEDICIONES

figZoom = figure( ...
    'Color','w', ...
    'Name','/t/ - Distancias dentoalveolares', ...
    'NumberTitle','off', ...
    'Position',[130 100 1180 690]);

ax = axes( ...
    'Parent',figZoom, ...
    'Units','normalized', ...
    'Position',[0.07 0.16 0.68 0.74]);

hold(ax,'on');

% Franjas anatomicas.
for k = 1:numel(R)

    B = R(k);

    ok = B.valido(:) & ...
        isfinite(B.y(:)) & ...
        isfinite(B.zSuperior(:)) & ...
        isfinite(B.zInferior(:));

    y = B.y(ok);
    zi = B.zInferior(ok);
    zs = B.zSuperior(ok);

    if numel(y)<2
        continue
    end

    patch(ax, ...
        [y;flipud(y)], ...
        [zi;flipud(zs)], ...
        B.color, ...
        'FaceAlpha',0.16, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

end

% Corte completo de la cavidad.
C = sistema.cavidad.sagital.corteCompleto;

if ~isempty(C)

    nc = size(C,1);

    yy = reshape( ...
        [C(:,1),C(:,3),nan(nc,1)]',[],1);

    zz = reshape( ...
        [C(:,2),C(:,4),nan(nc,1)]',[],1);

    plot(ax,yy,zz,'k-', ...
        'LineWidth',1.5, ...
        'HandleVisibility','off');

end

hD = plot(ax,D(:,1),D(:,2), ...
    'Color',[0.06 0.46 0.86], ...
    'LineWidth',2.2, ...
    'DisplayName','Dental superior');

hA = plot(ax,A(:,1),A(:,2), ...
    'Color',[0.90 0.39 0.10], ...
    'LineWidth',2.2, ...
    'DisplayName','Alveolar superior');

S0 = sistema.lengua0.sagital;
SF = sim.lengua.sagital;

h0 = plot(ax,S0.y,S0.zSuperior, ...
    'k--','LineWidth',1.4, ...
    'DisplayName','Dorso de referencia');

hF = plot(ax,SF.ySuperior,SF.zSuperior, ...
    'r-','LineWidth',2.5, ...
    'DisplayName','Dorso final');

plot(ax,SF.yInferior,SF.zInferior, ...
    'Color',[0.60 0.25 0.46], ...
    'LineWidth',1.4, ...
    'HandleVisibility','off');

% Marcar los puntos de minima separacion.
colores = [
    0.06 0.46 0.86
    0.90 0.39 0.10
];

for r = 1:2

    plot(ax, ...
        [pLengua(r,1) pTecho(r,1)], ...
        [pLengua(r,2) pTecho(r,2)], ...
        '--','Color',colores(r,:), ...
        'LineWidth',2.0, ...
        'HandleVisibility','off');

    plot(ax,pLengua(r,1),pLengua(r,2), ...
        'o','MarkerSize',7, ...
        'MarkerFaceColor',colores(r,:), ...
        'MarkerEdgeColor','w', ...
        'HandleVisibility','off');

end

set(ax,'XDir','reverse');
axis(ax,'equal');
grid(ax,'on');

xlim(ax,[-6 12]);
ylim(ax,[-2 14]);

xlabel(ax,'Y longitudinal (mm)');
ylabel(ax,'Z vertical (mm)');

title(ax, ...
    '/t/: aproximacion al contorno dentoalveolar');

legend(ax,[hD hA h0 hF], ...
    'Location','southoutside', ...
    'NumColumns',2);

% Panel de mediciones separado para no encimar
% textos sobre la zona de cierre.
panelMed = uipanel( ...
    'Parent',figZoom, ...
    'Units','normalized', ...
    'Position',[0.78 0.20 0.20 0.66], ...
    'Title','Cierre sagital', ...
    'FontSize',11);

textoMed = {
    'SEPARACION MINIMA'
    ' '
    sprintf('Dental: %.3f mm',gap(1))
    sprintf('Alveolar: %.3f mm',gap(2))
    ' '
    'POSICION DESDE PUNTA'
    sprintf('Dental: s = %.3f',sMin(1))
    sprintf('Alveolar: s = %.3f',sMin(2))
    ' '
    'LONGITUD PROXIMA'
    sprintf('Dental: %.3f mm',longitudProxima(1))
    sprintf('Alveolar: %.3f mm',longitudProxima(2))
    ' '
    sprintf('Tolerancia: +/- %.2f mm',tolCerca)
    ' '
    'Coincidencia sagital.'
    'No representa contacto 3D.'
};

uicontrol(panelMed, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.05 0.05 0.91 0.91], ...
    'String',textoMed, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

%% 10. FIGURA 3: EVIDENCIA INSTRUMENTAL

evi = struct();

evi.s = s;
evi.P0 = P0;
evi.PF = PF;

evi.punta = sim.estado.puntaYZ;

evi.gapDental = gap(1);
evi.gapAlveolar = gap(2);

evi.sDental = sMin(1);
evi.sAlveolar = sMin(2);

evi.longitudDental = longitudProxima(1);
evi.longitudAlveolar = longitudProxima(2);

evi.cumpleFEM = met.cumpleFEM;

figArt = visualizar_evidencia_t(evi);

%% 11. FIGURA 4: EVALUACION FEM

figFEM = figure( ...
    'Color','w', ...
    'Name','/t/ - Evaluacion FEM', ...
    'NumberTitle','off', ...
    'Position',[150 100 1250 610]);

tri = M.elementos;

G = V.elementos.GreenMax(:);
J = V.elementos.J(:);

centros = V.elementos.centros;

limG = V.limites.GreenMax;

axFEM = axes( ...
    'Parent',figFEM, ...
    'Units','normalized', ...
    'Position',[0.07 0.20 0.63 0.67]);

hold(axFEM,'on');

patch(axFEM, ...
    'Faces',tri, ...
    'Vertices',XF, ...
    'FaceVertexCData',G, ...
    'FaceColor','flat', ...
    'EdgeColor','none');

colormap(axFEM,parula(256));

cb = colorbar(axFEM);
cb.Label.String = 'Deformacion Green-Lagrange';

caxis(axFEM,[0 max(limG,1.05*max(G))]);

fuera = find(G>limG);

if ~isempty(fuera)

    plot(axFEM, ...
        centros(fuera,1),centros(fuera,2), ...
        'rx','MarkerSize',10, ...
        'LineWidth',2);

end

[gMax,iMax] = max(G);

plot(axFEM, ...
    centros(iMax,1),centros(iMax,2), ...
    'wo','MarkerEdgeColor','k', ...
    'MarkerSize',9, ...
    'LineWidth',1.5);

set(axFEM,'XDir','reverse');

axis(axFEM,'equal');
grid(axFEM,'on');

xlim(axFEM,[-25 12]);
ylim(axFEM,[-4 12]);

xlabel(axFEM,'Y longitudinal (mm)');
ylabel(axFEM,'Z vertical (mm)');

title(axFEM, ...
    'Distribucion de deformacion Green-Lagrange');

%% PANEL DE CRITERIOS NUMERICOS

if met.cumpleFEM
    estado = 'CUMPLE';
    colorEstado = [0.10 0.50 0.20];
else
    estado = 'NO CUMPLE';
    colorEstado = [0.78 0.15 0.15];
end

panelFEM = uipanel( ...
    'Parent',figFEM, ...
    'Units','normalized', ...
    'Position',[0.76 0.16 0.22 0.70], ...
    'Title','Evaluacion del FEM', ...
    'FontSize',11, ...
    'FontWeight','bold');

uicontrol(panelFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.06 0.84 0.88 0.10], ...
    'String',estado, ...
    'ForegroundColor',colorEstado, ...
    'BackgroundColor','w', ...
    'FontSize',14, ...
    'FontWeight','bold');

textoFEM = {
    sprintf('Green: %.4f / %.4f', ...
        gMax,V.limites.GreenMax)
    sprintf('Fuera de Green: %d', ...
        V.global.elementosFueraGreen)
    ' '
    sprintf('J: %.4f a %.4f',min(J),max(J))
    sprintf('Limites J: %.2f a %.2f', ...
        V.limites.Jmin,V.limites.Jmax)
    sprintf('Fuera de J: %d', ...
        V.global.elementosFueraJ)
    ' '
    sprintf('Lambda: %.4f a %.4f', ...
        V.global.lambdaMin,V.global.lambdaMax)
    sprintf('Limites: %.2f a %.2f', ...
        V.limites.lambdaMin,V.limites.lambdaMax)
    sprintf('Fuera de lambda: %d', ...
        V.global.elementosFueraLambda)
    ' '
    sprintf('Elementos invertidos: %d', ...
        V.global.elementosInvertidos)
    sprintf('Cruces de contorno: %d', ...
        V.contorno.numeroCruces)
};

uicontrol(panelFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.06 0.19 0.90 0.62], ...
    'String',textoFEM, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

uicontrol(panelFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.06 0.04 0.90 0.12], ...
    'String',{ ...
        'Circulo: elemento mas deformado.', ...
        'X roja: limite excedido.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',9);

uicontrol(figFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.92 0.88 0.055], ...
    'String','Evaluacion biomecanica de la postura /t/', ...
    'BackgroundColor','w', ...
    'FontSize',15, ...
    'FontWeight','bold');

uicontrol(figFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.04 0.88 0.075], ...
    'String',{ ...
        'Green-Lagrange cuantifica la deformacion local del modelo.', ...
        'J evalua el cambio local de area; lambda evalua los estiramientos principales.', ...
        'Los limites son exploratorios y no equivalen a criterios clinicos.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

%% 12. SALIDA

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

fprintf('\nREPORTE DE POSTURA /t/ FINALIZADO.\n');

end

%% FUNCION AUXILIAR

function C = puntos_superiores_t(R)

ok = R.valido(:) & ...
    isfinite(R.y(:)) & ...
    isfinite(R.zSuperior(:));

C = sortrows( ...
    [R.y(ok),R.zSuperior(ok)],1);

[~,iu] = unique(C(:,1),'stable');
C = C(iu,:);

end
