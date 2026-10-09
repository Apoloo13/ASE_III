from scservo_sdk import *
import time

PUERTO = "COM7"  # Cambia por tu COM
BAUDRATE = 1000000

port = PortHandler(PUERTO)
servo = sms_sts(port)

if not port.openPort():
    print("ERROR: No se pudo abrir el puerto")
    quit()

if not port.setBaudRate(BAUDRATE):
    print("ERROR: Baudrate")
    port.closePort()
    quit()

print("\n=== DIAGNOSTICO STS3215 ===")

disponibles = []

for ID in [1, 2]:

    print(f"\n--- SERVO {ID} ---")

    modelo, resultado, error = servo.ping(ID)

    if resultado != COMM_SUCCESS:
        print("NO DETECTADO")
        continue

    print("DETECTADO")
    disponibles.append(ID)

    # Leer modo
    modo, resultado, error = servo.read1ByteTxRx(ID, 33)
    print("Modo:", modo if resultado == COMM_SUCCESS else "Error")

    # Leer voltaje
    voltaje, resultado, error = servo.read1ByteTxRx(ID, 62)
    if resultado == COMM_SUCCESS:
        print("Voltaje:", voltaje / 10, "V")
    else:
        print("Error leyendo voltaje")

    # Activar torque
    resultado, error = servo.write1ByteTxRx(ID, 40, 1)
    print("Activar torque:", resultado, "Error:", error)

    # Comprobar torque
    torque, resultado, error = servo.read1ByteTxRx(ID, 40)
    print("Torque:", torque if resultado == COMM_SUCCESS else "Error")

    # Posicion
    posicion, resultado, error = servo.ReadPos(ID)

    if resultado == COMM_SUCCESS:
        print("Posicion:", posicion)
    else:
        print("Error leyendo posicion")

print("\n=== CONTROL MANUAL ===")
print("Escribe: ID desplazamiento")
print("Ejemplo: 1 100")
print("Ejemplo: 2 -100")
print("q para salir")

try:
    while True:

        entrada = input("\n> ").strip()

        if entrada.lower() == "q":
            break

        try:
            ID, desplazamiento = map(int, entrada.split())

            if ID not in disponibles:
                print("Servo no detectado")
                continue

            if abs(desplazamiento) > 150:
                print("Usa desplazamientos de -150 a 150")
                continue

            modo, resultado, error = servo.read1ByteTxRx(ID, 33)

            if resultado != COMM_SUCCESS or modo != 0:
                print("El servo no esta en modo posicion (0)")
                continue

            actual, resultado, error = servo.ReadPos(ID)

            if resultado != COMM_SUCCESS:
                print("No se pudo leer la posicion")
                continue

            destino = actual + desplazamiento

            if not 0 <= destino <= 4095:
                print("Movimiento fuera de rango")
                continue

            print("Actual:", actual)
            print("Destino:", destino)

            resultado, error = servo.WritePosEx(
                ID, destino, 300, 20
            )

            print("Resultado:", resultado, "Error:", error)

            time.sleep(1)

            nueva, resultado, error = servo.ReadPos(ID)

            if resultado == COMM_SUCCESS:
                print("Posicion real:", nueva)
            else:
                print("Error leyendo posicion final")

        except ValueError:
            print("Formato: 1 100")

finally:
    for ID in disponibles:
        servo.write1ByteTxRx(ID, 40, 0)

    port.closePort()
    print("Puerto cerrado")