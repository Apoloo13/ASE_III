from scservo_sdk import *

DEVICENAME = "COM7"
BAUDRATE = 1000000

ID_ACTUAL = 1
ID_NUEVO = 2

portHandler = PortHandler(DEVICENAME)
servo = sms_sts(portHandler)

if not portHandler.openPort():
    print("ERROR: no se pudo abrir el puerto")
    quit()

if not portHandler.setBaudRate(BAUDRATE):
    print("ERROR: no se pudo configurar el baudrate")
    quit()

print("Buscando servo ID 1...")

modelo, resultado, error = servo.ping(ID_ACTUAL)

if resultado != COMM_SUCCESS:
    print("ERROR: no se encontro el servo ID 1")
    portHandler.closePort()
    quit()

print("Servo encontrado.")
print("Cambiando ID 1 -> ID 2...")

# Desbloquear memoria
servo.unLockEprom(ID_ACTUAL)

# Registro 5 = ID
resultado, error = servo.write1ByteTxRx(
    ID_ACTUAL,
    5,
    ID_NUEVO
)

# Ahora responde como ID 2
servo.LockEprom(ID_NUEVO)

print("Cambio realizado.")

# Comprobar
modelo, resultado, error = servo.ping(ID_NUEVO)

if resultado == COMM_SUCCESS:
    print("CORRECTO: ahora el servo tiene ID 2")
else:
    print("No pude comprobar el nuevo ID.")

portHandler.closePort()