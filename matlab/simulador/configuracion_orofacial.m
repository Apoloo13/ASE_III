
function cfg = configuracion_orofacial()
% CONFIGURACION_OROFACIAL
% Parametros generales del simulador.
% Unidades: mm, N, N/mm^2.

%% 1. RUTAS

cfg.rutas.raiz = fileparts(mfilename('fullpath'));
cfg.rutas.stl = fullfile(cfg.rutas.raiz,'STL');

%% 2. GEOMETRIA

cfg.geometria.lengua = struct();

cfg.geometria.malla = struct( ...
    'pasoLongitudinal',0.90, ...
    'nivelesEspesor',5, ...
    'refinarAnterior',true, ...
    'factorPasoAnterior',0.60, ...
    'extensionAnterior',0.35);

%% 3. BIOMECANICA

cfg.biomecanica = struct( ...
    'E',0.005, ...
    'nu',0.40, ...
    'espesor',1, ...
    'perfilRigidez','uniforme', ...
    'factorAnclaje',1.0, ...
    'longitudReferenciaAnclaje',5.0, ...
    'modoAnclajePosterior','banda', ...
    'anchoBandaPosterior',5.0, ...
    'activarSoporteVentral',false);

%% 4. SIMULACION FEM

cfg.simulacion = struct();

cfg.simulacion.opcionesNoLineales = struct( ...
    'nPasos',30, ...
    'maxIter',45, ...
    'tolFuerza',1e-9, ...
    'maxBacktrack',30);

cfg.simulacion.calcularBaseComparativa = false;

% Guiado geometrico
cfg.simulacion.factorRigidezGuia = 0.25;
cfg.simulacion.factorRigidezAngular = 0.20;

cfg.simulacion.distribucionGuia = struct( ...
    'modo','distribuido', ...
    'radio',0.06, ...
    'fraccionDistribuida',0.75, ...
    'excluirPunta',true);

% Control de forma
cfg.simulacion.factorRigidezCurvatura = 0.20;
cfg.simulacion.factorRigidezAngularLamina = 0.15;

% Regularizacion
cfg.simulacion.suavidad = struct( ...
    'activar',true, ...
    'factorDorsal',0.03, ...
    'factorVentral',0.03, ...
    'inicio',0.02, ...
    'fin',0.895, ...
    'anchoTransicion',0.04, ...
    'longitudReferencia',2.0);

cfg.simulacion.validar = true;
cfg.simulacion.mostrarConsola = true;

%% 5. CAVIDAD ORAL

cfg.cavidad = struct( ...
    'activar',true, ...
    'carpetaSTL',cfg.rutas.stl, ...
    'puntaReposo',[], ...
    'prepararContacto',true, ...
    'pasoContactoY',0.10);

%% 6. ANALISIS Y VALIDACION

% Umbral numerico exploratorio, no fisiologico.
cfg.analisis.JcriticoExploratorio = 0.84;

%% 7. VISUALIZACION

cfg.visualizacion = struct( ...
    'graficar',true, ...
    'mostrarCavidad',true, ...
    'mostrarPuntos',true, ...
    'mostrarReposo3D',false, ...
    'mostrarBase',false, ...
    'mostrarPenetraciones',true);

%% 8. SECUENCIAS

cfg.secuencias = struct();

cfg.secuencias.barridoModerado = [
     0.0   0.00
    -0.5   1.25
    -1.0   2.50
    -1.5   3.75
    -2.0   5.00
];

% Plantilla de postura articulatoria.
plantilla = struct( ...
    'nombre',"", ...
    'puntaYZ',[0 0], ...
    'dorso',zeros(0,4), ...
    'vientre',zeros(0,4), ...
    'anguloApice',NaN, ...
    'anguloLamina',NaN, ...
    'curvaturaApical',0, ...
    'curvaturaLaminal',0);

ruta = cfg.secuencias.barridoModerado;
n = size(ruta,1);

