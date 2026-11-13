# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)

## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 0.0521 ± 0.0986 u | 0.0842 ± 0.0162 u | 0.0505 u | 0.0401 u | 0.1485 u |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 0.1253 ± 0.1419 u | 0.1295 ± 0.0253 u | 0.1239 u | 0.1134 u | 0.2316 u |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 0.2157 ± 0.1357 u | 0.1060 ± 0.0294 u | 0.1099 u | 0.0911 u | 0.2354 u |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 0.0302 ± 0.0569 u | 0.1017 ± 0.0190 u | 0.0490 u | 0.0447 u | 0.0933 u |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 0.1058 ± 0.1083 u | 0.1053 ± 0.0278 u | 0.0834 u (0.0852 / 0.0663 / 0.0985) | 0.0723 u (0.0756 / 0.0546 / 0.0867) | 0.1772 u (0.1699 / 0.1608 / 0.2009) |

## 2. Tabla en Milímetros Físicos (Escala = 35.0 mm)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 1.82 ± 3.45 mm | 2.95 ± 0.57 mm | 1.77 mm | 1.40 mm | 5.20 mm |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 4.39 ± 4.97 mm | 4.53 ± 0.89 mm | 4.34 mm | 3.97 mm | 8.10 mm |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 7.55 ± 4.75 mm | 3.71 ± 1.03 mm | 3.85 mm | 3.19 mm | 8.24 mm |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 1.06 ± 1.99 mm | 3.56 ± 0.67 mm | 1.72 mm | 1.56 mm | 3.26 mm |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 3.70 ± 3.79 mm | 3.69 ± 0.97 mm | 2.92 mm (2.98 / 2.32 / 3.45) | 2.53 mm (2.65 / 1.91 / 3.04) | 6.20 mm (5.94 / 5.63 / 7.03) |
