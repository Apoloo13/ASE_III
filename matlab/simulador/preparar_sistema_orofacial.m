
function sistema = preparar_sistema_orofacial(cfg)
% PREPARAR_SISTEMA_OROFACIAL
%
% Inicializa:
%   1. Geometria lingual.
%   2. Malla FEM.
%   3. Modelo biomecanico.
%   4. Cavidad oral.
%   5. Referencias de contacto sagital.
%
% Los datos se preparan una sola vez.
% No ejecuta posturas ni crea figuras.

%% 1. VALIDACION

if nargin < 1 || ~isstruct(cfg)
    error('Se requiere configuracion_orofacial.');
end

fprintf('\n===== INICIALIZACION OROFACIAL =====\n');

%% 2. GEOMETRIA LINGUAL

fprintf('Preparando lengua...\n');

lengua0 = lengua_ideal( ...
    cfg.geometria.lengua,[],[]);

%% 3. MALLA FEM

fprintf('Generando malla FEM...\n');

malla = crear_malla_lengua( ...
    lengua0,cfg.geometria.malla);

%% 4. MODELO BIOMECANICO

fprintf('Configurando biomecanica...\n');

modeloFEM = configurar_biomecanica( ...
    malla,cfg.biomecanica);

% Comprobar que se aplico el anclaje solicitado.
if isfield(cfg.biomecanica,'modoAnclajePosterior')

    if ~isfield(modeloFEM.anclajes,'modoPosterior')
        error(['configurar_biomecanica no devuelve ', ...
            'el modo de anclaje posterior.']);
    end

    modoReal = string( ...
        modeloFEM.anclajes.modoPosterior);

    modoSolicitado = string( ...
        cfg.biomecanica.modoAnclajePosterior);

    if modoReal ~= modoSolicitado
        error('No se aplico el anclaje solicitado.');
    end

end

%% 5. CAVIDAD ORAL

cavidad = [];
contactoSagital = [];

if cfg.cavidad.activar

    fprintf('Importando cavidad oral...\n');

    carpetaSTL = cfg.cavidad.carpetaSTL;

    if ~isfolder(carpetaSTL)
        error('No existe la carpeta STL: %s',carpetaSTL);
    end

    % Referencia utilizada por lengua_ideal.
    puntaReposo = [0 23.5 -1.15];

    if isfield(lengua0,'parametros') && ...
            isfield(lengua0.parametros,'puntaReposo')

        puntaReposo = ...
            lengua0.parametros.puntaReposo;

    end

    % Permitir una referencia explicita.
    if ~isempty(cfg.cavidad.puntaReposo)
        puntaReposo = cfg.cavidad.puntaReposo;
    end

    % Preparar datos sin generar figuras.
    cavidad = cavidad_oral( ...
        carpetaSTL,puntaReposo,[],[]);

    %% 6. CONTACTO SAGITAL

    if cfg.cavidad.prepararContacto

        fprintf('Preparando regiones sagitales...\n');

        opContacto = struct();

        opContacto.pasoY = ...
            cfg.cavidad.pasoContactoY;

        contactoSagital = preparar_contacto_sagital( ...
            cavidad,opContacto);

    end

end

%% 7. GUARDAR SISTEMA

sistema = struct();

sistema.lengua0 = lengua0;
sistema.malla = malla;
sistema.modeloFEM = modeloFEM;

sistema.cavidad = cavidad;
sistema.contactoSagital = contactoSagital;

sistema.configuracion = cfg;

%% 8. RESUMEN

fprintf('\n===== SISTEMA PREPARADO =====\n');

fprintf('Nodos FEM: %d\n', ...
    size(malla.nodos,1));

fprintf('Elementos FEM: %d\n', ...
    size(malla.elementos,1));

fprintf('Modelo biomecanico: listo.\n');

if ~isempty(cavidad)

    fprintf('Regiones orales: %d\n', ...
        numel(cavidad.regiones));

    fprintf('Cavidad oral: lista.\n');

else

    fprintf('Cavidad oral: desactivada.\n');

end

if ~isempty(contactoSagital)

    fprintf('Referencias sagitales: listas.\n');

end

fprintf('\nINICIALIZACION COMPLETA.\n');

end
    