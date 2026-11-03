
function salida = ejecutar_trayectoria_fonema_t()
% EJECUTAR_TRAYECTORIA_FONEMA_T
%
% Trayectoria cuasiestatica del fonema /t/.
% Configuracion final: T5, factor 0.83.
%
% Reposo -> postura /t/ -> reposo.
%
% Calcula:
%   - Equilibrios FEM
%   - Trayectorias de puntos linguales
%   - Ecuaciones parametricas
%   - Indicadores FEM
%   - Visualizaciones 2D y 3D
%   - Exportacion interactiva de GIF
%
% No modifica la cavidad ni los archivos de /s/.

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

rehash;

%% 2. CONFIGURACION /t/

cfg = configuracion_orofacial();

assert(isfield(cfg,'trayectoriaT'), ...
    ['Falta cfg.trayectoriaT en ', ...
     'configuracion_orofacial.m.']);

C = cfg.trayectoriaT;

% Misma referencia adoptada en
% reporte_postura_fonema_t.m.
cfg.geometria.lengua.desplazamientoGlobal = ...
    [0 C.registroY_mm C.registroZ_mm];

% Los volumenes coloreados son franjas de
% referencia, no superficies de contacto.
%
% Evitar marcadores de penetracion derivados
% de las envolventes inferiores auxiliares.
cfg.visualizacion.mostrarPenetraciones = false;

%% 3. PREPARAR SISTEMA

sistema = preparar_sistema_orofacial(cfg);

puntaInicial = sistema.lengua0.punta(2:3);

assert(norm(puntaInicial - ...
    [C.registroY_mm C.registroZ_mm])<1e-6, ...
    'La referencia lingual inicial es incorrecta.');

fprintf('\n===== REFERENCIA DE TRAYECTORIA /t/ =====\n');

fprintf('Punta inicial YZ: [%.3f %.3f] mm\n', ...
    puntaInicial);

fprintf('Estados solicitados: %d\n',C.nEstados);

fprintf('Postura final: T5, factor 0.83\n');

%% 4. CALCULAR TRAYECTORIA FEM

trayectoria = generar_trayectoria_fonema_t( ...
    sistema,cfg);

%% 5. REVISAR EXTREMO FINAL

simFinal = trayectoria.simulaciones{end};

fprintf('\n===== POSTURA FINAL DE LA TRAYECTORIA =====\n');

fprintf('Punta final YZ: [%.3f %.3f] mm\n', ...
    simFinal.estado.puntaYZ);

fprintf('GreenMax: %.5f\n', ...
    simFinal.resumen.GreenMax);

fprintf('Jmin: %.5f\n', ...
    simFinal.resumen.Jmin);

fprintf('Jmax: %.5f\n', ...
    simFinal.resumen.Jmax);

fprintf('Cumple criterios FEM: %d\n', ...
    simFinal.resumen.cumpleCriteriosExploratorios);

if ~simFinal.resumen.cumpleCriteriosExploratorios

    warning(['La postura final de la trayectoria ', ...
        'no cumple los criterios FEM exploratorios.']);

end

%% 6. GUARDAR RESULTADOS

carpetaResultados = fullfile(raiz,'resultados');

if ~isfolder(carpetaResultados)
    mkdir(carpetaResultados);
end

ecuaciones = trayectoria.ecuaciones;

sMarcas = trayectoria.sMarcas;
nombres = trayectoria.nombres;

u = trayectoria.u;
avance = trayectoria.avance;
puntos = trayectoria.puntos;

green = trayectoria.green;

jmin = trayectoria.jmin;
jmax = trayectoria.jmax;

energia = trayectoria.energia;
cumpleFEM = trayectoria.cumpleFEM;

posturaFinal = trayectoria.posturaFinal;

archivoDatos = fullfile( ...
    carpetaResultados,'trayectoria_t_ecuaciones.mat');

save(archivoDatos, ...
    'ecuaciones', ...
    'sMarcas', ...
    'nombres', ...
    'u', ...
    'avance', ...
    'puntos', ...
    'green', ...
    'jmin', ...
    'jmax', ...
    'energia', ...
    'cumpleFEM', ...
    'posturaFinal');

fprintf('\nDatos y ecuaciones guardados en:\n');
fprintf('%s\n',archivoDatos);

%% 7. GENERAR INTERFAZ

interfaz = visualizar_trayectoria_fonema_t( ...
    trayectoria);

%% 8. RESULTADO GENERAL

salida = struct();

salida.cfg = cfg;
salida.sistema = sistema;

salida.trayectoria = trayectoria;
salida.interfaz = interfaz;

salida.archivoEcuaciones = archivoDatos;

nTotal = numel(u);
nValidos = nnz(cumpleFEM);

fprintf('\n===== TRAYECTORIA /t/ LISTA =====\n');

fprintf('Equilibrios FEM: %d\n',nTotal);

fprintf('Estados FEM admisibles: %d/%d\n', ...
    nValidos,nTotal);

fprintf('Mayor salto entre muestras: %.5f mm\n', ...
    trayectoria.maxSalto);

fprintf('Recorrido completo: %d fotogramas\n', ...
    2*nTotal-1);

if nValidos==nTotal

    fprintf('Todos los estados cumplen los criterios FEM.\n');

else

    fprintf(['ATENCION: existen %d estados ', ...
        'que requieren revision FEM.\n'], ...
        nTotal-nValidos);

end

fprintf(['El slider permite examinar la ', ...
    'trayectoria y su regreso.\n']);

fprintf(['Los GIF pueden exportarse con ', ...
    'la orientacion 3D seleccionada.\n']);

end
