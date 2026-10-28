

function modelo = configurar_biomecanica(malla, opciones)
% CONFIGURAR_BIOMECANICA
% FEM 2D de elasticidad lineal en deformacion plana.
%
% Permite:
%   - Material uniforme o rigidez regional continua.
%   - Anclaje elastico posterior.
%   - Soporte elastico ventral posterior opcional.
%
% Los parametros regionales son experimentales.
% No representan musculos anatomicos identificados.
%
% Unidades: mm, N, N/mm^2.

%% 1. OPCIONES

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

E = opcion(opciones,'E',0.005);
nu = opcion(opciones,'nu',0.35);
t = opcion(opciones,'espesor',1);

factorAnclaje = opcion(opciones,'factorAnclaje',1);
Lref = opcion(opciones,'longitudReferenciaAnclaje',5);


% Configuracion espacial del anclaje posterior.
%
% 'borde': comportamiento original.
% 'banda': distribucion gradual hacia el cuerpo.

modoAnclajePosterior = lower(string( ...
    opcion(opciones,'modoAnclajePosterior','borde')));

% Extension longitudinal de la banda (mm).
anchoBandaPosterior = opcion( ...
    opciones,'anchoBandaPosterior',5.0);

if ~isscalar(modoAnclajePosterior) || ...
        ~ismember(modoAnclajePosterior,["borde","banda"])
    error('Modo de anclaje posterior invalido.');
end

validateattributes(anchoBandaPosterior,{'numeric'}, ...
    {'scalar','real','finite','positive'});

perfil = lower(string( ...
    opcion(opciones,'perfilRigidez','uniforme')));

factores = opcion(opciones, ...
    'factoresRigidez',[0.60 1.00 1.20]);

limites = opcion(opciones, ...
    'limitesRegionales',[0.30 0.75]);

ancho = opcion(opciones,'anchoTransicion',0.12);

activarSoporte = opcion( ...
    opciones,'activarSoporteVentral',false);

factorSoporte = opcion( ...
    opciones,'factorSoporteVentral',0.05);

inicioSoporte = opcion( ...
    opciones,'inicioSoporte',0.50);

finSoporte = opcion( ...
    opciones,'finTransicionSoporte',0.80);

