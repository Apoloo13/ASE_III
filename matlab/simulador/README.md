# Simulador orofacial — modelo lingual

Simulador experimental en MATLAB para definir, resolver y visualizar **posturas de la lengua** dentro de una cavidad oral de referencia. Combina un modelo geométrico paramétrico, un modelo de elementos finitos (FEM) no lineal en el plano sagital y una reconstrucción superficial tridimensional.

## Qué permite hacer

- Definir una postura a partir de la posición de la punta y, opcionalmente, de objetivos del dorso, vientre y curvatura.
- Resolver el equilibrio cuasiestático mediante un FEM 2D hiperelástico.
- Reconstruir y visualizar la superficie lingual en 3D y su perfil sagital junto con las regiones de la cavidad oral.
- Medir proximidades, holguras y solapamientos **sagitales aproximados** con las regiones dental, alveolar, prepalatal y mediopalatal.
- Calcular varias posturas y mostrarlas en las mismas figuras mediante controles interactivos. Las interpolaciones visuales entre soluciones no son nuevos equilibrios FEM.

## Requisitos y datos

- MATLAB con soporte para las funciones empleadas por el proyecto, incluidas `stlread` y las interfaces gráficas convencionales.
- Las carpetas funcionales del simulador incorporadas a la ruta de búsqueda de MATLAB. No es necesario activar `experimental/` para el flujo principal.

## Usar el simulador desde otro script

El flujo básico recomendado es **configurar → preparar → simular → analizar → visualizar**:

```matlab
cfg = configuracion_orofacial();
sistema = preparar_sistema_orofacial(cfg);

postura = struct();
postura.puntaYZ = [-2 5];              % [Y Z] en mm
postura.anguloApice = NaN;             % Sin objetivo angular
postura.anguloLamina = NaN;
postura.curvaturaApical = 0;
postura.curvaturaLaminal = 0;
postura.dorso = zeros(0,4);
postura.vientre = zeros(0,4);

sim = simular_postura_lingual( ...
    sistema.modeloFEM,sistema.lengua0,postura,cfg.simulacion);

analisis = analizar_articulacion(sistema,sim);
graficos = visualizar_sistema_orofacial( ...
    sistema,sim,analisis,cfg.visualizacion);
```

Para representar otra postura en **las mismas figuras**, resuélvela y analízala, y después llama a:

```matlab
graficos = actualizar_visualizacion( ...
    graficos,sistema,otraSimulacion,otroAnalisis);
```

Las subcarpetas deben estar en el *path* de MATLAB antes de ejecutar el ejemplo desde un script independiente.

### Convenciones de postura

- Ejes: `Y` longitudinal y `Z` vertical; el origen corresponde a la punta lingual en reposo. Las posiciones se expresan en milímetros.
- Coordenada material `s`: `0` en la punta y `1` en el extremo posterior del modelo FEM.
- `postura.puntaYZ = [Y Z]`: destino absoluto de la punta en el sistema del simulador.
- `postura.dorso` y `postura.vientre`: matrices `[s, DeltaZ, peso]` o `[s, Yobjetivo, Zobjetivo, peso]`. En el formato de cuatro columnas, `NaN` deja libre una coordenada.
- Los ángulos `NaN` desactivan la restricción angular correspondiente.

## Organización del módulo

| Carpeta o archivo | Responsabilidad |
| --- | --- |
| `principal.m` | Ejemplo principal y orquestación de una simulación. |
| `configuracion_orofacial.m` | Parámetros del modelo, la cavidad, visualización y secuencias de prueba. |
| `preparar_sistema_orofacial.m` | Inicialización de las mallas, material y cavidad oral. |
| `geometria/` | Modelo de lengua, mallado FEM, reconstrucción 3D y lectura de la cavidad. |
| `biomecanica/` | Modelo material, anclajes, activación interna y solucionador no lineal. |
| `control/` | Conversión de objetivos articulatorios y guiado de posturas. |
| `analisis/` | Validación de deformaciones y análisis de proximidad y solapamiento. |
| `visualizacion/` | Creación de figuras y actualización sin volver a cargar los STL. |
| `secuencias/` | Generación de objetivos y gestos cuasiestáticos. |
| `pruebas/` | Scripts de prueba y barridos interactivos. |
| `experimental/` | Implementaciones alternativas, fuera del flujo principal. |
| `STL/` | Geometría de referencia de la cavidad oral. |

## Resultados y validación

La simulación devuelve, entre otros, `sim.estado` (nodos y desplazamientos), `sim.lengua` (geometría reconstruida), `sim.validacion` y `sim.resumen`. El análisis anatómico se obtiene por separado mediante `analizar_articulacion`.

Las comprobaciones numéricas incluyen convergencia, deformación y ausencia de inversión local de elementos. Las comprobaciones anatómicas son **geométricas y principalmente sagitales**; no equivalen a una simulación de contacto mecánico ni garantizan ausencia de intersecciones en 3D.

## Alcance y limitaciones

Este simulador emplea una aproximación biomecánica simplificada de la lengua, orientada principalmente al análisis de sus configuraciones y deformaciones en el plano sagital. Utiliza un FEM bidimensional no lineal para calcular posturas cuasiestáticas y una reconstrucción superficial tridimensional para facilitar su interpretación espacial. Su planteamiento toma como antecedentes los modelos biomecánicos linguales desarrollados por [Payan y Perrier (1997)](https://doi.org/10.1016/S0167-6393(97)00019-8) y [Perrier et al. (2003)](https://doi.org/10.1121/1.1587737), que estudian el comportamiento articulatorio mediante elementos finitos. Aunque incorpora simplificaciones geométricas y mecánicas, busca aproximar comportamientos articulatorios plausibles y analizar su relación con la cavidad oral. Actualmente no considera contacto mecánico unilateral ni fricción con el paladar, y sus criterios de aceptación numérica son exploratorios, no umbrales clínicos.

Para extender el sistema, se recomienda **definir nuevas posturas o secuencias desde las interfaces existentes**, sin modificar el solucionador biomecánico salvo que el cambio esté justificado y se acompañe de pruebas de regresión.