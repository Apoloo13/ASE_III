
function malla = crear_malla_lengua(lengua, opciones)
% CREAR_MALLA_LENGUA
% Malla triangular FEM 2D del perfil sagital.
%
% Permite refinamiento longitudinal gradual anterior.
% Mantiene la estructura nodal original:
%   - Columnas longitudinales
%   - Niveles de espesor constantes
%   - Punta como nodo unico final
%   - Nueve costillas como nodos dorsales exactos
%
% No modifica la geometria de lengua_ideal.
% No utiliza STL ni requiere toolboxes.
%
% OPCIONES:
% pasoLongitudinal  = 0.90 mm
% nivelesEspesor    = 5
% refinarAnterior   = true
% factorPasoAnterior = 0.60
% extensionAnterior = 0.35
% areaMinima        = 1e-10 mm^2
% anguloAdvertencia = 10 grados

%% 1. VALIDACION Y OPCIONES

if nargin < 1 || ~isstruct(lengua) || ...
        ~isfield(lengua,'sagital') || ...
        ~isfield(lengua,'costillas') || ...
        ~isfield(lengua,'punta')
    error('Se requiere la estructura de lengua_ideal.');
end

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

paso = leerOpcion( ...
    opciones,'pasoLongitudinal',0.90);

niveles = leerOpcion( ...
    opciones,'nivelesEspesor',5);

refinar = leerOpcion( ...
    opciones,'refinarAnterior',true);

factorAnterior = leerOpcion( ...
    opciones,'factorPasoAnterior',0.60);

extensionAnterior = leerOpcion( ...
    opciones,'extensionAnterior',0.35);

areaMin = leerOpcion( ...
    opciones,'areaMinima',1e-10);

anguloAviso = leerOpcion( ...
    opciones,'anguloAdvertencia',10);

