
function estado = resolver_postura_no_lineal(modelo, objetivo, opciones)
% RESOLVER_POSTURA_NO_LINEAL
% FEM hiperelastico 2D en deformacion plana.
% Neo-Hookeano compresible con deformacion activa.
%
% Solucion:
%   Newton-Raphson incremental
%   Rigidez tangente consistente
%   Busqueda de paso por energia
%
% Compatible con la malla y configuracion actuales.
% No incluye contacto anatomico.
%
% Unidades: mm, N, N/mm^2.

%% 1. OPCIONES

if nargin < 3 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

nPasos = leer(opciones,'nPasos',12);
maxIter = leer(opciones,'maxIter',35);
tolFuerza = leer(opciones,'tolFuerza',1e-9);
maxBacktrack = leer(opciones,'maxBacktrack',24);

validateattributes(nPasos,{'numeric'}, ...
    {'scalar','integer','positive','<=',200});

validateattributes(maxIter,{'numeric'}, ...
    {'scalar','integer','positive','<=',200});

validateattributes(tolFuerza,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(maxBacktrack,{'numeric'}, ...
    {'scalar','integer','positive','<=',40});

%% 2. MODELO DE REFERENCIA

if ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo,'material') || ...
        ~isfield(modelo,'matrices')
    error('Modelo FEM invalido.');
end

malla = modelo.malla;
X = malla.nodos;
tri = malla.elementos;

N = size(X,1);
M = size(tri,1);
nGDL = 2*N;

Ka = modelo.matrices.Kanclajes;

if ~isequal(size(Ka),[nGDL nGDL])
    error('Matriz de anclajes incompatible.');
end

Eelementos = modelo.material.Eelementos(:);
nu = modelo.material.nu;
espesor = modelo.material.espesor;

if numel(Eelementos) ~= M
    error('Propiedades elementales incompatibles.');
end

% Constantes de Lame por elemento.
mu = Eelementos./(2*(1+nu));

lambda = Eelementos*nu/ ...
    ((1+nu)*(1-2*nu));

%% 3. OBJETIVO ARTICULATORIO

if ~isstruct(objetivo) || ...
        ~isscalar(objetivo) || ...
        ~isfield(objetivo,'puntaYZ')
    error('Objetivo invalido.');
end

puntaObjetivo = reshape(objetivo.puntaYZ,1,[]);

