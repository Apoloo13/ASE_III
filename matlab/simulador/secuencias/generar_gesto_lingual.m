
function gesto = generar_gesto_lingual(tipo, opciones)
% GENERAR_GESTO_LINGUAL
% Secuencia cuasiestatica de objetivos FEM.
%
% Tipos disponibles:
%   "solo_punta"
%   "apice_dorsal"
%   "apice_ventral"
%   "apice_dorsal_lamina_ventral"
%   "apice_ventral_lamina_dorsal"
%   "cuerpo_dorsal"
%   "personalizado"
%
% ENTRADA:
%   tipo
%   opciones.puntaInicioYZ = [0 0]
%   opciones.puntaFinalYZ  = [0 3]
%   opciones.duracion      = 1.0
%   opciones.nMuestras     = 9
%   opciones.fraccionSubida = 0.35
%   opciones.fraccionBajada = 0.35
%
% Para tipo "personalizado":
%   opciones.intensidades = [AD AV LD LV CD CV]
%
% SALIDA:
%   gesto.tiempo
%   gesto.factor
%   gesto.objetivos
%   gesto.indicePico
%   gesto.intensidadesPico
%
% No calcula FEM. No representa dinamica muscular.

%% 1. OPCIONES

if nargin < 1
    error('Especifica el tipo de gesto.');
end

if nargin < 2 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

tipo = lower(string(tipo));

if ~isscalar(tipo) || ismissing(tipo)
    error('Tipo de gesto invalido.');
end

puntaInicio = leer( ...
    opciones,'puntaInicioYZ',[0 0]);

puntaFinal = leer( ...
    opciones,'puntaFinalYZ',[0 3]);

duracion = leer(opciones,'duracion',1.0);
nMuestras = leer(opciones,'nMuestras',9);

fraccionSubida = leer( ...
    opciones,'fraccionSubida',0.35);

fraccionBajada = leer( ...
    opciones,'fraccionBajada',0.35);

