
% PRINCIPAL
%
% SIMULADOR GENERAL DE POSTURAS LINGUALES
%
% Modificar principalmente la seccion 3.
%
% Sistema de coordenadas:
%   Y: longitudinal
%   Z: vertical
%   Origen: punta lingual en reposo
%
% Unidades: mm.

clear; clc; close all;

%% =====================================================
% CONFIGURACION DE RUTAS DEL PROYECTO
% ======================================================

% Ruta absoluta de la carpeta donde esta principal.m.
raizProyecto = fileparts(mfilename('fullpath'));

% Carpeta principal.
addpath(raizProyecto);

% Subcarpetas funcionales.
carpetas = {
    'geometria'
    'biomecanica'
    'control'
    'analisis'
    'visualizacion'
    'secuencias'
    'pruebas'
    };

for i = 1:numel(carpetas)

    ruta = fullfile(raizProyecto,carpetas{i});

    if ~isfolder(ruta)
        error('No existe la carpeta: %s',ruta);
    end

    addpath(ruta);

end

% Actualizar cache de funciones.
rehash;

fprintf('Rutas del proyecto configuradas.\n');


%% =====================================================
% 1. CONFIGURACION GENERAL
% ======================================================

cfg = configuracion_orofacial();

%% =====================================================
% 2. INICIALIZACION DEL SISTEMA
% ======================================================

sistema = preparar_sistema_orofacial(cfg);

% Variables compatibles con el simulador actual.
lengua0 = sistema.lengua0;
malla = sistema.malla;
modelo = sistema.modeloFEM;

%% =====================================================
% 3. POSTURA - RETROFLEXION APICAL EXPERIMENTAL
% ======================================================

postura = struct();

% Punta mas elevada y retraida.
postura.puntaYZ = [-5.0 15.5];

% Curvatura localizada (1/mm).
postura.curvaturaApical  = 0.035;
postura.curvaturaLaminal = -0.008;

% Orientaciones adicionales.
% Inicialmente liberamos los angulos.
postura.anguloApice = NaN;
postura.anguloLamina = NaN;
postura.pesoAngulo = 1.0;

% DORSO
% [s Yobjetivo Zobjetivo Peso]
postura.dorso = [
    0.04  -7.0  16.8  1.00
    0.08  -8.8  16.5  1.00
    0.14 -11.0  13.8  0.95
    0.22 -13.8  10.0  0.90
    0.34    NaN  7.6  0.75
    0.50    NaN  6.0  0.50
    0.70    NaN  4.4  0.30
];

% VIENTRE
% [s Yobjetivo Zobjetivo Peso]
postura.vientre = [
    0.06  NaN  12.2  0.85
    0.12  NaN   9.0  0.90
    0.20  NaN   5.2  0.85
    0.32  NaN   1.7  0.70
    0.48  NaN  -0.3  0.50
    0.65  NaN  -1.3  0.35
];

%% =====================================================
% 4. OPCIONES DEL SIMULADOR
% ======================================================

op = cfg.simulacion;

%% =====================================================
% 5. SIMULACION
% ======================================================

simulacion = simular_postura_lingual( ...
    sistema.modeloFEM, ...
    sistema.lengua0, ...
    postura, ...
    cfg.simulacion);

%% =====================================================
% 5B. ANALISIS ARTICULATORIO
% ======================================================

analisis = analizar_articulacion( ...
    sistema,simulacion);

%% =====================================================
% 5C. VALIDACION CONJUNTA
% ======================================================

cumpleFEM = ...
    simulacion.resumen.cumpleCriteriosExploratorios;

cumpleGeometria = ...
    analisis.validacionGeometrica.sinSolapamiento;

simulacion.resumen.cumpleGeometriaSagital = ...
    cumpleGeometria;

simulacion.resumen.cumpleValidacionConjunta = ...
    cumpleFEM && cumpleGeometria;

fprintf('\n===== VALIDACION CONJUNTA =====\n');

fprintf('Criterios FEM: %d\n',cumpleFEM);

fprintf('Sin solapamiento sagital: %d\n', ...
    cumpleGeometria);

fprintf('Area maxima de interferencia: %.3f mm2\n', ...
    analisis.validacionGeometrica.areaMaxima_mm2);

%% =====================================================
% 5D. VISUALIZACION INTEGRADA
% ======================================================

graficos = [];

if cfg.visualizacion.graficar

    graficos = visualizar_sistema_orofacial( ...
        sistema,simulacion,analisis, ...
        cfg.visualizacion);

end

% Mantener acceso a identificadores graficos.
simulacion.graficos = graficos;

%% =====================================================
% 6. RESULTADOS ACCESIBLES
% ======================================================

% Geometria 3D:
% simulacion.lengua.malla.X
% simulacion.lengua.malla.Y
% simulacion.lengua.malla.Z
%
% Perfil sagital:
% simulacion.lengua.sagital
%
% Desplazamientos nodales:
% simulacion.estado.desplazamientos
%
% Diagnostico:
% simulacion.validacion
%
% Resumen:
% simulacion.resumen

fprintf('\n===== RESUMEN PRINCIPAL =====\n');

disp(simulacion.resumen);

fprintf('\nMODELO LISTO.\n');