validateattributes(E,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(nu,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<',0.49});

validateattributes(t,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(factorAnclaje,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(Lref,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(factores,{'numeric'}, ...
    {'vector','numel',3,'real','finite','positive'});

validateattributes(limites,{'numeric'}, ...
    {'vector','numel',2,'real','finite','>',0,'<',1});

validateattributes(ancho,{'numeric'}, ...
    {'scalar','real','finite','positive','<',1});

validateattributes(factorSoporte,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(inicioSoporte,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<',1});

validateattributes(finSoporte,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',1});

if ~isscalar(activarSoporte) || ...
        ~(islogical(activarSoporte) || ...
        (isnumeric(activarSoporte) && ...
        ismember(activarSoporte,[0 1])))
    error('activarSoporteVentral debe ser logico.');
end

activarSoporte = logical(activarSoporte);

if ~isscalar(perfil) || ...
        ~ismember(perfil,["uniforme","regional"])
    error('perfilRigidez debe ser uniforme o regional.');
end

if limites(1) >= limites(2) || ...
        limites(2)-limites(1) <= ancho
    error('Transiciones regionales incompatibles.');
end

if inicioSoporte >= finSoporte
    error('Intervalo del soporte invalido.');
end

if nu >= 0.45
    warning('Posible bloqueo volumetrico del FEM lineal.');
end

%% 2. GEOMETRIA DE REFERENCIA

nodos = malla.nodos;
tri = malla.elementos;

N = size(nodos,1);
M = size(tri,1);
nGDL = 2*N;

if size(nodos,2) ~= 2 || size(tri,2) ~= 3 || ...
        any(~isfinite(nodos(:))) || ...
        any(~isfinite(tri(:))) || ...
        any(tri(:) < 1) || any(tri(:) > N) || ...
        any(tri(:) ~= round(tri(:)))
    error('Malla FEM invalida.');
end

indicePunta = malla.seguimiento.puntaIndice;
posterior = malla.frontera.posterior(:);

if numel(posterior) < 2 || ...
        any(posterior < 1) || any(posterior > N) || ...
        any(posterior ~= round(posterior)) || ...
        numel(unique(posterior)) ~= numel(posterior)
    error('Frontera posterior invalida.');
end

yPunta = nodos(indicePunta,1);
yPosterior = min(nodos(:,1));

longitud = yPunta-yPosterior;

if longitud <= 0
    error('Longitud de referencia invalida.');
end

% Coordenada normalizada:
% s = 0 en punta y s = 1 en extremo posterior.
sNodos = (yPunta-nodos(:,1))/longitud;

%% 3. RIGIDEZ REGIONAL

centroides = ( ...
    nodos(tri(:,1),:) + ...
    nodos(tri(:,2),:) + ...
    nodos(tri(:,3),:))/3;

sElementos = ...
    (yPunta-centroides(:,1))/longitud;

if perfil == "uniforme"

    multiplicador = ones(M,1);

else

    % Transiciones C1 mediante smoothstep.
    q1 = suave( ...
        (sElementos-limites(1))/ancho+0.5);

    q2 = suave( ...
        (sElementos-limites(2))/ancho+0.5);

    multiplicador = factores(1) + ...
        (factores(2)-factores(1))*q1 + ...
        (factores(3)-factores(2))*q2;

end

Eelementos = E*multiplicador;

%% 4. MATRIZ CONSTITUTIVA

Dunitaria = 1/((1+nu)*(1-2*nu))*[
    1-nu, nu, 0;
    nu, 1-nu, 0;
    0, 0, (1-2*nu)/2
];

Dreferencia = E*Dunitaria;

%% 5. ENSAMBLAJE ELASTICO

I = zeros(36*M,1);
J = zeros(36*M,1);
V = zeros(36*M,1);

areas = zeros(M,1);

for e = 1:M

    ids = tri(e,:);
    p = nodos(ids,:);

    y = p(:,1);
    z = p(:,2);

    dobleArea = ...
        (y(2)-y(1))*(z(3)-z(1)) - ...
        (y(3)-y(1))*(z(2)-z(1));

    A = dobleArea/2;

    if A <= 1e-10
        error('Elemento %d invalido.',e);
    end

    areas(e) = A;

    b = [
        z(2)-z(3);
        z(3)-z(1);
        z(1)-z(2)
    ]/dobleArea;

    c = [
        y(3)-y(2);
        y(1)-y(3);
        y(2)-y(1)
    ]/dobleArea;

    B = [
        b(1),0,b(2),0,b(3),0;
        0,c(1),0,c(2),0,c(3);
        c(1),b(1),c(2),b(2),c(3),b(3)
    ];

    Dlocal = Eelementos(e)*Dunitaria;

    Ke = t*A*(B'*Dlocal*B);

    gdl = reshape([2*ids-1;2*ids],1,[]);

    [ii,jj] = ndgrid(gdl,gdl);

    rango = (e-1)*36+(1:36);

    I(rango) = ii(:);
    J(rango) = jj(:);
    V(rango) = Ke(:);

end

Kelastica = sparse(I,J,V,nGDL,nGDL);
Kelastica = (Kelastica+Kelastica')/2;


%% =====================================================
% 6. ANCLAJE POSTERIOR CONFIGURABLE
% ======================================================

% Rigidez por unidad de longitud del borde.
kPosterior = factorAnclaje*E*t/Lref;

Kposterior = sparse(nGDL,nGDL);

% Registro de rigidez nodal para el modo distribuido.
kNodalPosterior = zeros(N,1);

% Longitud total de la frontera posterior.
segmentosPosteriores = diff(nodos(posterior,:),1,1);

longitudesPosteriores = ...
    vecnorm(segmentosPosteriores,2,2);

if any(longitudesPosteriores <= 0)
    error('Frontera posterior degenerada.');
end

LPosterior = sum(longitudesPosteriores);

% Rigidez traslacional equivalente.
KPosteriorTotal = kPosterior*LPosterior;

switch modoAnclajePosterior

    %% A. ANCLAJE ORIGINAL SOBRE EL BORDE

    case "borde"

        for j = 1:numel(posterior)-1

            a = posterior(j);
            b = posterior(j+1);

            L = longitudesPosteriores(j);

            Ksegmento = kPosterior*L/6 * [
                2,1;
                1,2
            ];

            for componente = 0:1

                gdl = 2*[a b]-1+componente;

                Kposterior(gdl,gdl) = ...
                    Kposterior(gdl,gdl)+Ksegmento;

            end

        end

    %% B. ANCLAJE DISTRIBUIDO EN BANDA POSTERIOR

    case "banda"

        % Area tributaria de cada nodo.
        % Cada triangulo reparte un tercio
        % de su area entre sus tres vertices.

        areaNodal = accumarray( ...
            tri(:), ...
            repmat(areas/3,3,1), ...
            [N 1]);

        % Distancia longitudinal desde el
        % extremo posterior de referencia.
        distanciaPosterior = ...
            nodos(:,1)-yPosterior;

        % Peso espacial:
        %
        % 1 en el borde posterior.
        % 0 al finalizar la banda.
        % Transicion C1 mediante smoothstep.

        q = 1-distanciaPosterior/ ...
            anchoBandaPosterior;

        pesoBanda = suave(q);

        % Peso asociado a area y proximidad.
        ponderacion = areaNodal.*pesoBanda;

        sumaPesos = sum(ponderacion);

        if sumaPesos <= 0 || ~isfinite(sumaPesos)
            error('Banda posterior sin nodos validos.');
        end

        % Normalizacion:
        %
        % Se conserva la rigidez equivalente
        % frente a una traslacion uniforme.
        %
        % sum(kNodalPosterior) =
        % kPosterior*LPosterior

        kNodalPosterior = ...
            KPosteriorTotal* ...
            ponderacion/sumaPesos;

        % Resortes nodales en Y y Z.
        diagonal = repelem(kNodalPosterior,2);

        Kposterior = spdiags( ...
            diagonal,0,nGDL,nGDL);

end

Kposterior = (Kposterior+Kposterior')/2;


%% 7. SOPORTE VENTRAL DISTRIBUIDO

Ksoporte = sparse(nGDL,nGDL);
kNodal = zeros(N,1);

if activarSoporte

    % Area asociada a cada nodo.
    areaNodal = accumarray( ...
        tri(:),repmat(areas/3,3,1),[N 1]);

    % Proximidad al lado inferior.
    niveles = malla.referencia.nivelesEspesor;

    eta = ones(N,1);

    indicesRegulares = setdiff( ...
        (1:N)',indicePunta);

    eta(indicesRegulares) = ...
        mod(indicesRegulares-1,niveles)/(niveles-1);

    % Activacion longitudinal suave.
    pesoLongitudinal = suave( ...
        (sNodos-inicioSoporte)/ ...
        (finSoporte-inicioSoporte));

    % Mayor soporte en la superficie inferior.
    pesoProfundidad = (1-eta).^2;

    % Densidad de rigidez por area, N/mm^3.
    kArea = factorSoporte*E*t/Lref^2;

    kNodal = kArea*areaNodal.* ...
        pesoLongitudinal.*pesoProfundidad;

    % Dos componentes de desplazamiento por nodo.
    diagonal = repelem(kNodal,2);

    Ksoporte = spdiags( ...
        diagonal,0,nGDL,nGDL);

end

%% 8. RIGIDEZ TOTAL

Kanclajes = Kposterior+Ksoporte;

Ktotal = Kelastica+Kanclajes;
Ktotal = (Ktotal+Ktotal')/2;

errorSimetria = norm( ...
    Ktotal-Ktotal','fro')/ ...
    max(norm(Ktotal,'fro'),eps);

[~,pChol] = chol(Ktotal);

if pChol ~= 0
    error(['La matriz no es definida positiva. ', ...
        'Revisa anclajes y conectividad.']);
end

%% 9. SALIDA COMPATIBLE

modelo.malla = malla;

modelo.material.E = E;
modelo.material.nu = nu;
modelo.material.espesor = t;
modelo.material.D = Dreferencia;
modelo.material.formulacion = 'Deformacion plana';

modelo.material.perfilRigidez = perfil;
modelo.material.Eelementos = Eelementos;
modelo.material.multiplicadores = multiplicador;

modelo.anclajes.nodos = posterior;
modelo.anclajes.rigidezDistribuida = kPosterior;
modelo.anclajes.factor = factorAnclaje;
modelo.anclajes.longitudReferencia = Lref;

modelo.anclajes.modoPosterior = ...
    modoAnclajePosterior;

modelo.anclajes.anchoBandaPosterior = ...
    anchoBandaPosterior;

modelo.anclajes.rigidezNodalPosterior = ...
    kNodalPosterior;

modelo.anclajes.nodosBandaPosterior = ...
    find(kNodalPosterior>0);

modelo.anclajes.rigidezTotalPosterior = ...
    KPosteriorTotal;

modelo.anclajes.soporteVentralActivo = activarSoporte;
modelo.anclajes.rigidecesVentrales = kNodal;

modelo.matrices.Kelastica = Kelastica;
modelo.matrices.Kposterior = Kposterior;
modelo.matrices.Ksoporte = Ksoporte;
modelo.matrices.Kanclajes = Kanclajes;
modelo.matrices.Ktotal = Ktotal;

modelo.gdl.total = nGDL;
modelo.gdl.Y = (1:2:nGDL)';
modelo.gdl.Z = (2:2:nGDL)';

modelo.regiones.sNodos = sNodos;
modelo.regiones.sElementos = sElementos;
modelo.regiones.limites = limites;
modelo.regiones.factoresRigidez = factores;

modelo.diagnostico.nNodos = N;
modelo.diagnostico.nElementos = M;
modelo.diagnostico.areaTotal = sum(areas);
modelo.diagnostico.errorSimetria = errorSimetria;
modelo.diagnostico.definidaPositiva = true;
modelo.diagnostico.elementosInvertidos = 0;
modelo.diagnostico.nodosConSoporte = nnz(kNodal>0);

end

%% FUNCIONES LOCALES

function valor = opcion(s,nombre,defecto)
if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end
end

function q = suave(x)
x = max(0,min(1,x));
q = x.^2.*(3-2*x);
end
