# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)

## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 0.0521 ± 0.0986 u | 0.0947 ± 0.0357 u | 0.0450 u | 0.0370 u | 0.1167 u |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 0.1253 ± 0.1419 u | 0.1032 ± 0.0351 u | 0.0518 u | 0.0423 u | 0.1171 u |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 0.2157 ± 0.1357 u | 0.1329 ± 0.0367 u | 0.0688 u | 0.0533 u | 0.1536 u |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 0.0302 ± 0.0569 u | 0.0526 ± 0.0106 u | 0.0291 u | 0.0245 u | 0.0669 u |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 0.1058 ± 0.1083 u | 0.0959 ± 0.0422 u | 0.0487 u (0.0447 / 0.0457 / 0.0556) | 0.0393 u (0.0368 / 0.0354 / 0.0456) | 0.1136 u (0.1040 / 0.1138 / 0.1231) |

## 2. Tabla en Milímetros Físicos (Escala = 35.0 mm)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 1.82 ± 3.45 mm | 3.32 ± 1.25 mm | 1.58 mm | 1.29 mm | 4.09 mm |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 4.39 ± 4.97 mm | 3.61 ± 1.23 mm | 1.81 mm | 1.48 mm | 4.10 mm |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 7.55 ± 4.75 mm | 4.65 ± 1.28 mm | 2.41 mm | 1.87 mm | 5.38 mm |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 1.06 ± 1.99 mm | 1.84 ± 0.37 mm | 1.02 mm | 0.86 mm | 2.34 mm |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 3.70 ± 3.79 mm | 3.36 ± 1.48 mm | 1.70 mm (1.56 / 1.60 / 1.95) | 1.37 mm (1.29 / 1.24 / 1.60) | 3.98 mm (3.64 / 3.98 / 4.31) |
