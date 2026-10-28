
function varargout = controlar_forma_lingual(accion,varargin)
% CONTROLAR_FORMA_LINGUAL
%
% Control energetico de curvatura dorsal y orientacion
% laminal para el FEM geometrically no lineal.
%
% USO:
%
% forma = controlar_forma_lingual( ...
%     'preparar',modelo,config);
%
% [E,f,K,valido] = controlar_forma_lingual( ...
%     'evaluar',forma,u,alpha,true);
%
% Curvaturas: cambio respecto a reposo, en 1/mm.
% Angulo laminal: cambio respecto a reposo, en grados.
%
% Fuerzas = gradiente exacto de la energia.
% Tangente = aproximacion Gauss-Newton simetrica.
%
% No incluye contacto ni autocolision.

switch lower(string(accion))

    case "preparar"
        varargout = {preparar(varargin{:})};

    case "evaluar"
        [E,f,K,valido] = evaluar(varargin{:});
        varargout = {E,f,K,valido};

    otherwise
        error('Accion desconocida.');

end

end

%% =====================================================
% PREPARACION DE REGIONES
% ======================================================

function forma = preparar(modelo,cfg)

if nargin < 2 || isempty(cfg)
    cfg = struct();
end

malla = modelo.malla;
X = double(malla.nodos);

N = size(X,1);

% Contorno superior ordenado desde punta a posterior.
ids = flipud(malla.frontera.superior(:));

indicePunta = malla.seguimiento.puntaIndice;

if ids(1) ~= indicePunta
    error('Orden inesperado de la frontera dorsal.');
end

yPunta = X(indicePunta,1);
L = yPunta-min(X(:,1));

s = (yPunta-X(ids,1))/L;

if any(diff(s) <= 0)
    error('Coordenada longitudinal no monotona.');
end

% Parametros funcionales.
kappaA = leer(cfg,'curvaturaApical',0);
kappaL = leer(cfg,'curvaturaLaminal',0);
anguloL = leer(cfg,'anguloLamina',NaN);

factorCurv = leer(cfg, ...
    'factorRigidezCurvatura',0.20);

factorAng = leer(cfg, ...
    'factorRigidezAngularLamina',0.15);

Lref = leer(cfg,'longitudReferencia',3.0);

validateattributes(kappaA,{'numeric'}, ...
    {'scalar','real','finite'});

validateattributes(kappaL,{'numeric'}, ...
    {'scalar','real','finite'});

