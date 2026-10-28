
function varargout = regularizar_flexion_lingual(accion,varargin)
% REGULARIZAR_FLEXION_LINGUAL
%
% Regularizacion no lineal de flexion del contorno sagital.
%
% USO:
%
% reg = regularizar_flexion_lingual( ...
%     'preparar',modelo,opciones);
%
% [energia,f,K,diagnostico] = ...
%     regularizar_flexion_lingual( ...
%     'evaluar',reg,u,calcularTangente);
%
% Formulacion:
%   E = 0.5*sum((B_i/ell_i)*deltaTheta_i^2)
%
% deltaTheta: cambio del angulo entre segmentos
% consecutivos respecto al reposo.
%
% Incluye gradiente y Hessiana exactos de la
% energia angular, salvo discontinuidad de rama
% en +/-pi, que se excluye por seguridad.
%
% La energia es invariante ante traslaciones y
% rotaciones rigidas del contorno.
%
% Unidades: mm, N, N/mm^2.
% No requiere toolboxes adicionales.

accion = lower(string(accion));

switch accion

    case "preparar"

        modelo = varargin{1};

        if numel(varargin) >= 2
            opciones = varargin{2};
        else
            opciones = struct();
        end

        varargout{1} = preparar(modelo,opciones);

    case "evaluar"

        reg = varargin{1};
        u = varargin{2};

        if numel(varargin) >= 3
            calcularTangente = varargin{3};
        else
            calcularTangente = true;
        end

        [energia,f,K,diagnostico] = ...
            evaluar(reg,u,calcularTangente);

        varargout = {energia,f,K,diagnostico};

    otherwise

        error('Operacion desconocida.');

end

end

%% =====================================================
% PREPARACION DEL REGULARIZADOR
% ======================================================

function reg = preparar(modelo,opciones)

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('Opciones de suavidad invalidas.');
end

if ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo,'material')
    error('Modelo FEM invalido.');
end

%% 1. PARAMETROS

activar = leer(opciones,'activar',false);

factorDorsal = leer( ...
    opciones,'factorDorsal',0.03);

factorVentral = leer( ...
    opciones,'factorVentral',0.03);

inicio = leer(opciones,'inicio',0.02);
fin = leer(opciones,'fin',0.895);

ancho = leer( ...
    opciones,'anchoTransicion',0.04);

Lref = leer( ...
    opciones,'longitudReferencia',2.0);

validateattributes(activar,{'numeric','logical'}, ...
    {'scalar','binary'});

