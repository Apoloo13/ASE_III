# Guía de desarrollo y mantenimiento

Registrar criterios prácticos para ampliar el simulador sin perder consistencia ni reproducibilidad. No sustituye al [README](../README.md), la [arquitectura](ARQUITECTURA.md) ni la [referencia de funciones](REFERENCIA_FUNCIONES.md).

## 1. Dónde realizar los cambios

| Necesidad | Intervención recomendada |
| --- | --- |
| Probar otra postura | Definir nuevos objetivos `postura` y utilizar las interfaces existentes. |
| Incorporar un fonema o gesto | Añadir su definición y secuencia en `secuencias/`, separadas del solucionador y de las demostraciones. |
| Cambiar material, anclajes o resolución de malla | Ajustar `cfg` y **reconstruir `sistema`** antes de resolver. |
| Añadir mediciones o indicadores | Extender `analisis/` sin alterar el equilibrio FEM, salvo que sea indispensable. |
| Modificar la presentación | Trabajar en `visualizacion/` y conservar los identificadores gráficos existentes. |
| Cambiar ecuaciones o estrategias de guiado | Justificar el cambio, documentar su efecto y repetir las pruebas de regresión. |

**Criterio general:** modificar primero la capa que define el problema; intervenir el núcleo biomecánico solo cuando las interfaces existentes no permitan representar lo requerido.

## 2. Construcción de gestos y fonemas

- **Separar datos y cálculo.** Una definición articulatoria debe almacenar sus objetivos; no duplicar dentro de ella el FEM, el análisis de cavidad ni la visualización.
- **Identificar el origen de cada objetivo:** medición humana, referencia instrumental o bibliográfica, transformación calculada, o hipótesis exploratoria. Registrar unidades y sistema de referencia.
- **Conservar la correspondencia material.** Si se interpolan objetivos dorsales o ventrales entre dos posturas, sus posiciones `s` deben corresponder entre sí; verificar también dimensiones y significado de columnas. Una interpolación de consignas requiere resolver cada estado que se vaya a evaluar.
- **No confundir representación con solución.** Las mallas interpoladas para reproducción son cuadros visuales; no deben generar métricas FEM, holguras ni afirmaciones de contacto como si hubieran sido resueltas.
- **Mantener los fonemas independientes.** Sus parámetros deben poder modificarse sin alterar la configuración global ni afectar otras secuencias.

## 3. Consistencia de datos y resultados

- Trabajar siempre en el sistema de referencia del simulador. Antes de incorporar datos externos, documentar su transformación espacial y, para secuencias, la normalización temporal empleada.
- Reutilizar un `sistema` únicamente mientras permanezcan iguales la geometría, la malla, el material, los anclajes y la cavidad. Evitar modificar sus campos durante los barridos.
- Conservar por separado **objetivos solicitados**, **estado calculado**, **validación numérica** y **análisis geométrico**. Que el solucionador converja no demuestra por sí mismo plausibilidad anatómica.
- Interpretar `NaN` en las holguras como ausencia de una comparación válida en esa región; no sustituirlo automáticamente por cero.
- Registrar la configuración usada y las condiciones de cada ensayo si sus resultados van a compararse, presentarse o publicarse.

## 4. Verificación mínima antes de aceptar un cambio

1. Comprobar que MATLAB utiliza las funciones esperadas (`which nombre_funcion -all`) y que `experimental/` no introduce implementaciones antiguas en la ruta activa.
2. Ejecutar el caso de referencia anterior **sin cambiar sus parámetros**; comparar tamaño de malla, posición final de la punta, `Jmin` y resultados sagitales. Los valores de referencia están en `ARQUITECTURA.md`.
3. Resolver y analizar por separado la nueva postura o secuencia; identificar advertencias, fallos de convergencia, inversión de elementos y posibles solapamientos.
4. Verificar que la actualización de figuras no reimporte la cavidad ni regenere ejes por cada postura.
5. Si cambia el comportamiento de una interfaz pública, actualizar `REFERENCIA_FUNCIONES.md`; si cambia una decisión de diseño, actualizar esta guía.

## 5. Límites que condicionan el desarrollo

El modelo prioriza la deformación **sagital cuasiestática**. La reconstrucción 3D facilita la inspección espacial, pero no constituye un FEM volumétrico. La proximidad a una región de la cavidad **no es una fuerza de contacto**, y las secuencias no representan todavía una dinámica muscular ni una temporización fisiológica validada.

Las regiones STL y los parámetros geométricos y mecánicos deben conservar su **procedencia documentada**; las publicaciones citadas en `ARQUITECTURA.md` son antecedentes metodológicos, no validaciones directas de esta implementación.

**Antes de ampliar el proyecto:** comprobar qué está realmente implementado, qué es experimental y qué sigue siendo una hipótesis. No convertir una capacidad propuesta en una capacidad documentada como existente.