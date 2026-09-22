from scservo_sdk import *

DEVICENAME = "COM7"
BAUDRATE = 1000000

portHandler = PortHandler(DEVICENAME)
servo = sms_sts(portHandler)

if not portHandler.openPort():
    print("ERROR abriendo puerto")
    quit()

if not portHandler.setBaudRate(BAUDRATE):
    print("ERROR configurando baudrate")
    quit()

print("============================")
print(" CONTROL DE DOS STS3215")
print("============================")
print()
print("Escribe:")
print()
print("1 2048")
print("para mover el servo 1")
print()
print("2 2048")
print("para mover el servo 2")
print()
print("q para salir")
print()

while True:

    comando = input("> ")

    if comando.lower() == "q":
        break

    try:
        datos = comando.split()

        if len(datos) != 2:
            print("Formato: ID POSICION")
            continue

        servo_id = int(datos[0])
        posicion = int(datos[1])

        if servo_id != 1 and servo_id != 2:
            print("El ID debe ser 1 o 2")
            continue

        if posicion < 0 or posicion > 4095:
            print("La posicion debe estar entre 0 y 4095")
            continue

        servo.WritePosEx(
            servo_id,
            posicion,
            300,
            20
        )

        print("Servo", servo_id, "->", posicion)

    except:
        print("Comando incorrecto.")

portHandler.closePort()