validateattributes(puntaInicio,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

validateattributes(puntaFinal,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

validateattributes(duracion,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(nMuestras,{'numeric'}, ...
    {'scalar','integer','>=',5,'<=',200});

validateattributes(fraccionSubida,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<',1});

validateattributes(fraccionBajada,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<',1});

if fraccionSubida+fraccionBajada >= 1
    error('Debe existir una fase de sostenimiento.');
end

puntaInicio = reshape(puntaInicio,1,2);
puntaFinal = reshape(puntaFinal,1,2);

%% 2. DEFINIR ACTIVACIONES MAXIMAS

% Orden:
% AD: Apice dorsal
% AV: Apice ventral
% LD: Lamina dorsal
% LV: Lamina ventral
% CD: Cuerpo dorsal
% CV: Cuerpo ventral

switch tipo

    case "solo_punta"
        aMax = [0 0 0 0 0 0];

    case "apice_dorsal"
        aMax = [0.030 0 0 0 0 0];

    case "apice_ventral"
        aMax = [0 0.025 0 0 0 0];

    case "apice_dorsal_lamina_ventral"
        aMax = [0.030 0 0 0.020 0 0];

    case "apice_ventral_lamina_dorsal"
        aMax = [0 0.025 0.025 0 0 0];

    case "cuerpo_dorsal"
        aMax = [0 0 0 0 0.030 0];

    case "personalizado"
        if ~isfield(opciones,'intensidades')
            error('Faltan intensidades personalizadas.');
        end

        aMax = opciones.intensidades;

    otherwise
        error('Tipo de gesto desconocido: %s', ...
            char(tipo));

end

validateattributes(aMax,{'numeric'}, ...
    {'vector','numel',6,'real','finite', ...
    '>=',0,'<=',0.10});

aMax = reshape(aMax,1,6);

%% 3. DEFINIR PARCHES MATERIALES

% Centros longitudinales normalizados.
centros = leer(opciones,'centros', ...
    [0.045 0.045 0.21 0.21 0.52 0.52]);

% Radios longitudinales.
radios = leer(opciones,'radios', ...
    [0.07 0.07 0.11 0.11 0.17 0.17]);

validateattributes(centros,{'numeric'}, ...
    {'vector','numel',6,'real','finite', ...
    '>=',0,'<=',1});

validateattributes(radios,{'numeric'}, ...
    {'vector','numel',6,'real','finite', ...
    '>',0,'<=',0.30});

centros = reshape(centros,1,6);
radios = reshape(radios,1,6);

capas = [ ...
    "dorsal","ventral", ...
    "dorsal","ventral", ...
    "dorsal","ventral"
];

%% 4. PERFIL TEMPORAL

tiempo = linspace(0,duracion,nMuestras)';

fase = tiempo/duracion;

factor = zeros(nMuestras,1);

inicioBajada = 1-fraccionBajada;

for k = 1:nMuestras

    u = fase(k);

    if u <= fraccionSubida

        v = u/fraccionSubida;
        factor(k) = suaveQuintico(v);

    elseif u < inicioBajada

        factor(k) = 1;

    else

        v = (1-u)/fraccionBajada;
        factor(k) = suaveQuintico(v);

    end

end

% Evitar ruido numerico en extremos.
factor(1) = 0;
factor(end) = 0;

%% 5. GENERAR OBJETIVOS FEM

objetivos = cell(nMuestras,1);

posicionesPunta = zeros(nMuestras,2);
activacionesTiempo = zeros(nMuestras,6);

for k = 1:nMuestras

    alfa = factor(k);

    punta = puntaInicio + ...
        alfa*(puntaFinal-puntaInicio);

    intensidades = alfa*aMax;

    posicionesPunta(k,:) = punta;
    activacionesTiempo(k,:) = intensidades;

    %% A. CONSTRUIR ACTIVACION

    if ~any(intensidades > 0)

        % Reposo sin activacion, compatible con
        % calcular_activacion_lingual.
        act = struct( ...
            'apice',[0 0], ...
            'lamina',[0 0], ...
            'cuerpo',[0 0]);

    else

        indicesActivos = find(intensidades > 0);

        parches = repmat(struct( ...
            'centro',0, ...
            'radio',0, ...
            'capa',"dorsal", ...
            'intensidad',0), ...
            1,numel(indicesActivos));

        for j = 1:numel(indicesActivos)

            id = indicesActivos(j);

            parches(j).centro = centros(id);
            parches(j).radio = radios(id);
            parches(j).capa = capas(id);

            parches(j).intensidad = ...
                intensidades(id);

        end

        act = struct('parches',parches);

    end

    %% B. OBJETIVO FEM

    obj = struct();

    obj.puntaYZ = punta;
    obj.modo = 'prescrito';
    obj.componentes = [true true];

    obj.activacion = act;

    objetivos{k} = obj;

end

%% 6. SALIDA

[~,indicePico] = min(abs(fase-0.5));

gesto.tipo = tipo;

gesto.tiempo = tiempo;
gesto.fase = fase;
gesto.factor = factor;

gesto.objetivos = objetivos;

gesto.posicionesPunta = posicionesPunta;
gesto.activacionesTiempo = activacionesTiempo;

gesto.indicePico = indicePico;
gesto.intensidadesPico = aMax;

gesto.puntaInicioYZ = puntaInicio;
gesto.puntaFinalYZ = puntaFinal;

gesto.parametros = opciones;

end

%% FUNCION LOCAL: TRANSICION QUINTICA

function q = suaveQuintico(x)

x = max(0,min(1,x));

% Smoothstep de quinto orden:
% valor, velocidad y aceleracion continuos
% con derivadas nulas en los extremos.

q = 6*x.^5-15*x.^4+10*x.^3;

end

%% FUNCION LOCAL: OPCIONES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
