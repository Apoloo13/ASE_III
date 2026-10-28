
function resultado = ajustar_activaciones_linguales( ...
    modelo,lengua0,regiones,objetivo,opciones)
% AJUSTAR_ACTIVACIONES_LINGUALES
% Control inverso de flexion y curvatura lingual.
%
% CONTROLES:
%   apice  [dorsal ventral]
%   lamina [dorsal ventral]
%   cuerpo [dorsal ventral]
%
% OBJETIVOS ANGULARES (elegir un formato):
%
% A) Flexion relativa:
%   deltaFlexionAL_deg
%   deltaFlexionLC_deg
%   deltaOrientacionCuerpo_deg
%
% B) Orientaciones regionales anteriores:
%   deltaAngulos_deg = [apice lamina cuerpo]
%
% OBJETIVO DE CURVATURA OPCIONAL:
%   deltaCurvaturaFirmada_1mm = [apice lamina cuerpo]
%
% Utilizar NaN para no controlar alguna curvatura.
%
% Todos los objetivos son cambios adicionales
% respecto a la postura sin activacion y con
% la misma posicion de punta.
%
% No requiere Optimization Toolbox.

%% 1. OPCIONES

if nargin < 5 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('Opciones invalidas.');
end

maxIter = leer(opciones,'maxIter',8);
maxActivacion = leer(opciones,'maxActivacion',0.03);
escalaActivacion = leer(opciones,'escalaActivacion',0.02);
pasoFD = leer(opciones,'pasoFD',0.001);
pasoMax = leer(opciones,'pasoMaxNormalizado',0.40);
regularizacion = leer(opciones,'regularizacion',0.02);
maxBusqueda = leer(opciones,'maxBusqueda',10);

pesosAngulares = leer( ...
    opciones,'pesosAngulares',[1 1 1]);

pesosCurvatura = leer( ...
    opciones,'pesosCurvatura',[1 1 1]);

escalaAngular = leer( ...
    opciones,'escalaAngular_deg',1.0);

escalaCurvatura = leer( ...
    opciones,'escalaCurvatura_1mm',0.002);

tolAngular = leer( ...
    opciones,'toleranciaAngular',0.05);

tolCurvatura = leer( ...
    opciones,'toleranciaCurvatura_1mm',0.0002);

opNL = leer(opciones,'opcionesNoLineales', ...
    struct('nPasos',12, ...
           'maxIter',40, ...
           'tolFuerza',1e-9, ...
           'maxBacktrack',24));

opAnalisis = leer(opciones, ...
    'opcionesAnalisisCurvatura',struct());

validateattributes(maxIter,{'numeric'}, ...
    {'scalar','integer','positive','<=',30});

