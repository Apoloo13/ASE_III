
function resultado = resolver_postura_guiada( ...
    modelo,pose,opciones)
% RESOLVER_POSTURA_GUIADA
% Ajusta parches contractiles a objetivos materiales.
%
% La punta es prescrita.
% Los otros objetivos se aproximan mediante FEM.
%
% Utiliza:
%   resolver_postura_no_lineal
%   calcular_activacion_lingual (modo parches)
%
% Metodo:
%   Diferencias finitas
%   Minimos cuadrados regularizados
%   Paso acotado y busqueda de descenso
%
% No necesita Optimization Toolbox.
% No modifica las matrices ni la malla FEM.

%% 1. OPCIONES

if nargin < 3 || isempty(opciones)
    opciones = struct();
end

maxIter = leer(opciones,'maxIter',5);
maxAct = leer(opciones,'maxActivacion',0.04);
pasoFD = leer(opciones,'pasoFD',0.002);

regularizacion = leer( ...
    opciones,'regularizacion',0.02);

pasoMax = leer( ...
    opciones,'pasoMaxNormalizado',0.35);

maxBusqueda = leer(opciones,'maxBusqueda',8);

escalaPos = leer( ...
    opciones,'escalaPosicion_mm',1.0);

escalaAng = leer( ...
    opciones,'escalaAngulo_deg',2.0);

tolerancia = leer( ...
    opciones,'toleranciaNormalizada',0.05);

opNL = leer(opciones,'opcionesNoLineales', ...
    struct('nPasos',16, ...
           'maxIter',40, ...
           'tolFuerza',1e-9, ...
           'maxBacktrack',24));

% Cuatro estaciones longitudinales.
% Dos capas por estacion.
centros = leer(opciones,'centros', ...
    [0.05 0.05 0.18 0.18 ...
     0.38 0.38 0.62 0.62]);

radios = leer(opciones,'radios', ...
    [0.07 0.07 0.12 0.12 ...
     0.18 0.18 0.20 0.20]);

capas = [ ...
    "dorsal","ventral", ...   % Estacion 1: Apice
    "dorsal","ventral", ...   % Estacion 2: Lamina
    "dorsal","ventral", ...   % Estacion 3: Cuerpo anterior
    "dorsal","ventral"];     % Estacion 4: Cuerpo medio

nControl = 8;

% Verificacion de consistencia.
if numel(centros) ~= nControl || ...
        numel(radios) ~= nControl || ...
        numel(capas) ~= nControl

    error('Configuracion de parches incompatible.');

end
validateattributes(maxIter,{'numeric'}, ...
    {'scalar','integer','positive','<=',30});

