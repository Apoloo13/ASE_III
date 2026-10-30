
from scservo_sdk import *

# =====================================
# CONFIGURACION
# =====================================

PUERTO = "COM3"  # Usa tu puerto COM correcto
BAUDRATE = 1000000

VELOCIDAD = 300
ACELERACION = 30

# =====================================
# CONVERSIONES
# =====================================

def a_grados(pos):
    return pos * 360 / 4095

def a_posicion(grados):
    if not 0 <= grados <= 360:
        raise ValueError("El angulo debe estar entre 0 y 360")
    return round(grados * 4095 / 360)

# =====================================
# CONEXION
# =====================================

port = PortHandler(PUERTO)
servo = sms_sts(port)

habilitados = []

def leer_posicion(ID):
    pos, resultado, error = servo.ReadPos(ID)

    if resultado != COMM_SUCCESS or error != 0:
        raise RuntimeError(f"No se pudo leer ID {ID}")

    if not 0 <= pos <= 4095:
        raise RuntimeError(f"Posicion invalida en ID {ID}")

    return pos

def mover_individual(ID, grados):
    posicion = a_posicion(grados)

    resultado, error = servo.WritePosEx(
        ID, posicion, VELOCIDAD, ACELERACION
    )

    if resultado != COMM_SUCCESS or error != 0:
        raise RuntimeError(f"Error al mover ID {ID}")

    print(f"ID {ID} -> {grados:.1f} grados")

def mover_ambos(objetivos):
    try:
        for ID, grados in objetivos.items():
            posicion = a_posicion(grados)

            agregado = servo.SyncWritePosEx(
                ID, posicion, VELOCIDAD, ACELERACION
            )

            if not agregado:
                raise RuntimeError(
                    f"No se pudo preparar ID {ID}"
                )

        resultado = servo.groupSyncWrite.txPacket()

        if resultado != COMM_SUCCESS:
            raise RuntimeError("Error en envio sincronizado")

        print("Movimiento enviado a ambos servos")

    finally:
        servo.groupSyncWrite.clearParam()

# =====================================
# PROGRAMA PRINCIPAL
# =====================================

try:
    if not port.openPort():
        raise RuntimeError("No se pudo abrir el puerto")

    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("No se pudo configurar baudrate")

    print("Puerto abierto correctamente")
    print("Buscando servos...")

    encontrados = []

    for ID in range(0, 21):
        modelo, resultado, error = servo.ping(ID)

        if resultado == COMM_SUCCESS and error == 0:
            encontrados.append(ID)
            print(f"Servo detectado: ID {ID}, modelo {modelo}")

    if len(encontrados) != 2 or 2 not in encontrados:
        raise RuntimeError(
            "Se requieren exactamente 2 IDs distintos, "
            "incluyendo el ID 2. Revisa los servos."
        )

    # El servo previamente probado sera el numero 1
    IDs = [2, next(i for i in encontrados if i != 2)]

    posiciones = {}

    print("\n========== SERVOS ==========")

    for numero, ID in enumerate(IDs, 1):
        pos = leer_posicion(ID)
        posiciones[ID] = a_grados(pos)

        print(
            f"Servo {numero}: ID {ID} | "
            f"{posiciones[ID]:.1f} grados"
        )

    # Activar torque
    for ID in IDs:
        resultado, error = servo.write1ByteTxRx(
            ID, 40, 1
        )

        if resultado != COMM_SUCCESS or error != 0:
            raise RuntimeError(
                f"No se pudo activar torque en ID {ID}"
            )

        habilitados.append(ID)

    # =================================
    # CONTROL MANUAL
    # =================================

    print("\n======= CONTROL MANUAL =======")
    print("1 180       -> Servo 1 a 180 grados")
    print("2 90        -> Servo 2 a 90 grados")
    print("1 +10       -> Servo 1 avanza 10 grados")
    print("2 -10       -> Servo 2 retrocede 10 grados")
    print("ambos 180   -> Ambos a 180 grados")
    print("ambos 90 180 -> Dos angulos diferentes")
    print("p           -> Leer posiciones reales")
    print("q           -> Salir")
    print("==============================")

    while True:
        comando = input("\nComando: ").strip().lower()
        partes = comando.split()

        if not partes:
            continue

        if partes[0] == "q":
            break

        if partes[0] == "p":
            for numero, ID in enumerate(IDs, 1):
                posicion = leer_posicion(ID)
                grados = a_grados(posicion)
                posiciones[ID] = grados

                print(
                    f"Servo {numero} (ID {ID}): "
                    f"{grados:.1f} grados"
                )
            continue

        try:
            # MOVER LOS DOS SIMULTANEAMENTE
            if partes[0] == "ambos":
                if len(partes) not in (2, 3):
                    print("Uso: ambos 180 o ambos 90 180")
                    continue

                ang1 = float(partes[1])
                ang2 = (
                    float(partes[2])
                    if len(partes) == 3 else ang1
                )

                objetivos = {
                    IDs[0]: ang1,
                    IDs[1]: ang2
                }

                # Validar antes de enviar
                for ang in objetivos.values():
                    a_posicion(ang)

                mover_ambos(objetivos)
                posiciones.update(objetivos)

            # MOVER UN SOLO SERVO
            elif partes[0] in ("1", "2"):
                if len(partes) != 2:
                    print("Uso: 1 180 o 2 90")
                    continue

                numero = int(partes[0])
                ID = IDs[numero - 1]
                valor = partes[1]

                if valor.startswith(("+", "-")):
                    objetivo = posiciones[ID] + float(valor)
                else:
                    objetivo = float(valor)

                mover_individual(ID, objetivo)
                posiciones[ID] = objetivo

            else:
                print("Comando no reconocido")

        except (ValueError, RuntimeError) as e:
            print(f"ERROR: {e}")

except KeyboardInterrupt:
    print("\nPrograma interrumpido")

except Exception as e:
    print(f"\nERROR: {e}")

finally:
    for ID in habilitados:
        try:
            servo.write1ByteTxRx(ID, 40, 0)
        except Exception:
            pass

    port.closePort()
    print("Puerto cerrado")
