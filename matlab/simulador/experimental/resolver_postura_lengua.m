
function estado = resolver_postura_lengua(modelo, objetivo)
% RESOLVER_POSTURA_LENGUA
% Equilibrio FEM 2D con objetivos de punta y activacion interna.
%
% objetivo.puntaYZ      : [Y Z] en mm
% objetivo.modo         : 'prescrito' o 'penalizado'
% objetivo.componentes  : [controlY controlZ]
% objetivo.rigidezPunta : N/mm, para modo penalizado
% objetivo.activacion   : estructura opcional con:
%       anterior [dorsal ventral]
%       central  [dorsal ventral]
%
% Las activaciones producen fuerzas internas equivalentes.
% No incluye contacto ni comportamiento no lineal.

%% 1. VALIDACION

if ~isstruct(modelo) || ...
        ~isfield(modelo,'malla') || ...
        ~isfield(modelo,'matrices')
    error('Modelo FEM invalido.');
end

if nargin < 2 || ~isstruct(objetivo) || ...
        ~isscalar(objetivo) || ...
        ~isfield(objetivo,'puntaYZ')
    error('Debes proporcionar objetivo.puntaYZ.');
end

malla = modelo.malla;

nodos0 = malla.nodos;
elementos = malla.elementos;

K = modelo.matrices.Ktotal;

N = size(nodos0,1);
nGDL = 2*N;

if ~isequal(size(K),[nGDL nGDL])
    error('La matriz de rigidez no coincide con la malla.');
end

puntaObjetivo = objetivo.puntaYZ;

