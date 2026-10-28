# Arquitectura del simulador orofacial

Este documento describe **cómo se organiza y se utiliza internamente el simulador lingual**. Aquí se explican las interfaces, el flujo de datos y las dependencias necesarias para extender el sistema sin modificar su núcleo.

## 1. Diseño general

El sistema separa cinco operaciones: **configurar → preparar → simular → analizar → visualizar**. La geometría y el modelo FEM se preparan una sola vez y pueden reutilizarse para resolver varias posturas. La visualización recibe resultados ya calculados; no debe volver a importar los STL ni resolver el equilibrio.

```text
configuracion_orofacial()
          │ cfg
          ▼
preparar_sistema_orofacial(cfg)
          │ sistema: lengua0, malla, modeloFEM, cavidad, contactoSagital
          │
          ├──────────────────────────────┐
          ▼                              │
simular_postura_lingual(...)             │
          │ simulacion                    │
          ▼                              │
analizar_articulacion(sistema,simulacion)│
          │ analisis                     │
          ▼                              │
visualizar_sistema_orofacial(...) ◄──────┘
          │ graficos
          ▼
actualizar_visualizacion(...)  ← siguientes posturas y sus análisis
```

**Alcance mecánico:** el equilibrio se calcula con un FEM no lineal **bidimensional y cuasiestático**; la superficie 3D se reconstruye a partir de la deformación sagital. Los controles interactivos no transforman este cálculo en una simulación dinámica. Tampoco existe todavía una restricción de contacto mecánico unilateral con la cavidad.

## 2. Organización de archivos

| Ubicación | Funciones y responsabilidad |
| --- | --- |
| `configuracion_orofacial.m` | Devuelve `cfg`: parámetros geométricos, biomecánicos, numéricos, visuales y secuencias de prueba. |
| `preparar_sistema_orofacial.m` | Construye `sistema` una sola vez: lengua de referencia, malla, modelo FEM, cavidad y referencias sagitales. |
| `principal.m` | Ejecuta una demostración completa; **no** contiene la única interfaz posible del simulador. |
| `geometria/` | `lengua_ideal`, `crear_malla_lengua`, `reconstruir_lengua_3d`, `cavidad_oral`. |
| `biomecanica/` | `configurar_biomecanica`, `resolver_postura_no_lineal`, `calcular_activacion_lingual`. |
| `control/` | `simular_postura_lingual`, `resolver_postura_con_guia` y funciones auxiliares para objetivos, regiones, guiado y control de forma. |
| `analisis/` | `preparar_contacto_sagital`, `validar_deformacion_lingual`, `analizar_articulacion`; opcionalmente `analizar_curvatura_lingual`. |
| `visualizacion/` | `visualizar_sistema_orofacial`, `visualizar_cavidad_preparada`, `actualizar_visualizacion`. |
| `secuencias/` | Utilidades para definir gestos y transiciones; no sustituyen el solucionador FEM. |
| `pruebas/` | Ensayos de integración y `prueba_barrido_orofacial.m`. |
| `experimental/` | Métodos alternativos o en desarrollo; fuera de las rutas activas del flujo principal. |
| `STL/` | Geometría de referencia de la cavidad y sus regiones. |

Los nombres de los archivos MATLAB deben coincidir con los de sus funciones principales. No se requiere renombrar `visualizar_sistema_orofacial.m` a `visualizar_sistema.m`: este último **no** es un archivo de la implementación actual.

## 3. Interfaces recomendadas

Estas son las funciones que conviene utilizar desde nuevos scripts, pruebas o futuros módulos de fonemas:

| Función | Entrada principal | Salida | Cuándo utilizarla |
| --- | --- | --- | --- |
| `configuracion_orofacial()` | Ninguna | `cfg` | Al comenzar una ejecución. |
| `preparar_sistema_orofacial(cfg)` | `cfg` | `sistema` | Una vez por configuración de geometría/material/cavidad. |
| `simular_postura_lingual(modelo,lengua0,postura,op)` | Modelo FEM, referencia, postura, opciones | `simulacion` | Para cada postura que requiera equilibrio FEM. |
| `analizar_articulacion(sistema,simulacion)` | Sistema y postura calculada | `analisis` | Cuando se necesiten distancias, holguras o solapamientos. |
| `visualizar_sistema_orofacial(sistema,simulacion,analisis,op)` | Resultados y opciones visuales | `graficos` | **Una vez** para abrir las dos figuras. |
| `actualizar_visualizacion(graficos,sistema,simulacion,analisis)` | Gráficos existentes y nuevos resultados | `graficos` | Para actualizar figuras sin recrearlas. |

Las restantes funciones son principalmente **componentes internos**. Pueden estudiarse o utilizarse en investigaciones específicas, pero para añadir una postura no es necesario llamar directamente a `resolver_postura_no_lineal` ni modificar sus ecuaciones.

