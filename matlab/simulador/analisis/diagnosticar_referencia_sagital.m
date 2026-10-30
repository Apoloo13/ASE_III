
function reporte = diagnosticar_referencia_sagital(sistema,simulacion)
% Compara los contornos STL y la geometria lingual.
% No modifica el sistema ni ejecuta FEM.

%% 1. DATOS

C = sistema.cavidad.sagital.corteCompleto;
R = sistema.contactoSagital.regiones;

malla = sistema.malla;
X0 = malla.nodos;

ids = malla.frontera.superior(:);

yp = X0(malla.seguimiento.puntaIndice,1);
L = yp-min(X0(:,1));

s = (yp-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);

if nargin >= 2 && ~isempty(simulacion)
    PF = simulacion.estado.nodos(ids,:);
else
    PF = P0;
end

%% 2. FIGURA

figure('Color','w', ...
    'Name','Diagnostico de referencia sagital');

ax = axes;
hold(ax,'on');

%% 3. CORTE DEL STL COMPLETO

if ~isempty(C)

    n = size(C,1);

    yc = reshape([ ...
        C(:,1) C(:,3) nan(n,1)]',[],1);

    zc = reshape([ ...
        C(:,2) C(:,4) nan(n,1)]',[],1);

    plot(ax,yc,zc,'k-', ...
        'LineWidth',1.7, ...
        'DisplayName','Corte STL completo');

end

%% 4. ENVOLVENTES DE CADA REGION

for k = 1:numel(R)

    rk = R(k);

    ok = rk.valido(:) & ...
        isfinite(rk.y(:)) & ...
        isfinite(rk.zInferior(:)) & ...
        isfinite(rk.zSuperior(:));

    if ~any(ok)
        continue
    end

    nombre = char(rk.nombre);

    plot(ax,rk.y(ok),rk.zInferior(ok), ...
        '-','Color',rk.color, ...
        'LineWidth',2.0, ...
        'DisplayName',[nombre ' - inferior']);

    plot(ax,rk.y(ok),rk.zSuperior(ok), ...
        ':','Color',rk.color, ...
        'LineWidth',1.5, ...
        'DisplayName',[nombre ' - superior']);

end

%% 5. LENGUA

S0 = sistema.lengua0.sagital;

plot(ax,S0.y,S0.zSuperior,'k--', ...
    'LineWidth',1.2, ...
    'DisplayName','Lengua referencia');

plot(ax,PF(:,1),PF(:,2),'r-', ...
    'LineWidth',2.3, ...
    'DisplayName','Dorso evaluado');

%% 6. PUNTOS MATERIALES

sMarcas = [0.12;0.16;0.24;0.29;0.32];

Q0 = interp1(s,P0,sMarcas,'linear');
QF = interp1(s,PF,sMarcas,'linear');

plot(ax,QF(:,1),QF(:,2),'yo', ...
    'MarkerEdgeColor','k', ...
    'MarkerFaceColor','y', ...
    'MarkerSize',6, ...
    'DisplayName','Puntos materiales');

for k = 1:numel(sMarcas)

    text(ax, ...
        QF(k,1),QF(k,2)+0.55, ...
        sprintf('s=%.2f',sMarcas(k)), ...
        'FontSize',9, ...
        'HorizontalAlignment','center');

end

%% 7. ORIENTACION LAMINAL

% Vector desde la region posterior hacia la anterior.
iA = 2; % s = 0.16
iP = 4; % s = 0.29

v0 = Q0(iA,:)-Q0(iP,:);
vF = QF(iA,:)-QF(iP,:);

angulo0 = atan2d(v0(2),v0(1));
anguloF = atan2d(vF(2),vF(1));

plot(ax, ...
    [QF(iA,1) QF(iP,1)], ...
    [QF(iA,2) QF(iP,2)], ...
    'm-','LineWidth',2.3, ...
    'DisplayName','Orientacion laminal');

%% 8. PRESENTACION

set(ax,'XDir','reverse');

axis(ax,'equal');
grid(ax,'on');

xlabel(ax,'Y (mm)');
ylabel(ax,'Z (mm)');

title(ax,'Referencias anatomicas y linguales');

xlim(ax,[-30 12]);
ylim(ax,[-5 30]);

legend(ax,'Location','eastoutside');

%% 9. REPORTE

fprintf('\n===== REFERENCIA SAGITAL =====\n');

fprintf('%-8s %10s %10s %10s %10s\n', ...
    's','Y inicial','Z inicial','Y final','Z final');

for k = 1:numel(sMarcas)

    fprintf('%-8.2f %10.3f %10.3f %10.3f %10.3f\n', ...
        sMarcas(k),Q0(k,:),QF(k,:));

end

fprintf('\nOrientacion laminal inicial: %.3f grados\n', ...
    angulo0);

fprintf('Orientacion laminal final: %.3f grados\n', ...
    anguloF);

fprintf('Cambio angular: %.3f grados\n', ...
    atan2d(sind(anguloF-angulo0), ...
           cosd(anguloF-angulo0)));

reporte.s = sMarcas;
reporte.puntosIniciales = Q0;
reporte.puntosFinales = QF;
reporte.anguloInicial_deg = angulo0;
reporte.anguloFinal_deg = anguloF;

end
