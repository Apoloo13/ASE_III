
function diagnostico = validar_deformacion_lingual( ...
    modelo,estado,opciones)
% VALIDAR_DEFORMACION_LINGUAL
%
% Diagnostico geometrico y mecanico de una postura FEM.
%
% ENTRADAS:
%   modelo  : salida de configurar_biomecanica
%   estado  : salida de resolver_postura_no_lineal
%   opciones:
%       graficar           = true
%       mostrarConsola     = true
%       mostrarReferencia  = false
%       nombrePostura      = 'Postura FEM'
%       limites.Jmin       = 0.90
%       limites.Jmax       = 1.10
%       limites.lambdaMin  = 0.80
%       limites.lambdaMax  = 1.20
%       limites.GreenMax   = 0.20
%       limites.anguloMin  = 10
%
% SALIDA:
%   diagnostico.elementos
%   diagnostico.global
%   diagnostico.criterios
%   diagnostico.contorno
%   diagnostico.graficos
%
% Evalua la deformacion geometrica TOTAL F.
% No separa la deformacion elastica de la activa.
%
% No modifica ni resuelve el FEM.
% No necesita toolboxes adicionales.

%% 1. OPCIONES

if nargin < 3 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('Opciones invalidas.');
end

graficar = leer(opciones,'graficar',true);
mostrarConsola = leer( ...
    opciones,'mostrarConsola',true);

mostrarReferencia = leer( ...
    opciones,'mostrarReferencia',false);

nombrePostura = char(string( ...
    leer(opciones,'nombrePostura','Postura FEM')));

limites = leer(opciones,'limites',struct());

limJmin = leer(limites,'Jmin',0.90);
limJmax = leer(limites,'Jmax',1.10);

limLambdaMin = leer(limites,'lambdaMin',0.80);
limLambdaMax = leer(limites,'lambdaMax',1.20);

limGreen = leer(limites,'GreenMax',0.20);
limAngulo = leer(limites,'anguloMin',10);

valoresLimite = [
    limJmin,limJmax, ...
    limLambdaMin,limLambdaMax, ...
    limGreen,limAngulo
];

if any(~isfinite(valoresLimite)) || ...
        any(valoresLimite <= 0)
    error('Limites de diagnostico invalidos.');
end

if limJmin >= limJmax || ...
        limLambdaMin >= limLambdaMax || ...
        limAngulo >= 60
    error('Intervalos de diagnostico incompatibles.');
end

%% 2. GEOMETRIA FEM

if ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo.malla,'nodos') || ...
        ~isfield(modelo.malla,'elementos')
    error('Modelo FEM invalido.');
end

if ~isstruct(estado) || ...
        ~isfield(estado,'nodos')
    error('Estado FEM invalido.');
end

malla = modelo.malla;

X = double(malla.nodos);
x = double(estado.nodos);
tri = double(malla.elementos);

N = size(X,1);
M = size(tri,1);

if size(X,2) ~= 2 || ...
        ~isequal(size(x),size(X)) || ...
        size(tri,2) ~= 3 || ...
        M == 0 || ...
        any(~isfinite(X(:))) || ...
        any(~isfinite(x(:))) || ...
        any(~isfinite(tri(:))) || ...
        any(tri(:)<1) || ...
        any(tri(:)>N) || ...
        any(tri(:)~=round(tri(:)))
    error('Geometria FEM incompatible o no finita.');
end

%% 3. VARIABLES POR ELEMENTO

Ftodos = zeros(2,2,M);

J = zeros(M,1);

lambdaMax = zeros(M,1);
lambdaMin = zeros(M,1);

GreenMax = zeros(M,1);
GreenNorma = zeros(M,1);

condicionF = zeros(M,1);

areaInicial = zeros(M,1);
areaFinal = zeros(M,1);

centros = zeros(M,2);

%% 4. CALCULAR GRADIENTE DE DEFORMACION