### Ejemplo mínimo de utilización

```matlab
cfg = configuracion_orofacial();
sistema = preparar_sistema_orofacial(cfg);

postura = struct( ...
    'puntaYZ',[-2 5], ...
    'dorso',zeros(0,4), ...
    'vientre',zeros(0,4), ...
    'anguloApice',NaN, ...
    'anguloLamina',NaN, ...
    'curvaturaApical',0, ...
    'curvaturaLaminal',0);

sim = simular_postura_lingual( ...
    sistema.modeloFEM,sistema.lengua0,postura,cfg.simulacion);
analisis = analizar_articulacion(sistema,sim);
g = visualizar_sistema_orofacial( ...
    sistema,sim,analisis,cfg.visualizacion);
```

Para mostrar otra postura, se vuelve a llamar a `simular_postura_lingual` y `analizar_articulacion`, seguidos de `g = actualizar_visualizacion(g,sistema,nuevaSim,nuevoAnalisis)`. **No debe llamarse otra vez a `visualizar_sistema_orofacial` si se quieren conservar las figuras existentes.**

El ejemplo presupone que las subcarpetas funcionales están incluidas en el *path* de MATLAB. No se recomienda incluir `experimental/` indiscriminadamente, para evitar conflictos con implementaciones anteriores.

## 4. Datos y convenciones

### `cfg`: configuración

- `cfg.rutas`: raíz del módulo y ruta absoluta a `STL/`.
- `cfg.geometria`: parámetros de `lengua_ideal` y de mallado.
- `cfg.biomecanica`: propiedades constitutivas y anclajes.
- `cfg.simulacion`: opciones del solucionador, guiado, control de forma, regularización y validación.
- `cfg.cavidad`: lectura de STL y preparación de referencias sagitales.
- `cfg.analisis`: criterios exploratorios del análisis.
- `cfg.visualizacion`: selección de figuras, puntos, cavidad y marcadores.
- `cfg.secuencias`: **ejemplos de prueba** de barridos y transiciones; no son todavía una biblioteca de fonemas.

**Regla:** modificar `cfg.biomecanica` o la geometría exige preparar un `sistema` nuevo. Para cambiar solamente `postura`, puede reutilizarse el `sistema` existente.

### `sistema`: elementos reutilizables

| Campo | Contenido |
| --- | --- |
| `lengua0` | Geometría de referencia en reposo. |
| `malla` | Nodos y elementos de la malla FEM. |
| `modeloFEM` | Propiedades, restricciones y estructuras necesarias para resolver. |
| `cavidad` | Geometría y regiones importadas desde los STL. |
| `contactoSagital` | Referencias geométricas preprocesadas; **no** genera fuerzas de contacto. |
| `configuracion` | Copia de la configuración usada para construir el sistema. |

### `postura`: objetivos articulatorios

| Campo | Formato | Interpretación |
| --- | --- | --- |
| `puntaYZ` | `[Y Z]` | Posición absoluta objetivo de la punta, en mm. |
| `dorso`, `vientre` | `[s, DeltaZ, peso]` | Desplazamiento vertical respecto a la referencia en la coordenada material `s`. |
| `dorso`, `vientre` | `[s, Yobjetivo, Zobjetivo, peso]` | Objetivos absolutos alternativos; `NaN` permite dejar libre una coordenada. |
| `curvaturaApical`, `curvaturaLaminal` | Escalares | Objetivos de control de forma. |
| `anguloApice`, `anguloLamina` | Escalares o `NaN` | Objetivos angulares; `NaN` indica que no se impone ese objetivo. |
| `nombre` | Texto | Identificador opcional para secuencias. |

**Convenciones:** `X` es lateral, `Y` anteroposterior (`+Y` anterior) y `Z` vertical. La punta en reposo es el origen de las coordenadas de simulación. La coordenada material es `s = 0` en la punta y `s = 1` hacia el extremo posterior; no es una distancia en milímetros.

### `simulacion` y `analisis`: resultados

- `simulacion.estado`: estado deformado FEM, incluidos nodos y posición final de la punta.
- `simulacion.lengua`: geometría reconstruida, con `malla` 3D y perfil `sagital`.
- `simulacion.resultado`: información interna de la solución, errores y puntos objetivo.
- `simulacion.estadoBase`: solución comparativa opcional; puede estar vacía.
- `simulacion.validacion` y `simulacion.resumen`: indicadores de aceptación numérica y resumen de postura.
- `analisis.holguras`: distancias verticales sagitales por región, cuando hay cobertura geométrica.
- `analisis.solapamiento` y `analisis.validacionGeometrica`: estimaciones geométricas de intersección y su evaluación.