validateattributes(factorCurv,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(factorAng,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(Lref,{'numeric'}, ...
    {'scalar','real','finite','positive'});

if ~isscalar(anguloL) || ...
        ~isnumeric(anguloL) || ...
        ~isreal(anguloL) || isinf(anguloL)
    error('anguloLamina invalido.');
end

% Escala energetica:
% E [N/mm^2], espesor [mm], Lref [mm].
% E*espesor*Lref^2 -> N*mm.

escala = modelo.material.E * ...
    modelo.material.espesor * Lref^2;

%% 1. CONTROL DE CURVATURA

centros = (2:numel(ids)-1)';

sCentro = s(centros);

% Regiones experimentales.
% La zona posterior comienza en s=0.895,
% pero no se controla directamente aqui.

wA = ventana(sCentro,0.02,0.12,0.02);
wL = ventana(sCentro,0.12,0.32,0.03);

tripletas = [ ...
    ids(centros-1), ...
    ids(centros), ...
    ids(centros+1)];

nTripletas = size(tripletas,1);

theta0 = zeros(nTripletas,1);
longitudes = zeros(nTripletas,1);

for j = 1:nTripletas

    p = X(tripletas(j,:),:);

    e1 = p(2,:)-p(1,:);
    e2 = p(3,:)-p(2,:);

    l1 = norm(e1);
    l2 = norm(e2);

    if min(l1,l2) <= 1e-6
        error('Segmento dorsal degenerado.');
    end

    longitudes(j) = 0.5*(l1+l2);

    theta0(j) = atan2( ...
        cruz2D(e1,e2),dot(e1,e2));

end

% Distribucion normalizada de rigidez.
pesos = zeros(nTripletas,1);

if kappaA ~= 0 && factorCurv > 0

    pA = wA.*longitudes;

    if sum(pA) <= 0
        error('Region apical sin soporte.');
    end

    pesos = pesos+pA/sum(pA);

end

if kappaL ~= 0 && factorCurv > 0

    pL = wL.*longitudes;

    if sum(pL) <= 0
        error('Region laminal sin soporte.');
    end

    pesos = pesos+pL/sum(pL);

end

% Giro adicional deseado entre segmentos.
% Delta theta = Delta kappa * longitud de referencia.

deltaTheta = ...
    (kappaA*wA+kappaL*wL).*longitudes;

mascara = pesos > 1e-12;

curv.ids = tripletas(mascara,:);
curv.theta0 = theta0(mascara);
curv.deltaTheta = deltaTheta(mascara);
curv.pesos = pesos(mascara);

curv.rigidez = escala*factorCurv;

%% 2. CONTROL DE ORIENTACION LAMINAL

lamina = struct( ...
    'activar',false, ...
    'ids',[], ...
    'coef',[], ...
    'angulo0',0, ...
    'deltaAngulo',0, ...
    'rigidez',0);

if ~isnan(anguloL) && factorAng > 0

    % Dos posiciones materiales sobre el dorso.
    sAnterior = 0.16;
    sPosterior = 0.29;

    [idsA,cA] = interpolarMaterial( ...
        s,ids,sAnterior);

    [idsP,cP] = interpolarMaterial( ...
        s,ids,sPosterior);

    idsCombinados = [idsA;idsP];
    coefCombinados = [cA;-cP];

    [idsUnicos,~,ic] = unique(idsCombinados);

    coef = accumarray( ...
        ic,coefCombinados, ...
        [numel(idsUnicos),1]);

    vector0 = coef'*X(idsUnicos,:);

    if norm(vector0) < 1e-6
        error('Orientacion laminal degenerada.');
    end

    lamina.activar = true;
    lamina.ids = idsUnicos;
    lamina.coef = coef;

    lamina.angulo0 = ...
        atan2(vector0(2),vector0(1));

    lamina.deltaAngulo = deg2rad(anguloL);

    lamina.rigidez = escala*factorAng;

end

%% 3. GUARDAR MODELO

forma.X = X;
forma.nGDL = 2*N;

forma.curvatura = curv;
forma.lamina = lamina;

forma.activo = ...
    ~isempty(curv.pesos) || lamina.activar;

forma.configuracion = cfg;

end

%% =====================================================
% EVALUACION EN CONFIGURACION DEFORMADA
% ======================================================

function [E,f,K,valido] = evaluar( ...
    forma,u,alpha,calcularTangente)

nGDL = forma.nGDL;

E = 0;
f = zeros(nGDL,1);
K = sparse(nGDL,nGDL);

valido = true;

if ~forma.activo
    return
end

x = forma.X+reshape(u,2,[])';

%% 1. ENERGIA DE CURVATURA

C = forma.curvatura;

for j = 1:numel(C.pesos)

    ids = C.ids(j,:);
    p = x(ids,:);

    e1 = p(2,:)-p(1,:);
    e2 = p(3,:)-p(2,:);

    n1 = dot(e1,e1);
    n2 = dot(e2,e2);

    if min(n1,n2) < 1e-10

        valido = false;
        E = inf;
        return

    end

    theta = atan2( ...
        cruz2D(e1,e2),dot(e1,e2));

    thetaDeseado = C.theta0(j) + ...
        alpha*C.deltaTheta(j);

    r = envolver(theta-thetaDeseado);

    k = C.rigidez*C.pesos(j);

    E = E+0.5*k*r^2;

    if k == 0
        continue
    end

    % Gradiente del angulo de cada segmento.
    g1 = [-e1(2);e1(1)]/n1;
    g2 = [-e2(2);e2(1)]/n2;

    % Gradiente de giro respecto a tres nodos:
    % [Y1 Z1 Y2 Z2 Y3 Z3].
    g = [g1;-g1-g2;g2];

    gdl = reshape( ...
        [2*ids-1;2*ids],1,[]);

    f(gdl) = f(gdl)+k*r*g;

    if calcularTangente

        % Aproximacion Gauss-Newton.
        K(gdl,gdl) = K(gdl,gdl)+k*(g*g');

    end

end

%% 2. ENERGIA DE ORIENTACION LAMINAL

A = forma.lamina;

if A.activar

    ids = A.ids;
    coef = A.coef;

    v = coef'*x(ids,:);

    norma2 = dot(v,v);

    if norma2 < 1e-10

        valido = false;
        E = inf;
        return

    end

    angulo = atan2(v(2),v(1));

    objetivo = A.angulo0 + ...
        alpha*A.deltaAngulo;

    r = envolver(angulo-objetivo);

    k = A.rigidez;

    E = E+0.5*k*r^2;

    % Gradiente de la orientacion.
    gv = [-v(2);v(1)]/norma2;

    gMat = coef*gv';

    g = reshape(gMat',[],1);

    gdl = reshape( ...
        [2*ids'-1;2*ids'],1,[]);

    f(gdl) = f(gdl)+k*r*g;

    if calcularTangente

        K(gdl,gdl) = ...
            K(gdl,gdl)+k*(g*g');

    end

end

end

%% =====================================================
% FUNCIONES AUXILIARES
% ======================================================

function w = ventana(s,a,b,transicion)

entrada = suave( ...
    (s-(a-transicion))/(2*transicion));

salida = suave( ...
    ((b+transicion)-s)/(2*transicion));

w = entrada.*salida;

end

function q = suave(x)

x = max(0,min(1,x));
q = x.^2.*(3-2*x);

end

function [idsLocal,coef] = ...
    interpolarMaterial(s,ids,sObjetivo)

j = find(s <= sObjetivo,1,'last');

if isempty(j) || j >= numel(s)
    error('Posicion material fuera de intervalo.');
end

t = (sObjetivo-s(j))/(s(j+1)-s(j));

idsLocal = ids(j:j+1);
coef = [1-t;t];

end

function z = cruz2D(a,b)

z = a(1)*b(2)-a(2)*b(1);

end

function a = envolver(a)

a = atan2(sin(a),cos(a));

end

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