for e = 1:M

    ids = tri(e,:);

    P = X(ids,:);
    Q = x(ids,:);

    % Matrices de aristas de referencia y final.
    D0 = [
        (P(2,:)-P(1,:))', ...
        (P(3,:)-P(1,:))'
    ];

    D1 = [
        (Q(2,:)-Q(1,:))', ...
        (Q(3,:)-Q(1,:))'
    ];

    A0 = det(D0)/2;

    if A0 <= 1e-10
        error('Elemento de referencia %d invalido.',e);
    end

    % Gradiente total de deformacion:
    % F = dx/dX.

    F = D1/D0;

    Ftodos(:,:,e) = F;

    %% A. JACOBIANO

    Je = det(F);

    J(e) = Je;

    areaInicial(e) = A0;
    areaFinal(e) = Je*A0;

    %% B. ESTIRAMIENTOS PRINCIPALES

    valoresSingulares = svd(F);

    lambdaMax(e) = valoresSingulares(1);
    lambdaMin(e) = valoresSingulares(2);

    condicionF(e) = ...
        lambdaMax(e)/max(lambdaMin(e),eps);

    %% C. DEFORMACION DE GREEN-LAGRANGE

    Egreen = 0.5*(F'*F-eye(2));

    deformacionesPrincipales = ...
        0.5*(valoresSingulares.^2-1);

    GreenMax(e) = ...
        max(abs(deformacionesPrincipales));

    GreenNorma(e) = norm(Egreen,'fro');

    %% D. CENTROIDE FINAL

    centros(e,:) = mean(Q,1);

end

%% 5. CALIDAD DE TRIANGULOS

angulosOriginal = angulosMinimos(X,tri);
angulosFinales = angulosMinimos(x,tri);

%% 6. DESPLAZAMIENTOS NODALES

desplazamientos = x-X;

magnitudDesplazamiento = ...
    sqrt(sum(desplazamientos.^2,2));

%% 7. COMPROBAR CONTORNO SAGITAL

[indicesContorno,contornoDisponible] = ...
    construirContorno(malla,N);

nCruces = NaN;
paresCruces = zeros(0,2);

if contornoDisponible

    [nCruces,paresCruces] = ...
        contarCrucesContorno( ...
        x(indicesContorno,:));

end

%% 8. ESTADISTICAS GLOBALES

Jmin = min(J);
Jmax = max(J);

estiramientoMaximo = max(lambdaMax);
estiramientoMinimo = min(lambdaMin);

GreenMaxGlobal = max(GreenMax);

anguloMinFinal = min(angulosFinales);

nInvertidos = nnz(J <= 0);

nFueraJ = nnz( ...
    J < limJmin | J > limJmax);

nFueraLambda = nnz( ...
    lambdaMin < limLambdaMin | ...
    lambdaMax > limLambdaMax);

nFueraGreen = nnz(GreenMax > limGreen);

nAngulosPequenos = ...
    nnz(angulosFinales < limAngulo);

[~,indiceJcritico] = min(J);
[~,indiceGreenCritico] = max(GreenMax);

area0 = sum(areaInicial);
area1 = sum(areaFinal);

cambioArea = 100*(area1/area0-1);

%% 9. CRITERIOS EXPLORATORIOS

criterios = struct();

criterios.sinElementosInvertidos = ...
    nInvertidos == 0;

criterios.JDentroLimites = ...
    nFueraJ == 0;

criterios.estiramientosDentroLimites = ...
    nFueraLambda == 0;

criterios.GreenDentroLimites = ...
    nFueraGreen == 0;

criterios.angulosAceptables = ...
    nAngulosPequenos == 0;

criterios.contornoComprobado = ...
    contornoDisponible;

criterios.sinCrucesContorno = ...
    contornoDisponible && nCruces == 0;

criterios.cumpleCriteriosExploratorios = ...
    criterios.sinElementosInvertidos && ...
    criterios.JDentroLimites && ...
    criterios.estiramientosDentroLimites && ...
    criterios.GreenDentroLimites && ...
    criterios.angulosAceptables && ...
    criterios.sinCrucesContorno;

%% 10. SALIDA

diagnostico.elementos.F = Ftodos;

diagnostico.elementos.J = J;

diagnostico.elementos.lambdaMax = lambdaMax;
diagnostico.elementos.lambdaMin = lambdaMin;

diagnostico.elementos.GreenMax = GreenMax;
diagnostico.elementos.GreenNorma = GreenNorma;

diagnostico.elementos.condicionF = condicionF;

diagnostico.elementos.anguloMinimo = angulosFinales;

diagnostico.elementos.areaReferencia = areaInicial;
diagnostico.elementos.areaFinal = areaFinal;

diagnostico.elementos.centros = centros;

diagnostico.nodos.desplazamientos = desplazamientos;
diagnostico.nodos.magnitudes = magnitudDesplazamiento;

diagnostico.global.nNodos = N;
diagnostico.global.nElementos = M;

diagnostico.global.Jmin = Jmin;
diagnostico.global.Jmax = Jmax;

diagnostico.global.lambdaMax = estiramientoMaximo;
diagnostico.global.lambdaMin = estiramientoMinimo;

diagnostico.global.GreenMax = GreenMaxGlobal;

diagnostico.global.anguloMinOriginal = ...
    min(angulosOriginal);

diagnostico.global.anguloMinFinal = anguloMinFinal;

diagnostico.global.areaReferencia = area0;
diagnostico.global.areaFinalFirmada = area1;
diagnostico.global.cambioAreaPorcentaje = cambioArea;

diagnostico.global.desplazamientoMaximo = ...
    max(magnitudDesplazamiento);

diagnostico.global.elementosInvertidos = nInvertidos;
diagnostico.global.elementosFueraJ = nFueraJ;
diagnostico.global.elementosFueraLambda = nFueraLambda;
diagnostico.global.elementosFueraGreen = nFueraGreen;

diagnostico.global.elementosAnguloPequeno = ...
    nAngulosPequenos;

diagnostico.global.elementoJcritico = ...
    indiceJcritico;

diagnostico.global.elementoGreenCritico = ...
    indiceGreenCritico;

diagnostico.contorno.disponible = ...
    contornoDisponible;

diagnostico.contorno.indices = indicesContorno;
diagnostico.contorno.numeroCruces = nCruces;
diagnostico.contorno.paresCruces = paresCruces;

diagnostico.criterios = criterios;

diagnostico.limites = struct( ...
    'Jmin',limJmin, ...
    'Jmax',limJmax, ...
    'lambdaMin',limLambdaMin, ...
    'lambdaMax',limLambdaMax, ...
    'GreenMax',limGreen, ...
    'anguloMin',limAngulo);

diagnostico.graficos = struct();

%% 11. INFORME DE CONSOLA

if mostrarConsola

    fprintf('\n===== VALIDACION DEFORMACION LINGUAL =====\n');

    fprintf('Postura: %s\n',nombrePostura);

    fprintf('Nodos: %d\n',N);
    fprintf('Triangulos: %d\n',M);

    fprintf('\nDEFORMACION GEOMETRICA\n');

    fprintf('J minimo: %.6f\n',Jmin);
    fprintf('J maximo: %.6f\n',Jmax);

    fprintf('Lambda minima: %.6f\n',estiramientoMinimo);
    fprintf('Lambda maxima: %.6f\n',estiramientoMaximo);

    fprintf('Green-Lagrange maximo absoluto: %.6f\n', ...
        GreenMaxGlobal);

    fprintf('Cambio global de area sagital: %+.3f %%\n', ...
        cambioArea);

    fprintf('Desplazamiento nodal maximo: %.4f mm\n', ...
        diagnostico.global.desplazamientoMaximo);

    fprintf('\nCALIDAD DE MALLA\n');

    fprintf('Angulo minimo original: %.3f grados\n', ...
        diagnostico.global.anguloMinOriginal);

    fprintf('Angulo minimo deformado: %.3f grados\n', ...
        anguloMinFinal);

    fprintf('Triangulos invertidos: %d\n',nInvertidos);

    fprintf('Fuera de limites J: %d\n',nFueraJ);
    fprintf('Fuera de limites lambda: %d\n',nFueraLambda);
    fprintf('Fuera de limites Green: %d\n',nFueraGreen);
    fprintf('Triangulos con angulo pequeno: %d\n', ...
        nAngulosPequenos);

    if contornoDisponible
        fprintf('Cruces del contorno sagital: %d\n', ...
            nCruces);
    else
        fprintf('Contorno sagital: no disponible\n');
    end

    fprintf('\nDIAGNOSTICO EXPLORATORIO\n');

    if criterios.cumpleCriteriosExploratorios

        fprintf('Estado: dentro de los criterios configurados.\n');

    else

        fprintf(['Estado: requiere revision de uno ', ...
            'o mas criterios.\n']);

    end

    fprintf(['Nota: los limites son exploratorios, ', ...
        'no fisiologicos.\n']);

end

%% 12. VISUALIZACION

if graficar

    fig = figure( ...
        'Name',['Deformacion FEM - ',nombrePostura], ...
        'NumberTitle','off', ...
        'Color','w', ...
        'Toolbar','figure', ...
        'Menubar','figure', ...
        'WindowStyle','normal');

    t = tiledlayout(fig,2,2, ...
        'TileSpacing','compact', ...
        'Padding','compact');

    valores = {
        J
        lambdaMax
        GreenMax
        angulosFinales
    };

    titulos = {
        'Jacobian J = det(F)'
        'Estiramiento principal maximo'
        'Green-Lagrange maximo absoluto'
        'Angulo minimo por triangulo'
    };

    etiquetasColor = {
        'J'
        'Lambda max'
        'Deformacion'
        'Grados'
    };

    ejes = gobjects(4,1);

    for k = 1:4

        ax = nexttile(t);
        ejes(k) = ax;

        hold(ax,'on');

        patch(ax, ...
            'Faces',tri, ...
            'Vertices',x, ...
            'FaceVertexCData',valores{k}, ...
            'FaceColor','flat', ...
            'EdgeColor',[0.60 0.60 0.60], ...
            'LineWidth',0.35);

        colormap(ax,parula(256));

        cb = colorbar(ax);
        cb.Label.String = etiquetasColor{k};

        if mostrarReferencia && ...
                isfield(malla,'frontera')

            if isfield(malla.frontera,'superior')

                ids = malla.frontera.superior(:);

                plot(ax,X(ids,1),X(ids,2), ...
                    'k--','LineWidth',1);

            end

            if isfield(malla.frontera,'inferior')

                ids = malla.frontera.inferior(:);

                plot(ax,X(ids,1),X(ids,2), ...
                    'k--','LineWidth',1);

            end

        end

        axis(ax,'equal');
        grid(ax,'on');

        set(ax, ...
            'XDir','reverse', ...
            'YDir','normal');

        xlabel(ax,'Y (mm)');
        ylabel(ax,'Z (mm)');

        title(ax,titulos{k});

    end

    % Señalar el elemento de menor J.
    pCritico = centros(indiceJcritico,:);

    plot(ejes(1),pCritico(1),pCritico(2), ...
        'ko','MarkerFaceColor','w', ...
        'MarkerSize',7,'LineWidth',1.2);

    title(t, ...
        ['Diagnostico de deformacion - ',nombrePostura]);

    diagnostico.graficos.figura = fig;
    diagnostico.graficos.ejes = ejes;

end

end

%% FUNCION LOCAL: ANGULOS MINIMOS

function anguloMin = angulosMinimos(nodos,tri)

A = nodos(tri(:,1),:);
B = nodos(tri(:,2),:);
C = nodos(tri(:,3),:);

a = sqrt(sum((B-C).^2,2));
b = sqrt(sum((C-A).^2,2));
c = sqrt(sum((A-B).^2,2));

n = size(tri,1);
anguloMin = zeros(n,1);

validos = a > 1e-12 & ...
          b > 1e-12 & ...
          c > 1e-12;

av = a(validos);
bv = b(validos);
cv = c(validos);

cosA = (bv.^2+cv.^2-av.^2)./(2*bv.*cv);
cosB = (av.^2+cv.^2-bv.^2)./(2*av.*cv);

angA = acosd(max(-1,min(1,cosA)));
angB = acosd(max(-1,min(1,cosB)));

angC = 180-angA-angB;

anguloMin(validos) = ...
    min([angA angB angC],[],2);

end

%% FUNCION LOCAL: CONSTRUIR CONTORNO

function [ids,disponible] = construirContorno(malla,N)

ids = [];
disponible = false;

if ~isfield(malla,'frontera')
    return
end

f = malla.frontera;

if ~isfield(f,'inferior') || ...
        ~isfield(f,'superior') || ...
        ~isfield(f,'posterior')
    return
end

infIds = f.inferior(:);
supIds = f.superior(:);
postIds = f.posterior(:);

if numel(infIds)<2 || ...
        numel(supIds)<2 || ...
        numel(postIds)<2
    return
end

if infIds(end) ~= supIds(end) || ...
        infIds(1) ~= postIds(1) || ...
        supIds(1) ~= postIds(end)
    return
end

% Recorrido cerrado:
% inferior posterior -> punta ->
% superior posterior -> frontera posterior.

ids = [
    infIds
    flipud(supIds(1:end-1))
    flipud(postIds(2:end-1))
];

if any(ids<1) || any(ids>N) || ...
        numel(unique(ids)) ~= numel(ids)
    ids = [];
    return
end

disponible = true;

end

%% FUNCION LOCAL: CRUCES DE CONTORNO

function [nCruces,pares] = contarCrucesContorno(P)

n = size(P,1);

nCruces = 0;
pares = zeros(0,2);

% Segmentos cerrados del poligono.
Q = P([2:end 1],:);

for i = 1:n-1

    a = P(i,:);
    b = Q(i,:);

    for j = i+1:n

        % Segmentos vecinos comparten un vertice:
        % no se consideran autointerseccion.
        if j == i+1 || (i == 1 && j == n)
            continue
        end

        c = P(j,:);
        d = Q(j,:);

        if segmentosCruzan(a,b,c,d)

            nCruces = nCruces+1;
            pares(end+1,:) = [i j]; %#ok<AGROW>

        end

    end

end

end

%% FUNCION LOCAL: INTERSECCION ENTRE SEGMENTOS

function cruza = segmentosCruzan(a,b,c,d)

tol = 1e-9;

r = b-a;
s = d-c;
q = c-a;

% Prueba previa por cajas envolventes.
if max(min(a(1),b(1)),min(c(1),d(1))) > ...
        min(max(a(1),b(1)),max(c(1),d(1)))+tol || ...
   max(min(a(2),b(2)),min(c(2),d(2))) > ...
        min(max(a(2),b(2)),max(c(2),d(2)))+tol

    cruza = false;
    return

end

detRS = cruz2D(r,s);

escala = max(1,norm(r)*norm(s));

if abs(detRS) > tol*escala

    t = cruz2D(q,s)/detRS;
    u = cruz2D(q,r)/detRS;

    cruza = ...
        t >= -tol && t <= 1+tol && ...
        u >= -tol && u <= 1+tol;

else

    % Segmentos paralelos.
    % Detectar tambien solapamiento colineal.

    if abs(cruz2D(q,r)) > tol*max(1,norm(r))
        cruza = false;
        return
    end

    if norm(r) <= tol || norm(s) <= tol
        cruza = true;
        return
    end

    [~,eje] = max(abs(r));

    intervalo1 = sort([a(eje) b(eje)]);
    intervalo2 = sort([c(eje) d(eje)]);

    solapamiento = ...
        min(intervalo1(2),intervalo2(2))- ...
        max(intervalo1(1),intervalo2(1));

    cruza = solapamiento >= -tol;

end

end

%% FUNCION LOCAL: PRODUCTO CRUZ 2D

function c = cruz2D(a,b)

c = a(1)*b(2)-a(2)*b(1);

end

%% FUNCION LOCAL: OPCIONES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
