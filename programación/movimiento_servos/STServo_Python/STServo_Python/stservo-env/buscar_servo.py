from scservo_sdk import *

# CONFIGURACION
DEVICENAME = "COM7"  # Cambia por tu puerto COM

BAUDRATES = [1000000, 115200]

portHandler = PortHandler(DEVICENAME)
servo = sms_sts(portHandler)

print("Abriendo puerto:", DEVICENAME)

if not portHandler.openPort():
    print("ERROR: No se pudo abrir el puerto")
    quit()

print("Puerto abierto correctamente.")

encontrados = []

try:
    for baud in BAUDRATES:

        print()
        print("==============================")
        print("Probando baudrate:", baud)
        print("==============================")

        if not portHandler.setBaudRate(baud):
            print("Error configurando baudrate")
            continue

        for servo_id in range(254):

            modelo, resultado, error = servo.ping(servo_id)

            if resultado == COMM_SUCCESS:

                print()
                print("############################")
                print("SERVO ENCONTRADO")
                print("ID:", servo_id)
                print("BAUDRATE:", baud)
                print("MODELO:", modelo)
                print("############################")
                print()

                encontrados.append((servo_id, baud))

    print()
    print("========== RESULTADOS ==========")

    if encontrados:
        for ID, baud in encontrados:
            print(f"Servo ID {ID} - Baudrate {baud}")
    else:
        print("NO SE ENCONTRO NINGUN SERVO")
        print()
        print("Revisa:")
        print("1. Jumper Waveshare en B")
        print("2. Fuente externa de 12 V")
        print("3. Conexion D/V/G")
        print("4. Cable USB")
        print("5. Puerto COM")

finally:
    portHandler.closePort()

print()
print("Busqueda terminada.")