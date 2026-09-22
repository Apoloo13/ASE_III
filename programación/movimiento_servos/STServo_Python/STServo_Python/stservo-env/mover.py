from scservo_sdk import *
import time

# ============================
# CONFIGURACION
# ============================

DEVICENAME = 'COM7'      # CAMBIA ESTO
BAUDRATE = 1000000
SERVO_ID = 1

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
    quit()

print("Baudrate configurado")

# ============================
# PING
# ============================

model_number, comm_result, error = servo.ping(SERVO_ID)

if comm_result != COMM_SUCCESS:
    print("ERROR: servo no encontrado")
    portHandler.closePort()
    quit()

print("Servo encontrado")
print("Modelo:", model_number)

# ============================
# ACTIVAR TORQUE
# ============================

servo.write1ByteTxRx(
    SERVO_ID,
    40,       # Torque Enable
    1
)

print()
print("==========================")
print(" CONTROL STS3215")
print("==========================")
print("Escribe una posicion")
print("0 - 4095")
print("q = salir")
print()

# ============================
# CONTROL
# ============================

while True:

    entrada = input("Posicion: ")

    if entrada.lower() == "q":
        break

    try:
        posicion = int(entrada)

        if posicion < 0 or posicion > 4095:
            print("Usa valores entre 0 y 4095")
            continue

        # ID, posicion, velocidad, aceleracion
        servo.WritePosEx(
            SERVO_ID,
            posicion,
            500,
            50
        )

        time.sleep(0.2)

        posicion_real, resultado, error = servo.ReadPos(SERVO_ID)

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