validateattributes(puntaObjetivo,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

modo = lower(string(leer( ...
    objetivo,'modo','prescrito')));

if ~isscalar(modo) || ...
        ~ismember(modo,["prescrito","penalizado"])
    error('Modo de objetivo invalido.');
end

componentes = leer(objetivo, ...
    'componentes',[true true]);

if ~(islogical(componentes) || isnumeric(componentes)) || ...
        numel(componentes) ~= 2 || ...
        ~all(ismember(double(componentes(:)),[0 1]))
    error('Componentes de control invalidas.');
end

componentes = logical(reshape(componentes,1,2));

if ~any(componentes)
    error('Debe controlarse al menos una componente.');
end

indicePunta = malla.seguimiento.puntaIndice;

gdlPunta = [
    2*indicePunta-1, 2*indicePunta
];

gdlControl = gdlPunta(componentes);

delta = puntaObjetivo-X(indicePunta,:);
deltaControl = delta(componentes)';

%% 4. OBJETIVO PENALIZADO O PRESCRITO

Kp = sparse(nGDL,nGDL);
kp = [];

libres = true(nGDL,1);

if modo == "prescrito"

    libres(gdlControl) = false;

else

    rigidez = leer(objetivo, ...
        'rigidezPunta',0.1);

    if isscalar(rigidez)
        rigidez = [rigidez rigidez];
    end

    validateattributes(rigidez,{'numeric'}, ...
        {'vector','numel',2,'real','finite','positive'});

    rigidez = reshape(rigidez,1,2);
    kp = rigidez(componentes)';

    Kp = sparse( ...
        gdlControl,gdlControl,kp, ...
        nGDL,nGDL);

end


%% 4B. GUIADO GEOMETRICO OPCIONAL

guia = leer(objetivo,'guia',[]);

if isempty(guia)
    guia = struct('objetivos',struct([]));
end

if ~isstruct(guia) || ~isscalar(guia)
    error('La guia geometrica debe ser una estructura escalar.');
end

% Factores adimensionales experimentales.
% No representan constantes de tejido anatomico.

factorGuia = leer( ...
    objetivo,'factorRigidezGuia',0.25);

factorAngular = leer( ...
    objetivo,'factorRigidezAngular',0.20);

validateattributes(factorGuia,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(factorAngular,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

% E [N/mm^2] * espesor [mm] = N/mm.
% Rigidez puntual de referencia.

kGuia = factorGuia*modelo.material.E*espesor;

% La rigidez angular efectiva se multiplica
% posteriormente por la longitud apical al cuadrado.
% Unidad efectiva: N*mm/rad^2.

kAngularBase = ...
    factorAngular*modelo.material.E*espesor;

%% 5. DEFORMACIONES ACTIVAS

epsilonActiva = zeros(M,3);
cargaActiva = [];

if isfield(objetivo,'activacion') && ...
        ~isempty(objetivo.activacion)

    cargaActiva = calcular_activacion_lingual( ...
        modelo,objetivo.activacion);

    epsilonActiva = ...
        cargaActiva.deformacionActiva;

    if ~isequal(size(epsilonActiva),[M 3])
        error('Deformacion activa incompatible.');
    end

end

%% 6. PRECALCULAR ELEMENTOS

datos = struct();

datos.X = X;
datos.tri = tri;
datos.N = N;
datos.M = M;
datos.nGDL = nGDL;

datos.mu = mu;
datos.lambda = lambda;
datos.espesor = espesor;

datos.epsilonActiva = epsilonActiva;

datos.gradientes = zeros(3,2,M);
datos.areas = zeros(M,1);
datos.gdl = zeros(M,6);

for e = 1:M

    ids = tri(e,:);
    p = X(ids,:);

    D0 = [
        (p(2,:)-p(1,:))', ...
        (p(3,:)-p(1,:))'
    ];

    A0 = det(D0)/2;

    if A0 <= 1e-10
        error('Elemento de referencia %d invalido.',e);
    end

    invD0 = D0\eye(2);

    grad = zeros(3,2);
    grad(2:3,:) = invD0;
    grad(1,:) = -sum(grad(2:3,:),1);

    datos.gradientes(:,:,e) = grad;
    datos.areas(e) = A0;

    datos.gdl(e,:) = reshape( ...
        [2*ids-1;2*ids],1,[]);

end


%% 6B. REGULARIZACION DE FLEXION

opSuavidad = leer( ...
    objetivo,'suavidad',struct());

regularizador = regularizar_flexion_lingual( ...
    'preparar',modelo,opSuavidad);


%% CONTROL DE FORMA OPCIONAL

controlForma = [];

if isfield(objetivo,'controlForma') && ...
        ~isempty(objetivo.controlForma)

    controlForma = objetivo.controlForma;

end

%% 7. NEWTON-RAPHSON INCREMENTAL

inicio = tic;

uInicial = zeros(nGDL,1);

if isfield(opciones,'uInicial') && ...
        ~isempty(opciones.uInicial)

    uInicial = opciones.uInicial(:);

    validateattributes(uInicial,{'numeric'}, ...
        {'column','numel',nGDL,'real','finite'});

end

u = uInicial;

historia.iteraciones = zeros(nPasos,1);
historia.residuos = zeros(nPasos,1);
historia.Jmin = zeros(nPasos,1);
historia.energias = zeros(nPasos,1);

for paso = 1:nPasos

    alpha = paso/nPasos;

    % Condiciones de desplazamiento prescrito.
    if modo == "prescrito"
        controlPaso = ...
            uInicial(gdlControl) + ...
            alpha*(deltaControl-uInicial(gdlControl));

        u(gdlControl) = controlPaso;
    end

    fObjetivo = zeros(nGDL,1);

    if modo == "penalizado"
        fObjetivo(gdlControl) = ...
            alpha*kp.*deltaControl;
    end

    convergio = false;

    for iter = 0:maxIter
        
        %% A. ENERGIA, FUERZAS Y RIGIDEZ

        % 1. Contribucion hiperelastica del FEM.
        [Eint,fint,Kint,Jmin,~,valido] = ...
            ensamblarFEM(u,alpha,datos,true);

        if ~valido
            error('Configuracion invertida en paso %d.',paso);
        end

        % 2. Contribucion del guiado geometrico.
        [Eguia,fguia,Kguia] = evaluar_guia_lingual( ...
            u,alpha,X,guia,kGuia,kAngularBase,true);


        % Contribucion de regularizacion de flexion.

        [Esuav,fsuav,Ksuav,diagSuav] = ...
            regularizar_flexion_lingual( ...
            'evaluar',regularizador,u,true);

        if ~diagSuav.valido
            error('Geometria invalida en regularizacion.');
        end

        % 3. Ensamblar residuo total.
        
        residuo = fint + Ka*u + Kp*u + ...
            fguia + fsuav - fObjetivo;

        % 4. Ensamblar matriz tangente total.
        Kt = Kint + Ka + Kp + Kguia + Ksuav;

        % 5. Garantizar simetria numerica.
        Kt = (Kt+Kt')/2;


        %% CONTROL DE CURVATURA Y ORIENTACION

        Eforma = 0;
        fForma = zeros(nGDL,1);
        Kforma = sparse(nGDL,nGDL);

        if ~isempty(controlForma)

            [Eforma,fForma,Kforma,validoForma] = ...
                controlar_forma_lingual( ...
                'evaluar',controlForma,u,alpha,true);

            if ~validoForma
                error('Control de forma geometricamente invalido.');
            end

        end

        % Incorporar las nuevas contribuciones.
        residuo = residuo + fForma;

        Kt = Kt + Kforma;
        Kt = (Kt+Kt')/2;

        % 6. Extraer grados de libertad no prescritos.
        residuoLibre = residuo(libres);

        normaR = norm(residuoLibre,inf);

        % 7. Potencial total.
        potencial = Eint + ...
            0.5*u'*Ka*u + ...
            Eguia + Esuav + Eforma;

        % 8. Contribucion de la punta penalizada.
        if modo == "penalizado"

            errorObjetivo = ...
                u(gdlControl)-alpha*deltaControl;

            potencial = potencial + ...
                0.5*sum(kp.*errorObjetivo.^2);

        end

        %% B. CONVERGENCIA

        if normaR <= tolFuerza

            convergio = true;

            historia.iteraciones(paso) = iter;
            historia.residuos(paso) = normaR;
            historia.Jmin(paso) = Jmin;
            historia.energias(paso) = potencial;

            break

        end

        if iter == maxIter
            break
        end

        %% C. INCREMENTO DE NEWTON

        Kll = Kt(libres,libres);

        % Regularizacion si la tangente no es
        % definida positiva.
        [~,pChol] = chol(Kll);

        if pChol ~= 0

            escala = max(abs(diag(Kll)));
            regularizacion = max(escala,eps)*1e-8;

            for intento = 1:12

                Kprueba = Kll + regularizacion* ...
                    speye(size(Kll,1));

                [~,pChol] = chol(Kprueba);

                if pChol == 0
                    Kll = Kprueba;
                    break
                end

                regularizacion = ...
                    regularizacion*10;

            end

            if pChol ~= 0
                error('Tangente no estabilizable.');
            end

        end

        duLibre = -(Kll\residuoLibre);

        derivada = residuoLibre'*duLibre;

        if ~isfinite(derivada) || derivada >= 0
            error('Direccion de Newton no descendente.');
        end

        %% D. BUSQUEDA DE PASO

        beta = 1;
        aceptado = false;

        for intento = 1:maxBacktrack

            uPrueba = u;

            uPrueba(libres) = ...
                u(libres)+beta*duLibre;

            if modo == "prescrito"
                uPrueba(gdlControl) = controlPaso;
            end

            [Eprueba,~,~,~,~,validoPrueba] = ...
                ensamblarFEM( ...
                uPrueba,alpha,datos,false);

            if validoPrueba

                % Evaluar la energia del guiado para el
                % desplazamiento candidato.

                [EguiaPrueba,~,~] = evaluar_guia_lingual( ...
                    uPrueba,alpha,X,guia, ...
                    kGuia,kAngularBase,false);

                [EsuavPrueba,~,~,diagSuavPrueba] = ...
                    regularizar_flexion_lingual( ...
                    'evaluar',regularizador,uPrueba,false);

                if ~diagSuavPrueba.valido
                    beta = beta/2;
                    continue
                end


                %% ENERGIA DEL CONTROL DE FORMA

                EformaPrueba = 0;
                validoFormaPrueba = true;

                if ~isempty(controlForma)

                    [EformaPrueba,~,~,validoFormaPrueba] = ...
                        controlar_forma_lingual( ...
                        'evaluar',controlForma, ...
                        uPrueba,alpha,false);

                end

                if ~validoFormaPrueba || ~isfinite(EformaPrueba)

                    beta = beta/2;
                    continue

                end

                potencialPrueba = ...
                    Eprueba + ...
                    0.5*uPrueba'*Ka*uPrueba + ...
                    EguiaPrueba + EsuavPrueba + ...
                    EformaPrueba;

                if modo == "penalizado"

                    errorObjetivo = ...
                        uPrueba(gdlControl)- ...
                        alpha*deltaControl;

                    potencialPrueba = ...
                        potencialPrueba + ...
                        0.5*sum(kp.*errorObjetivo.^2);

                end

                if potencialPrueba <= ...
                        potencial+1e-4*beta*derivada

                    aceptado = true;
                    u = uPrueba;
                    break

                end

            end

            beta = beta/2;

        end

        if ~aceptado
            error(['No se encontro un incremento valido ', ...
                'en el paso %d, iteracion %d.'], ...
                paso,iter);
        end

    end

    if ~convergio
        error(['Newton no convergio en paso %d. ', ...
            'Prueba mas incrementos o un objetivo menor.'], ...
            paso);
    end

end

tiempoResolucion = toc(inicio);

%% 8. RECONSTRUCCION NODAL

desplazamientos = reshape(u,2,[])';

nodosFinales = X+desplazamientos;

puntaFinal = nodosFinales(indicePunta,:);

idsCostillas = ...
    malla.seguimiento.costillasIndices;

costillasFinales = ...
    nodosFinales(idsCostillas,:);

errorPunta = puntaObjetivo-puntaFinal;

%% 9. DIAGNOSTICO GEOMETRICO

Jgeometrico = zeros(M,1);

for e = 1:M

    ids = tri(e,:);

    p = nodosFinales(ids,:);

    F = p'*datos.gradientes(:,:,e);

    Jgeometrico(e) = det(F);

end

if any(Jgeometrico <= 0)
    error('El resultado contiene elementos invertidos.');
end

magnitudes = vecnorm(desplazamientos,2,2);

%% 9B. DIAGNOSTICO DE GUIADO GEOMETRICO

[energiaGuia,fuerzasGuia,~,detalleGuia] = ...
    evaluar_guia_lingual( ...
    u,1,X,guia,kGuia,kAngularBase,false);

fuerzasGuiaNodales = ...
    reshape(fuerzasGuia,2,[])';

fuerzaGuiaMaxima = max( ...
    vecnorm(fuerzasGuiaNodales,2,2));


%% 9C. DIAGNOSTICO DE REGULARIZACION

[energiaSuavidad,~,~,diagSuavidad] = ...
    regularizar_flexion_lingual( ...
    'evaluar',regularizador,u,false);

%% 10. SALIDA

estado.u = u;
estado.nodos = nodosFinales;
estado.desplazamientos = desplazamientos;

estado.puntaYZ = puntaFinal;
estado.costillasYZ = costillasFinales;

estado.objetivo = objetivo;
estado.modo = modo;
estado.componentesControladas = componentes;

estado.cargaActiva = cargaActiva;

estado.formulacion = ...
    'Neo-Hookeano 2D - deformacion plana';

estado.diagnostico.convergio = true;

estado.diagnostico.errorPuntaYZ = errorPunta;

estado.diagnostico.errorControlado = ...
    norm(errorPunta(componentes));

estado.diagnostico.residuoEquilibrio = ...
    historia.residuos(end);

estado.diagnostico.desplazamientoMaximo = ...
    max(magnitudes);

estado.diagnostico.Jmin = min(Jgeometrico);
estado.diagnostico.Jmax = max(Jgeometrico);

estado.diagnostico.variacionAreaMaxima = ...
    max(abs(Jgeometrico-1));

estado.diagnostico.energiaTotal = ...
    historia.energias(end);

estado.diagnostico.tiempoResolucion = ...
    tiempoResolucion;

estado.diagnostico.iteracionesPorPaso = ...
    historia.iteraciones;

estado.historia = historia;

% Diagnosticos especificos del guiado.

estado.guia = detalleGuia;

estado.diagnostico.energiaGuia = energiaGuia;

estado.diagnostico.fuerzaGuiaMaxima = ...
    fuerzaGuiaMaxima;

estado.diagnostico.rigidezGuiaBase = kGuia;

estado.diagnostico.factorRigidezAngular = ...
    factorAngular;

% Diagnosticos adicionales de flexion.

estado.regularizacion = diagSuavidad;

estado.diagnostico.energiaSuavidad = ...
    energiaSuavidad;

estado.diagnostico.rmsCambioCurvatura = ...
    diagSuavidad.rmsCambioCurvatura;

estado.diagnostico.rmsCurvaturaDorsal = ...
    diagSuavidad.rmsCambioCurvaturaDorsal;

estado.diagnostico.rmsCurvaturaVentral = ...
    diagSuavidad.rmsCambioCurvaturaVentral;

estado.diagnostico.maxCambioAngular_deg = ...
    diagSuavidad.maxCambioAngular_deg;


%% ENERGIA FINAL DE CONTROL DE FORMA

estado.diagnostico.energiaControlForma = 0;

if ~isempty(controlForma)

    [EformaFinal,~,~,validoFormaFinal] = ...
        controlar_forma_lingual( ...
        'evaluar',controlForma,u,1,false);

    if ~validoFormaFinal
        error('Configuracion final invalida.');
    end

    estado.diagnostico.energiaControlForma = ...
        EformaFinal;

end


end

%% FUNCION LOCAL: ENSAMBLAJE HIPERELASTICO

function [energia,f,K,Jmin,Jmax,valido] = ...
    ensamblarFEM(u,alpha,datos,calcularTangente)

N = datos.N;
M = datos.M;
nGDL = datos.nGDL;

x = datos.X+reshape(u,2,[])';

energia = 0;

f = zeros(nGDL,1);
K = sparse(nGDL,nGDL);

Jmin = inf;
Jmax = -inf;

valido = true;

if calcularTangente
    I = zeros(36*M,1);
    Jindices = zeros(36*M,1);
    V = zeros(36*M,1);
end

for e = 1:M

    ids = datos.tri(e,:);
    gdl = datos.gdl(e,:);

    grad = datos.gradientes(:,:,e);
    A0 = datos.areas(e);

    mu = datos.mu(e);
    lambda = datos.lambda(e);

    %% A. DEFORMACION ACTIVA

    epsilon = datos.epsilonActiva(e,:);

    Ea = [
        epsilon(1),epsilon(3)/2;
        epsilon(3)/2,epsilon(2)
    ];

    Fa = eye(2)+alpha*Ea;

    Ja = det(Fa);

    if Ja <= 0
        valido = false;
        energia = inf;
        return
    end

    G = Fa\eye(2);

    %% B. GRADIENTE DEFORMACION

    F = x(ids,:)'*grad;

    Fe = F*G;

    Je = det(Fe);
    Jtotal = det(F);

    if ~isfinite(Je) || Je <= 1e-8 || ...
            ~isfinite(Jtotal) || Jtotal <= 1e-8

        valido = false;
        energia = inf;
        return

    end

    Jmin = min(Jmin,Jtotal);
    Jmax = max(Jmax,Jtotal);

    logJ = log(Je);

    %% C. ENERGIA NEO-HOOKEANA

    W = 0.5*mu*( ...
        sum(Fe(:).^2)-2-2*logJ) + ...
        0.5*lambda*logJ^2;

    volumen = datos.espesor*A0;

    energia = energia + volumen*Ja*W;

    if ~calcularTangente
        continue
    end

    %% D. PRIMER PIOLA-KIRCHHOFF

    A = Fe'\eye(2);

    Pe = mu*(Fe-A)+lambda*logJ*A;

    P = Ja*Pe*G';

    fuerzasElemento = ...
        volumen*grad*P';

    fe = reshape(fuerzasElemento',6,1);

    f(gdl) = f(gdl)+fe;

    %% E. RIGIDEZ TANGENTE CONSISTENTE

    Ke = zeros(6,6);

    for b = 1:3

        for componente = 1:2

            dF = zeros(2,2);

            dF(componente,:) = ...
                grad(b,:);

            dFe = dF*G;

            % Derivada de Fe^(-T).
            dA = -A*dFe'*A;

            dLogJ = sum(A(:).*dFe(:));

            dPe = mu*dFe + ...
                (lambda*logJ-mu)*dA + ...
                lambda*dLogJ*A;

            dP = Ja*dPe*G';

            df = volumen*grad*dP';

            columna = 2*b-2+componente;

            Ke(:,columna) = ...
                reshape(df',6,1);

        end

    end

    %% F. ENSAMBLAJE

    [ii,jj] = ndgrid(gdl,gdl);

    rango = (e-1)*36+(1:36);

    I(rango) = ii(:);
    Jindices(rango) = jj(:);
    V(rango) = Ke(:);

end

if calcularTangente

    K = sparse( ...
        I,Jindices,V,nGDL,nGDL);

    K = (K+K')/2;

end

end

%% FUNCION LOCAL

function valor = leer(s,nombre,defecto)
if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end
end