Un resultado `NaN` en una holgura puede indicar **ausencia de cobertura o correspondencia válida**, no necesariamente contacto ni una falla del solucionador. Las distancias a regiones tampoco son equivalentes a fuerzas de contacto.

## 5. Qué realiza cada etapa internamente

**Preparación.** `preparar_sistema_orofacial` solicita la lengua paramétrica, crea la malla FEM, configura el material y el anclaje posterior, importa la cavidad y prepara la referencia sagital de sus regiones. El resultado se reutiliza entre posturas.

**Resolución.** `simular_postura_lingual` interpreta los objetivos y delega la solución en `resolver_postura_con_guia`, que organiza las restricciones de posición, forma y regularización antes de usar `resolver_postura_no_lineal`. La deformación se reconstruye en 3D mediante `reconstruir_lengua_3d` y se somete a controles numéricos. La solución comparativa sin ciertas guías es opcional (`calcularBaseComparativa`).

**Análisis anatómico.** `analizar_articulacion` compara el estado calculado con las referencias preparadas de la cavidad. Calcula proximidades, holguras y solapamientos principalmente sagitales; esta operación **no retroalimenta fuerzas de contacto al FEM**.

**Visualización.** `visualizar_sistema_orofacial` crea una figura 3D y otra sagital. `visualizar_cavidad_preparada` dibuja los STL ya importados. `actualizar_visualizacion` modifica las superficies, perfiles y marcadores mediante sus identificadores gráficos; conserva las figuras y la cavidad fija.

**Secuencias.** Las pruebas actuales calculan varias posturas de equilibrio y las almacenan para mostrarlas con un slider. Entre soluciones FEM precalculadas se pueden interpolar *visualmente* las mallas, pero **esas interpolaciones no son soluciones FEM adicionales y no tienen validación anatómica propia**.

## 6. Extender el simulador sin alterar el núcleo

Para incorporar un fonema o gesto nuevo:

1. Definir sus objetivos en una estructura `postura` o una sucesión de estructuras con el mismo contrato.
2. Documentar el origen de los objetivos (medidos, bibliográficos, calculados o exploratorios) y sus unidades.
3. Reutilizar `sistema` y resolver cada postura mediante `simular_postura_lingual`.
4. Evaluar cada solución con `analizar_articulacion` y las métricas numéricas disponibles.
5. Visualizar con las funciones existentes; mantener separado el cálculo de la reproducción.
6. Añadir una prueba de regresión antes de modificar funciones de `control/` o `biomecanica/`.

No se debe interpretar una configuración que converge como una articulación fisiológicamente demostrada. La validación numérica y la plausibilidad anatómica se evalúan por separado.

## 7. Verificación y mantenimiento

- **Prueba principal:** `principal.m` verifica la integración completa, pero su postura de demostración extrema puede producir advertencias de compresión e interferencia; **no es el caso de referencia para una postura aceptada**.
- **Barrido moderado:** el caso de punta `[-2, 5] mm`, sin objetivos dorsales/ventrales, ha dado aproximadamente `Jmin = 0.95049`, sin solapamientos sagitales detectados en la configuración comprobada.
- **Transición completa:** en la prueba de nueve posturas, el último estado con guías dorsales/ventrales y curvatura apical ha dado aproximadamente `Jmin = 0.90819`, sin solapamientos sagitales detectados. Este resultado **no es intercambiable** con el caso anterior.
- **Tras mover carpetas:** comprobar con `which nombre_funcion -all` que MATLAB carga la implementación esperada y no una versión histórica.
- **Tras cambiar material, malla o solucionador:** volver a ejecutar los casos anteriores; las cifras son referencias de regresión para esa configuración, no tolerancias universales.

`prueba_barrido_orofacial.m`, en su versión actual, es un **script de prueba** que reutiliza `cfg`, `sistema` y `simulacion` presentes en el espacio de trabajo después de ejecutar `principal.m`. No debe documentarse como una función autónoma hasta modificar esa dependencia.

## 8. Antecedentes metodológicos

El empleo de un modelo simplificado centrado en la mecánica lingual y el plano sagital tiene antecedentes en trabajos de modelado biomecánico con elementos finitos:

1. Y. Payan y P. Perrier, “Synthesis of V-V sequences with a 2D biomechanical tongue model controlled by the Equilibrium Point Hypothesis,” *Speech Communication*, vol. 22, núms. 2–3, pp. 185–205, 1997. https://doi.org/10.1016/S0167-6393(97)00019-8
2. P. Perrier, Y. Payan, M. Zandipour y J. Perkell, “Influences of tongue biomechanics on speech movements during the production of velar stop consonants: a modeling study,” *The Journal of the Acoustical Society of America*, vol. 114, núm. 3, pp. 1582–1599, 2003. https://doi.org/10.1121/1.1587737