validateattributes(paso,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(niveles,{'numeric'}, ...
    {'scalar','integer','>=',2});

validateattributes(factorAnterior,{'numeric'}, ...
    {'scalar','real','finite','>=',0.35,'<=',1});

validateattributes(extensionAnterior,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',1});

validateattributes(areaMin,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(anguloAviso,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<',60});

if ~isscalar(refinar) || ...
        ~(islogical(refinar) || ...
        (isnumeric(refinar) && ismember(refinar,[0 1])))
    error('refinarAnterior debe ser logico.');
end

refinar = logical(refinar);

%% 2. PERFIL ORIGINAL

campos = {'y','zSuperior','zInferior'};

for i = 1:numel(campos)
    if ~isfield(lengua.sagital,campos{i})
        error('Falta lengua.sagital.%s.',campos{i});
    end
end

if ~isfield(lengua.costillas,'centros')
    error('Faltan los centros de las costillas.');
end

y0 = lengua.sagital.y(:);
zSup0 = lengua.sagital.zSuperior(:);
zInf0 = lengua.sagital.zInferior(:);

costillas0 = lengua.costillas.centros;
punta0 = lengua.punta(:)';

if numel(y0) < 4 || ...
        numel(y0) ~= numel(zSup0) || ...
        numel(y0) ~= numel(zInf0) || ...
        any(~isfinite([y0;zSup0;zInf0])) || ...
        any(diff(y0) <= 0)
    error('Perfil sagital invalido.');
end

if ~isequal(size(costillas0),[9 3]) || ...
        any(~isfinite(costillas0(:)))
    error('Se requieren nueve costillas [9 x 3].');
end

if numel(punta0) ~= 3 || any(~isfinite(punta0))
    error('Coordenadas de punta invalidas.');
end

espesor0 = zSup0-zInf0;

if any(espesor0(1:end-1) <= 0) || ...
        abs(espesor0(end)) > 1e-7
    error('El perfil debe cerrarse en una punta unica.');
end

if abs(y0(end)-punta0(2)) > 1e-7 || ...
        abs(zSup0(end)-punta0(3)) > 1e-7
    error('La punta no coincide con el perfil.');
end

%% 3. NUEVE COSTILLAS

yCostillas = costillas0(:,2);

if any(yCostillas <= y0(1)) || ...
        any(yCostillas >= y0(end)) || ...
        any(diff(yCostillas) <= 0)
    error('Posiciones longitudinales de costillas invalidas.');
end

zDorsal = interp1( ...
    y0,zSup0,yCostillas,'pchip');

if max(abs(zDorsal-costillas0(:,3))) > 1e-3
    error('Los marcadores no coinciden con el dorso.');
end

%% 4. SECCIONES LONGITUDINALES

% Anclas obligatorias:
% posterior, nueve costillas y punta.

anclas = [y0(1);yCostillas;y0(end)];

yPosterior = y0(1);
yPunta = y0(end);

longitudTotal = yPunta-yPosterior;

nIntervalos = numel(anclas)-1;

tramos = cell(nIntervalos,1);

for i = 1:nIntervalos

    ya = anclas(i);
    yb = anclas(i+1);

    if ~refinar

        % Mallado original uniforme por intervalo.
        nDiv = max(1,ceil((yb-ya)/paso));

        yy = linspace(ya,yb,nDiv+1)';

    else

        % Refinamiento mediante densidad longitudinal
        % variable con transicion suave.

        yMuestra = linspace(ya,yb,201)';

        % Distancia normalizada desde la punta.
        s = (yPunta-yMuestra)/longitudTotal;

        % Smoothstep:
        % 0 en punta, 1 fuera de zona anterior.
        q = min(max(s/extensionAnterior,0),1);
        q = q.^2.*(3-2*q);

        factorLocal = factorAnterior + ...
            (1-factorAnterior)*q;

        pasoLocal = paso*factorLocal;

        % Coordenada acumulada de densidad.
        acumulada = cumtrapz( ...
            yMuestra,1./pasoLocal);

        nDiv = max(1,ceil(acumulada(end)));

        % Secciones equiespaciadas en la coordenada
        % acumulada, no en Y.
        yy = interp1( ...
            acumulada,yMuestra, ...
            linspace(0,acumulada(end),nDiv+1)', ...
            'linear');

        % Mantener las anclas exactamente.
        yy(1) = ya;
        yy(end) = yb;

    end

    % No duplicar la columna inicial del
    % siguiente intervalo.
    tramos{i} = yy(1:end-1);

end

yColumnas = vertcat(tramos{:});

nColumnas = numel(yColumnas);

if any(diff(yColumnas) <= 0)
    error('Las columnas longitudinales no son crecientes.');
end

%% 5. PERFILES EN COLUMNAS

zSup = interp1( ...
    y0,zSup0,yColumnas,'pchip');

zInf = interp1( ...
    y0,zInf0,yColumnas,'pchip');

columnasCostillas = zeros(9,1);

for i = 1:9

    [distancia,col] = min( ...
        abs(yColumnas-yCostillas(i)));

    if distancia > 1e-8
        error('No se encontro la costilla %d.',i);
    end

    if abs(zSup(col)-costillas0(i,3)) > 1e-3
        error('Error de posicion dorsal en costilla %d.',i);
    end

    zSup(col) = costillas0(i,3);
    columnasCostillas(i) = col;

end

if any(zSup <= zInf)
    error('Existen secciones de espesor no positivo.');
end

%% 6. GENERAR NODOS

eta = linspace(0,1,niveles)';

nNodos = nColumnas*niveles+1;

nodos = zeros(nNodos,2);

for i = 1:nColumnas

    ids = (i-1)*niveles+(1:niveles);

    nodos(ids,1) = yColumnas(i);

    nodos(ids,2) = zInf(i) + ...
        eta*(zSup(i)-zInf(i));

end

% Punta como nodo material unico.
indicePunta = nNodos;

nodos(indicePunta,:) = [
    yPunta,zSup0(end)
];

%% 7. GENERAR TRIANGULOS

nElementos = ...
    2*(nColumnas-1)*(niveles-1) + ...
    (niveles-1);

elementos = zeros(nElementos,3);

k = 0;

for i = 1:nColumnas-1

    for j = 1:niveles-1

        a = (i-1)*niveles+j;
        b = a+1;

        c = i*niveles+j;
        d = c+1;

        k = k+1;
        elementos(k,:) = [a c d];

        k = k+1;
        elementos(k,:) = [a d b];

    end

end

% Abanico triangular de la ultima columna
% hacia el nodo unico de la punta.

for j = 1:niveles-1

    k = k+1;

    a = (nColumnas-1)*niveles+j;
    b = a+1;

    elementos(k,:) = [a indicePunta b];

end

%% 8. CALIDAD GEOMETRICA

a = nodos(elementos(:,1),:);
b = nodos(elementos(:,2),:);
c = nodos(elementos(:,3),:);

areas = 0.5*( ...
    (b(:,1)-a(:,1)).*(c(:,2)-a(:,2)) - ...
    (b(:,2)-a(:,2)).*(c(:,1)-a(:,1)));

if any(~isfinite(areas)) || any(areas <= areaMin)
    error('Triangulos degenerados o invertidos.');
end

% Longitudes de aristas.
la = vecnorm(b-c,2,2);
lb = vecnorm(c-a,2,2);
lc = vecnorm(a-b,2,2);

% Angulos internos.
cosA = (lb.^2+lc.^2-la.^2)./(2*lb.*lc);
cosB = (la.^2+lc.^2-lb.^2)./(2*la.*lc);

angA = acosd(max(-1,min(1,cosA)));
angB = acosd(max(-1,min(1,cosB)));

angulos = min([
    angA,angB,180-angA-angB
],[],2);

anguloMinimo = min(angulos);

if anguloMinimo < anguloAviso
    warning('crear_malla_lengua:AnguloPequeno', ...
        'Angulo minimo %.2f grados.',anguloMinimo);
end

%% 9. FRONTERAS

frontera.inferior = [
    (1:niveles:nColumnas*niveles)';
    indicePunta
];

frontera.superior = [
    (niveles:niveles:nColumnas*niveles)';
    indicePunta
];

frontera.posterior = (1:niveles)';
frontera.punta = indicePunta;

%% 10. SEGUIMIENTO

indicesCostillas = columnasCostillas*niveles;

seguimiento.puntaIndice = indicePunta;
seguimiento.puntaYZ = nodos(indicePunta,:);

seguimiento.costillasIndices = indicesCostillas;
seguimiento.costillasYZ = ...
    nodos(indicesCostillas,:);

%% 11. DIAGNOSTICO

areaPerfil = trapz(y0,espesor0);
areaMalla = sum(areas);

if areaPerfil <= 0
    error('Area original invalida.');
end

calidad.areas = areas;
calidad.areaTotal = areaMalla;
calidad.areaPerfilOriginal = areaPerfil;

calidad.errorRelativoArea = ...
    abs(areaMalla-areaPerfil)/areaPerfil;

calidad.anguloMinimoGrados = anguloMinimo;
calidad.angulosMinimosGrados = angulos;

calidad.todosOrientados = all(areas > 0);

% Informacion adicional de refinamiento.
sElementos = (yPunta- ...
    (a(:,1)+b(:,1)+c(:,1))/3)/longitudTotal;

mascaraAnterior = sElementos <= extensionAnterior;

calidad.nElementosAnteriores = ...
    nnz(mascaraAnterior);

calidad.anguloMinimoAnterior = ...
    min(angulos(mascaraAnterior));

calidad.areaMinima = min(areas);
calidad.areaMaxima = max(areas);

%% 12. SALIDA

malla.nodos = nodos;
malla.elementos = elementos;

malla.frontera = frontera;
malla.seguimiento = seguimiento;
malla.calidad = calidad;

malla.referencia.yColumnas = yColumnas;
malla.referencia.nivelesEspesor = niveles;

malla.referencia.pasoLongitudinal = paso;

malla.referencia.refinarAnterior = refinar;

malla.referencia.factorPasoAnterior = ...
    factorAnterior;

malla.referencia.extensionAnterior = ...
    extensionAnterior;

malla.referencia.sistema = ...
    'Sagital (Y,Z), coordenadas de lengua_ideal';

end

%% FUNCION LOCAL

function valor = leerOpcion(opciones,nombre,defecto)

if isfield(opciones,nombre)
    valor = opciones.(nombre);
else
    valor = defecto;
end

end
