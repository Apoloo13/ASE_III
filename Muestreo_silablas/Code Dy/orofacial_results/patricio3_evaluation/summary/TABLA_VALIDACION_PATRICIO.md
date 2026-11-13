# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)

## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 0.0521 ± 0.0986 u | 0.1005 ± 0.0219 u | 0.1557 u | 0.1325 u | 0.3400 u |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 0.1253 ± 0.1419 u | 0.2364 ± 0.0331 u | 0.2292 u | 0.2235 u | 0.3391 u |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 0.2157 ± 0.1357 u | 0.1144 ± 0.0225 u | 0.1679 u | 0.1561 u | 0.2894 u |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 0.0302 ± 0.0569 u | 0.0680 ± 0.0139 u | 0.0358 u | 0.0315 u | 0.0779 u |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 0.1058 ± 0.1083 u | 0.1298 ± 0.0684 u | 0.1471 u (0.1503 / 0.1353 / 0.1558) | 0.1359 u (0.1399 / 0.1237 / 0.1441) | 0.2616 u (0.2552 / 0.2492 / 0.2804) |

## 2. Tabla en Milímetros Físicos (Escala = 35.0 mm)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 1.82 ± 3.45 mm | 3.52 ± 0.77 mm | 5.45 mm | 4.64 mm | 11.90 mm |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 4.39 ± 4.97 mm | 8.27 ± 1.16 mm | 8.02 mm | 7.82 mm | 11.87 mm |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 7.55 ± 4.75 mm | 4.00 ± 0.79 mm | 5.88 mm | 5.46 mm | 10.13 mm |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 1.06 ± 1.99 mm | 2.38 ± 0.49 mm | 1.25 mm | 1.10 mm | 2.73 mm |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 3.70 ± 3.79 mm | 4.54 ± 2.39 mm | 5.15 mm (5.26 / 4.74 / 5.45) | 4.76 mm (4.90 / 4.33 / 5.04) | 9.16 mm (8.93 / 8.72 / 9.81) |