validateattributes(puntaObjetivo,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

puntaObjetivo = reshape(puntaObjetivo,1,2);

if isfield(objetivo,'modo')
    modo = lower(string(objetivo.modo));
else
    modo = "prescrito";
end

if ~isscalar(modo) || ...
        ~ismember(modo,["prescrito","penalizado"])
    error('Modo de control invalido.');
end

if isfield(objetivo,'componentes')
    componentes = objetivo.componentes;
else
    componentes = [true true];
end

if ~(islogical(componentes) || isnumeric(componentes)) || ...
        numel(componentes) ~= 2 || ...
        ~all(ismember(double(componentes(:)),[0 1]))
    error('componentes debe contener dos valores logicos.');
end

componentes = logical(reshape(componentes,1,2));

if ~any(componentes)
    error('No se seleccionaron componentes de control.');
end

%% 2. FUERZAS DE ACTIVACION INTERNA

inicio = tic;

fActiva = zeros(nGDL,1);
cargaActiva = [];

if isfield(objetivo,'activacion') && ...
        ~isempty(objetivo.activacion)

    cargaActiva = calcular_activacion_lingual( ...
        modelo,objetivo.activacion);

    fActiva = cargaActiva.f(:);

    if numel(fActiva) ~= nGDL || ...
            any(~isfinite(fActiva))
        error('Fuerzas activas incompatibles con el FEM.');
    end

end

%% 3. PREPARAR OBJETIVO DE PUNTA

indicePunta = malla.seguimiento.puntaIndice;

puntaInicial = nodos0(indicePunta,:);

deltaObjetivo = puntaObjetivo-puntaInicial;

gdlPunta = [
    2*indicePunta-1, ...
    2*indicePunta
];

gdlControl = gdlPunta(componentes);

deltaControl = deltaObjetivo(componentes)';

u = zeros(nGDL,1);

fuerzaControl = zeros(1,2);

energiaObjetivo = 0;

%% 4. RESOLVER EQUILIBRIO

switch modo

    case "prescrito"

        % Desplazamientos impuestos de la punta.
        u(gdlControl) = deltaControl;

        libres = true(nGDL,1);
        libres(gdlControl) = false;

        Kll = K(libres,libres);
        Klc = K(libres,gdlControl);

        % Equilibrio con fuerzas activas.
        u(libres) = Kll \ ( ...
            fActiva(libres) - ...
            Klc*u(gdlControl));

        % Fuerza externa requerida para imponer
        % los desplazamientos prescritos.
        reacciones = K*u-fActiva;

        fuerzaControl(componentes) = ...
            reacciones(gdlControl);

        residuoEquilibrio = norm( ...
            reacciones(libres),inf);

    case "penalizado"

        if isfield(objetivo,'rigidezPunta')
            rigidez = objetivo.rigidezPunta;
        else
            rigidez = 0.1;
        end

        if isscalar(rigidez)
            rigidez = repmat(rigidez,1,2);
        end

        validateattributes(rigidez,{'numeric'}, ...
            {'vector','numel',2,'real','finite','positive'});

        rigidez = reshape(rigidez,1,2);

        rigidezControl = rigidez(componentes)';

        % Matriz de rigidez del objetivo.
        Kobjetivo = sparse( ...
            gdlControl,gdlControl,rigidezControl, ...
            nGDL,nGDL);

        fObjetivo = zeros(nGDL,1);

        fObjetivo(gdlControl) = ...
            rigidezControl.*deltaControl;

        % Fuerzas internas + objetivo articulatorio.
        Ksistema = K+Kobjetivo;

        fTotal = fActiva+fObjetivo;

        u = Ksistema\fTotal;

        residuoEquilibrio = norm( ...
            Ksistema*u-fTotal,inf);

        errorControl = ...
            deltaControl-u(gdlControl);

        fuerzaControl(componentes) = ...
            rigidezControl.*errorControl;

        energiaObjetivo = 0.5*sum( ...
            rigidezControl.*errorControl.^2);

        reacciones = K*u-fActiva;

end

tiempoResolucion = toc(inicio);

%% 5. GEOMETRIA DEFORMADA

desplazamientos = reshape(u,2,[])';

nodosFinales = nodos0+desplazamientos;

puntaFinal = nodosFinales(indicePunta,:);

indicesCostillas = ...
    malla.seguimiento.costillasIndices;

costillasFinales = ...
    nodosFinales(indicesCostillas,:);

%% 6. VERIFICAR ELEMENTOS

a0 = nodos0(elementos(:,1),:);
b0 = nodos0(elementos(:,2),:);
c0 = nodos0(elementos(:,3),:);

areas0 = 0.5*( ...
    (b0(:,1)-a0(:,1)).*(c0(:,2)-a0(:,2)) - ...
    (b0(:,2)-a0(:,2)).*(c0(:,1)-a0(:,1)));

a = nodosFinales(elementos(:,1),:);
b = nodosFinales(elementos(:,2),:);
c = nodosFinales(elementos(:,3),:);

areasFinales = 0.5*( ...
    (b(:,1)-a(:,1)).*(c(:,2)-a(:,2)) - ...
    (b(:,2)-a(:,2)).*(c(:,1)-a(:,1)));

if any(areas0 <= 1e-10)
    error('La malla original contiene elementos invalidos.');
end

if any(~isfinite(areasFinales)) || ...
        any(areasFinales <= 1e-10)
    error(['La postura produce elementos invalidos. ', ...
        'Reduce el objetivo o la activacion.']);
end

variacionArea = ...
    (areasFinales-areas0)./areas0;

%% 7. ENERGIAS Y DIAGNOSTICO

Ke = modelo.matrices.Kelastica;
Ka = modelo.matrices.Kanclajes;

% Energia cuadratica pasiva.
energiaElastica = 0.5*u'*Ke*u;

energiaAnclajes = 0.5*u'*Ka*u;

% Trabajo de las fuerzas activas equivalentes.
trabajoActivo = u'*fActiva;

% Energia cuadratica compatible con el codigo anterior.
energiaTotal = energiaElastica + ...
    energiaAnclajes + energiaObjetivo;

% Potencial reducido: omite la constante asociada
% a la deformacion activa prescrita.
potencialTotal = energiaTotal-trabajoActivo;

errorPunta = puntaObjetivo-puntaFinal;

errorControlado = norm( ...
    errorPunta(componentes));

magnitudes = sqrt(sum( ...
    desplazamientos.^2,2));

%% 8. SALIDA

estado.u = u;

estado.desplazamientos = desplazamientos;
estado.nodos = nodosFinales;

estado.puntaYZ = puntaFinal;
estado.costillasYZ = costillasFinales;

estado.objetivo = objetivo;
estado.modo = modo;
estado.componentesControladas = componentes;

estado.fuerzaControlPunta = fuerzaControl;
estado.reacciones = reacciones;

% Informacion de activacion distribuida.
estado.fuerzaActiva = fActiva;
estado.cargaActiva = cargaActiva;

estado.diagnostico.errorPuntaYZ = errorPunta;
estado.diagnostico.errorControlado = ...
    errorControlado;

estado.diagnostico.residuoEquilibrio = ...
    residuoEquilibrio;

estado.diagnostico.desplazamientoMaximo = ...
    max(magnitudes);

estado.diagnostico.areaMinima = ...
    min(areasFinales);

estado.diagnostico.variacionAreaMaxima = ...
    max(abs(variacionArea));

estado.diagnostico.energiaElastica = ...
    energiaElastica;

estado.diagnostico.energiaAnclajes = ...
    energiaAnclajes;

estado.diagnostico.energiaObjetivo = ...
    energiaObjetivo;

estado.diagnostico.trabajoActivo = ...
    trabajoActivo;

estado.diagnostico.energiaTotal = energiaTotal;
estado.diagnostico.potencialTotal = potencialTotal;

estado.diagnostico.tiempoResolucion = ...
    tiempoResolucion;

end
