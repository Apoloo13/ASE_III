
%% IMPORTACION DE LENGUA ROBOTICA A SIMSCAPE
clc;

% Directorio donde se encuentra este script
raiz = fileparts(mfilename('fullpath'));

% Carpetas del proyecto
carpetaCAD = fullfile(raiz, 'cad_export');
carpetaModelo = fullfile(raiz, 'modelo_simscape');

% Archivo de exportacion
archivoXML = fullfile(carpetaCAD, ...
    'lengua_robotica_cinematica_v2.xml');

% Validaciones
assert(isfile(archivoXML), ...
    'No se encontro el XML de la lengua robotica.');

if ~isfolder(carpetaModelo)
    mkdir(carpetaModelo);
end

% Agregar geometrias STEP a MATLAB Path
addpath(carpetaCAD);

% Directorio de salida
cd(carpetaModelo);

% Importar modelo multicuerpo
[modelo, datos] = smimport(archivoXML, ...
    'ModelName', 'lengua_robotica_SM_v2', ...
    'ModelSimplification', 'bringJointsToTop');

% Guardar modelo Simulink
save_system(modelo);

% Abrir modelo
open_system(modelo);

disp('Modelo de lengua robotica importado correctamente.');
disp(['Archivo de parametros: ', char(datos)]);