validateattributes(factorDorsal,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(factorVentral,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(Lref,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(inicio,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<',1});

validateattributes(fin,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',1});

validateattributes(ancho,{'numeric'}, ...
    {'scalar','real','finite','positive'});

if inicio >= fin || 2*ancho >= fin-inicio
    error('Intervalo de regularizacion invalido.');
end

activar = logical(activar);

%% 2. GEOMETRIA DE REFERENCIA

malla = modelo.malla;

X = double(malla.nodos);

N = size(X,1);
nGDL = 2*N;

if size(X,2) ~= 2 || any(~isfinite(X(:)))
    error('Nodos FEM invalidos.');
end

if ~isfield(malla,'frontera') || ...
        ~isfield(malla.frontera,'superior') || ...
        ~isfield(malla.frontera,'inferior')
    error('Faltan fronteras de la malla.');
end

idDorsal = malla.frontera.superior(:);
idVentral = malla.frontera.inferior(:);

contornos = {idDorsal,idVentral};

idPunta = malla.seguimiento.puntaIndice;

if idDorsal(end) ~= idPunta || ...
        idVentral(end) ~= idPunta
    error('La punta no coincide con las fronteras.');
end

yPunta = X(idPunta,1);
yPosterior = min(X(:,1));

longitud = yPunta-yPosterior;

if longitud <= 0
    error('Longitud lingual invalida.');
end

%% 3. RIGIDEZ DE FLEXION

E = modelo.material.E;
espesor = modelo.material.espesor;

validateattributes(E,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(espesor,{'numeric'}, ...
    {'scalar','real','finite','positive'});

% Rigidez de flexion de referencia.
%
% E [N/mm^2] * t [mm] * Lref^3 [mm^3]
% = N*mm^2

Breferencia = E*espesor*Lref^3;

factores = [factorDorsal factorVentral];

%% 4. CONSTRUIR TRIPLETAS

idsTodos = zeros(0,3);
angulosRef = zeros(0,1);
longitudes = zeros(0,1);
pesosZona = zeros(0,1);
rigideces = zeros(0,1);
regiones = zeros(0,1);
posicionesS = zeros(0,1);

for region = 1:2

    ids = contornos{region};

    if any(ids < 1) || any(ids > N) || ...
            numel(unique(ids)) ~= numel(ids)
        error('Contorno FEM invalido.');
    end

    for i = 2:numel(ids)-1

        triple = ids(i-1:i+1);

        p = X(triple,:);

        v1 = p(2,:)-p(1,:);
        v2 = p(3,:)-p(2,:);

        h1 = norm(v1);
        h2 = norm(v2);

        if min(h1,h2) <= 1e-8
            error('Arista de referencia degenerada.');
        end

        ell = 0.5*(h1+h2);

        s = (yPunta-p(2,1))/longitud;

        % Transiciones C1 para evitar saltos de
        % rigidez en los limites funcionales.
        pesoEntrada = suave((s-inicio)/ancho);
        pesoSalida = suave((fin-s)/ancho);

        peso = pesoEntrada*pesoSalida;

        if peso <= 1e-12
            continue
        end

        theta1 = atan2(v1(2),v1(1));
        theta2 = atan2(v2(2),v2(1));

        theta0 = envolver(theta2-theta1);

        % Rigidez local N*mm/rad^2.
        kLocal = ...
            Breferencia*factores(region)*peso/ell;

        if ~activar
            kLocal = 0;
        end

        idsTodos(end+1,:) = triple; %#ok<AGROW>

        angulosRef(end+1,1) = theta0; %#ok<AGROW>
        longitudes(end+1,1) = ell; %#ok<AGROW>
        pesosZona(end+1,1) = peso; %#ok<AGROW>

        rigideces(end+1,1) = kLocal; %#ok<AGROW>
        regiones(end+1,1) = region; %#ok<AGROW>
        posicionesS(end+1,1) = s; %#ok<AGROW>

    end

end

%% 5. ESTRUCTURA PRECALCULADA

reg.X = X;

reg.nGDL = nGDL;
reg.nTripletas = size(idsTodos,1);

reg.ids = idsTodos;
reg.thetaReferencia = angulosRef;

reg.longitudes = longitudes;
reg.pesosZona = pesosZona;
reg.rigideces = rigideces;

reg.regiones = regiones;
reg.posicionesS = posicionesS;

reg.activo = activar;

reg.factores = factores;
reg.Breferencia = Breferencia;

reg.parametros = opciones;

end

%% =====================================================
% EVALUACION DE ENERGIA, FUERZAS Y TANGENTE
% ======================================================

function [energia,f,K,diagnostico] = ...
    evaluar(reg,u,calcularTangente)

nGDL = reg.nGDL;
n = reg.nTripletas;

validateattributes(u,{'numeric'}, ...
    {'vector','numel',nGDL,'real','finite'});

u = u(:);

x = reg.X+reshape(u,2,[])';

energia = 0;
f = zeros(nGDL,1);

K = sparse(nGDL,nGDL);

diagnostico.valido = true;

diagnostico.energiaDorsal = 0;
diagnostico.energiaVentral = 0;

diagnostico.maxCambioAngular_deg = 0;

diagnostico.rmsCambioCurvatura = 0;
diagnostico.rmsCambioCurvaturaDorsal = 0;
diagnostico.rmsCambioCurvaturaVentral = 0;

diagnostico.numeroTripletas = n;

if n == 0
    return
end

%% 1. OPERADORES LOCALES

I2 = eye(2);
O2 = zeros(2);

% v1 = p2-p1
% v2 = p3-p2

B1 = [-I2 I2 O2];
B2 = [O2 -I2 I2];

% Ensamblaje disperso.
if calcularTangente

    filas = zeros(36*n,1);
    columnas = zeros(36*n,1);
    valores = zeros(36*n,1);

    contador = 0;

end

% Acumuladores del diagnostico.
numerador = zeros(2,1);
denominador = zeros(2,1);

maxAngulo = 0;

%% 2. RECORRER TRIPLETAS

for e = 1:n

    ids = reg.ids(e,:);
    p = x(ids,:);

    v1 = (p(2,:)-p(1,:))';
    v2 = (p(3,:)-p(2,:))';

    L1 = norm(v1);
    L2 = norm(v2);

    % No permitir segmentos colapsados.
    if min(L1,L2) <= 1e-6

        diagnostico.valido = false;
        energia = inf;
        return

    end

    theta1 = atan2(v1(2),v1(1));
    theta2 = atan2(v2(2),v2(1));

    thetaActual = envolver(theta2-theta1);

    delta = envolver( ...
        thetaActual-reg.thetaReferencia(e));

    % Evitar la discontinuidad de rama en +/-pi.
    if abs(delta) >= pi-1e-3

        diagnostico.valido = false;
        energia = inf;
        return

    end

    ell = reg.longitudes(e);
    peso = reg.pesosZona(e);

    region = reg.regiones(e);

    % Medida aproximada del cambio de curvatura:
    % delta angulo / longitud local de referencia.
    cambioCurvatura = delta/ell;

    pesoMetrica = ell*peso;

    numerador(region) = ...
        numerador(region) + ...
        pesoMetrica*cambioCurvatura^2;

    denominador(region) = ...
        denominador(region)+pesoMetrica;

    maxAngulo = max(maxAngulo,abs(delta));

    k = reg.rigideces(e);

    if k == 0
        continue
    end

    %% A. ENERGIA

    Ee = 0.5*k*delta^2;

    energia = energia+Ee;

    if region == 1
        diagnostico.energiaDorsal = ...
            diagnostico.energiaDorsal+Ee;
    else
        diagnostico.energiaVentral = ...
            diagnostico.energiaVentral+Ee;
    end

    %% B. GRADIENTE ANGULAR

    [g1,H1] = derivadasAngulo(v1);
    [g2,H2] = derivadasAngulo(v2);

    % Gradiente de:
    % theta2-theta1.

    g = B2'*g2-B1'*g1;

    %% C. FUERZAS INTERNAS

    fe = k*delta*g;

    gdl = reshape([ ...
        2*ids-1;
        2*ids],1,[]);

    f(gdl) = f(gdl)+fe;

    %% D. HESSIANA CONSISTENTE

    if calcularTangente

        H = B2'*H2*B2-B1'*H1*B1;

        Ke = k*(g*g'+delta*H);

        Ke = (Ke+Ke')/2;

        [ii,jj] = ndgrid(gdl,gdl);

        rango = contador+(1:36);

        filas(rango) = ii(:);
        columnas(rango) = jj(:);
        valores(rango) = Ke(:);

        contador = contador+36;

    end

end

%% 3. ENSAMBLAJE FINAL

if calcularTangente && contador > 0

    K = sparse( ...
        filas(1:contador), ...
        columnas(1:contador), ...
        valores(1:contador), ...
        nGDL,nGDL);

    K = (K+K')/2;

end

%% 4. DIAGNOSTICO

rmsRegional = sqrt( ...
    numerador./max(denominador,eps));

diagnostico.rmsCambioCurvaturaDorsal = ...
    rmsRegional(1);

diagnostico.rmsCambioCurvaturaVentral = ...
    rmsRegional(2);

diagnostico.rmsCambioCurvatura = sqrt( ...
    sum(numerador)/max(sum(denominador),eps));

diagnostico.maxCambioAngular_deg = ...
    rad2deg(maxAngulo);

diagnostico.energia = energia;

end

%% =====================================================
% DERIVADAS DE atan2(y,x)
% ======================================================

function [g,H] = derivadasAngulo(v)

a = v(1);
b = v(2);

r2 = a^2+b^2;

g = [
    -b
     a
]/r2;

H = [
    2*a*b,    b^2-a^2;
    b^2-a^2, -2*a*b
]/r2^2;

end

%% =====================================================
% FUNCIONES AUXILIARES
% ======================================================

function q = suave(x)

x = max(0,min(1,x));

q = x.^2.*(3-2*x);

end

function theta = envolver(theta)

theta = atan2(sin(theta),cos(theta));

end

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
