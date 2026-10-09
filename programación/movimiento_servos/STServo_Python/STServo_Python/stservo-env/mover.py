from scservo_sdk import *
import time

# ============================
# CONFIGURACION
# ============================

DEVICENAME = "COM7"
BAUDRATE = 1000000

# ============================
# INICIAR
# ============================

portHandler = PortHandler(DEVICENAME)
servo = sms_sts(portHandler)

if not portHandler.openPort():
    print("ERROR: no se pudo abrir el puerto")
    quit()

print("Puerto abierto correctamente")

if not portHandler.setBaudRate(BAUDRATE):
    print("ERROR: no se pudo configurar el baudrate")
    portHandler.closePort()
    quit()

print("Baudrate configurado:", BAUDRATE)

# ============================
# BUSCAR SERVO
# ============================

SERVO_ID = None

print()
print("Buscando servo...")

for id_actual in [1, 2]:

    print("Probando ID", id_actual)

    modelo, resultado, error = servo.ping(id_actual)

    if resultado == COMM_SUCCESS:

        SERVO_ID = id_actual

        print()
        print("==========================")
        print(" SERVO ENCONTRADO")
        print("==========================")
        print("ID:", SERVO_ID)
        print("Modelo:", modelo)

        break

if SERVO_ID is None:

    print()
    print("ERROR: no se encontro ID 1 ni ID 2")
    print()
    print("Revisa:")
    print("- Jumper Waveshare en B")
    print("- Fuente externa de 12 V")
    print("- D / V / G")
    print("- COM7")
    
    portHandler.closePort()
    quit()

# ============================
# ACTIVAR TORQUE
# ============================

resultado, error = servo.write1ByteTxRx(
    SERVO_ID,
    40,
    1
)

print()
print("Torque activado")

# ============================
# LEER POSICION INICIAL
# ============================

posicion, resultado, error = servo.ReadPos(SERVO_ID)

print("Posicion inicial:", posicion)

print()
print("==========================")
print(" CONTROL STS3215")
print("==========================")
print()
print("Escribe una posicion.")
print("Prueba primero:")
print("1900")
print("2048")
print("2200")
print()
print("q = salir")
print()

# ============================
# CONTROL
# ============================

while True:

    entrada = input("Posicion: ").strip()

    if entrada.lower() == "q":
        break

    try:

        posicion = int(entrada)

        if posicion < 0 or posicion > 4095:
            print("Usa valores entre 0 y 4095")
            continue

        print(
            "Moviendo servo",
            SERVO_ID,
            "a",
            posicion
        )

        resultado, error = servo.WritePosEx(
            SERVO_ID,
            posicion,
            300,    # velocidad
            20      # aceleracion
        )

        time.sleep(0.5)

        posicion_real, resultado, error = servo.ReadPos(
            SERVO_ID
        )

        print("Posicion real:", posicion_real)
        print()

    except ValueError:

        print("Escribe un numero valido")

# ============================
# SALIR
# ============================

servo.write1ByteTxRx(
    SERVO_ID,
    40,
    0
)

portHandler.closePort()

print("Servo desconectado")


ㅤㅤㅤ