validateattributes(maxActivacion,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',0.10});

validateattributes(escalaActivacion,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(pasoFD,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(pasoMax,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(regularizacion,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(maxBusqueda,{'numeric'}, ...
    {'scalar','integer','positive','<=',30});

validateattributes(pesosAngulares,{'numeric'}, ...
    {'vector','numel',3,'real','finite','positive'});

validateattributes(pesosCurvatura,{'numeric'}, ...
    {'vector','numel',3,'real','finite','positive'});

validateattributes(escalaAngular,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(escalaCurvatura,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(tolAngular,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(tolCurvatura,{'numeric'}, ...
    {'scalar','real','finite','positive'});

if pasoFD >= maxActivacion
    error('pasoFD debe ser menor que maxActivacion.');
end

if ~isstruct(opNL) || ~isscalar(opNL) || ...
        ~isstruct(opAnalisis) || ~isscalar(opAnalisis)
    error('Opciones de solucion invalidas.');
end

pesosAngulares = pesosAngulares(:);
pesosCurvatura = pesosCurvatura(:);

%% 2. OBJETIVOS ANGULARES

if ~isstruct(objetivo) || ...
        ~isscalar(objetivo) || ...
        ~isfield(objetivo,'puntaYZ')
    error('Objetivo incompleto.');
end

puntaYZ = reshape(objetivo.puntaYZ,1,[]);

validateattributes(puntaYZ,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

camposFlexion = {
    'deltaFlexionAL_deg'
    'deltaFlexionLC_deg'
    'deltaOrientacionCuerpo_deg'
};

presentes = cellfun( ...
    @(nombre) isfield(objetivo,nombre), ...
    camposFlexion);

tieneOrientacion = isfield( ...
    objetivo,'deltaAngulos_deg');

if all(presentes) && ~tieneOrientacion

    modoObjetivo = "flexion";

    metaAngular = [
        objetivo.deltaFlexionAL_deg;
        objetivo.deltaFlexionLC_deg;
        objetivo.deltaOrientacionCuerpo_deg
    ];

    nombresAngulares = [
        "Flexion Apice-Lamina"
        "Flexion Lamina-Cuerpo"
        "Orientacion Cuerpo"
    ];

elseif ~any(presentes) && tieneOrientacion

    modoObjetivo = "orientacion";

    metaAngular = objetivo.deltaAngulos_deg(:);

    nombresAngulares = [
        "Orientacion Apice"
        "Orientacion Lamina"
        "Orientacion Cuerpo"
    ];

else

    error('Define un unico formato angular completo.');

end

validateattributes(metaAngular,{'numeric'}, ...
    {'vector','numel',3,'real','finite'});

metaAngular = metaAngular(:);

%% 3. OBJETIVOS OPCIONALES DE CURVATURA

metaCurvatura = leer(objetivo, ...
    'deltaCurvaturaFirmada_1mm',nan(3,1));

if ~isnumeric(metaCurvatura) || ...
        ~isreal(metaCurvatura) || ...
        numel(metaCurvatura) ~= 3 || ...
        any(isinf(metaCurvatura(:)))

    error('Objetivo de curvatura invalido.');

end

metaCurvatura = metaCurvatura(:);

% NaN significa que esa region no tiene objetivo.
mascaraCurvatura = isfinite(metaCurvatura);
indicesCurvatura = find(mascaraCurvatura);

nCurvaturas = numel(indicesCurvatura);

% Vector conjunto de objetivos fisicos.
meta = [
    metaAngular;
    metaCurvatura(indicesCurvatura)
];

% Factores para convertir errores a variables
% adimensionales comparables.
escalas = [
    escalaAngular*ones(3,1);
    escalaCurvatura*ones(nCurvaturas,1)
];

pesos = [
    pesosAngulares;
    pesosCurvatura(indicesCurvatura)
];

factorResidual = pesos./escalas;

%% 4. OBJETIVO FEM DE PUNTA

objetivoFEM = struct();

objetivoFEM.puntaYZ = puntaYZ;
objetivoFEM.modo = 'prescrito';
objetivoFEM.componentes = [true true];

if size(regiones.elementos.pesos,1) ~= ...
        size(modelo.malla.elementos,1)
    error('Malla y regiones incompatibles.');
end

%% 5. CONTROLES NORMALIZADOS

% Orden:
% [ApiceD ApiceV LaminaD LaminaV CuerpoD CuerpoV]

nControles = 6;

x = zeros(nControles,1);

limiteX = maxActivacion/escalaActivacion;
h = pasoFD/escalaActivacion;

mapaCache = [];
nEvaluaciones = 0;

historial = zeros(maxIter,6);
nIteraciones = 0;

sensibilidadFinal = zeros(numel(meta),nControles);

%% 6. POSTURA BASE

inicioTiempo = tic;

base = evaluar(x);
actual = base;

medidasBase = medidas(base);

estadoFinal = "max_iteraciones";

%% 7. OPTIMIZACION INVERSA

for iter = 1:maxIter

    respuesta = medidas(actual)-medidasBase;

    errorFisico = meta-respuesta;

    % Residual adimensional ponderado.
    r = factorResidual.*errorFisico;

    costo = 0.5*(r'*r) + ...
        0.5*regularizacion*(x'*x);

    errorAngular = errorFisico(1:3);

    cumpleAngulos = ...
        norm(pesosAngulares.*errorAngular) <= ...
        tolAngular;

    cumpleCurvatura = true;

    if nCurvaturas > 0

        cumpleCurvatura = all( ...
            abs(errorFisico(4:end)) <= tolCurvatura);

    end

    if cumpleAngulos && cumpleCurvatura

        estadoFinal = "tolerancia_alcanzada";
        break

    end

    %% A. JACOBIANO POR DIFERENCIAS FINITAS

    J = zeros(numel(meta),nControles);

    for j = 1:nControles

        xPrueba = x;

        if x(j)+h <= limiteX

            delta = h;

        else

            delta = -h;

        end

        xPrueba(j) = x(j)+delta;

        prueba = evaluar(xPrueba);

        diferencia = ...
            (medidas(prueba)-medidas(actual))/delta;

        J(:,j) = factorResidual.*diferencia;

    end

    sensibilidadFinal = J;

    %% B. SUBPROBLEMA CUADRATICO

    H = J'*J + ...
        regularizacion*eye(nControles);

    b = J'*r-regularizacion*x;

    dx = resolverPasoAcotado( ...
        H,b,x,limiteX,pasoMax);

    if any(~isfinite(dx))
        error('Direccion de optimizacion invalida.');
    end

    if norm(dx,inf) < 1e-5

        estadoFinal = "estacionario_acotado";
        break

    end

    %% C. BUSQUEDA DE PASO

    aceptado = false;
    beta = 1;

    for intento = 1:maxBusqueda

        candidatoX = min(max( ...
            x+beta*dx,0),limiteX);

        if norm(candidatoX-x,inf) < 1e-9

            beta = beta/2;
            continue

        end

        candidato = evaluar(candidatoX);

        respuestaNueva = ...
            medidas(candidato)-medidasBase;

        errorNuevo = meta-respuestaNueva;

        rNuevo = factorResidual.*errorNuevo;

        costoNuevo = 0.5*(rNuevo'*rNuevo) + ...
            0.5*regularizacion* ...
            (candidatoX'*candidatoX);

        if costoNuevo < costo-1e-12

            aceptado = true;

            x = candidatoX;
            actual = candidato;

            break

        end

        beta = beta/2;

    end

    if ~aceptado

        estadoFinal = "sin_descenso";
        break

    end

    %% D. HISTORIAL

    nIteraciones = nIteraciones+1;

    historial(nIteraciones,:) = [
        iter, ...
        norm(rNuevo), ...
        norm(pesosAngulares.*errorNuevo(1:3)), ...
        costoNuevo, ...
        max(x)*escalaActivacion, ...
        beta
    ];

    fprintf(['Iteracion %d: residual=%.5f, ', ...
        'error angular=%.5f deg, ', ...
        'activacion max=%.5f\n'], ...
        iter,norm(rNuevo), ...
        norm(pesosAngulares.*errorNuevo(1:3)), ...
        max(x)*escalaActivacion);

end

%% 8. CALCULAR RESPUESTAS FINALES

respuesta = medidas(actual)-medidasBase;

respuestaAngular = respuesta(1:3);
errorAngular = metaAngular-respuestaAngular;

% Guardar cambios de curvatura en las tres regiones,
% incluso si una region no fue controlada.
respuestaCurvatura = ...
    actual.curvatura-base.curvatura;

errorCurvatura = nan(3,1);

errorCurvatura(mascaraCurvatura) = ...
    metaCurvatura(mascaraCurvatura) - ...
    respuestaCurvatura(mascaraCurvatura);

residuoFinal = ...
    factorResidual.*(meta-respuesta);

activacionFinal = ...
    vectorActivacion(x*escalaActivacion);

%% 9. SALIDA COMPATIBLE

resultado.activacion = activacionFinal;
resultado.vectorActivaciones = x*escalaActivacion;

resultado.tipoControl = modoObjetivo;
resultado.nombresControl = nombresAngulares;

% Salidas angulares anteriores.
resultado.objetivoAngular = metaAngular;
resultado.respuestaAngular = respuestaAngular;
resultado.errorAngular = errorAngular;

resultado.angulosBase = base.angulos;
resultado.angulosFinales = actual.angulos;

resultado.objetivoControl = metaAngular;
resultado.respuestaControl = respuestaAngular;
resultado.errorControl = errorAngular;

resultado.referenciaControl = ...
    base.angulos;

resultado.controlFinal = actual.angulos;

% Nuevas salidas de curvatura.
resultado.objetivoCurvatura = metaCurvatura;
resultado.respuestaCurvatura = respuestaCurvatura;
resultado.errorCurvatura = errorCurvatura;

resultado.mascaraCurvatura = mascaraCurvatura;

resultado.estado = actual.estado;
resultado.lengua = actual.lengua;
resultado.analisis = actual.analisis;

resultado.estadoBase = base.estado;
resultado.analisisBase = base.analisis;

resultado.sensibilidadFinal = sensibilidadFinal;
resultado.sensibilidadFinalNormalizada = ...
    sensibilidadFinal;

%% 10. DIAGNOSTICO

resultado.diagnostico.estado = estadoFinal;
resultado.diagnostico.iteraciones = nIteraciones;
resultado.diagnostico.evaluacionesFEM = nEvaluaciones;

% Mantener el error angular anterior, en grados.
resultado.diagnostico.errorPonderado = ...
    norm(pesosAngulares.*errorAngular);

resultado.diagnostico.errorAngularPonderado_deg = ...
    norm(pesosAngulares.*errorAngular);

% Nuevo error conjunto adimensional.
resultado.diagnostico.errorObjetivoNormalizado = ...
    norm(residuoFinal);

resultado.diagnostico.activacionMaxima = ...
    max(resultado.vectorActivaciones);

resultado.diagnostico.Jmin = ...
    actual.estado.diagnostico.Jmin;

resultado.diagnostico.tiempoTotal = toc(inicioTiempo);

resultado.historial = array2table( ...
    historial(1:nIteraciones,:), ...
    'VariableNames',{ ...
    'Iteracion', ...
    'ErrorObjetivoNormalizado', ...
    'ErrorAngularPonderado_deg', ...
    'Costo', ...
    'ActivacionMaxima', ...
    'FactorPaso'});

%% FUNCION ANIDADA: EXTRAER MEDIDAS

    function q = medidas(datos)

        q = [
            datos.angulos;
            datos.curvatura(indicesCurvatura)
        ];

    end

%% FUNCION ANIDADA: EVALUAR FEM

    function datos = evaluar(xEvaluacion)

        a = xEvaluacion*escalaActivacion;

        obj = objetivoFEM;
        obj.activacion = vectorActivacion(a);

        estadoLocal = resolver_postura_no_lineal( ...
            modelo,obj,opNL);

        [lenguaLocal,mapaCache] = ...
            reconstruir_lengua_3d( ...
            lengua0,modelo.malla, ...
            estadoLocal,mapaCache);

        analisisLocal = analizar_curvatura_lingual( ...
            lengua0,lenguaLocal,regiones,opAnalisis);

        switch modoObjetivo

            case "flexion"

                ang = analisisLocal.control.vector(:);

            case "orientacion"

                ang = analisisLocal.resumen. ...
                    CambioAngular_deg(:);

        end

        curv = analisisLocal.resumen. ...
            CambioCurvaturaFirmada_1mm(:);

        if any(~isfinite([ang;curv])) || ...
                ~estadoLocal.diagnostico.convergio || ...
                estadoLocal.diagnostico.Jmin <= 0
            error('Evaluacion FEM invalida.');
        end

        nEvaluaciones = nEvaluaciones+1;

        datos.angulos = ang;
        datos.curvatura = curv;

        datos.estado = estadoLocal;
        datos.lengua = lenguaLocal;
        datos.analisis = analisisLocal;

    end

end

%% FUNCION LOCAL: CONVERTIR ACTIVACIONES

function activacion = vectorActivacion(a)

a = a(:);

if numel(a) ~= 6
    error('Se requieren seis activaciones.');
end

activacion.apice = [a(1) a(2)];
activacion.lamina = [a(3) a(4)];
activacion.cuerpo = [a(5) a(6)];

end

%% FUNCION LOCAL: OPTIMIZACION ACOTADA

function dx = resolverPasoAcotado( ...
    H,b,x,limiteX,pasoMax)

% Subproblema:
% min 0.5*dx'*H*dx - b'*dx
%
% Sujeto a:
% 0 <= x+dx <= limiteX
% |dx| <= pasoMax
%
% Descenso por coordenadas, sin toolboxes.

n = numel(x);
dx = zeros(n,1);

inferior = max( ...
    -x,-pasoMax*ones(n,1));

superior = min( ...
    limiteX-x,pasoMax*ones(n,1));

if any(inferior > superior)
    error('Limites de activacion incompatibles.');
end

for barrido = 1:500

    anterior = dx;

    for j = 1:n

        if H(j,j) <= 0
            error('Hessiana cuadratica invalida.');
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

%% FUNCION LOCAL: OPCIONES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
