
function salida = ejecutar_trayectoria_fonema_s()
% Ejecuta la trayectoria cuasiestatica de /s/ laminal.
% Genera estados FEM, ecuaciones, graficos y controles GIF.

%% 1. RUTAS

raiz = fileparts(fileparts(mfilename('fullpath')));

assert(isfile(fullfile(raiz,'principal.m')), ...
    'Este archivo debe estar en simulador/secuencias/.');

addpath(raiz);

carpetas = { ...
    'geometria', ...
    'biomecanica', ...
    'control', ...
    'analisis', ...
    'visualizacion', ...
    'secuencias'};

for k = 1:numel(carpetas)

    ruta = fullfile(raiz,carpetas{k});

    assert(isfolder(ruta), ...
        'No existe la carpeta: %s',ruta);

    addpath(ruta);

end

%% 2. CONFIGURACION

cfg = configuracion_orofacial();

assert(isfield(cfg,'trayectoriaS'), ...
    'Falta cfg.trayectoriaS en configuracion_orofacial.m.');

% Misma referencia geometrica adoptada para S2.
cfg.geometria.lengua.desplazamientoGlobal = ...
    [0 cfg.trayectoriaS.registroY_mm 0];

%% 3. PREPARAR SISTEMA

sistema = preparar_sistema_orofacial(cfg);

%% 4. CALCULAR TRAYECTORIA FEM

trayectoria = generar_trayectoria_fonema_s( ...
    sistema,cfg);

%% 5. GUARDAR DATOS DE CONTROL

carpetaResultados = fullfile(raiz,'resultados');

if ~isfolder(carpetaResultados)
    mkdir(carpetaResultados);
end

ecuaciones = trayectoria.ecuaciones;
sMarcas = trayectoria.sMarcas;
nombres = trayectoria.nombres;

u = trayectoria.u;
puntos = trayectoria.puntos;

green = trayectoria.green;
jmin = trayectoria.jmin;
energia = trayectoria.energia;
cumpleFEM = trayectoria.cumpleFEM;

archivoDatos = fullfile( ...
    carpetaResultados,'trayectoria_s_ecuaciones.mat');

save(archivoDatos, ...
    'ecuaciones','sMarcas','nombres', ...
    'u','puntos','green','jmin', ...
    'energia','cumpleFEM');

fprintf('\nEcuaciones guardadas en:\n%s\n',archivoDatos);

%% 6. GENERAR INTERFAZ

interfaz = visualizar_trayectoria_fonema_s( ...
    trayectoria);

%% 7. RESULTADO

salida = struct();

salida.trayectoria = trayectoria;
salida.interfaz = interfaz;
salida.archivoEcuaciones = archivoDatos;

fprintf('\n===== TRAYECTORIA /s/ LISTA =====\n');

fprintf('Estados: %d\n',numel(u));

fprintf('Admisibilidad FEM: %d/%d estados\n', ...
    nnz(cumpleFEM),numel(cumpleFEM));

fprintf(['Utiliza el slider para recorrer los ', ...
    'equilibrios calculados.\n']);

fprintf(['Selecciona la vista 3D y pulsa ', ...
    '"Exportar GIF 3D" para guardar la animacion.\n']);

end
