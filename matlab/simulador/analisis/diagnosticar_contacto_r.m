
function d = diagnosticar_contacto_r(sistema,sim,op)
% DIAGNOSTICAR_CONTACTO_R
% Proximidad sagital exploratoria para la vibrante multiple /r/.
%
% Usa zSuperior de los STL regionales, como el reporte /t/.
% No calcula contacto mecanico, fuerzas ni mapa EPG bilateral.

if nargin<3 || isempty(op)
    op = struct();
end

if ~isfield(op,'graficar')
    op.graficar = false;
end

if ~isfield(op,'umbralCerca_mm')
    op.umbralCerca_mm = 0.50;
end

if ~isfield(op,'toleranciaPen_mm')
    op.toleranciaPen_mm = 0.10;
end

%% 1. CONTORNO LINGUAL MATERIAL

M = sistema.malla;
X0 = M.nodos;
XF = sim.estado.nodos;

ids = M.frontera.superior(:);
idTip = M.seguimiento.puntaIndice;

L = X0(idTip,1)-min(X0(:,1));

assert(L>0,'Longitud lingual de referencia invalida.');

s = (X0(idTip,1)-X0(ids,1))/L;

[s,ord] = sort(s);
ids = ids(ord);

[s,iu] = unique(s,'stable');
ids = ids(iu);

% Region anterior y parte del dorso.
sEval = linspace(0,min(0.60,max(s)),361)';

Q0 = interp1(s,X0(ids,:),sEval,'linear');
Q = interp1(s,XF(ids,:),sEval,'linear');

ds = hypot(diff(Q(:,1)),diff(Q(:,2)));

%% 2. REGIONES ANATOMICAS

R = sistema.contactoSagital.regiones;

lista = { ...
    'Dental', ...
    'Alveolar', ...
    'Prepalatal', ...
    'Mediopalatal'};

colores = [
    0.15 0.45 0.86
    0.94 0.43 0.10
    0.55 0.33 0.78
    0.18 0.62 0.45
];

base = struct( ...
    'nombre','', ...
    'gapMin_mm',NaN, ...
    'sMin',NaN, ...
    'Ymin_mm',NaN, ...
    'longitudCercana_mm',0, ...
    'penetracionMax_mm',NaN, ...
    'distanciaPunta_mm',NaN, ...
    'proximidadApical',false);

regiones = repmat(base,numel(lista),1);

contornos = cell(numel(lista),1);
holguras = cell(numel(lista),1);

%% 3. MEDICIONES POR REGION

for r = 1:numel(lista)

    regiones(r).nombre = lista{r};

    j = find(strcmpi( ...
        string({R.nombre}),lista{r}),1);

    if isempty(j)
        continue
    end

    B = R(j);

    valido = B.valido(:) & ...
        isfinite(B.y(:)) & ...
        isfinite(B.zSuperior(:));

    C = sortrows( ...
        [B.y(valido),B.zSuperior(valido)],1);

    [~,ia] = unique(C(:,1),'stable');
    C = C(ia,:);

    if size(C,1)<2
        continue
    end

    contornos{r} = C;

    % Distancia euclidiana de la punta
    % al contorno regional.

    pTip = sim.estado.puntaYZ(:)';

    regiones(r).distanciaPunta_mm = ...
        min(hypot( ...
        C(:,1)-pTip(1), ...
        C(:,2)-pTip(2)));

    % Separacion vertical respecto a zSuperior.
    % No equivale a distancia normal de contacto.

    zRef = interp1( ...
        C(:,1),C(:,2),Q(:,1),'linear',NaN);

    h = zRef-Q(:,2);

    holguras{r} = h;

    % Evaluacion anterior para Dental/Alveolar.
    % Observacion mas amplia para regiones posteriores.

    if r<=2
        sLimite = 0.30;
    else
        sLimite = 0.60;
    end

    ok = isfinite(h) & sEval<=sLimite;
    ix = find(ok);

    if isempty(ix)
        continue
    end

    [hMin,kLocal] = min(h(ix));
    k = ix(kLocal);

    cerca = ok & ...
        abs(h)<=op.umbralCerca_mm & ...
        h>=-op.toleranciaPen_mm;

    regiones(r).gapMin_mm = hMin;
    regiones(r).sMin = sEval(k);
    regiones(r).Ymin_mm = Q(k,1);

    regiones(r).longitudCercana_mm = ...
        sum(ds.*( ...
        cerca(1:end-1) & cerca(2:end)));

    regiones(r).penetracionMax_mm = ...
        max(0,-hMin);

    regiones(r).proximidadApical = ...
        sEval(k)<=0.12;

