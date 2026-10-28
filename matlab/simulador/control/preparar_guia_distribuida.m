
function guia = preparar_guia_distribuida(malla,guia,opciones)
% PREPARAR_GUIA_DISTRIBUIDA
%
% Precalcula soportes materiales de objetivos sagitales.
%
% Opciones:
%   modo = 'puntual' o 'distribuido'
%   radio = 0.07
%   fraccionDistribuida = 0.75
%   excluirPunta = true
%
% radio se expresa en coordenada longitudinal s:
%   s=0: punta
%   s=1: extremo posterior truncado
%
% Cada objetivo distribuye su influencia sobre nodos
% vecinos de la misma superficie (dorso o vientre).
%
% Los pesos consideran la longitud material asociada
% a cada nodo y se normalizan para sumar 1.
%
% No modifica la malla ni calcula fuerzas.

%% 1. OPCIONES

if nargin < 3 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('Opciones de distribucion invalidas.');
end

modo = lower(string(leer( ...
    opciones,'modo','puntual')));

radio = leer(opciones,'radio',0.07);

fraccion = leer( ...
    opciones,'fraccionDistribuida',0.75);

excluirPunta = leer( ...
    opciones,'excluirPunta',true);

if ~isscalar(modo) || ...
        ~ismember(modo,["puntual","distribuido"])
    error('Modo de guiado invalido.');
end

validateattributes(radio,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<=',0.30});

validateattributes(fraccion,{'numeric'}, ...
    {'scalar','real','finite','>=',0,'<=',1});

if ~isscalar(excluirPunta) || ...
        ~(islogical(excluirPunta) || ...
        (isnumeric(excluirPunta) && ...
        ismember(excluirPunta,[0 1])))
    error('excluirPunta debe ser logico.');
end

%% 2. VALIDACION

if ~isstruct(guia) || ...
        ~isscalar(guia) || ...
        ~isfield(guia,'objetivos')
    error('Estructura de guia invalida.');
end

if ~isfield(malla,'frontera') || ...
        ~isfield(malla,'seguimiento')
    error('Faltan referencias de la malla.');
end

X = double(malla.nodos);

N = size(X,1);

indicePunta = malla.seguimiento.puntaIndice;

yPunta = X(indicePunta,1);
yPosterior = min(X(:,1));

L = yPunta-yPosterior;

if L <= 0
    error('Longitud lingual invalida.');
end

%% 3. PRECALCULAR SUPERFICIES

superficies = cell(2,1);

superficies{1} = prepararSuperficie( ...
    malla.frontera.superior,X, ...
    yPunta,L,indicePunta,excluirPunta);

superficies{2} = prepararSuperficie( ...
    malla.frontera.inferior,X, ...
    yPunta,L,indicePunta,excluirPunta);

%% 4. PREPARAR OBJETIVOS

for i = 1:numel(guia.objetivos)

    a = guia.objetivos(i);

    % Eliminar cualquier soporte preparado previamente.
    guia.objetivos(i).soporte = [];

    if modo == "puntual" || fraccion == 0
        continue
    end

    if ~isfield(a,'s') || ...
            ~isfield(a,'superficie')
        error('Objetivo %d incompleto.',i);
    end

    validateattributes(a.s,{'numeric'}, ...
        {'scalar','real','finite','>',0,'<',1});

    switch lower(string(a.superficie))

        case "dorso"
            superficie = superficies{1};

        case "vientre"
            superficie = superficies{2};

        otherwise
            error('Superficie invalida en objetivo %d.',i);

    end

    %% A. DISTANCIA LONGITUDINAL

    distancia = abs(superficie.s-a.s);

    q = distancia/radio;

    %% B. VENTANA COMPACTA SUAVE

    % Funcion con valor y pendiente nulos
    % en el borde del soporte.
    %
    % w = (1-q^2)^2, para q < 1.

    ventana = zeros(size(q));

    dentro = q < 1;

    ventana(dentro) = ...
        (1-q(dentro).^2).^2;

    %% C. CORRECCION POR ESPACIADO DE MALLA

    pesoBruto = ...
        ventana.*superficie.longitudNodal;

    activos = pesoBruto > 1e-14;

    if ~any(activos)

        error(['Objetivo %d sin nodos en su ', ...
            'radio de influencia. Aumenta radio.'],i);

    end

    pesos = pesoBruto(activos);

    pesos = pesos/sum(pesos);

    ids = superficie.ids(activos);

    %% D. GUARDAR SOPORTE

    soporte = struct();

    soporte.ids = ids(:);

    soporte.pesos = pesos(:);

    soporte.fraccionDistribuida = fraccion;

    soporte.radio = radio;

    soporte.numeroNodos = numel(ids);

    guia.objetivos(i).soporte = soporte;

end

%% 5. INFORMACION GLOBAL

guia.distribucion.modo = modo;
guia.distribucion.radio = radio;
guia.distribucion.fraccionDistribuida = fraccion;
guia.distribucion.longitud_mm = L;
guia.distribucion.radioAproximado_mm = radio*L;

end

%% PREPARAR UNA SUPERFICIE

function superficie = prepararSuperficie( ...
    ids,X,yPunta,L,indicePunta,excluirPunta)

ids = ids(:);

N = size(X,1);

if numel(ids) < 3 || ...
        any(ids < 1) || any(ids > N) || ...
        numel(unique(ids)) ~= numel(ids)
    error('Frontera superficial invalida.');
end

P = X(ids,:);

%% A. LONGITUD DE SEGMENTOS

dP = diff(P,1,1);

longitudes = sqrt(sum(dP.^2,2));

if any(longitudes <= 1e-10)
    error('Segmentos degenerados en frontera.');
end

%% B. LONGITUD MATERIAL ASOCIADA A CADA NODO

n = numel(ids);

longitudNodal = zeros(n,1);

longitudNodal(1) = longitudes(1)/2;

longitudNodal(end) = longitudes(end)/2;

longitudNodal(2:end-1) = ...
    0.5*(longitudes(1:end-1)+ ...
         longitudes(2:end));

%% C. COORDENADA NORMALIZADA

s = (yPunta-P(:,1))/L;

%% D. EXCLUIR LA PUNTA PRESCRITA

if excluirPunta

    mascara = ids ~= indicePunta;

    ids = ids(mascara);
    s = s(mascara);

    longitudNodal = longitudNodal(mascara);

end

superficie.ids = ids;
superficie.s = s;

superficie.longitudNodal = longitudNodal;

end

%% OPCIONES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
