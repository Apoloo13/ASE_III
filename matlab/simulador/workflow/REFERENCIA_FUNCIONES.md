# Referencia de funciones

Consulta rápida de las interfaces, entradas y salidas del simulador. Para el flujo interno, consultar [ARQUITECTURA.md](ARQUITECTURA.md).

## 1. Funciones de uso directo

| Función | Llamada | Devuelve | Uso |
| --- | --- | --- | --- |
| `configuracion_orofacial` | `cfg = configuracion_orofacial()` | `cfg` | Parámetros generales y secuencias de ejemplo. |
| `preparar_sistema_orofacial` | `sistema = preparar_sistema_orofacial(cfg)` | `sistema` | Construye geometría, malla, FEM y referencias anatómicas. Ejecutar una vez por configuración. |
| `simular_postura_lingual` | `sim = simular_postura_lingual(sistema.modeloFEM, sistema.lengua0, postura, cfg.simulacion)` | `sim` | Resuelve una postura cuasiestática y reconstruye la lengua. |
| `analizar_articulacion` | `analisis = analizar_articulacion(sistema, sim)` | `analisis` | Calcula proximidades, holguras y solapamientos geométricos. |
| `visualizar_sistema_orofacial` | `g = visualizar_sistema_orofacial(sistema, sim, analisis, cfg.visualizacion)` | `g` | Crea las vistas 3D y sagital; llamar una sola vez para cada conjunto de figuras. |
| `actualizar_visualizacion` | `g = actualizar_visualizacion(g, sistema, sim, analisis)` | `g` | Actualiza las figuras existentes para otra postura. |

**Orden de uso:** configurar → preparar → simular → analizar → visualizar; para posturas siguientes, repetir únicamente **simular → analizar → actualizar**. Las subcarpetas funcionales deben estar en el *path* de MATLAB.

## 2. Datos que se intercambian

| Estructura | Campos relevantes | Observación |
| --- | --- | --- |
| `cfg` | `rutas`, `geometria`, `biomecanica`, `simulacion`, `cavidad`, `analisis`, `visualizacion`, `secuencias` | `cfg.visualizacion` es independiente de `cfg.simulacion`. |
| `sistema` | `lengua0`, `malla`, `modeloFEM`, `cavidad`, `contactoSagital`, `configuracion` | Reutilizable mientras no cambien geometría, biomecánica o cavidad. |
| `postura` | `puntaYZ`, `dorso`, `vientre`, `anguloApice`, `anguloLamina`, `curvaturaApical`, `curvaturaLaminal` | Objetivos de la postura, no resultados FEM. |
| `sim` | `estado`, `estadoBase`, `lengua`, `resultado`, `validacion`, `resumen` | `estadoBase` puede estar vacío. |
| `analisis` | `holguras`, `solapamiento`, `validacionGeometrica` | Evaluación geométrica posterior a la solución. |
| `g` | `figura3D`, `figuraSagital`, `superficie3D`, `dorso`, `vientre`, `cavidad`, `interferencias` | Identificadores gráficos: deben conservarse y reasignarse al actualizar. |

### Formato de `postura`

| Campo | Valor o formato | Significado |
| --- | --- | --- |
| `puntaYZ` | `[Y Z]` | Posición absoluta de la punta, en mm. |
| `dorso`, `vientre` | `[s, DeltaZ, peso]` | Objetivo vertical relativo a la referencia. |
| `dorso`, `vientre` | `[s, Yobjetivo, Zobjetivo, peso]` | Objetivo absoluto; `NaN` deja libre una coordenada. |
| `dorso`, `vientre` | `zeros(0,4)` | Sin objetivos regionales. |
| `anguloApice`, `anguloLamina` | Escalar o `NaN` | `NaN` desactiva el objetivo angular correspondiente. |
| `curvaturaApical`, `curvaturaLaminal` | Escalares | Consignas de control de forma. |
| `nombre` | Texto, opcional | Identificador de postura en secuencias. |