end

%% 4. ESTRUCTURA DE RESULTADOS

d = struct();

d.regiones = regiones;

d.s = sEval;
d.P0 = Q0;
d.PF = Q;

d.holguras = holguras;
d.contornos = contornos;

d.gapAlveolar_mm = regiones(2).gapMin_mm;
d.gapDental_mm = regiones(1).gapMin_mm;

d.sAlveolar = regiones(2).sMin;

d.distanciaPuntaAlveolar_mm = ...
    regiones(2).distanciaPunta_mm;

% Condicion geometrica preliminar:
% separacion alveolar positiva inferior a 1 mm.
% No demuestra capacidad de vibracion.

d.cercaniaAlveolarPrevia = ...
    isfinite(d.gapAlveolar_mm) && ...
    d.gapAlveolar_mm>0 && ...
    d.gapAlveolar_mm<1.0;

d.toleranciaCerca_mm = op.umbralCerca_mm;
d.toleranciaPen_mm = op.toleranciaPen_mm;

d.figura = [];

%% 5. VISUALIZACION OPCIONAL

if ~op.graficar
    return
end

fprintf('\n===== DIAGNOSTICO SAGITAL /r/ =====\n');

for r = 1:numel(lista)

    fprintf([ ...
        '%-13s gap=%8.3f mm | ', ...
        's=%6.3f | cerca=%7.3f mm\n'], ...
        lista{r}, ...
        regiones(r).gapMin_mm, ...
        regiones(r).sMin, ...
        regiones(r).longitudCercana_mm);

end

fprintf('Punta a contorno alveolar (2D): %.3f mm\n', ...
    d.distanciaPuntaAlveolar_mm);

fprintf(['Nota: no se determina contacto 3D ', ...
    'ni patron EPG.\n']);

fig = figure( ...
    'Color','w', ...
    'Name','/r/ - Diagnostico anterior', ...
    'NumberTitle','off', ...
    'Position',[130 110 1350 580]);

tl = tiledlayout(fig,1,2, ...
    'TileSpacing','compact');

%% Figura izquierda: anatomia y perfil

ax1 = nexttile(tl,1);
hold(ax1,'on');

for r = 1:numel(lista)

    C = contornos{r};

    if isempty(C)
        continue
    end

    plot(ax1,C(:,1),C(:,2),'-', ...
        'Color',colores(r,:), ...
        'LineWidth',1.8, ...
        'DisplayName',lista{r});

end

plot(ax1,Q0(:,1),Q0(:,2),'k--', ...
    'LineWidth',1.6, ...
    'DisplayName','Referencia FEM');

plot(ax1,Q(:,1),Q(:,2),'r-', ...
    'LineWidth',2.3, ...
    'DisplayName','Candidata /r/');

plot(ax1, ...
    sim.estado.puntaYZ(1), ...
    sim.estado.puntaYZ(2),'ro', ...
    'MarkerFaceColor','r', ...
    'HandleVisibility','off');

set(ax1,'XDir','reverse');

grid(ax1,'on');
axis(ax1,'equal');

xlabel(ax1,'Y (mm)');
ylabel(ax1,'Z (mm)');

title(ax1,'Perfil y contornos regionales superiores');
legend(ax1,'Location','best');

%% Figura derecha: separaciones

ax2 = nexttile(tl,2);
hold(ax2,'on');

for r = 1:3

    h = holguras{r};

    if isempty(h)
        continue
    end

    plot(ax2,sEval,h,'-', ...
        'Color',colores(r,:), ...
        'LineWidth',2, ...
        'DisplayName',lista{r});

end

yline(ax2,0,'k--','Separacion nula');

yline(ax2,1.0,':', ...
    '1 mm - referencia exploratoria');

yline(ax2,-op.toleranciaPen_mm,'r:', ...
    'Penetracion significativa');

xlim(ax2,[0 0.60]);

grid(ax2,'on');

xlabel(ax2, ...
    'Coordenada material s (punta = 0)');

ylabel(ax2, ...
    'Gap vertical respecto a zSuperior (mm)');

title(ax2, ...
    'Separacion sagital, no contacto mecanico');

legend(ax2,'Location','best');

title(tl, ...
    '/r/ - Proximidad apicoalveolar exploratoria');

d.figura = fig;

end