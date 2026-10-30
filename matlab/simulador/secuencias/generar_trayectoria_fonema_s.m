
function tray = generar_trayectoria_fonema_s(sistema,cfg)
% Trayectoria cuasiestatica del fonema /s/ laminal.
% Cada muestra representa un equilibrio FEM resuelto.
% El progreso entre consignas sigue un perfil minimo-jerk.

C = cfg.trayectoriaS;
n = C.nEstados;

validateattributes(n,{'numeric'}, ...
    {'scalar','integer','>=',6,'<=',300});

%% 1. POSTURA FINAL Y REFERENCIA

PF = definir_postura_fonema_s_laminal(sistema);

M = sistema.malla;
X0 = M.nodos;

ids = M.frontera.superior(:);

idPunta = M.seguimiento.puntaIndice;
yPunta = X0(idPunta,1);

L = yPunta-min(X0(:,1));
s = (yPunta-X0(ids,1))/L;

[s,ord] = sort(s);
ids = ids(ord);

[s,iu] = unique(s,'stable');
ids = ids(iu);

PReferencia = X0(ids,:);

assert(size(PF.dorso,2)==4, ...
    'La postura final requiere objetivos [s Y Z peso].');

assert(isempty(PF.vientre) || size(PF.vientre,2)==4, ...
    'Los objetivos ventrales deben tener cuatro columnas.');

% Misma estructura de objetivos en ambos extremos.
PI = PF;
PI.nombre = "Referencia inicial /s/";
PI.puntaYZ = X0(idPunta,:);

PI.dorso(:,2:3) = interp1( ...
    s,PReferencia,PF.dorso(:,1),'linear');

if ~isempty(PF.vientre)

    idsInf = M.frontera.inferior(:);

    sInf = (yPunta-X0(idsInf,1))/L;
    [sInf,ordInf] = sort(sInf);
    idsInf = idsInf(ordInf);

    [sInf,iuInf] = unique(sInf,'stable');
    idsInf = idsInf(iuInf);

    PI.vientre(:,2:3) = interp1( ...
        sInf,X0(idsInf,:), ...
        PF.vientre(:,1),'linear');

end

assert(all(isfinite(PI.dorso(:,2:3)),'all'), ...
    'No fue posible interpolar los puntos iniciales.');

%% 2. PARAMETRO DE TRAYECTORIA

u = linspace(0,1,n)';

% Quintica de minimo jerk, con extremos suaves.
a = 10*u.^3-15*u.^4+6*u.^5;

a(1) = 0;
a(end) = 1;

%% 3. PUNTOS MATERIALES A SEGUIR

nombres = { ...
    'Punta', ...
    'Apice anterior', ...
    'Lamina anterior', ...
    'Predorso', ...
    'Dorso medio', ...
    'Dorso posterior'};

sMarcas = [0 0.06 0.12 0.24 0.50 0.75];

np = numel(sMarcas);

% N estados x N puntos x [Y Z].
puntos = nan(n,np,2);

%% 4. RESOLVER EQUILIBRIOS FEM

op = cfg.simulacion;
op.mostrarConsola = false;
op.validar = true;
op.calcularBaseComparativa = false;

simulaciones = cell(n,1);
analisis = cell(n,1);
posturas = cell(n,1);

green = nan(n,1);
jmin = nan(n,1);
jmax = nan(n,1);
energia = nan(n,1);
cumple = false(n,1);

fprintf('\n===== TRAYECTORIA FEM /s/ =====\n');
fprintf('Estados solicitados: %d\n',n);

for k = 1:n

    P = PF;
    P.nombre = sprintf("S2 - Estado %d/%d",k,n);

    % Interpolacion de las consignas, NO de la malla.
    P.puntaYZ = PI.puntaYZ + ...
        a(k)*(PF.puntaYZ-PI.puntaYZ);

    P.dorso(:,2:3) = PI.dorso(:,2:3) + ...
        a(k)*(PF.dorso(:,2:3)-PI.dorso(:,2:3));

    if ~isempty(P.vientre)

        P.vientre(:,2:3) = PI.vientre(:,2:3) + ...
            a(k)*(PF.vientre(:,2:3)-PI.vientre(:,2:3));

    end

    % La postura S2 utiliza angulos libres y curvatura nula.
    % Se conservan los valores de la definicion final.
    P.curvaturaApical = PI.curvaturaApical + ...
        a(k)*(PF.curvaturaApical-PI.curvaturaApical);

    P.curvaturaLaminal = PI.curvaturaLaminal + ...
        a(k)*(PF.curvaturaLaminal-PI.curvaturaLaminal);

    try

        sim = simular_postura_lingual( ...
            sistema.modeloFEM,sistema.lengua0,P,op);

    catch ME

        error(['Fallo FEM en estado %d/%d ', ...
               '(progreso %.4f): %s'], ...
               k,n,u(k),ME.message);

    end

    simulaciones{k} = sim;
    posturas{k} = P;

    green(k) = sim.resumen.GreenMax;
    jmin(k) = sim.resumen.Jmin;
    jmax(k) = sim.resumen.Jmax;

    cumple(k) = ...
        sim.resumen.cumpleCriteriosExploratorios;

    energia(k) = sim.estado.diagnostico.energiaTotal;

    % Coordenadas reales de puntos materiales deformados.
    Q = interp1( ...
        s,sim.estado.nodos(ids,:), ...
        sMarcas,'linear');

    Q(1,:) = sim.estado.puntaYZ;

    puntos(k,:,1) = Q(:,1)';
    puntos(k,:,2) = Q(:,2)';

    % El analisis geometrico puede ser costoso.
    % Por defecto se realiza en ambos extremos.
    if C.analizarCadaEstado || k==1 || k==n

        analisis{k} = analizar_articulacion( ...
            sistema,sim);

    end

    fprintf(['Estado %3d/%d | a=%6.3f | ', ...
             'Green=%7.4f | Jmin=%7.4f | FEM=%d\n'], ...
        k,n,a(k),green(k),jmin(k),cumple(k));

