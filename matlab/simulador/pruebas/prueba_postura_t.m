
% PRUEBA_POSTURA_T
%
% POSTURA /t/ LAMINO-DENTOALVEOLAR
% Revision anatomica y seleccion de compromiso.
%
% No modifica STL, malla, material ni solucionador.
% No simula fuerzas de contacto ni produccion acustica.
%
% Y: longitudinal. Z: vertical. Unidades: mm.

clear; clc; close all;

%% =====================================================
% 1. CONFIGURACION DE LA PRUEBA
% ======================================================

% SUPERFICIE DE REFERENCIA:
%
% 'inferior': primer borde del volumen regional
%             encontrado al ascender desde abajo.
%
% 'superior': borde opuesto del volumen regional.
%
% Se comienza con 'inferior' porque la lengua
% esta debajo de los volúmenes STL.
%
% Cambiar a 'superior' SOLO si la inspeccion
% anatomica justifica esa interpretacion.

superficieReferencia = 'inferior';

% Intensidades exploratorias.
niveles = [0.40 0.50 0.60 0.65 ...
           0.70 0.75 0.80 0.85 0.90];

% Parametros de aproximacion.
holguraObjetivo = 0.50;   % mm
radioGuia = 0.10;

% Parametros de seleccion exploratoria.
% No sustituyen los criterios del FEM.
greenExploratorio = 0.27;
JmaxExploratorio = 1.12;
JminExploratorio = 0.90;

% Tolerancia para la comparacion sagital.
toleranciaCruce = 0.10;   % mm

% Holgura usada para estimar extension proxima.
umbralProximidad = 1.00; % mm, exploratorio

%% =====================================================
% 2. RUTAS Y SISTEMA
% ======================================================

raiz = fileparts(fileparts(mfilename('fullpath')));

if ~isfile(fullfile(raiz,'principal.m'))
    error('Guarda el script en simulador/pruebas/.');
end

addpath(raiz);

carpetas = {'geometria','biomecanica','control', ...
    'analisis','visualizacion','secuencias','pruebas'};

for k = 1:numel(carpetas)

    ruta = fullfile(raiz,carpetas{k});

    if ~isfolder(ruta)
        error('Falta la carpeta: %s',ruta);
    end

    addpath(ruta);

end

rehash;

cfg = configuracion_orofacial();
sistema = preparar_sistema_orofacial(cfg);

malla = sistema.malla;
X0 = malla.nodos;

ids = malla.frontera.superior(:);

yPunta = X0(malla.seguimiento.puntaIndice,1);
L = yPunta-min(X0(:,1));

