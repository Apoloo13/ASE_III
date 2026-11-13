# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)

## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 0.0521 ± 0.0986 u | 0.1044 ± 0.0391 u | 0.0575 u | 0.0475 u | 0.1566 u |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 0.1253 ± 0.1419 u | 0.1086 ± 0.0470 u | 0.0541 u | 0.0444 u | 0.1258 u |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 0.2157 ± 0.1357 u | 0.0953 ± 0.0370 u | 0.0926 u | 0.0727 u | 0.1940 u |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 0.0302 ± 0.0569 u | 0.0641 ± 0.0253 u | 0.0383 u | 0.0344 u | 0.0760 u |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 0.1058 ± 0.1083 u | 0.0931 ± 0.0409 u | 0.0606 u (0.0603 / 0.0512 / 0.0703) | 0.0497 u (0.0496 / 0.0405 / 0.0591) | 0.1381 u (0.1379 / 0.1200 / 0.1565) |

## 2. Tabla en Milímetros Físicos (Escala = 35.0 mm)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 1.82 ± 3.45 mm | 3.65 ± 1.37 mm | 2.01 mm | 1.66 mm | 5.48 mm |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 4.39 ± 4.97 mm | 3.80 ± 1.65 mm | 1.89 mm | 1.55 mm | 4.40 mm |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 7.55 ± 4.75 mm | 3.34 ± 1.30 mm | 3.24 mm | 2.54 mm | 6.79 mm |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 1.06 ± 1.99 mm | 2.24 ± 0.89 mm | 1.34 mm | 1.20 mm | 2.66 mm |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 3.70 ± 3.79 mm | 3.26 ± 1.43 mm | 2.12 mm (2.11 / 1.79 / 2.46) | 1.74 mm (1.73 / 1.42 / 2.07) | 4.83 mm (4.82 / 4.20 / 5.48) |