**Convenciones:** `X` lateral, `+Y` anterior, `Z` vertical; origen en la punta en reposo. La coordenada material `s` va de **0 (punta)** a **1 (posterior)** y no se expresa en mm.

## 3. Índice de funciones auxiliares

Estas funciones componen el sistema, pero **no es necesario llamarlas directamente para definir una nueva postura**. Sus firmas y opciones especializadas deben consultarse en cada archivo `.m`.

| Carpeta | Función | Responsabilidad |
| --- | --- | --- |
| `geometria/` | `lengua_ideal` | Geometría lingual de referencia. |
| | `crear_malla_lengua` | Mallado triangular 2D del perfil sagital. |
| | `reconstruir_lengua_3d` | Reconstrucción superficial a partir del estado FEM. |
| | `cavidad_oral` | Lectura, transformación y preparación de las regiones STL. |
| `biomecanica/` | `configurar_biomecanica` | Material, restricciones y anclajes. |
| | `resolver_postura_no_lineal` | Equilibrio FEM no lineal. |
| | `calcular_activacion_lingual` | Activaciones internas del modelo. |
| `control/` | `resolver_postura_con_guia` | Integra consignas de postura y solución FEM. |
| | `definir_postura_lingual` | Preparación de objetivos articulatorios. |
| | `definir_regiones_funcionales` | Regiones funcionales de la lengua. |
| | `preparar_guia_distribuida` | Distribución espacial del guiado. |
| | `evaluar_guia_lingual` | Evaluación del guiado geométrico. |
| | `regularizar_flexion_lingual` | Regularización de la deformación. |
| | `controlar_forma_lingual` | Restricciones de curvatura y orientación. |
| `analisis/` | `preparar_contacto_sagital` | Referencia geométrica de cavidad, **sin fuerzas de contacto**. |
| | `validar_deformacion_lingual` | Comprobaciones numéricas de deformación. |
| | `analizar_curvatura_lingual` | Análisis complementario de ángulos y curvaturas. |
| `visualizacion/` | `visualizar_cavidad_preparada` | Dibuja la cavidad ya importada, sin releer STL. |

**Funciones especializadas:** `analizar_curvatura_lingual(lengua0, lenguaNueva, regiones, opciones)` devuelve medidas regionales de curvatura y flexión. `ajustar_activaciones_linguales(modelo, lengua0, regiones, objetivo, opciones)` es un procedimiento de control inverso **experimental**, no parte del flujo de posturas principal.

**Scripts:** `principal.m` es una demostración integrada. `prueba_barrido_orofacial.m` utiliza las variables que deja `principal.m` en el espacio de trabajo; no debe ejecutarse como función independiente. Los solucionadores de `experimental/` no sustituyen al FEM vigente.

## 4. Reglas de integración

- **Nueva postura o fonema:** construir `postura` o una secuencia de posturas; utilizar `simular_postura_lingual`, no llamar directamente al solucionador interno.
- **Nuevo material, anclaje, malla o cavidad:** modificar `cfg` y volver a ejecutar `preparar_sistema_orofacial`.
- **Nueva vista de una postura:** conservar `g` y usar `actualizar_visualizacion`; no volver a importar STL ni crear figuras en cada cuadro.
- **Resultados:** distinguir `sim.validacion` (numérico) de `analisis.validacionGeometrica` (geométrico). Las holguras `NaN` no significan penetración.
- **Secuencias:** cada postura precalculada puede tener solución FEM; los cuadros interpolados para reproducción son **solo visuales** y no tienen equilibrio ni validación propios.
- **Pruebas:** conservar fuera de `experimental/` las implementaciones que se quieran ejecutar desde el flujo principal; después de modificar el núcleo, comprobar los casos de regresión descritos en `ARQUITECTURA.md`.

> **Alcance de esta referencia:** se documenta la interfaz de uso y la función de cada componente, no los detalles matemáticos ni la totalidad de los parámetros internos. Las funciones auxiliares pueden evolucionar sin cambiar el contrato de uso principal.