s = (yPunta-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

P0 = X0(ids,:);

%% =====================================================
% 3. EXTRAER AMBAS SUPERFICIES STL
% ======================================================

regiones = sistema.contactoSagital.regiones;

iD = find(strcmpi( ...
    string({regiones.nombre}),'Dental'),1);

iA = find(strcmpi( ...
    string({regiones.nombre}),'Alveolar'),1);

if isempty(iD) || isempty(iA)
    error('Faltan las regiones dental o alveolar.');
end

[yD,zDinf,zDsup] = contornos_region_t(regiones(iD));
[yA,zAinf,zAsup] = contornos_region_t(regiones(iA));

switch lower(superficieReferencia)

    case 'inferior'
        zD = zDinf;
        zA = zAinf;

    case 'superior'
        zD = zDsup;
        zA = zAsup;

    otherwise
        error('Superficie: usar inferior o superior.');
end

fprintf('\n===== REFERENCIA ANATOMICA =====\n');

fprintf('Superficie elegida: %s\n', ...
    superficieReferencia);

fprintf('Dental Y: [%.3f %.3f] mm\n', ...
    min(yD),max(yD));

fprintf('Alveolar Y: [%.3f %.3f] mm\n', ...
    min(yA),max(yA));

fprintf(['Los contornos son envolventes STL; ', ...
    'no prueban contacto anatomico por si solos.\n']);


%% =====================================================
% 4. OBJETIVOS ARTICULATORIOS DENTOALVEOLARES
% ======================================================

% Dos regiones de control diferenciadas.
sControl = [0.06;0.16];

pesos = [0.75;0.85];

Pini = interp1(s,P0,sControl,'linear');

% Primera meta: dental.
% Segunda meta: alveolar.
yObjetivo = [4.4;1.0];

metas = zeros(2,2);

for k = 1:2

    if k == 1
        yRegion = yD;
        zRegion = zD;
    else
        yRegion = yA;
        zRegion = zA;
    end

    zObjetivo = interp1( ...
        yRegion,zRegion,yObjetivo(k), ...
        'linear',NaN);

    if ~isfinite(zObjetivo)
        error('Objetivo fuera de la region.');
    end

    metas(k,:) = [ ...
        yObjetivo(k), ...
        zObjetivo-holguraObjetivo
        ];

end

delta = metas-Pini;

fprintf('\n===== NUEVOS OBJETIVOS /t/ =====\n');

fprintf('%6s %10s %10s %10s %10s\n', ...
    's','MetaY','MetaZ','DeltaY','DeltaZ');

for k = 1:numel(sControl)

    fprintf('%6.2f %10.3f %10.3f %10.3f %10.3f\n', ...
        sControl(k),metas(k,:),delta(k,:));

end


%% =====================================================
% 5. PREPARAR CALIBRACION
% ======================================================

op = cfg.simulacion;
op.mostrarConsola = false;
op.distribucionGuia.radio = radioGuia;

n = numel(niveles);

simulaciones = cell(n,1);
posturas = cell(n,1);
analisis = cell(n,1);

% Distancias a la superficie seleccionada.
dDental = nan(n,1);
dAlveolar = nan(n,1);

sDental = nan(n,1);
sAlveolar = nan(n,1);

% Distancias a ambas envolventes.
dDentalInf = nan(n,1);
dDentalSup = nan(n,1);
dAlveolarInf = nan(n,1);
dAlveolarSup = nan(n,1);

% Geometria.
penetracion = nan(n,1);
longitudProxima = nan(n,1);
sinSolapamiento = false(n,1);

% FEM.
green = nan(n,1);
Jmin = nan(n,1);
Jmax = nan(n,1);
cumpleFEM = false(n,1);

% Intervalos materiales de evaluacion.
sEvalDental = linspace(0.02,0.18,201)';
sEvalAlveolar = linspace(0.12,0.24,201)';

%% =====================================================
% 6. RESOLVER POSTURAS
% ======================================================

fprintf('\n===== CALIBRACION DE /t/ =====\n');

for k = 1:n

    a = niveles(k);

    postura = struct();

    postura.nombre = sprintf('T nivel %.2f',a);

    % Misma progresion utilizada anteriormente.
    postura.puntaYZ = [4.5*a/0.80 0];

    % Objetivos absolutos Y-Z.
    Pmeta = Pini+a*delta;

    postura.dorso = [
        sControl Pmeta pesos
    ];

    postura.vientre = zeros(0,4);

    postura.curvaturaApical = 0;
    postura.curvaturaLaminal = 0;

    postura.anguloApice = NaN;
    postura.anguloLamina = NaN;

    posturas{k} = postura;

    try

        sim = simular_postura_lingual( ...
            sistema.modeloFEM, ...
            sistema.lengua0,postura,op);

        % Conservar el analisis del sistema,
        % evitando imprimir todas sus tablas.
        evalc('an = analizar_articulacion(sistema,sim);');

        simulaciones{k} = sim;
        analisis{k} = an;

        PF = sim.estado.nodos(ids,:);

        % Distancias respecto a superficie elegida.
        [dDental(k),sDental(k)] = distancia_t( ...
            s,PF,sEvalDental,yD,zD);

        [dAlveolar(k),sAlveolar(k)] = distancia_t( ...
            s,PF,sEvalAlveolar,yA,zA);

        % Comparar ambas envolventes, siempre.
        [dDentalInf(k),~] = distancia_t( ...
            s,PF,sEvalDental,yD,zDinf);

        [dDentalSup(k),~] = distancia_t( ...
            s,PF,sEvalDental,yD,zDsup);

        [dAlveolarInf(k),~] = distancia_t( ...
            s,PF,sEvalAlveolar,yA,zAinf);

        [dAlveolarSup(k),~] = distancia_t( ...
            s,PF,sEvalAlveolar,yA,zAsup);

        % Penetracion respecto al borde inferior:
        % el posible primer encuentro desde abajo.
        penetracion(k) = penetracion_t( ...
            s,PF,regiones);

        % Area de solapamiento del analisis original.
        sinSolapamiento(k) = ...
            an.validacionGeometrica.sinSolapamiento;

        % Extension de la lengua anterior con
        % holgura positiva menor al umbral.
        longitudProxima(k) = longitud_proxima_t( ...
            s,PF,yD,zD,yA,zA, ...
            umbralProximidad);

        green(k) = sim.resumen.GreenMax;
        Jmin(k) = sim.resumen.Jmin;
        Jmax(k) = sim.validacion.global.Jmax;

        cumpleFEM(k) = ...
            sim.resumen.cumpleCriteriosExploratorios;

    catch ME

        warning('Nivel %.2f: %s',a,ME.message);

    end

end

%% =====================================================
% 7. RESULTADOS
% ======================================================

fprintf('\n===== PROXIMIDAD ARTICULATORIA =====\n');

fprintf('%6s %9s %9s %10s %10s %9s\n', ...
    'Nivel','Dental','Alveolar', ...
    's Dental','s Alv.','Long. prox.');

for k = 1:n

    if isempty(simulaciones{k})
        continue
    end

    fprintf('%6.2f %9.3f %9.3f %10.4f %10.4f %9.3f\n', ...
        niveles(k),dDental(k),dAlveolar(k), ...
        sDental(k),sAlveolar(k), ...
        longitudProxima(k));

end

fprintf('\nLong. prox.: longitud sagital anterior con\n');
fprintf('holgura positiva menor a %.2f mm.\n', ...
    umbralProximidad);

fprintf('\n===== COMPARACION DE CONTORNOS =====\n');

fprintf('%6s %9s %9s %9s %9s\n', ...
    'Nivel','D Inf','D Sup','A Inf','A Sup');

for k = 1:n

    if isempty(simulaciones{k})
        continue
    end

    fprintf('%6.2f %9.3f %9.3f %9.3f %9.3f\n', ...
        niveles(k), ...
        dDentalInf(k),dDentalSup(k), ...
        dAlveolarInf(k),dAlveolarSup(k));

end

fprintf('\n===== VALIDACION MECANICA =====\n');

fprintf('%6s %9s %9s %9s %6s %8s %9s\n', ...
    'Nivel','Green','Jmin','Jmax', ...
    'FEM','SinSolap','Penetr.');

for k = 1:n

    if isempty(simulaciones{k})
        continue
    end

    fprintf('%6.2f %9.4f %9.4f %9.4f %6d %8d %9.3f\n', ...
        niveles(k),green(k),Jmin(k),Jmax(k), ...
        cumpleFEM(k),sinSolapamiento(k), ...
        penetracion(k));

end

%% =====================================================
% 8. SELECCION DE POSTURAS
% ======================================================

% Criterios geometricos.
% No permitimos penetracion importante ni
% solapamiento regional detectado.

geometriaAdmisible = ...
    sinSolapamiento & ...
    penetracion <= toleranciaCruce;

% A. Posturas completamente admisibles.
admisiblesFEM = find( ...
    cumpleFEM & geometriaAdmisible);

% B. Posturas exploratorias.
% Permiten excedencia moderada de Green o Jmax,
% pero NO se declaran validadas por el FEM.
admisiblesExploratorias = find( ...
    geometriaAdmisible & ...
    green <= greenExploratorio & ...
    Jmin >= JminExploratorio & ...
    Jmax <= JmaxExploratorio);

% Priorizar proximidad anterior y alveolar.
% Penalizar progresivamente excedencias Green.
%
% Puntuacion interna de ingenieria:
% no corresponde a una escala clinica.

puntuacion = ...
    0.45*dDental + ...
    0.55*dAlveolar + ...
    0.60*max(0,(green-0.20)/0.05) - ...
    0.05*min(longitudProxima,5);

% Mejor postura estrictamente FEM.
kFEM = [];

if ~isempty(admisiblesFEM)

    [~,j] = min(puntuacion(admisiblesFEM));
    kFEM = admisiblesFEM(j);

end

% Mejor compromiso exploratorio.
kCompromiso = [];

if ~isempty(admisiblesExploratorias)

    [~,j] = min( ...
        puntuacion(admisiblesExploratorias));

    kCompromiso = admisiblesExploratorias(j);

end

fprintf('\n===== SELECCION DE POSTURAS =====\n');

if ~isempty(kFEM)

    fprintf('\nMEJOR POSTURA FEM:\n');

    informar_t(kFEM,niveles,dDental,dAlveolar, ...
        green,cumpleFEM,longitudProxima);

else

    fprintf('\nNo hay postura estrictamente FEM admisible.\n');

end

if ~isempty(kCompromiso)

    fprintf('\nMEJOR COMPROMISO EXPLORATORIO:\n');

    informar_t(kCompromiso,niveles,dDental,dAlveolar, ...
        green,cumpleFEM,longitudProxima);

else

    fprintf('\nNo hay compromiso exploratorio admisible.\n');

end

% Seleccionar para visualizacion el compromiso.
% Si no existe, utilizar la mejor FEM.
if ~isempty(kCompromiso)

    kSel = kCompromiso;

elseif ~isempty(kFEM)

    kSel = kFEM;

else

    candidatos = find(~cellfun( ...
        @isempty,simulaciones));

    if isempty(candidatos)
        error('Ninguna simulacion se completo.');
    end

    [~,j] = min(green(candidatos));
    kSel = candidatos(j);

    warning('Solo se muestra una postura diagnostica.');

end

%% =====================================================
% 9. RESULTADOS REUTILIZABLES
% ======================================================

simSeleccionada = simulaciones{kSel};
reporteT = analizar_correspondencia_comun( ...
    sistema,simSeleccionada,'/t/');
posturaSeleccionada = posturas{kSel};

referenciaT = struct();

referenciaT.superficie = superficieReferencia;
referenciaT.radioGuia = radioGuia;

referenciaT.indiceFEM = kFEM;
referenciaT.indiceCompromiso = kCompromiso;

referenciaT.nivel = niveles(kSel);
referenciaT.postura = posturaSeleccionada;

referenciaT.distanciaDental_mm = dDental(kSel);
referenciaT.distanciaAlveolar_mm = dAlveolar(kSel);

referenciaT.GreenMax = green(kSel);
referenciaT.cumpleFEM = cumpleFEM(kSel);
referenciaT.sinSolapamiento = ...
    sinSolapamiento(kSel);

referenciaT.penetracion_mm = penetracion(kSel);
referenciaT.longitudProxima_mm = ...
    longitudProxima(kSel);

%% =====================================================
% 10. VISUALIZACION ANATOMICA
% ======================================================

figure('Color','w', ...
    'Name','Interpretacion anatomica de los STL');

hold on;

% Secciones regionales coloreadas.
patch([yD;flipud(yD)], ...
    [zDinf;flipud(zDsup)], ...
    [0.25 0.55 0.90], ...
    'FaceAlpha',0.15,'EdgeColor','none', ...
    'DisplayName','Volumen regional dental');

patch([yA;flipud(yA)], ...
    [zAinf;flipud(zAsup)], ...
    [0.95 0.55 0.15], ...
    'FaceAlpha',0.15,'EdgeColor','none', ...
    'DisplayName','Volumen regional alveolar');

% Ambos bordes de las regiones.
plot(yD,zDinf,'b-', ...
    'LineWidth',2,'DisplayName','Dental inferior');

plot(yD,zDsup,'b--', ...
    'LineWidth',2,'DisplayName','Dental superior');

plot(yA,zAinf,'Color',[0.9 0.4 0.1], ...
    'LineWidth',2, ...
    'DisplayName','Alveolar inferior');

plot(yA,zAsup,'--', ...
    'Color',[0.9 0.4 0.1], ...
    'LineWidth',2, ...
    'DisplayName','Alveolar superior');

% Corte de la cavidad completa para contexto.
seg = sistema.cavidad.sagital.corteCompleto;

if ~isempty(seg)

    m = size(seg,1);

    yy = reshape( ...
        [seg(:,1) seg(:,3) nan(m,1)]',[],1);

    zz = reshape( ...
        [seg(:,2) seg(:,4) nan(m,1)]',[],1);

    plot(yy,zz,'-', ...
        'Color',[0.72 0.72 0.72], ...
        'LineWidth',0.6, ...
        'HandleVisibility','off');

end

S0 = sistema.lengua0.sagital;

plot(S0.y,S0.zSuperior,'k--', ...
    'LineWidth',1.4, ...
    'DisplayName','Lengua en reposo');

S = simSeleccionada.lengua.sagital;

plot(S.ySuperior,S.zSuperior,'r-', ...
    'LineWidth',2.6, ...
    'DisplayName','Lengua seleccionada');

set(gca,'XDir','reverse');

axis equal;
grid on;

xlabel('Y (mm)');
ylabel('Z (mm)');

title('Contornos regionales y cavidad completa');
legend('Location','best');

xlim([-23 12]);

%% =====================================================
% 11. COMPARACION DE POSTURAS
% ======================================================

figure('Color','w', ...
    'Name','Seleccion articulatoria /t/');

hold on;

plot(yD,zD,'b-', ...
    'LineWidth',2.3, ...
    'DisplayName','Referencia dental');

plot(yA,zA, ...
    'Color',[0.90 0.40 0.10], ...
    'LineWidth',2.3, ...
    'DisplayName','Referencia alveolar');

plot(S0.y,S0.zSuperior,'k--', ...
    'LineWidth',1.2, ...
    'DisplayName','Reposo');

if ~isempty(kFEM)

    SF = simulaciones{kFEM}.lengua.sagital;

    plot(SF.ySuperior,SF.zSuperior, ...
        'Color',[0.20 0.60 0.35], ...
        'LineWidth',2, ...
        'DisplayName','Mejor FEM');

end

if ~isempty(kCompromiso)

    SC = simulaciones{kCompromiso}.lengua.sagital;

    plot(SC.ySuperior,SC.zSuperior,'r-', ...
        'LineWidth',2.5, ...
        'DisplayName','Mejor compromiso');

end

set(gca,'XDir','reverse');

axis equal;
grid on;

xlabel('Y (mm)');
ylabel('Z (mm)');

title('Comparacion de referencias /t/');
legend('Location','best');

xlim([-23 12]);

%% =====================================================
% 12. CONCLUSION
% ======================================================

fprintf('\n===== CONCLUSION =====\n');

fprintf('Contorno evaluado: %s\n', ...
    superficieReferencia);

fprintf('Nivel visualizado: %.2f\n',niveles(kSel));

fprintf('Cumple FEM: %d\n',cumpleFEM(kSel));

fprintf('Solapamiento regional: %d\n', ...
    ~sinSolapamiento(kSel));

fprintf('Penetracion maxima: %.3f mm\n', ...
    penetracion(kSel));

fprintf(['La seleccion es una aproximacion ', ...
    'articulatoria sagital exploratoria.\n']);

fprintf(['No demuestra cierre oral 3D ', ...
    'ni produccion acustica del fonema.\n']);

fprintf('\nPRUEBA /t/ FINALIZADA.\n');

%% =====================================================
% FUNCIONES LOCALES
% ======================================================

function [y,zInf,zSup] = contornos_region_t(R)

    ok = R.valido(:) & ...
        isfinite(R.y(:)) & ...
        isfinite(R.zInferior(:)) & ...
        isfinite(R.zSuperior(:));

    y = R.y(ok);
    zInf = R.zInferior(ok);
    zSup = R.zSuperior(ok);

    [y,ord] = sort(y);

    zInf = zInf(ord);
    zSup = zSup(ord);

    [y,iu] = unique(y,'stable');

    zInf = zInf(iu);
    zSup = zSup(iu);

end

function [dMin,sCercano] = distancia_t( ...
    s,P,sEval,yR,zR)

    Q = interp1(s,P,sEval,'linear');

    D = hypot( ...
        Q(:,1)-yR(:)', ...
        Q(:,2)-zR(:)');

    [dMin,idx] = min(D(:));

    [i,~] = ind2sub(size(D),idx);

    sCercano = sEval(i);

end

function pMax = penetracion_t(s,P,regiones)

    sEval = linspace(0.0,0.40,401)';

    Q = interp1(s,P,sEval,'linear');

    pMax = 0;

    for k = 1:numel(regiones)

        [y,zInf,~] = contornos_region_t( ...
            regiones(k));

        zContacto = interp1( ...
            y,zInf,Q(:,1),'linear',NaN);

        validos = isfinite(zContacto);

        if any(validos)

            exceso = Q(validos,2)-zContacto(validos);

            pMax = max(pMax,max([0;exceso]));

        end

    end

end

function longitud = longitud_proxima_t( ...
    s,P,yD,zD,yA,zA,umbral)

    sEval = linspace(0.02,0.24,301)';

    Q = interp1(s,P,sEval,'linear');

    hD = interp1( ...
        yD,zD,Q(:,1),'linear',NaN)-Q(:,2);

    hA = interp1( ...
        yA,zA,Q(:,1),'linear',NaN)-Q(:,2);

    h = nan(size(sEval));

    for k = 1:numel(h)

        valores = [hD(k),hA(k)];
        valores = valores(isfinite(valores));

        if ~isempty(valores)
            h(k) = min(valores);
        end

    end

    cerca = isfinite(h) & ...
        h >= 0 & h <= umbral;

    segmentos = hypot( ...
        diff(Q(:,1)),diff(Q(:,2)));

    longitud = sum( ...
        segmentos(cerca(1:end-1) & cerca(2:end)));

end

function informar_t(k,niveles,dD,dA,green,fem,longitud)

    fprintf('Nivel: %.2f\n',niveles(k));

    fprintf('Distancia dental: %.3f mm\n',dD(k));
    fprintf('Distancia alveolar: %.3f mm\n',dA(k));

    fprintf('GreenMax: %.4f\n',green(k));
    fprintf('Cumple FEM: %d\n',fem(k));

    fprintf('Extension proxima: %.3f mm\n',longitud(k));

    if ~fem(k)
        fprintf(['ATENCION: postura exploratoria; ', ...
            'no cumple toda la validacion FEM.\n']);
    end

end
