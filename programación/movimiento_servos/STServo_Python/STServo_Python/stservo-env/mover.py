
from scservo_sdk import *

# =====================================
# CONFIGURACION
# =====================================

PUERTO = "COM3"   # Usa el COM que te funciono
BAUDRATE = 1000000
SERVO_ID = 2

VELOCIDAD = 300
ACELERACION = 30
PASO = 10

# =====================================
# FUNCIONES
# =====================================

def a_grados(posicion):
    return posicion * 360 / 4095

def a_posicion(grados):
    return round(grados * 4095 / 360)

def leer_posicion():
    pos, resultado, error = servo.ReadPos(SERVO_ID)
    if resultado != COMM_SUCCESS or error != 0:
        raise RuntimeError("Error al leer posicion")
    return pos

def mover(grados):
    grados = max(0, min(360, grados))
    posicion = a_posicion(grados)

    resultado, error = servo.WritePosEx(
        SERVO_ID,
        posicion,
        VELOCIDAD,
        ACELERACION
    )

    if resultado == COMM_SUCCESS and error == 0:
        print(f"Objetivo: {grados:.1f} grados")
        return True

    print("Error al enviar movimiento")
    return False

# =====================================
# CONECTAR
# =====================================

port = PortHandler(PUERTO)
servo = sms_sts(port)
torque_activado = False

try:
    if not port.openPort():
        raise RuntimeError("No se pudo abrir el puerto")

    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("Error al configurar baudrate")

    print("Puerto abierto correctamente")

    modelo, resultado, error = servo.ping(SERVO_ID)

    if resultado != COMM_SUCCESS or error != 0:
        raise RuntimeError("Servo ID 2 no detectado")

    print(f"Servo ID {SERVO_ID} conectado")
    print(f"Modelo: {modelo}")

    posicion_inicial = leer_posicion()
    angulo = a_grados(posicion_inicial)

    print(f"Posicion actual: {angulo:.1f} grados")

    resultado, error = servo.write1ByteTxRx(
        SERVO_ID, 40, 1
    )

    if resultado != COMM_SUCCESS or error != 0:
        raise RuntimeError("No se pudo activar el torque")

    torque_activado = True

    # =================================
    # CONTROL MANUAL
    # =================================

    print("\n====== CONTROL MANUAL ======")
    print("a = Girar 10 grados menos")
    print("d = Girar 10 grados mas")
    print("p = Leer posicion real")
    print("0-360 = Elegir angulo")
    print("q = Salir")
    print("============================")

    while True:

        comando = input("\nComando: ").strip().lower()

        if comando == "q":
            break

        if comando == "p":
            angulo = a_grados(leer_posicion())
            print(f"Posicion real: {angulo:.1f} grados")
            continue

        if comando == "a":
            objetivo = angulo - PASO

        elif comando == "d":
            objetivo = angulo + PASO

        else:
            try:
                objetivo = float(comando)
            except ValueError:
                print("Comando no valido")
                continue

        objetivo = max(0, min(360, objetivo))

        if mover(objetivo):
            angulo = objetivo

except KeyboardInterrupt:
    print("\nPrograma interrumpido")

except Exception as e:
    print(f"\nERROR: {e}")

finally:
    if torque_activado:
        servo.write1ByteTxRx(SERVO_ID, 40, 0)

    port.closePort()
    print("Puerto cerrado")