validateattributes(maxAct,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',0.10});

validateattributes(pasoFD,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(regularizacion,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(pasoMax,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(maxBusqueda,{'numeric'}, ...
    {'scalar','integer','positive'});

validateattributes(escalaPos,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(escalaAng,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(tolerancia,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(centros,{'numeric'}, ...
    {'vector','numel',8,'real','finite', ...
    '>=',0,'<=',1});

validateattributes(radios,{'numeric'}, ...
    {'vector','numel',8,'real','finite', ...
    '>',0,'<=',0.30});

if pasoFD >= maxAct
    error('pasoFD debe ser menor que maxAct.');
end

centros = centros(:)';
radios = radios(:)';

nControl = 8;

%% 2. PREPARAR OBJETIVO FEM

objFEM = struct();

objFEM.puntaYZ = pose.puntaYZ;
objFEM.modo = 'prescrito';
objFEM.componentes = [true true];

%% 3. VECTOR DE METAS NORMALIZADAS

meta = zeros(0,1);

for i = 1:pose.numeroObjetivos

    p = pose.objetivos(i);

    for componente = 1:2

        if isfinite(p.meta(componente))

            meta(end+1,1) = ...
                sqrt(p.peso)* ...
                p.meta(componente)/escalaPos;

        end

    end

end

usarAngulo = isfinite( ...
    pose.apice.deltaAngulo_deg);

if usarAngulo

    meta(end+1,1) = ...
        sqrt(pose.apice.peso)* ...
        pose.apice.deltaAngulo_deg/escalaAng;

end

%% 4. POSTURA BASE

x = zeros(nControl,1);

nEvaluaciones = 0;

inicioTiempo = tic;

base = evaluar(x);
actual = base;

anguloBase = base.anguloApice;

historial = zeros(maxIter,4);
nAceptadas = 0;

estadoOpt = "max_iteraciones";

%% 5. OPTIMIZACION

for iter = 1:maxIter

    r = meta-medir(actual);

    costo = 0.5*(r'*r) + ...
        0.5*regularizacion*(x'*x);

    if norm(r) <= tolerancia

        estadoOpt = "tolerancia_alcanzada";
        break

    end

    %% A. SENSIBILIDAD

    J = zeros(numel(r),nControl);

    h = pasoFD/maxAct;

    for j = 1:nControl

        xp = x;

        if x(j)+h <= 1
            d = h;
        else
            d = -h;
        end

        xp(j) = x(j)+d;

        prueba = evaluar(xp);

        J(:,j) = ...
            (medir(prueba)-medir(actual))/d;

    end

    %% B. PASO ACOTADO

    H = J'*J + ...
        regularizacion*eye(nControl);

    b = J'*r-regularizacion*x;

    dx = pasoAcotado(H,b,x,pasoMax);

    if norm(dx,inf) < 1e-6

        estadoOpt = "estacionario_acotado";
        break

    end

    %% C. BUSQUEDA DE PASO

    beta = 1;
    aceptado = false;

    for intento = 1:maxBusqueda

        xc = min(max(x+beta*dx,0),1);

        if norm(xc-x,inf) < 1e-9
            beta = beta/2;
            continue
        end

        candidato = evaluar(xc);

        rc = meta-medir(candidato);

        costoC = 0.5*(rc'*rc) + ...
            0.5*regularizacion*(xc'*xc);

        if costoC < costo-1e-12

            x = xc;
            actual = candidato;

            aceptado = true;
            break

        end

        beta = beta/2;

    end

    if ~aceptado

        estadoOpt = "sin_descenso";
        break

    end

    nAceptadas = nAceptadas+1;

    historial(nAceptadas,:) = [
        iter,norm(rc),costoC,beta
    ];

    fprintf(['Iteracion %d: error norm=%.5f, ', ...
        'activacion max=%.5f\n'], ...
        iter,norm(rc),max(x)*maxAct);

end

%% 6. DIAGNOSTICO FINAL

puntosBase = base.puntos;
puntosFinal = actual.puntos;

erroresPuntos = nan(pose.numeroObjetivos,2);

for i = 1:pose.numeroObjetivos

    metaPunto = pose.objetivos(i).meta;

    for componente = 1:2

        if isfinite(metaPunto(componente))

            erroresPuntos(i,componente) = ...
                metaPunto(componente)- ...
                puntosFinal(i,componente);

        end

    end

end

deltaAngulo = envolver180( ...
    actual.anguloApice-anguloBase);

if usarAngulo

    errorAngulo = ...
        pose.apice.deltaAngulo_deg-deltaAngulo;

else

    errorAngulo = NaN;

end

%% 7. SALIDA

resultado.pose = pose;

resultado.estadoBase = base.estado;
resultado.estado = actual.estado;

resultado.puntosBase = puntosBase;
resultado.puntosFinal = puntosFinal;
resultado.erroresPuntos = erroresPuntos;

resultado.anguloApiceBase_deg = anguloBase;

resultado.anguloApiceFinal_deg = ...
    actual.anguloApice;

resultado.deltaAnguloApice_deg = deltaAngulo;
resultado.errorAnguloApice_deg = errorAngulo;

resultado.activaciones = x*maxAct;

resultado.parches = crearParches( ...
    resultado.activaciones);

resultado.diagnostico.estado = estadoOpt;
resultado.diagnostico.iteraciones = nAceptadas;
resultado.diagnostico.evaluacionesFEM = nEvaluaciones;

resultado.diagnostico.errorNormalizado = ...
    norm(meta-medir(actual));

resultado.diagnostico.Jmin = ...
    actual.estado.diagnostico.Jmin;

resultado.diagnostico.tiempo_s = toc(inicioTiempo);

resultado.historial = array2table( ...
    historial(1:nAceptadas,:), ...
    'VariableNames',{ ...
    'Iteracion','ErrorNormalizado', ...
    'Costo','FactorPaso'});

%% FUNCION ANIDADA: SIMULAR

    function datos = evaluar(xActual)

        intensidad = xActual(:)*maxAct;

        parches = crearParches(intensidad);

        obj = objFEM;

        if isempty(parches)

            obj.activacion = struct( ...
                'apice',[0 0], ...
                'lamina',[0 0], ...
                'cuerpo',[0 0]);

        else

            obj.activacion = struct( ...
                'parches',parches);

        end

        estado = resolver_postura_no_lineal( ...
            modelo,obj,opNL);

        if ~estado.diagnostico.convergio || ...
                estado.diagnostico.Jmin <= 0

            error(['El FEM no converge o presenta ', ...
                'elementos invertidos.']);

        end

        puntos = zeros(pose.numeroObjetivos,2);

        for ii = 1:pose.numeroObjetivos

            ancla = pose.objetivos(ii);

            puntos(ii,:) = ...
                ancla.coef*estado.nodos(ancla.ids,:);

        end

        a = pose.apice.anterior;
        p = pose.apice.posterior;

        pa = a.coef*estado.nodos(a.ids,:);
        pp = p.coef*estado.nodos(p.ids,:);

        v = pa-pp;

        theta = atan2d(v(2),v(1));

        datos.estado = estado;
        datos.puntos = puntos;
        datos.anguloApice = theta;

        nEvaluaciones = nEvaluaciones+1;

    end

%% FUNCION ANIDADA: MEDICIONES

    function q = medir(datos)

        q = zeros(0,1);

        for ii = 1:pose.numeroObjetivos

            p = pose.objetivos(ii);

            for componente = 1:2

                if isfinite(p.meta(componente))

                    q(end+1,1) = ...
                        sqrt(p.peso)* ...
                        datos.puntos(ii,componente)/ ...
                        escalaPos;

                end

            end

        end

        if usarAngulo

            cambio = envolver180( ...
                datos.anguloApice-anguloBase);

            q(end+1,1) = ...
                sqrt(pose.apice.peso)* ...
                cambio/escalaAng;

        end

    end

%% FUNCION ANIDADA: GENERAR PARCHES

    function parches = crearParches(intensidad)

        ids = find(intensidad > 1e-10);

        parches = repmat(struct( ...
            'centro',0, ...
            'radio',0, ...
            'capa',"dorsal", ...
            'intensidad',0),1,numel(ids));

        for kk = 1:numel(ids)

            j = ids(kk);

            parches(kk).centro = centros(j);
            parches(kk).radio = radios(j);
            parches(kk).capa = capas(j);

            parches(kk).intensidad = intensidad(j);

        end

    end

end

%% FUNCION LOCAL: PASO CUADRATICO ACOTADO

function dx = pasoAcotado(H,b,x,pasoMax)

n = numel(x);

dx = zeros(n,1);

inferior = max(-x,-pasoMax);
superior = min(1-x,pasoMax);

for barrido = 1:400

    anterior = dx;

    for j = 1:n

        if H(j,j) <= 0
            error('Hessiana invalida.');
        end

        gradiente = H(j,:)*dx-b(j);

        nuevo = dx(j)-gradiente/H(j,j);

        dx(j) = min(max( ...
            nuevo,inferior(j)),superior(j));

    end

    if norm(dx-anterior,inf) < 1e-9
        break
    end

end

end

%% FUNCIONES LOCALES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end

function a = envolver180(a)

a = mod(a+180,360)-180;

end