posturas = repmat(plantilla,n,1);

for k = 1:n
    posturas(k).nombre = sprintf("Postura %d",k);
    posturas(k).puntaYZ = ruta(k,:);
end

cfg.secuencias.posturasModeradas = posturas;

%% 9. TRANSICION COMPLETA

P0 = posturas(1);
P1 = posturas(end);

P0.nombre = "Inicio";
P1.nombre = "Final";

% Objetivos regionales [s DeltaZ Peso].
P0.dorso = [
    0.12  0.00  0.45
    0.25  0.00  0.35
    0.40  0.00  0.25
];

P1.dorso = [
    0.12  0.35  0.45
    0.25  0.25  0.35
    0.40  0.10  0.25
];

P0.vientre = [
    0.12  0.00  0.35
    0.25  0.00  0.25
];

P1.vientre = [
    0.12  0.15  0.35
    0.25  0.10  0.25
];

P0.curvaturaApical = 0;
P1.curvaturaApical = 0.006;

cfg.secuencias.transicionCompleta = struct( ...
    'inicio',P0, ...
    'fin',P1, ...
    'nPosturas',9);

%% 10. REPRODUCCION

cfg.secuencias.pasosVisuales = 12;
cfg.secuencias.pausaVisual_s = 0.035;


%% TRAYECTORIA DEL FONEMA /s/

cfg.trayectoriaS = struct( ...
    'nEstados',60, ...
    'registroY_mm',3.0, ...
    'duracionVisual_s',3.0, ...
    'fpsGIF',15, ...
    'analizarCadaEstado',false, ...
    'gradoPolinomio',5);


%% TRAYECTORIA DEL FONEMA /t/

cfg.trayectoriaT = struct( ...
    'nEstados',60, ...
    'registroY_mm',3.0, ...
    'registroZ_mm',1.0, ...
    'duracionVisual_s',3.0, ...
    'fpsGIF',15, ...
    'analizarCadaEstado',false, ...
    'gradoPolinomio',5);

%% FONEMA /t/ - CONFIGURACIONES EXPLORATORIAS

cfg.fonemaT = struct();

cfg.fonemaT.registroY_mm = 3.0;
cfg.fonemaT.indicePrincipal = 2;

cfg.fonemaT.umbralProximidad_mm = 1.0;
cfg.fonemaT.toleranciaPenetracion_mm = 0.10;

% Posiciones materiales para el control anterior.
cfg.fonemaT.sControl = [0.05; 0.10; 0.16; 0.23];
cfg.fonemaT.pesos = [0.55; 0.80; 0.75; 0.40];

% Candidatas: T1 laminal, T2 apico-laminal, T3 apical.
cfg.fonemaT.nombres = { ...
    'T1 - Laminal moderada', ...
    'T2 - Apico-laminal curvada', ...
    'T3 - Apical exploratoria'};

% Desplazamientos de la punta respecto a su referencia [dY dZ].
cfg.fonemaT.deltaPuntaYZ = [
    2.5  0.0
    2.8  0.0
    2.4  1.0
    ];

% Cada capa contiene los objetivos [dY dZ] de una candidata.
% Son consignas iniciales de prueba, no medidas clinicas.

cfg.fonemaT.deltaDorso = cat(3, ...
    [1.5 1.2; 2.2 1.9; 3.0 2.0; 1.7 0.8], ...
    [1.1 1.0; 2.8 2.9; 3.7 2.8; 1.5 1.0], ...
    [1.4 1.4; 2.2 1.5; 2.0 1.0; 0.9 0.6]);

cfg.fonemaT.curvaturaApical = [0 0.003 0.006];
cfg.fonemaT.curvaturaLaminal = [0 0.003 0];

cfg.fonemaT.anguloApice = [NaN NaN NaN];
cfg.fonemaT.anguloLamina = [NaN NaN NaN];

end