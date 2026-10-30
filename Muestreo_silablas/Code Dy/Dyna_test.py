from dynamixel_sdk import *
import time

# ============================================================
# 1. CONFIGURACIÓN
# ============================================================
DEVICENAME = "COM5"      # Confirma que siga siendo el mismo puerto
BAUDRATE = 1000000       # Velocidad de comunicación de fábrica
PROTOCOL_XL = 2.0        # Los XL320 usan protocolo 2.0
IDS_XL = [4, 5]          # Pon aquí los IDs de tus motores

# Direcciones en la memoria del XL-320
ADDR_TORQUE = 24
ADDR_GOAL_POS = 30
ADDR_SPEED = 32

# ============================================================
# 2. ABRIR CONEXIÓN
# ============================================================
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_XL)

portHandler.openPort()
portHandler.setBaudRate(BAUDRATE)

# ============================================================
# 3. ENCENDER MÚSCULOS Y FIJAR VELOCIDAD
# ============================================================
# En XL320 la velocidad va de 0 a 1023. 200 es suave para pruebas iniciales.
VELOCIDAD = 200 

for dxl_id in IDS_XL:
    packetHandler.write1ByteTxRx(portHandler, dxl_id, ADDR_TORQUE, 1) # 1 = Torque ON
    packetHandler.write2ByteTxRx(portHandler, dxl_id, ADDR_SPEED, VELOCIDAD)

print("Motores activados. Iniciando secuencia...")

# ============================================================
# 4. RUTINA DE MOVIMIENTO
# ============================================================
# En XL320 la posición va de 0 a 1023 (0 a 300 grados)
# 512 es exactamente el centro (150 grados)

try:
    # Movimiento 1 (Ej. Posición de reposo)
    print("Posición A")
    for dxl_id in IDS_XL:
        packetHandler.write2ByteTxRx(portHandler, dxl_id, ADDR_GOAL_POS, 400)
    time.sleep(1.5) # Espera 1.5 segundos

    # Movimiento 2 (Ej. Apertura de mandíbula)
    print("Posición B")
    for dxl_id in IDS_XL:
        packetHandler.write2ByteTxRx(portHandler, dxl_id, ADDR_GOAL_POS, 600)
    time.sleep(1.5)

    # Regreso al centro
    print("Regreso al centro")
    for dxl_id in IDS_XL:
        packetHandler.write2ByteTxRx(portHandler, dxl_id, ADDR_GOAL_POS, 512)
    time.sleep(0.3)

    for dxl_id in IDS_XL:
        packetHandler.write2ByteTxRx(portHandler, dxl_id, ADDR_GOAL_POS, 0)
    time.sleep(1)

except KeyboardInterrupt:
    print("\nDetenido por el usuario.")

# ============================================================
# 5. APAGAR Y CERRAR
# ============================================================
# Es crucial apagar el torque al terminar para que los motores no se calienten
for dxl_id in IDS_XL:
    packetHandler.write1ByteTxRx(portHandler, dxl_id, ADDR_TORQUE, 0) # 0 = Torque OFF

portHandler.closePort()
print("Conexión cerrada.")