# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)

## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 0.0521 ± 0.0986 u | 0.0793 ± 0.0288 u | 0.0876 u | 0.0704 u | 0.2162 u |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 0.1253 ± 0.1419 u | 0.0981 ± 0.0391 u | 0.0922 u | 0.0764 u | 0.1961 u |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 0.2157 ± 0.1357 u | 0.1421 ± 0.0424 u | 0.0841 u | 0.0671 u | 0.1947 u |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 0.0302 ± 0.0569 u | 0.0698 ± 0.0208 u | 0.0294 u | 0.0246 u | 0.0651 u |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 0.1058 ± 0.1083 u | 0.0973 ± 0.0433 u | 0.0733 u (0.0665 / 0.0632 / 0.0903) | 0.0596 u (0.0550 / 0.0510 / 0.0729) | 0.1680 u (0.1548 / 0.1497 / 0.1996) |

## 2. Tabla en Milímetros Físicos (Escala = 35.0 mm)

| Subsistema / Mecanismo | Actuadores / Método | Ref. Humana / MATLAB (μ ± σ) | Medición FK / Sim. PySINDy | RMSE | MAE | Error Máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Comisuras (5 barras 2 GDL, 61/291) | IDs 5–8 (FK Encoder) | 1.82 ± 3.45 mm | 2.78 ± 1.01 mm | 3.06 mm | 2.46 mm | 7.57 mm |
| Mandíbula (Arco circular, 152) | IDs 1–2 (FK Encoder) | 4.39 ± 4.97 mm | 3.43 ± 1.37 mm | 3.23 mm | 2.67 mm | 6.86 mm |
| Labio Inf. (Piñón-cremallera, 17) | ID 10 (FK Encoder) | 7.55 ± 4.75 mm | 4.98 ± 1.48 mm | 2.94 mm | 2.35 mm | 6.82 mm |
| Labio Sup. (Manivela-pistón, 0) | ID 9 (FK Encoder) | 1.06 ± 1.99 mm | 2.44 ± 0.73 mm | 1.03 mm | 0.86 mm | 2.28 mm |
| Lengua (Costillas pull-pull, /r,s,t/) | 2 Servos (Sim. PySINDy) | [ Polígono MATLAB ] | [ Espacio Estados ] | [ -- ] | [ -- ] | [ -- ] |
| Desempeño Global por Sílabas | SA–SU / TA–TU / RA–RU | 3.70 ± 3.79 mm | 3.41 ± 1.52 mm | 2.57 mm (2.33 / 2.21 / 3.16) | 2.09 mm (1.92 / 1.78 / 2.55) | 5.88 mm (5.42 / 5.24 / 6.99) |
