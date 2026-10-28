
function pose = definir_postura_lingual(malla,config)
% DEFINIR_POSTURA_LINGUAL
% Define objetivos materiales para una postura FEM.
%
% config.puntaYZ = [Y Z]
% config.deltaAnguloApice_deg = cambio angular adicional
% config.pesoAngulo = prioridad angular
%
% config.dorso:
%   [s, Y_obj, Z_obj, peso]
%
% config.vientre:
%   [s, Y_obj, Z_obj, peso]
%
% NaN permite dejar libre Y o Z.
% s=0: punta; s=1: extremo posterior truncado.
%
% Los objetivos son suaves, excepto la punta.
% No calcula deformaciones.

if nargin < 2 || isempty(config)
    config = struct();
end

puntaYZ = leer(config,'puntaYZ',[0 3]);

deltaAngulo = leer( ...
    config,'deltaAnguloApice_deg',NaN);

pesoAngulo = leer(config,'pesoAngulo',1);

dorso = leer(config,'dorso',zeros(0,4));
vientre = leer(config,'vientre',zeros(0,4));

validateattributes(puntaYZ,{'numeric'}, ...
    {'vector','numel',2,'real','finite'});

validateattributes(pesoAngulo,{'numeric'}, ...
    {'scalar','real','finite','positive'});

if ~isscalar(deltaAngulo) || ...
        ~isnumeric(deltaAngulo) || ...
        ~isreal(deltaAngulo) || ...
        isinf(deltaAngulo)
    error('Angulo apical invalido.');
end

validarTabla(dorso,'dorso');
validarTabla(vientre,'vientre');

pose.puntaYZ = reshape(puntaYZ,1,2);

pose.apice.deltaAngulo_deg = deltaAngulo;
pose.apice.peso = pesoAngulo;

% Dos marcadores dorsales interiores.
% Evitan calcular la tangente en la punta singular.
pose.apice.anterior = ...
    crearAncla(malla,'dorso',0.025);

pose.apice.posterior = ...
    crearAncla(malla,'dorso',0.10);

pose.objetivos = struct( ...
    'superficie',{}, ...
    's',{}, ...
    'ids',{}, ...
    'coef',{}, ...
    'referencia',{}, ...
    'meta',{}, ...
    'peso',{});

tablas = {dorso,vientre};
superficies = {'dorso','vientre'};

for j = 1:2

    T = tablas{j};

    for i = 1:size(T,1)

        ancla = crearAncla( ...
            malla,superficies{j},T(i,1));

        ancla.meta = T(i,2:3);
        ancla.peso = T(i,4);

        pose.objetivos(end+1) = ancla;

    end

end

pose.numeroObjetivos = numel(pose.objetivos);

pose.descripcion = ...
    'Postura guiada mediante objetivos materiales FEM';

end

%% ANCLA MATERIAL EN EL CONTORNO

function a = crearAncla(malla,superficie,s)

if ~isscalar(s) || ~isfinite(s) || ...
        s <= 0 || s >= 1
    error('La coordenada s debe estar entre 0 y 1.');
end

nodos = malla.nodos;
niveles = malla.referencia.nivelesEspesor;

yColumnas = malla.referencia.yColumnas(:);
nColumnas = numel(yColumnas);

idPunta = malla.seguimiento.puntaIndice;

if size(nodos,1) ~= nColumnas*niveles+1
    error('Numeracion FEM incompatible.');
end

switch superficie

    case 'dorso'
        indices = (niveles:niveles: ...
            nColumnas*niveles)';

    case 'vientre'
        indices = (1:niveles: ...
            nColumnas*niveles)';

    otherwise
        error('Superficie desconocida.');

end

yPunta = nodos(idPunta,1);

yPerfil = [yColumnas;yPunta];
indices = [indices;idPunta];

L = yPunta-yColumnas(1);

yConsulta = yPunta-s*L;

j = find(yPerfil <= yConsulta,1,'last');

if j >= numel(yPerfil)
    j = numel(yPerfil)-1;
end

if isempty(j) || j < 1
    error('Ancla fuera del dominio.');
end

lambda = (yConsulta-yPerfil(j))/ ...
    (yPerfil(j+1)-yPerfil(j));

ids = indices([j j+1]);

coef = [1-lambda lambda];

referencia = coef*nodos(ids,:);

a.superficie = superficie;
a.s = s;

a.ids = ids(:)';
a.coef = coef;

a.referencia = referencia;

a.meta = [NaN NaN];
a.peso = 1;

end

%% VALIDACION DE TABLAS

function validarTabla(T,nombre)

if ~isnumeric(T) || ~isreal(T) || ...
        size(T,2) ~= 4
    error('%s debe ser una matriz Nx4.',nombre);
end

if isempty(T)
    return
end

if any(~isfinite(T(:,1))) || ...
        any(T(:,1) <= 0 | T(:,1) >= 1)
    error('Coordenadas s invalidas en %s.',nombre);
end

if any(~isfinite(T(:,4))) || any(T(:,4) <= 0)
    error('Pesos invalidos en %s.',nombre);
end

valores = T(:,2:3);

if any(isinf(valores(:))) || ...
        any(all(isnan(valores),2))
    error('Objetivos incompletos en %s.',nombre);
end

end

%% OPCIONES

function valor = leer(s,nombre,defecto)

if isfield(s,nombre)
    valor = s.(nombre);
else
    valor = defecto;
end

end
