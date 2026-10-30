# import pandas as pd
# import matplotlib.pyplot as plt

# def graficar_trayectoria(csv_path, silaba_objetivo="TA"):
#     # Cargar los datos
#     df = pd.read_csv(csv_path)
    
#     # Filtrar solo la sílaba que queremos analizar
#     df_syl = df[df['Silaba'] == silaba_objetivo]
    
#     if df_syl.empty:
#         print(f"No se encontraron datos para la sílaba: {silaba_objetivo}")
#         return

#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
#     # --- Gráfica 1: Movimiento 2D de los puntos (Trayectoria XY) ---
#     ax1.plot(df_syl['BOCA_SUP_Norm_X'], df_syl['BOCA_SUP_Norm_Y'], label='Superior', color='blue', alpha=0.7)
#     ax1.plot(df_syl['BOCA_INF_Norm_X'], df_syl['BOCA_INF_Norm_Y'], label='Inferior', color='red', alpha=0.7)
#     ax1.plot(df_syl['BOCA_IZQ_Norm_X'], df_syl['BOCA_IZQ_Norm_Y'], label='Izquierda', color='green', alpha=0.7)
#     ax1.plot(df_syl['BOCA_DER_Norm_X'], df_syl['BOCA_DER_Norm_Y'], label='Derecha', color='orange', alpha=0.7)
    
#     # Invertimos el eje Y para que coincida con la visión humana (cara no invertida)
#     ax1.invert_yaxis()
#     ax1.set_title(f"Trayectoria Espacial XY - Sílaba '{silaba_objetivo}'")
#     ax1.set_xlabel("Eje X Normalizado (Relativo a la nariz)")
#     ax1.set_ylabel("Eje Y Normalizado (Relativo a la nariz)")
#     ax1.legend()
#     ax1.grid(True, linestyle='--', alpha=0.6)
    
#     # --- Gráfica 2: Dinámica de Apertura en el Tiempo ---
#     # Calculamos la distancia vertical y horizontal en cada frame
#     apertura_vertical = df_syl['BOCA_INF_Norm_Y'] - df_syl['BOCA_SUP_Norm_Y']
#     apertura_horizontal = abs(df_syl['BOCA_IZQ_Norm_X'] - df_syl['BOCA_DER_Norm_X'])
    
#     ax2.plot(df_syl['Tiempo_ms'], apertura_vertical, label='Apertura Vertical', color='purple')
#     ax2.plot(df_syl['Tiempo_ms'], apertura_horizontal, label='Apertura Horizontal', color='teal')
#     ax2.set_title(f"Apertura en el Tiempo - Sílaba '{silaba_objetivo}'")
#     ax2.set_xlabel("Tiempo (milisegundos)")
#     ax2.set_ylabel("Distancia Normalizada")
#     ax2.legend()
#     ax2.grid(True, linestyle='--', alpha=0.6)
    
#     plt.tight_layout()
#     plt.show()

# # Para usarlo solo pones la ruta de tu archivo CSV y la sílaba
# graficar_trayectoria("./BRO/TA.csv", "TA")
import pandas as pd
import matplotlib.pyplot as plt

import pandas as pd
import matplotlib.pyplot as plt

def comparar_participantes(csv_path_1, csv_path_2, nombre_1="Participante 1", nombre_2="Participante 2"):
    try:
        # Cargar los datos
        df1 = pd.read_csv(csv_path_1)
        df2 = pd.read_csv(csv_path_2)
        
        # 1. Calcular la Apertura Vertical Bruta
        apertura1 = df1['BOCA_INF_Norm_Y'] - df1['BOCA_SUP_Norm_Y']
        apertura2 = df2['BOCA_INF_Norm_Y'] - df2['BOCA_SUP_Norm_Y']
        
        # 2. Normalizar el Tiempo (Hacer que ambos empiecen en t = 0 ms)
        tiempo1 = df1['Tiempo_ms'] - df1['Tiempo_ms'].iloc[0]
        tiempo2 = df2['Tiempo_ms'] - df2['Tiempo_ms'].iloc[0]
        
        # 3. Normalizar el Reposo (Hacer que ambas bocas empiecen cerradas en y = 0)
        desplazamiento1 = apertura1 - apertura1.iloc[0]
        desplazamiento2 = apertura2 - apertura2.iloc[0]
        
        # --- Dibujar la gráfica ---
        plt.figure(figsize=(10, 6))
        
        # Graficamos el Desplazamiento (Delta) a lo largo del tiempo corregido
        plt.plot(tiempo1, desplazamiento1, label=nombre_1, color='purple', linewidth=2)
        plt.plot(tiempo2, desplazamiento2, label=nombre_2, color='teal', linewidth=2)
        
        silaba = df1['Silaba'].iloc[0]
        
        plt.title(f"Comparación de Movimiento: Sílaba '{silaba}'")
        plt.xlabel("Tiempo desde inicio de grabación (ms)")
        plt.ylabel("Desplazamiento Vertical (Apertura Neta)")
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Hubo un error: {e}")
        print("Revisa que las rutas a los archivos CSV sean las correctas.")

# --- AQUÍ ESTÁ LA CORRECCIÓN ---
# Tienes que poner las rutas reales de tus carpetas aquí. 
# Por ejemplo, si tienes una carpeta BRO y otra LO:
comparar_participantes("./lue/SE.csv", "./Bro/SE.csv", "lue", "Bro")