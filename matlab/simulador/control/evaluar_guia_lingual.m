
function [energia,f,K,detalle] = evaluar_guia_lingual( ...
    u,alpha,X,guia,kBase,kAngularBase,calcularTangente)
% EVALUAR_GUIA_LINGUAL
%
% Energia, fuerzas internas equivalentes y tangente
% de objetivos geometricos suaves sobre una malla FEM.
%
% Coordenadas: [Y,Z] en mm.
%
% GUIADO POSICIONAL
%
% E = 0.5*k*||x_material - x_objetivo||^2
%
% Las coordenadas objetivo pueden contener NaN.
% Solo se penalizan las componentes definidas.
%
% GUIADO ANGULAR
%
% E = 0.5*kTheta*(theta-thetaObjetivo)^2
%
% Incluye gradiente y Hessiana angular consistente.
%
% alpha permite introducir progresivamente los
% objetivos durante los incrementos FEM.
%
% No necesita toolboxes.

%% 1. GEOMETRIA

N = size(X,1);
nGDL = 2*N;

if nargin < 7
    calcularTangente = true;
end

validateattributes(alpha,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<=',1});

validateattributes(u,{'numeric'}, ...
    {'vector','numel',nGDL,'real','finite'});

validateattributes(kBase,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(kAngularBase,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

x = X+reshape(u,2,[])';

energia = 0;
f = zeros(nGDL,1);

K = sparse(nGDL,nGDL);

if ~isfield(guia,'objetivos')
    objetivos = struct([]);
else
    objetivos = guia.objetivos;
end

if ~isstruct(objetivos)
    error('Objetivos geometricos invalidos.');
end

nObjetivos = numel(objetivos);

detalle.puntos = zeros(nObjetivos,2);
detalle.metas = nan(nObjetivos,2);
detalle.errores = nan(nObjetivos,2);

detalle.anguloActual_deg = NaN;
detalle.anguloObjetivo_deg = NaN;
detalle.errorAngular_deg = NaN;

%% 2. OBJETIVOS POSICIONALES

for i = 1:nObjetivos

    a = objetivos(i);

    ids = reshape(a.ids,1,[]);
    coef = reshape(a.coef,1,[]);

    meta = reshape(a.meta,1,[]);

    if numel(ids) ~= numel(coef) || ...
            isempty(ids) || ...
            numel(meta) ~= 2 || ...
            any(ids < 1) || any(ids > N) || ...
            any(ids ~= round(ids)) || ...
            any(~isfinite(coef)) || ...
            any(isinf(meta)) || ...
            abs(sum(coef)-1) > 1e-8

        error('Ancla material %d invalida.',i);

    end

    validateattributes(a.peso,{'numeric'}, ...
        {'scalar','real','finite','>=',0});

    %% A. POSICION DEL PUNTO MATERIAL CENTRAL

    p0 = coef*X(ids,:);

    p = coef*x(ids,:);

    detalle.puntos(i,:) = p;

    %% B. IDENTIFICAR MODO DE GUIADO

    fraccionDistribuida = 0;

    idsSoporte = [];
    pesosSoporte = [];

    if isfield(a,'soporte') && ...
            ~isempty(a.soporte)

        soporte = a.soporte;

        fraccionDistribuida = ...
            soporte.fraccionDistribuida;

        idsSoporte = soporte.ids(:);
        pesosSoporte = soporte.pesos(:);

        if isempty(idsSoporte) || ...
                numel(idsSoporte) ~= numel(pesosSoporte) || ...
                any(idsSoporte < 1) || ...
                any(idsSoporte > N) || ...
                any(~isfinite(pesosSoporte)) || ...
                any(pesosSoporte < 0) || ...
                abs(sum(pesosSoporte)-1) > 1e-8

            error('Soporte distribuido %d invalido.',i);

        end

        validateattributes(fraccionDistribuida, ...
            {'numeric'}, ...
            {'scalar','real','finite','>=',0,'<=',1});

    end

    %% C. RIGIDECES DE AMBOS MODOS

    kTotal = kBase*a.peso;

    kPuntual = ...
        kTotal*(1-fraccionDistribuida);

    kDistribuida = ...
        kTotal*fraccionDistribuida;

    %% D. CONTROL DE CADA COMPONENTE Y,Z

    for componente = 1:2

        if isnan(meta(componente))
            continue
        end

        % Desplazamiento objetivo de este punto
        % material respecto a su posicion inicial.

        deltaObjetivo = ...
            meta(componente)-p0(componente);

        % Objetivo incremental del punto central.

        metaIncremental = ...
            p0(componente)+alpha*deltaObjetivo;

        errorPunto = ...
            p(componente)-metaIncremental;

        detalle.metas(i,componente) = ...
            metaIncremental;

        detalle.errores(i,componente) = ...
            errorPunto;

        %% E. CONTRIBUCION PUNTUAL

        if kPuntual > 0

            energia = energia + ...
                0.5*kPuntual*errorPunto^2;

            gdl = 2*ids-2+componente;

            f(gdl) = f(gdl) + ...
                kPuntual*errorPunto*coef(:);

            if calcularTangente

                K(gdl,gdl) = K(gdl,gdl) + ...
                    kPuntual*(coef(:)*coef(:)');

            end

        end

        %% F. CONTRIBUCION DISTRIBUIDA

        if kDistribuida > 0

            % Cada nodo vecino recibe el mismo
            % desplazamiento objetivo, no la misma
            % posicion absoluta.
            %
            % Esto evita colapsar los nodos hacia
            % un unico punto geometrico.

            gdlSoporte = ...
                2*idsSoporte-2+componente;

            uSoporte = u(gdlSoporte);

            errorSoporte = ...
                uSoporte-alpha*deltaObjetivo;

            %% ENERGIA

            energia = energia + ...
                0.5*kDistribuida* ...
                sum(pesosSoporte.*errorSoporte.^2);

            %% FUERZAS

            f(gdlSoporte) = ...
                f(gdlSoporte) + ...
                kDistribuida* ...
                (pesosSoporte.*errorSoporte);

            %% MATRIZ TANGENTE

            if calcularTangente

                K = K + sparse( ...
                    gdlSoporte,gdlSoporte, ...
                    kDistribuida*pesosSoporte, ...
                    nGDL,nGDL);

            end

        end

    end

end

%% 3. ORIENTACION APICAL OPCIONAL

if isfield(guia,'apice') && ...
        isfield(guia.apice,'anguloObjetivo_deg') && ...
        isfinite(guia.apice.anguloObjetivo_deg)

    apice = guia.apice;

    a = apice.anterior;
    p = apice.posterior;

    idsA = reshape(a.ids,1,[]);
    coefA = reshape(a.coef,1,[]);

    idsP = reshape(p.ids,1,[]);
    coefP = reshape(p.coef,1,[]);

    % Vector desde marcador posterior al anterior.

    pa = coefA*x(idsA,:);
    pp = coefP*x(idsP,:);

    v = (pa-pp)';

    pa0 = coefA*X(idsA,:);
    pp0 = coefP*X(idsP,:);

    v0 = (pa0-pp0)';

    L2 = v'*v;
    L02 = v0'*v0;

    if L2 <= 1e-12 || L02 <= 1e-12
        error('Orientacion apical degenerada.');
    end

    %% A. OBJETIVO ANGULAR INCREMENTAL

    theta = atan2(v(2),v(1));
    theta0 = atan2(v0(2),v0(1));

    thetaMetaFinal = ...
        apice.anguloObjetivo_deg*pi/180;

    diferenciaObjetivo = envolverRadianes( ...
        thetaMetaFinal-theta0);

    thetaMeta = theta0+ ...
        alpha*diferenciaObjetivo;

    errorTheta = envolverRadianes( ...
        theta-thetaMeta);

    pesoAngulo = 1;

    if isfield(apice,'peso')
        pesoAngulo = apice.peso;
    end

    validateattributes(pesoAngulo,{'numeric'}, ...
        {'scalar','real','finite','>=',0});

    % Rigidez angular efectiva en N*mm/rad^2.
    kTheta = kAngularBase*L02*pesoAngulo;

    %% B. ENERGIA

    energia = energia+ ...
        0.5*kTheta*errorTheta^2;

    %% C. GRADIENTE DE ANGULO

    gradTheta = [
        -v(2);
         v(1)
    ]/L2;

    % Operador que convierte desplazamientos
    % nodales en el cambio del vector apical.

    C = sparse(2,nGDL);

    for j = 1:numel(idsA)

        id = idsA(j);

        C(1,2*id-1) = ...
            C(1,2*id-1)+coefA(j);

        C(2,2*id) = ...
            C(2,2*id)+coefA(j);

    end

    for j = 1:numel(idsP)

        id = idsP(j);

        C(1,2*id-1) = ...
            C(1,2*id-1)-coefP(j);

        C(2,2*id) = ...
            C(2,2*id)-coefP(j);

    end

    %% D. FUERZAS ANGULARES

    f = f+kTheta*errorTheta*(C'*gradTheta);

    %% E. HESSIANA ANGULAR CONSISTENTE

    if calcularTangente

        vy = v(1);
        vz = v(2);

        Htheta = [
            2*vy*vz, vz^2-vy^2;
            vz^2-vy^2, -2*vy*vz
        ]/(L2^2);

        Hlocal = ...
            gradTheta*gradTheta' + ...
            errorTheta*Htheta;

        K = K + kTheta*(C'*Hlocal*C);

    end

    detalle.anguloActual_deg = theta*180/pi;

    detalle.anguloObjetivo_deg = ...
        thetaMeta*180/pi;

    detalle.errorAngular_deg = ...
        errorTheta*180/pi;

end

%% 4. DIAGNOSTICO

detalle.energia = energia;

detalle.fuerzasNodales = ...
    reshape(f,2,[])';

detalle.fuerzaMaxima = ...
    max(vecnorm(detalle.fuerzasNodales,2,2));

% Garantizar simetria numerica.
if calcularTangente
    K = (K+K')/2;
end

end

%% FUNCION LOCAL

function angulo = envolverRadianes(angulo)

angulo = atan2(sin(angulo),cos(angulo));

end