end

%% 5. COMPROBACIONES DE CONTINUIDAD

saltos = zeros(n-1,np);

for j = 1:np

    Y = puntos(:,j,1);
    Z = puntos(:,j,2);

    saltos(:,j) = hypot(diff(Y),diff(Z));

end

maxSalto = max(saltos(:));

if ~all(cumple)

    warning(['Hay %d estados que no cumplen los ', ...
        'criterios FEM exploratorios.'],nnz(~cumple));

end

fprintf('\n===== RESUMEN DE TRAYECTORIA =====\n');

fprintf('Estados FEM: %d\n',n);
fprintf('Estados admisibles: %d/%d\n',nnz(cumple),n);

fprintf('Green maximo en trayectoria: %.5f\n', ...
    max(green));

fprintf('J minimo en trayectoria: %.5f\n', ...
    min(jmin));

fprintf('Mayor avance entre muestras: %.5f mm\n', ...
    maxSalto);

fprintf(['Este salto depende de la discretizacion ', ...
    'y no es una velocidad.\n']);

%% 6. ECUACIONES DE LOS PUNTOS MATERIALES

grado = C.gradoPolinomio;

validateattributes(grado,{'numeric'}, ...
    {'scalar','integer','>=',1,'<=',min(8,n-1)});

coefY = cell(np,1);
coefZ = cell(np,1);

ppY = cell(np,1);
ppZ = cell(np,1);

rmse = zeros(np,2);
errorMax = zeros(np,2);

fprintf('\n===== ECUACIONES PARAMETRICAS =====\n');

for j = 1:np

    y = puntos(:,j,1);
    z = puntos(:,j,2);

    % Aproximacion polinomica compacta.
    coefY{j} = polyfit(u,y,grado);
    coefZ{j} = polyfit(u,z,grado);

    yAjuste = polyval(coefY{j},u);
    zAjuste = polyval(coefZ{j},u);

    rmse(j,1) = sqrt(mean((y-yAjuste).^2));
    rmse(j,2) = sqrt(mean((z-zAjuste).^2));

    errorMax(j,1) = max(abs(y-yAjuste));
    errorMax(j,2) = max(abs(z-zAjuste));

    % Representacion interpolante: pasa por todas
    % las soluciones FEM muestreadas.
    ppY{j} = pchip(u,y);
    ppZ{j} = pchip(u,z);

    fprintf('\n%s (s=%.2f)\n', ...
        nombres{j},sMarcas(j));

    fprintf('Y(u) = %s\n', ...
        expresarPolinomio(coefY{j}));

    fprintf('Z(u) = %s\n', ...
        expresarPolinomio(coefZ{j}));

    fprintf('RMSE = [%.5f %.5f] mm\n', ...
        rmse(j,1),rmse(j,2));

end

%% 7. RESULTADO REUTILIZABLE

tray = struct();

tray.sistema = sistema;
tray.cfg = cfg;

tray.u = u;
tray.avance = a;

tray.posturaInicial = PI;
tray.posturaFinal = PF;

tray.posturas = posturas;
tray.simulaciones = simulaciones;
tray.analisis = analisis;

tray.nombres = nombres;
tray.sMarcas = sMarcas;
tray.puntos = puntos;

tray.green = green;
tray.jmin = jmin;
tray.jmax = jmax;
tray.energia = energia;
tray.cumpleFEM = cumple;

tray.saltos = saltos;
tray.maxSalto = maxSalto;

tray.ecuaciones = struct( ...
    'grado',grado, ...
    'coefY',{coefY}, ...
    'coefZ',{coefZ}, ...
    'ppY',{ppY}, ...
    'ppZ',{ppZ}, ...
    'rmse',rmse, ...
    'errorMax',errorMax);

end

%% FUNCION LOCAL: EXPRESION POLINOMICA

function str = expresarPolinomio(c)

grado = numel(c)-1;
partes = cell(1,numel(c));

for i = 1:numel(c)

    potencia = grado-i+1;

    if potencia==0

        partes{i} = sprintf('%+.6g',c(i));

    elseif potencia==1

        partes{i} = sprintf('%+.6g*u',c(i));

    else

        partes{i} = sprintf('%+.6g*u^%d', ...
            c(i),potencia);

    end

end

str = strjoin(partes,' ');

end
