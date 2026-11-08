# -*- coding: utf-8 -*-
"""Interfaz para 8 servos FEETECH STS3215-12V y hasta 4 parejas LIBRES.

Los ocho servos aparecen siempre como controles individuales (1..8).
Se pueden agrupar dos cualesquiera en parejas visuales, sin repetir servos.
Cada pareja conserva los modos ESPEJO / IGUAL / INDEPENDIENTE; las dos casillas
son excluyentes. Las parejas y sus ajustes se pueden guardar/cargar en JSON.

Los servos comparten el bus de datos (independientemente de los conectores
fisicos de la placa) y cada servo debe tener un ID UNICO.
La cantidad de motores admitidos depende tambien de la alimentacion y del bus.

Rutinas y grupos paralelos:
    Las rutinas individuales y los grupos se guardan en archivos JSON.
    Varias rutinas de servos distintos pueden ejecutarse en paralelo.
    El mismo hilo serial intercala las ordenes cuando vence cada espera:
    NO escribe simultaneamente por COM3. No se permite que dos rutinas
    activas controlen un mismo ID, para impedir ordenes contradictorias.
    Detener cancela las ordenes pendientes, NO frena un movimiento que
    ya recibio el servo ni constituye un paro de emergencia.

Requisitos:
    python -m pip install ftservo-python-sdk pyserial
Ejecutar:
    python interfaz_8_servos_parejas_personalizadas_COM3.py
"""

import json
import math
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from scservo_sdk import COMM_SUCCESS, PortHandler, sms_sts
except ImportError as exc:
    raise SystemExit(
        "Falta el SDK. Instala con: python -m pip install ftservo-python-sdk pyserial"
    ) from exc

COM = "COM3"
BAUDRATE = 1000000
ESCANEAR_DESDE = 0
ESCANEAR_HASTA = 20
TORQUE_ENABLE_ADDR = 40
SMS_STS_ID_ADDR = 5  # Registro ID del STS3215 (EPROM)
NUM_PAIRS = 4
NUM_SERVOS = NUM_PAIRS * 2
SERVO_NAMES = tuple(f"{letter}{number}" for letter in "ABCD" for number in (1, 2))
ROUTINE_FORMAT = "feetech_sts3215_routine"
ROUTINE_VERSION = 1
MAX_STEPS = 500
MAX_PARALLEL = 16
GROUP_FORMAT = "feetech_sts3215_parallel_group"
ROUTINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rutinas_sts3215")
PAIR_FORMAT = "feetech_sts3215_pair_configuration"
PAIR_VERSION = 1
PAIR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parejas_sts3215")

BG = "#0d1524"
PANEL = "#182338"
PANEL2 = "#202f48"
TEXT = "#eaf1fb"
MUTED = "#a6b6cf"
BLUE = "#4ea8ff"
GREEN = "#49d9ac"
DANGER = "#f29aa2"
BORDER = "#30415b"


def pos_to_deg(pos):
    return float(pos) * 360.0 / 4095.0


def deg_to_pos(deg):
    degree = float(deg)
    if not (0 <= degree <= 360):
        raise ValueError("El angulo debe estar entre 0 y 360 grados")
    return round(degree * 4095 / 360)



def validate_pair_configuration(raw):
    """Validacion segura de los archivos de configuracion de parejas."""
    if not isinstance(raw, dict) or raw.get("format") != PAIR_FORMAT \
            or raw.get("version") != PAIR_VERSION:
        raise ValueError("El archivo no es una configuracion de parejas compatible")
    servos = raw.get("servos")
    if not isinstance(servos, list) or len(servos) != NUM_SERVOS:
        raise ValueError("La configuracion debe contener los ocho servos")
    clean_servos, ids = [], set()
    for i, item in enumerate(servos):
        if not isinstance(item, dict):
            raise ValueError(f"Servo {i+1}: formato incorrecto")
        sid = item.get("id")
        if type(sid) is not str:
            raise ValueError(f"Servo {i+1}: ID incorrecto")
        sid = sid.strip()
        if sid:
            if not sid.isdecimal() or not 0 <= int(sid) <= 253:
                raise ValueError(f"Servo {i+1}: ID fuera de 0 a 253")
            if int(sid) in ids:
                raise ValueError(f"El ID {sid} aparece en mas de un servo")
            ids.add(int(sid))
        try:
            angle = float(item.get("angle"))
            deg_to_pos(angle)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"Servo {i+1}: objetivo angular invalido")
        if not math.isfinite(angle):
            raise ValueError(f"Servo {i+1}: angulo invalido")
        clean_servos.append({"id": sid, "angle": angle})
    pairs = raw.get("pairs")
    if not isinstance(pairs, list) or len(pairs) > NUM_PAIRS:
        raise ValueError("Maximo cuatro parejas")
    used, clean_pairs = set(), []
    for j, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"Pareja {j+1}: formato incorrecto")
        first, second = pair.get("first"), pair.get("second")
        if type(first) is not int or type(second) is not int or \
                not 0 <= first < NUM_SERVOS or not 0 <= second < NUM_SERVOS \
                or first == second or first in used or second in used:
            raise ValueError(f"Pareja {j+1}: servos repetidos o no validos")
        used.update((first, second))
        name = pair.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 45:
            raise ValueError(f"Pareja {j+1}: nombre incorrecto (1 a 45 caracteres)")
        mode = pair.get("mode")
        if mode not in ("mirror", "same", "independent"):
            raise ValueError(f"Pareja {j+1}: modo desconocido")
        enabled = pair.get("enabled")
        if type(enabled) is not bool:
            raise ValueError(f"Pareja {j+1}: opcion 'incluir' incorrecta")
        clean_pairs.append({"first": first, "second": second,
                            "name": name.strip(), "mode": mode,
                            "enabled": enabled})
    speed, acc = raw.get("speed"), raw.get("acc")
    if type(speed) is not int or not 50 <= speed <= 1500:
        raise ValueError("Velocidad fuera de 50 a 1500")
    if type(acc) is not int or not 0 <= acc <= 100:
        raise ValueError("Aceleracion fuera de 0 a 100")
    return {"format": PAIR_FORMAT, "version": PAIR_VERSION, "servos": clean_servos,
            "pairs": clean_pairs, "speed": speed, "acc": acc}


def validate_routine_document(raw):
    """Valida el JSON importado antes de permitir enviar ordenes al hardware."""
    if not isinstance(raw, dict):
        raise ValueError("El archivo no contiene una rutina valida")
    if raw.get("format") != ROUTINE_FORMAT or raw.get("version") != ROUTINE_VERSION:
        raise ValueError("Formato o version de rutina no compatibles")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("El nombre de la rutina es invalido (maximo 120 caracteres)")
    repeats = raw.get("repeats", 1)
    if type(repeats) is not int or not 1 <= repeats <= 100:
        raise ValueError("Las repeticiones deben estar entre 1 y 100")
    steps = raw.get("steps")
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise ValueError(f"La rutina debe contener maximo {MAX_STEPS} pasos")
    validated = []
    for ix, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Paso {ix}: formato incorrecto")
        step_name = step.get("name")
        if not isinstance(step_name, str) or not step_name.strip() or len(step_name) > 80:
            raise ValueError(f"Paso {ix}: nombre invalido (maximo 80 caracteres)")
        try:
            wait_s = float(step.get("wait_s"))
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"Paso {ix}: espera no numerica")
        if not math.isfinite(wait_s) or not 0 <= wait_s <= 60:
            raise ValueError(f"Paso {ix}: la espera debe estar entre 0 y 60 s")
        speed, acc = step.get("speed"), step.get("acc")
        if type(speed) is not int or not 50 <= speed <= 1500:
            raise ValueError(f"Paso {ix}: velocidad fuera de 50-1500")
        if type(acc) is not int or not 0 <= acc <= 100:
            raise ValueError(f"Paso {ix}: aceleracion fuera de 0-100")
        targets = step.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= NUM_SERVOS:
            raise ValueError(f"Paso {ix}: selecciona entre 1 y 8 servos")
        clean_targets, seen_slots, seen_ids = [], set(), set()
        for target in targets:
            if not isinstance(target, dict):
                raise ValueError(f"Paso {ix}: objetivo incorrecto")
            slot, servo_id = target.get("slot"), target.get("id")
            if slot not in SERVO_NAMES:
                raise ValueError(f"Paso {ix}: nombre de servo no valido: {slot}")
            if type(servo_id) is not int or not 0 <= servo_id <= 253:
                raise ValueError(f"Paso {ix}: ID no valido para {slot}")
            try:
                angle = float(target.get("angle_deg"))
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"Paso {ix}: angulo no numerico para {slot}")
            if not math.isfinite(angle) or not 0 <= angle <= 360:
                raise ValueError(f"Paso {ix}: angulo de {slot} fuera de 0-360°")
            if servo_id in seen_ids or slot in seen_slots:
                raise ValueError(f"Paso {ix}: ID o posicion logica duplicados")
            seen_ids.add(servo_id)
            seen_slots.add(slot)
            clean_targets.append({"slot": slot, "id": servo_id, "angle_deg": angle})
        validated.append({"name": step_name.strip(), "wait_s": wait_s,
                          "speed": speed, "acc": acc, "targets": clean_targets})
    return {"format": ROUTINE_FORMAT, "version": ROUTINE_VERSION,
            "name": name.strip(), "repeats": repeats, "steps": validated}

class ConcurrentRoutines:
    """Planificador cooperativo de rutinas. Nunca accede al puerto desde varios hilos.

    Cada rutina tiene su reloj independiente. Si dos pasos coinciden, sus
    WritePosEx se envian consecutivamente por el UNICO hilo del puerto serie.
    """

    def __init__(self, emit, writer):
        self.emit = emit
        self.writer = writer
        self.jobs = {}

    @staticmethod
    def ids_of(document):
        return {target["id"] for step in document["steps"]
                for target in step["targets"]}

    def start_batch(self, servo, proposed):
        if not isinstance(proposed, list) or not 1 <= len(proposed) <= MAX_PARALLEL:
            raise ValueError("Selecciona entre 1 y 16 rutinas")
        occupied = {servo_id: job["name"] for job in self.jobs.values()
                    for servo_id in job["ids"]}
        prepared = []
        known_run_ids = set(self.jobs)
        for payload in proposed:
            run_id = str(payload["run_id"])
            if run_id in known_run_ids:
                raise ValueError(f"La rutina {run_id} ya se esta ejecutando")
            known_run_ids.add(run_id)
            doc = validate_routine_document(payload["data"])
            if not doc["steps"]:
                raise ValueError(f'La rutina "{doc["name"]}" no tiene pasos')
            ids = self.ids_of(doc)
            for sid in sorted(ids):
                if sid in occupied:
                    raise ValueError(
                        f'Conflicto en ID {sid}: "{doc["name"]}" y '
                        f'"{occupied[sid]}". Cada servo debe pertenecer '
                        'a una sola rutina activa.'
                    )
                occupied[sid] = doc["name"]
            prepared.append((run_id, doc, ids))

        # Se verifican TODOS los servos ANTES de arrancar una sola rutina.
        for sid in sorted(occupied):
            model, result, error = servo.ping(sid)
            if result != COMM_SUCCESS or error != 0:
                raise RuntimeError(
                    f"El ID {sid} no responde. Ninguna nueva rutina fue iniciada."
                )

        common_start = time.monotonic()
        for run_id, doc, ids in prepared:
            self.jobs[run_id] = {
                "name": doc["name"], "steps": doc["steps"],
                "repeats": doc["repeats"], "ids": ids,
                "step": 0, "round": 0, "next_due": common_start,
                "final_wait": False,
            }
            self.emit("routine_job_started", run_id, doc["name"],
                      len(doc["steps"]), doc["repeats"])

    def complete(self, run_id, result, message):
        job = self.jobs.pop(run_id, None)
        if job is not None:
            self.emit("routine_job_done", run_id, result, message)

    def stop(self, run_ids=None):
        selected = list(self.jobs) if run_ids is None else list(run_ids)
        for run_id in selected:
            self.complete(run_id, "stopped", "Detenida por el usuario")

    def tick(self, servo):
        # Una iteracion puede enviar UN paso de CADA rutina lista. Esto impide
        # que una rutina con espera de 0 s monopolice el bus.
        for run_id, job in list(self.jobs.items()):
            if run_id not in self.jobs or time.monotonic() < job["next_due"]:
                continue
            if job["final_wait"]:
                self.complete(run_id, "completed", "Todos los pasos ejecutados")
                continue
            step = job["steps"][job["step"]]
            try:
                targets = [(target["id"], target["angle_deg"])
                           for target in step["targets"]]
                self.writer(servo, targets, step["speed"], step["acc"])
            except Exception as exc:
                self.complete(run_id, "error", str(exc))
                continue
            self.emit("routine_job_step", run_id, job["step"], job["round"],
                      len(job["steps"]), job["repeats"], step["name"])
            job["step"] += 1
            if job["step"] >= len(job["steps"]):
                job["step"] = 0
                job["round"] += 1
                if job["round"] >= job["repeats"]:
                    job["final_wait"] = True
            # Espera medida desde que terminaron de ENVIARSE las instrucciones.
            job["next_due"] = time.monotonic() + step["wait_s"]


class ServoWorker(threading.Thread):
    """Unico propietario del puerto COM3 y del planificador de rutinas."""

    def __init__(self, messages, events):
        super().__init__(daemon=True)
        self.messages = messages
        self.events = events
        self.enabled = set()
        self.scheduler = ConcurrentRoutines(self.emit, self.write_targets)

    def emit(self, *payload):
        self.events.put(payload)

    def write_targets(self, servo, targets, speed, acc):
        """Usa WritePosEx con confirmacion individual, nunca en paralelo."""
        for servo_id, _ in targets:
            if servo_id not in self.enabled:
                result, error = servo.write1ByteTxRx(
                    servo_id, TORQUE_ENABLE_ADDR, 1
                )
                if result != COMM_SUCCESS or error != 0:
                    raise RuntimeError(f"No se pudo activar torque en ID {servo_id}")
                self.enabled.add(servo_id)
        sent = []
        for servo_id, deg in targets:
            result, error = servo.WritePosEx(
                servo_id, deg_to_pos(deg), speed, acc
            )
            if result != COMM_SUCCESS or error != 0:
                raise RuntimeError(
                    f"ID {servo_id} no confirmo WritePosEx. "
                    f"Ordenes enviadas previamente: {sent}"
                )
            sent.append(servo_id)
        return sent

    def run(self):
        port = None
        try:
            port = PortHandler(COM)
            servo = sms_sts(port)
            if not port.openPort():
                raise RuntimeError(f"No se pudo abrir {COM}")
            if not port.setBaudRate(BAUDRATE):
                raise RuntimeError(f"No se pudo configurar {BAUDRATE} baudios")
            self.emit("connected")
            while True:
                try:
                    # Nunca dormir durante la espera de una rutina: se puede
                    # detener una sola o introducir otra rutina mientras corre.
                    action = self.messages.get(
                        timeout=0.02 if self.scheduler.jobs else None
                    )
                except queue.Empty:
                    action = None
                if action is not None:
                    cmd = action[0]
                    if cmd == "disconnect":
                        self.scheduler.stop()
                        break
                    try:
                        if cmd == "start_routines":
                            try:
                                self.scheduler.start_batch(servo, action[1])
                            except Exception as exc:
                                self.emit("routine_batch_error",
                                          [str(item["run_id"]) for item in action[1]],
                                          str(exc))
                        elif cmd == "stop_routines":
                            self.scheduler.stop(action[1])
                        else:
                            if self.scheduler.jobs:
                                raise RuntimeError(
                                    "Hay rutinas activas; termina o detenlas "
                                    "antes de enviar ordenes manuales o cambiar IDs."
                                )
                            if cmd == "scan":
                                self.emit("info", "Buscando IDs 0-20...")
                                found = []
                                for servo_id in range(ESCANEAR_DESDE, ESCANEAR_HASTA + 1):
                                    model, result, error = servo.ping(servo_id)
                                    if result == COMM_SUCCESS and error == 0:
                                        found.append((servo_id, model))
                                self.emit("scan_result", found)
                            elif cmd == "probe_ids":
                                checks = []
                                for index, servo_id in action[1]:
                                    model, result, error = servo.ping(servo_id)
                                    ok = result == COMM_SUCCESS and error == 0
                                    checks.append((index, servo_id, ok,
                                                   model if ok else None))
                                self.emit("probe_result", checks)
                            elif cmd == "change_id":
                                old_id, new_id = action[1:]
                                if old_id == new_id:
                                    raise ValueError("El ID nuevo debe ser diferente")
                                model, result, error = servo.ping(old_id)
                                if result != COMM_SUCCESS or error != 0:
                                    raise RuntimeError(
                                        f"El ID original {old_id} no responde. "
                                        "Busca el servo con UNO solo conectado."
                                    )
                                model, result, error = servo.ping(new_id)
                                if result == COMM_SUCCESS:
                                    raise RuntimeError(f"El ID {new_id} ya responde")
                                result, error = servo.unLockEprom(old_id)
                                if result != COMM_SUCCESS or error != 0:
                                    raise RuntimeError("No se pudo desbloquear EPROM")
                                servo.write1ByteTxRx(old_id, SMS_STS_ID_ADDR, new_id)
                                time.sleep(0.15)
                                changed = False
                                for _ in range(3):
                                    model, result, error = servo.ping(new_id)
                                    if result == COMM_SUCCESS and error == 0:
                                        changed = True
                                        break
                                    time.sleep(0.12)
                                if changed:
                                    lock_result, lock_error = servo.LockEprom(new_id)
                                    if lock_result != COMM_SUCCESS or lock_error != 0:
                                        self.emit("info", "ADVERTENCIA: ID nuevo detectado, "
                                                  "pero no se pudo confirmar bloqueo EPROM")
                                    self.enabled.discard(old_id)
                                    self.emit("id_changed", old_id, new_id, model)
                                else:
                                    try:
                                        servo.LockEprom(old_id)
                                    except Exception:
                                        pass
                                    raise RuntimeError(
                                        "No se pudo verificar el ID nuevo. "
                                        "No repitas la escritura sin revisar el ID real."
                                    )
                            elif cmd == "read":
                                for index, sid in action[1]:
                                    position, result, error = servo.ReadPos(sid)
                                    if result != COMM_SUCCESS or error != 0:
                                        self.emit("read_error", index, sid)
                                    elif 0 <= position <= 4095:
                                        self.emit("position", index, sid, pos_to_deg(position))
                                    else:
                                        self.emit("read_outside", index, sid, position)
                            elif cmd == "move":
                                targets, speed, acc = action[1:]
                                sent = self.write_targets(servo, targets, speed, acc)
                                self.emit("sent", sent)
                            elif cmd == "release":
                                failures = []
                                for sid in list(self.enabled):
                                    result, error = servo.write1ByteTxRx(
                                        sid, TORQUE_ENABLE_ADDR, 0
                                    )
                                    if result == COMM_SUCCESS and error == 0:
                                        self.enabled.discard(sid)
                                    else:
                                        failures.append(sid)
                                if failures:
                                    raise RuntimeError(
                                        f"No se pudo liberar torque en IDs {failures}"
                                    )
                                self.emit("info", "Torque liberado en los servos")
                    except Exception as exc:
                        self.emit("error", f"{cmd}: {exc}")
                if self.scheduler.jobs:
                    self.scheduler.tick(servo)
        except Exception as exc:
            self.emit("error", f"Conexion: {exc}")
        finally:
            self.scheduler.stop()
            if port is not None:
                try:
                    for sid in list(self.enabled):
                        servo.write1ByteTxRx(sid, TORQUE_ENABLE_ADDR, 0)
                except Exception:
                    pass
                try:
                    port.closePort()
                except Exception:
                    pass
            self.emit("disconnected")

class ServoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Control FEETECH STS3215 · parejas personalizadas · COM3")
        self.root.geometry("1180x890")
        self.root.minsize(970, 700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.commands = None
        self.worker = None
        self.connected = False
        self.closing = False
        self.ids_found = []
        self.servo_rows = []
        self.routine_steps = []
        self.routine_path = None
        self.routine_running = False
        self.routine_window = None
        self.routine_dirty = False
        self.parallel_window = None
        self.parallel_plans = []
        self.next_parallel_id = 0
        self.running_job_ids = set()
        self.running_job_data = {}
        self.editor_play_id = None
        self.routine_name_var = tk.StringVar(value="Mi rutina")
        self.routine_repeats_var = tk.StringVar(value="1")
        self.routine_name_var.trace_add("write", self.mark_routine_dirty)
        self.routine_repeats_var.trace_add("write", self.mark_routine_dirty)
        # Parejas creadas por el usuario; se identifican por numero de servo 0..7.
        self.pairs = []
        self.pair_file_path = None
        self.pair_filename_var = tk.StringVar(value="Parejas sin guardar")
        self.new_pair_name_var = tk.StringVar(value="")
        self.first_choice_var = tk.StringVar()
        self.second_choice_var = tk.StringVar()
        self.pair_choice_indices = {}
        self.status = tk.StringVar(value="Desconectado. Conecta la placa y presiona Conectar.")
        self.speed = tk.IntVar(value=300)
        self.acc = tk.IntVar(value=30)
        self.build()
        self.root.after(80, self.process_events)

    def label(self, parent, text, size=11, fg=TEXT, bold=False, **kw):
        return tk.Label(parent, text=text, font=("Segoe UI", size,
                        "bold" if bold else "normal"), fg=fg,
                        bg=kw.pop("bg", PANEL), **kw)

    def button(self, parent, text, command, bg=BLUE, fg=BG, **kw):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=GREEN, activeforeground=BG,
                         relief="flat", font=("Segoe UI", 10, "bold"),
                         cursor="hand2", padx=12, pady=7, **kw)

    def build(self):
        head = tk.Frame(self.root, bg=BG, padx=20, pady=14)
        head.pack(fill="x")
        self.label(head, "CONTROL DE SERVOS STS3215", size=18,
                   bold=True, bg=BG).pack(anchor="w")
        self.label(head,
                   "8 servos individuales · crea hasta 4 parejas personalizadas · COM3 · 1,000,000 baudios",
                   size=10, fg=MUTED, bg=BG).pack(anchor="w", pady=(3, 0))

        toolbar = tk.Frame(self.root, bg=PANEL, padx=15, pady=11)
        toolbar.pack(fill="x", padx=20, pady=(0, 12))
        self.connect_btn = self.button(toolbar, "Conectar COM3", self.connect, bg=GREEN)
        self.connect_btn.pack(side="left", padx=(0, 8))
        self.scan_btn = self.button(toolbar, "Buscar servos", self.scan, bg=BLUE)
        self.scan_btn.pack(side="left", padx=(0, 8))
        self.probe_btn = self.button(toolbar, "Comprobar IDs escritos", self.probe_ids,
                                     bg=PANEL2, fg=TEXT)
        self.probe_btn.pack(side="left", padx=(0, 8))
        self.id_btn = self.button(toolbar, "Asignar ID (1 servo)",
                                  self.open_id_dialog, bg="#e6bb68", fg=BG)
        self.id_btn.pack(side="left", padx=(0, 8))
        self.routines_btn = self.button(toolbar, "Rutinas: crear / cargar",
                                        self.open_routine_editor, bg="#b09cff")
        self.routines_btn.pack(side="left", padx=(0, 8))
        self.disc_btn = self.button(toolbar, "Desconectar", self.disconnect,
                                    bg=PANEL2, fg=TEXT)
        self.disc_btn.pack(side="left", padx=(0, 8))
        self.release_btn = self.button(toolbar, "Liberar torque", self.release,
                                       bg="#723845", fg="#ffffff")
        self.release_btn.pack(side="right")

        settings = tk.Frame(self.root, bg=BG, padx=20)
        settings.pack(fill="x", pady=(0, 8))
        self.label(settings, "Velocidad", bg=BG, fg=MUTED).pack(side="left")
        tk.Spinbox(settings, from_=50, to=1500, increment=50, width=7,
                   textvariable=self.speed, font=("Segoe UI", 11)).pack(
                       side="left", padx=(8, 20))
        self.label(settings, "Aceleracion", bg=BG, fg=MUTED).pack(side="left")
        tk.Spinbox(settings, from_=0, to=100, increment=5, width=6,
                   textvariable=self.acc, font=("Segoe UI", 11)).pack(
                       side="left", padx=(8, 20))
        self.found_label = self.label(settings, "IDs detectados: —", bg=BG,
                                      fg=GREEN, size=10)
        self.found_label.pack(side="right")

        # Panel desplazable para que quepan las 4 parejas en ventanas pequenas.
        scroll_container = tk.Frame(self.root, bg=BG)
        scroll_container.pack(fill="both", expand=True, padx=20)
        canvas = tk.Canvas(scroll_container, bg=BG, highlightthickness=0,
                           borderwidth=0)
        self.main_canvas = canvas
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical",
                                 command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
            window_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            -1 if e.delta > 0 else (1 if e.delta < 0 else 0), "units"))
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        self.label(content, "SERVOS INDIVIDUALES (1 A 8)", size=14,
                   bold=True, bg=BG).pack(anchor="w", pady=(8, 3), padx=6)
        self.label(content, "Cada servo se configura individualmente. Puedes agrupar dos cualesquiera abajo.",
                   bg=BG, fg=MUTED, size=10).pack(anchor="w", padx=6, pady=(0, 5))
        servo_grid = tk.Frame(content, bg=BG)
        servo_grid.pack(fill="x", pady=(0, 15))
        for column in (0, 1):
            servo_grid.grid_columnconfigure(column, weight=1, uniform="servos")
        for i in range(NUM_SERVOS):
            self.build_servo_row(servo_grid, i)

        self.label(content, "CREAR Y GUARDAR PAREJAS", size=14, bold=True,
                   bg=BG).pack(anchor="w", pady=(3, 7), padx=6)
        creator = tk.Frame(content, bg=PANEL, padx=12, pady=10)
        creator.pack(fill="x", padx=6, pady=(0, 7))
        self.pair_creator = creator
        self.main_content = content
        self.label(creator, "Maestro", size=10).pack(side="left")
        self.first_combo = ttk.Combobox(creator, state="readonly", width=19,
                                        textvariable=self.first_choice_var)
        self.first_combo.pack(side="left", padx=(6, 10))
        self.label(creator, "Segundo", size=10).pack(side="left")
        self.second_combo = ttk.Combobox(creator, state="readonly", width=19,
                                         textvariable=self.second_choice_var)
        self.second_combo.pack(side="left", padx=(6, 10))
        self.label(creator, "Nombre", size=10).pack(side="left")
        tk.Entry(creator, textvariable=self.new_pair_name_var, width=18,
                 font=("Segoe UI", 10)).pack(side="left", padx=(5, 8))
        self.button(creator, "Crear pareja", self.create_pair, bg=GREEN).pack(side="left")
        tools = tk.Frame(content, bg=BG)
        tools.pack(fill="x", padx=6, pady=(1, 6))
        self.button(tools, "Guardar parejas", self.save_pairs, bg=GREEN).pack(side="left", padx=(0, 8))
        self.button(tools, "Abrir parejas (.json)", self.load_pairs,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 8))
        self.button(tools, "Borrar todas las parejas", self.clear_pairs,
                    bg="#703d4a", fg=TEXT).pack(side="left", padx=(0, 8))
        self.label(tools, "", textvariable=self.pair_filename_var, bg=BG,
                   size=9, fg=MUTED).pack(side="right")

        self.label(content, "PAREJAS CREADAS", size=14, bold=True,
                   bg=BG).pack(anchor="w", pady=(11, 6), padx=6)
        self.pair_list_frame = tk.Frame(content, bg=BG)
        self.pair_list_frame.pack(fill="x", padx=0, pady=(0, 12))
        self.refresh_pairs()

        bottom = tk.Frame(self.root, bg=PANEL, padx=14, pady=12)
        bottom.pack(fill="x", padx=20, pady=(9, 6))
        self.button(bottom, "Mover parejas activas", self.move_active_pairs,
                    bg=GREEN).pack(side="left")
        self.button(bottom, "Leer IDs configurados", self.read_all,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=10)
        self.button(bottom, "Crear / editar parejas", self.show_pair_manager,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 8))
        self.stop_routine_btn = self.button(
            bottom, "Detener secuencia", self.stop_routine, bg="#813d4a", fg=TEXT
        )
        self.stop_routine_btn.pack(side="right")
        self.button(bottom, "Rutinas en paralelo", self.open_parallel_manager,
                    bg="#b09cff").pack(side="left", padx=(10, 0))

        note = self.label(self.root,
            "Primero configura los IDs reales de los servos. Crea libremente parejas, "
            "guarda su combinacion y vuelve a abrirla cuando necesites. Modos: "
            "ESPEJO = segundo 360° - primero; IGUAL = segundo igual al primero; "
            "AMBAS DESMARCADAS = control independiente de ambos servos. "
            "Las casillas espejo e igual se excluyen mutuamente. "
            "Los IDs deben ser unicos, incluso si estan en conectores distintos. "
            "El bus envia las ordenes consecutivamente, no al mismo instante. "
            "Para cambiar un ID permanente, conecta SOLO un servo. "
            "Usa alimentacion externa de 12 V adecuada para el total de servos. "
            "Rutinas en paralelo permite ejecutar varias secuencias sobre IDs distintos. "
            "Todas comparten COM3 y las ordenes se intercalan. "
            "DETENER SECUENCIA cancela pasos siguientes, NO es paro de emergencia.",
            bg=BG, fg=MUTED, size=9, wraplength=1100, justify="left")
        note.pack(fill="x", padx=22, pady=(1, 5))
        tk.Label(self.root, textvariable=self.status, anchor="w", bg="#263550",
                 fg="#f6f9ff", font=("Segoe UI", 10), padx=17,
                 pady=10).pack(side="bottom", fill="x")
        self.set_connected_ui(False)
        self.set_routine_ui(False)

    def make_pair(self, first, second, name, mode="independent", enabled=True):
        return {
            "first": first, "second": second,
            "name": tk.StringVar(value=name),
            "mirror": tk.BooleanVar(value=mode == "mirror"),
            "same": tk.BooleanVar(value=mode == "same"),
            "enabled": tk.BooleanVar(value=enabled),
            "mode_label": tk.StringVar(),
        }

    def build_pair(self, parent, pair, position):
        first, second = pair["first"], pair["second"]
        box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        box.grid(row=position // 2, column=position % 2, sticky="nsew", padx=7, pady=7)
        head = tk.Frame(box, bg=PANEL)
        head.pack(fill="x", padx=12, pady=(10, 5))
        tk.Entry(head, textvariable=pair["name"], width=19,
                 font=("Segoe UI", 12, "bold"), bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief="flat").pack(side="left")
        tk.Checkbutton(head, text="Incluir en mover todas", variable=pair["enabled"],
                       bg=PANEL, fg=TEXT, selectcolor=PANEL2,
                       activebackground=PANEL, activeforeground=TEXT,
                       highlightthickness=0).pack(side="right")
        for index, label_text in ((first, "MAESTRO"), (second, "SEGUNDO")):
            servo_line = tk.Frame(box, bg=PANEL2, padx=9, pady=7)
            servo_line.pack(fill="x", padx=12, pady=3)
            self.label(servo_line, f"{label_text} · Servo {index+1} ({SERVO_NAMES[index]})",
                       bg=PANEL2, size=10, bold=True).pack(side="left")
            self.label(servo_line, "ID:", bg=PANEL2, fg=MUTED,
                       size=9).pack(side="left", padx=(8, 2))
            self.label(servo_line, "", textvariable=self.servo_rows[index]["id"],
                       bg=PANEL2, fg=GREEN, size=10).pack(side="left")
            self.label(servo_line, "°", bg=PANEL2, fg=MUTED,
                       size=9).pack(side="right", padx=(3, 0))
            tk.Entry(servo_line, width=7, justify="center",
                     textvariable=self.servo_rows[index]["angle"],
                     font=("Segoe UI", 10)).pack(side="right")
        modes = tk.Frame(box, bg=PANEL)
        modes.pack(fill="x", padx=12, pady=(8, 1))
        tk.Checkbutton(modes, text="Espejo", variable=pair["mirror"],
                       bg=PANEL, fg=GREEN, selectcolor=PANEL2,
                       activebackground=PANEL, activeforeground=GREEN,
                       highlightthickness=0, font=("Segoe UI", 10, "bold"),
                       command=lambda p=pair: self.mode_changed(p, "mirror")
                       ).pack(side="left", padx=(0, 25))
        tk.Checkbutton(modes, text="Igual", variable=pair["same"],
                       bg=PANEL, fg=GREEN, selectcolor=PANEL2,
                       activebackground=PANEL, activeforeground=GREEN,
                       highlightthickness=0, font=("Segoe UI", 10, "bold"),
                       command=lambda p=pair: self.mode_changed(p, "same")
                       ).pack(side="left")
        self.label(box, "", textvariable=pair["mode_label"], fg=MUTED,
                   size=9).pack(anchor="w", padx=14, pady=(3, 7))
        buttons = tk.Frame(box, bg=PANEL)
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        self.button(buttons, "Mover pareja", lambda p=pair: self.send_move(
            [p["first"], p["second"]]), bg=BLUE).pack(side="left", padx=(0, 5))
        self.button(buttons, "Leer pareja", lambda p=pair: self.read_rows(
            [p["first"], p["second"]]), bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(buttons, "Eliminar", lambda p=pair: self.delete_pair(p),
                    bg="#703d4a", fg=TEXT).pack(side="right")
        self.update_mode_label(pair)

    def build_servo_row(self, parent, index):
        card = tk.Frame(parent, bg=PANEL2, padx=10, pady=8,
                        highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=index // 2, column=index % 2, padx=7, pady=6, sticky="nsew")
        top = tk.Frame(card, bg=PANEL2)
        top.pack(fill="x")
        self.label(top, f"Servo {index+1} ({SERVO_NAMES[index]})", size=10,
                   bold=True, bg=PANEL2).pack(side="left")
        self.label(top, "  ID:", size=9, fg=MUTED, bg=PANEL2).pack(side="left")
        id_var = tk.StringVar(value="2" if index == 0 else "")
        tk.Entry(top, textvariable=id_var, width=5,
                 font=("Segoe UI", 10), justify="center").pack(side="left", padx=5)
        actual = tk.StringVar(value="Sin leer")
        self.label(top, "", textvariable=actual, size=9, fg=GREEN,
                   bg=PANEL2).pack(side="right")
        middle = tk.Frame(card, bg=PANEL2)
        middle.pack(fill="x", pady=(5, 1))
        self.label(middle, "Objetivo (°)", size=9, fg=MUTED,
                   bg=PANEL2).pack(side="left")
        angle_var = tk.StringVar(value="180")
        entry = tk.Entry(middle, textvariable=angle_var, width=8,
                         justify="center", font=("Segoe UI", 10))
        entry.pack(side="right")
        entry.bind("<Return>", lambda ev, i=index: self.move_from_control(i))
        slider = tk.Scale(card, from_=0, to=360, orient="horizontal",
                          resolution=1, showvalue=False, sliderlength=15,
                          bg=PANEL2, troughcolor="#384d6c",
                          highlightthickness=0, activebackground=GREEN)
        slider.set(180)
        slider.pack(fill="x")
        slider.bind("<ButtonRelease-1>", lambda ev, i=index: self.move_from_control(i))
        buttons = tk.Frame(card, bg=PANEL2)
        buttons.pack(fill="x", pady=(2, 0))
        self.button(buttons, "-10°", lambda i=index: self.nudge(i, -10),
                    bg=PANEL, fg=TEXT).pack(side="left", padx=(0, 4))
        self.button(buttons, "+10°", lambda i=index: self.nudge(i, 10),
                    bg=PANEL, fg=TEXT).pack(side="left", padx=(0, 4))
        self.button(buttons, "Mover", lambda i=index: self.move_from_control(i),
                    bg=BLUE).pack(side="left", padx=(0, 4))
        self.button(buttons, "Leer", lambda i=index: self.read_rows([i]),
                    bg=PANEL, fg=TEXT).pack(side="left")
        self.servo_rows.append(dict(id=id_var, angle=angle_var,
                                    slider=slider, actual=actual))
        slider.configure(command=lambda value, i=index: self.slider_changed(i, value))

    def refresh_pairs(self):
        for child in self.pair_list_frame.winfo_children():
            child.destroy()
        self.pair_list_frame.grid_columnconfigure(0, weight=1, uniform="formed")
        self.pair_list_frame.grid_columnconfigure(1, weight=1, uniform="formed")
        if not self.pairs:
            self.label(self.pair_list_frame,
                       "Todavia no hay parejas. Elige dos servos arriba y pulsa 'Crear pareja'.",
                       bg=BG, fg=MUTED, size=10).grid(row=0, column=0, sticky="w", padx=8, pady=12)
        else:
            for position, pair in enumerate(self.pairs):
                self.build_pair(self.pair_list_frame, pair, position)
        self.refresh_pair_choices()

    def refresh_pair_choices(self):
        occupied = {i for p in self.pairs for i in (p["first"], p["second"])}
        available = [i for i in range(NUM_SERVOS) if i not in occupied]
        labels = {f"Servo {i+1} ({SERVO_NAMES[i]})": i for i in available}
        self.pair_choice_indices = labels
        choices = list(labels)
        for widget, var in ((self.first_combo, self.first_choice_var),
                            (self.second_combo, self.second_choice_var)):
            previous = var.get()
            widget.configure(values=choices)
            if previous not in labels:
                var.set(choices[0] if choices else "")
        if len(choices) > 1 and self.first_choice_var.get() == self.second_choice_var.get():
            self.second_choice_var.set(choices[1])

    def show_pair_manager(self):
        """Saltar desde el boton fijo hasta el editor de parejas."""
        self.root.update_idletasks()
        total_height = max(self.main_content.winfo_height(), 1)
        self.main_canvas.yview_moveto(self.pair_creator.winfo_y() / total_height)

    def create_pair(self):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten las rutinas antes de editar parejas")
            return
        if len(self.pairs) >= NUM_PAIRS:
            messagebox.showwarning("Limite de parejas", "Con 8 servos puedes formar hasta 4 parejas")
            return
        first = self.pair_choice_indices.get(self.first_choice_var.get())
        second = self.pair_choice_indices.get(self.second_choice_var.get())
        if first is None or second is None or first == second:
            messagebox.showwarning("Pareja incorrecta", "Elige dos servos diferentes y disponibles")
            return
        name = self.new_pair_name_var.get().strip() or f"Pareja {len(self.pairs)+1}"
        if len(name) > 45:
            messagebox.showwarning("Nombre largo", "El nombre puede tener hasta 45 caracteres")
            return
        self.pairs.append(self.make_pair(first, second, name))
        self.new_pair_name_var.set("")
        self.refresh_pairs()
        self.pair_filename_var.set("Cambios sin guardar")
        self.show_pair_manager()
        self.status.set(f"Creada {name}: servo {first+1} (maestro) y servo {second+1}")

    def delete_pair(self, pair):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten las rutinas antes de editar parejas")
            return
        if pair in self.pairs:
            self.pairs.remove(pair)
            self.refresh_pairs()
            self.pair_filename_var.set("Cambios sin guardar")

    def clear_pairs(self):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten las rutinas antes de editar parejas")
            return
        if self.pairs and not messagebox.askyesno(
                "Borrar parejas", "¿Eliminar las parejas de la pantalla? No se borraran archivos guardados."):
            return
        self.pairs.clear()
        self.refresh_pairs()
        self.pair_filename_var.set("Cambios sin guardar")

    def current_pair_document(self):
        servos = [{"id": row["id"].get().strip(),
                   "angle": float(row["angle"].get().replace(",", "."))}
                  for row in self.servo_rows]
        pairs = [{"first": p["first"], "second": p["second"],
                  "name": p["name"].get(), "mode": self.pair_mode(p),
                  "enabled": p["enabled"].get()} for p in self.pairs]
        raw = {"format": PAIR_FORMAT, "version": PAIR_VERSION,
               "servos": servos, "pairs": pairs,
               "speed": int(self.speed.get()), "acc": int(self.acc.get())}
        return validate_pair_configuration(raw)

    def save_pairs(self):
        try:
            data = self.current_pair_document()
        except (ValueError, tk.TclError) as exc:
            messagebox.showwarning("Configuracion invalida", str(exc))
            return
        try:
            os.makedirs(PAIR_DIR, exist_ok=True)
            directory = PAIR_DIR
        except OSError:
            directory = os.path.expanduser("~")
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Guardar parejas y ajustes", initialdir=directory,
            initialfile=os.path.basename(self.pair_file_path) if self.pair_file_path else "mis_parejas.json",
            defaultextension=".json", filetypes=[("Configuracion de parejas JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
                out.write("\n")
        except OSError as exc:
            messagebox.showerror("No se pudo guardar", str(exc))
            return
        self.pair_file_path = path
        self.pair_filename_var.set(f"Guardado: {os.path.basename(path)}")
        self.status.set(f"Configuracion de parejas guardada: {path}")

    def load_pairs(self):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten las rutinas antes de cargar parejas")
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Abrir configuracion de parejas",
            initialdir=PAIR_DIR if os.path.isdir(PAIR_DIR) else os.path.dirname(os.path.abspath(__file__)),
            filetypes=[("Configuracion de parejas JSON", "*.json")])
        if not path:
            return
        try:
            if os.path.getsize(path) > 200_000:
                raise ValueError("El archivo de parejas es demasiado grande")
            with open(path, "r", encoding="utf-8") as inp:
                data = validate_pair_configuration(json.load(inp))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("No se pudo abrir", str(exc))
            return
        self.apply_pair_document(data)
        self.pair_file_path = path
        self.pair_filename_var.set(f"Abierto: {os.path.basename(path)}")
        self.status.set(f"Configuracion de parejas cargada: {path}")

    def apply_pair_document(self, data):
        """Aplica una configuracion ya validada. Sin mover el hardware."""
        data = validate_pair_configuration(data)
        self.pairs = [self.make_pair(p["first"], p["second"], p["name"],
                                     p["mode"], p["enabled"])
                      for p in data["pairs"]]
        for index, entry in enumerate(data["servos"]):
            self.servo_rows[index]["id"].set(entry["id"])
            self.set_target(index, entry["angle"])
        self.speed.set(data["speed"])
        self.acc.set(data["acc"])
        # Mostrar los angulos que realmente se guardaron, sin aplicar modo automaticamente.
        for index, entry in enumerate(data["servos"]):
            self.servo_rows[index]["angle"].set(f'{entry["angle"]:g}')
        self.refresh_pairs()

    def set_connected_ui(self, connected):
        self.connected = connected
        self.connect_btn.config(state="disabled" if connected else "normal")
        for btn in (self.scan_btn, self.probe_btn, self.id_btn,
                    self.disc_btn, self.release_btn):
            btn.config(state="normal" if connected else "disabled")
        self.set_routine_ui(self.routine_running)

    def set_routine_ui(self, running):
        self.routine_running = running
        self.stop_routine_btn.config(state="normal" if running else "disabled")
        # Evitar encolar movimientos manuales y configuraciones durante la rutina.
        for button in (self.scan_btn, self.probe_btn, self.id_btn):
            button.config(state="disabled" if running or not self.connected else "normal")
        if self.routine_window is not None and self.routine_window.winfo_exists():
            self.play_routine_btn.config(state="disabled" if running or not self.connected else "normal")
            self.editor_stop_btn.config(state="normal" if running else "disabled")
        self.refresh_parallel_tree()

    def connect(self):
        if self.connected or (self.worker and self.worker.is_alive()):
            return
        self.commands = queue.Queue()
        self.worker = ServoWorker(self.commands, self.events)
        self.status.set("Conectando al puerto COM3...")
        self.connect_btn.config(state="disabled")
        self.worker.start()

    def disconnect(self):
        if self.worker and self.worker.is_alive():
            if self.routine_running:
                self.stop_routine()
            self.status.set("Desconectando; liberando torque de servos activados...")
            self.commands.put(("disconnect",))
            self.disc_btn.config(state="disabled")

    def scan(self):
        if self.connected and not self.routine_running:
            self.scan_btn.config(state="disabled")
            self.commands.put(("scan",))

    def release(self):
        if self.connected:
            if self.routine_running:
                self.stop_routine()
            self.commands.put(("release",))

    def probe_ids(self):
        if self.routine_running:
            messagebox.showwarning("Rutina en curso", "Deten primero la rutina")
            return
        if not self.connected:
            self.status.set("Conecta primero a COM3")
            return
        selected = []
        seen = set()
        for index, row in enumerate(self.servo_rows):
            value = row["id"].get().strip()
            if not value:
                continue
            try:
                servo_id = int(value)
            except ValueError:
                messagebox.showwarning("ID incorrecto", f"El ID de {SERVO_NAMES[index]} no es numerico")
                return
            if not 0 <= servo_id <= 253:
                messagebox.showwarning("ID incorrecto", f"ID {servo_id} fuera de rango (0-253)")
                return
            if servo_id in seen:
                messagebox.showwarning("ID duplicado en la interfaz", f"Escribiste el ID {servo_id} mas de una vez")
                return
            seen.add(servo_id)
            selected.append((index, servo_id))
        if not selected:
            messagebox.showwarning("Faltan IDs", "Escribe al menos un ID para comprobarlo")
            return
        self.probe_btn.config(state="disabled")
        self.status.set("Comprobando los IDs escritos en COM3...")
        self.commands.put(("probe_ids", selected))

    def open_id_dialog(self):
        if self.routine_running:
            messagebox.showwarning("Rutina en curso", "Deten primero la rutina")
            return
        if not self.connected:
            messagebox.showwarning("Sin conexion", "Conecta COM3 primero")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Asignar ID real a un solo servo")
        dialog.geometry("475x320")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="CONFIGURAR ID EN LA MEMORIA DEL SERVO",
                 bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold"),
                 pady=12).pack()
        tk.Label(dialog,
                 text=("Desconecta la alimentacion y deja conectado "
                       "UN SOLO servo fisico.\n"
                       "Reconecta los 12 V y usa Buscar servos para conocer "
                       "su ID actual.\n"
                       "Este cambio se guarda dentro del servo. "
                       "No sirve si hay varios conectados."),
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10),
                 wraplength=435, justify="left").pack(padx=20, pady=(0, 10))
        fields = tk.Frame(dialog, bg=PANEL)
        fields.pack(pady=6)
        old_value = tk.StringVar(value="1")
        new_value = tk.StringVar(value="3")
        tk.Label(fields, text="ID actual", bg=PANEL, fg=TEXT).grid(
            row=0, column=0, padx=10)
        tk.Entry(fields, width=8, textvariable=old_value,
                 justify="center").grid(row=1, column=0, padx=10, pady=5)
        tk.Label(fields, text="ID nuevo", bg=PANEL, fg=TEXT).grid(
            row=0, column=1, padx=10)
        tk.Entry(fields, width=8, textvariable=new_value,
                 justify="center").grid(row=1, column=1, padx=10, pady=5)

        def confirm():
            try:
                old_id, new_id = int(old_value.get()), int(new_value.get())
                if not (0 <= old_id <= 253 and 0 <= new_id <= 253):
                    raise ValueError("Los IDs deben estar entre 0 y 253")
                if old_id == new_id:
                    raise ValueError("Los dos IDs son iguales")
            except ValueError as exc:
                messagebox.showerror("ID incorrecto", str(exc), parent=dialog)
                return
            ok = messagebox.askyesno(
                "Confirmacion importante",
                "¿Dejaste conectado SOLO UN servo fisico al bus?\n\n"
                f"Vas a cambiar su ID permanente de {old_id} a {new_id}.\n"
                "Si hay varios servos con el mismo ID, "
                "podrias modificar varios a la vez.",
                parent=dialog
            )
            if not ok:
                return
            self.commands.put(("change_id", old_id, new_id))
            self.status.set(f"Cambiando ID {old_id} a {new_id} ...")
            dialog.destroy()

        self.button(dialog, "Cambiar ID del UNICO servo conectado",
                    confirm, bg="#e6bb68").pack(pady=(10, 7))

    def set_target(self, index, degree):
        """Mantener slider y campo de destino coordinados sin enviar orden."""
        degree = max(0.0, min(360.0, float(degree)))
        row = self.servo_rows[index]
        row["slider"].set(round(degree))
        row["angle"].set(f"{degree:g}")
        # Mantener el seguidor sincronizado tambien en cambios programaticos.
        pair = self.pair_for_master(index)
        if pair is not None:
            self.sync_pair_display(pair)

    def pair_mode(self, pair):
        """Devuelve mirror, same o independent para una pareja dinamica."""
        if pair["mirror"].get():
            return "mirror"
        if pair["same"].get():
            return "same"
        return "independent"

    def update_mode_label(self, pair):
        mode = self.pair_mode(pair)
        if mode == "mirror":
            description = "ESPEJO: segundo = 360° - maestro (170° y 190°)"
        elif mode == "same":
            description = "IGUAL: segundo = maestro (170° y 170°)"
        else:
            description = "INDEPENDIENTES: dos angulos y dos controles separados"
        pair["mode_label"].set(description)

    def mode_changed(self, pair, selected_mode):
        if selected_mode == "mirror" and pair["mirror"].get():
            pair["same"].set(False)
        elif selected_mode == "same" and pair["same"].get():
            pair["mirror"].set(False)
        self.update_mode_label(pair)
        self.sync_pair_display(pair)

    def sync_pair_display(self, pair):
        """Vincula objetivos de la pareja sin enviar orden al bus."""
        mode = self.pair_mode(pair)
        if mode == "independent":
            return
        try:
            angle = float(self.servo_rows[pair["first"]]["angle"].get().replace(",", "."))
            deg_to_pos(angle)
        except ValueError:
            return
        follower = 360.0 - angle if mode == "mirror" else angle
        self.set_target(pair["second"], follower)

    def pair_for_master(self, index):
        return next((p for p in self.pairs if p["first"] == index), None)

    def slider_changed(self, index, raw_value):
        degree = float(raw_value)
        self.servo_rows[index]["angle"].set(f"{degree:g}")
        pair = self.pair_for_master(index)
        if pair is not None:
            self.sync_pair_display(pair)

    def move_from_control(self, index):
        pair = self.pair_for_master(index)
        if pair is not None and self.pair_mode(pair) != "independent":
            self.send_move([pair["first"], pair["second"]])
        else:
            self.send_move([index])

    def move_active_pairs(self):
        rows = [index for pair in self.pairs if pair["enabled"].get()
                for index in (pair["first"], pair["second"])]
        if not rows:
            messagebox.showwarning("Sin parejas", "Crea y activa al menos una pareja")
            return
        self.send_move(rows)

    def get_ids_and_targets(self, row_indices):
        ids_seen = set()
        targets = []
        for i in row_indices:
            row = self.servo_rows[i]
            try:
                servo_id = int(row["id"].get().strip())
            except ValueError:
                raise ValueError(f"Escribe el ID del servo {SERVO_NAMES[i]}")
            if not (0 <= servo_id <= 253):
                raise ValueError("Los IDs validos van de 0 a 253")
            if servo_id in ids_seen:
                raise ValueError(f"ID repetido: {servo_id}")
            ids_seen.add(servo_id)
            target = float(row["angle"].get().strip().replace(",", "."))
            deg_to_pos(target)
            targets.append((servo_id, target))
        return targets

    def get_ids_for_read(self, row_indices):
        result = []
        for i in row_indices:
            value = self.servo_rows[i]["id"].get().strip()
            try:
                servo_id = int(value)
            except ValueError:
                raise ValueError(f"ID no valido en {SERVO_NAMES[i]}")
            if not (0 <= servo_id <= 253):
                raise ValueError(f"ID fuera de rango: {servo_id}")
            result.append((i, servo_id))
        if len({ident for _, ident in result}) != len(result):
            raise ValueError("Hay IDs duplicados entre los servos seleccionados")
        return result

    def send_move(self, row_indices):
        if self.routine_running:
            self.status.set("Rutina activa. Deten la secuencia antes de mover manualmente.")
            return
        if not self.connected:
            self.status.set("Conecta primero a COM3")
            return
        try:
            # Aplica el modo solo si espejo/igual esta activo.
            # En independiente NO reemplaza el objetivo de ningun servo.
            # No cambia limites, ID ni calibracion de los servos.
            for pair in self.pairs:
                if pair["first"] in row_indices and pair["second"] in row_indices:
                    self.sync_pair_display(pair)
            targets = self.get_ids_and_targets(row_indices)
            speed = int(self.speed.get())
            acc = int(self.acc.get())
            if not (50 <= speed <= 1500 and 0 <= acc <= 100):
                raise ValueError("Velocidad 50-1500; aceleracion 0-100")
            self.commands.put(("move", targets, speed, acc))
            summary = ", ".join(f"ID {sid}={deg:g}°" for sid, deg in targets)
            self.status.set("Enviando: " + summary)
        except (ValueError, tk.TclError) as exc:
            messagebox.showwarning("Verifica datos", str(exc))

    def nudge(self, index, diff):
        row = self.servo_rows[index]
        try:
            actual_target = float(row["angle"].get().replace(",", "."))
            new_target = min(360, max(0, actual_target + diff))
            self.set_target(index, new_target)
            self.move_from_control(index)
        except ValueError:
            messagebox.showwarning("Angulo invalido", "Escribe un angulo numerico")

    def read_rows(self, row_indices):
        if self.routine_running or not self.connected:
            return
        try:
            row_ids = self.get_ids_for_read(row_indices)
            self.commands.put(("read", row_ids))
            self.status.set("Leyendo posiciones...")
        except ValueError as exc:
            messagebox.showwarning("Verifica IDs", str(exc))

    def read_all(self):
        # Omitir filas que aun no tienen un servo fisico asignado.
        indices = [i for i, row in enumerate(self.servo_rows)
                   if row["id"].get().strip()]
        if not indices:
            messagebox.showwarning("Faltan IDs", "Todavia no hay IDs escritos.")
            return
        self.read_rows(indices)

    def auto_fill_ids(self, found):
        ids = [servo_id for servo_id, _ in found]
        # Conservar configuraciones existentes, en particular ID 2 de A1.
        used = {int(r["id"].get()) for r in self.servo_rows
                if r["id"].get().strip().isdigit()
                and int(r["id"].get()) in ids}
        for row in self.servo_rows:
            if row["id"].get().strip():
                continue
            available = next((x for x in ids if x not in used), None)
            if available is None:
                break
            row["id"].set(str(available))
            used.add(available)
        # Leer las posiciones unicamente de IDs detectados y asignados.
        assigned = []
        seen = set()
        for index, row in enumerate(self.servo_rows):
            value = row["id"].get().strip()
            if value.isdigit() and int(value) in ids and int(value) not in seen:
                assigned.append((index, int(value)))
                seen.add(int(value))
        if assigned:
            self.commands.put(("read", assigned))

    def process_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "connected":
                self.set_connected_ui(True)
                self.status.set("COM3 conectado. Buscando IDs...")
                self.scan()
            elif kind == "disconnected":
                self.running_job_ids.clear()
                self.running_job_data.clear()
                self.editor_play_id = None
                self.set_routine_ui(False)
                self.set_connected_ui(False)
                self.worker = None
                self.status.set("COM3 desconectado")
                if self.closing:
                    self.root.destroy()
                    return
            elif kind == "scan_result":
                found = event[1]
                self.ids_found = [servo_id for servo_id, _ in found]
                self.found_label.config(text="IDs detectados: " +
                    (", ".join(str(x) for x in self.ids_found) if found else "ninguno"))
                self.scan_btn.config(state="normal" if not self.routine_running else "disabled")
                self.auto_fill_ids(found)
                self.status.set(
                    f"Se detectaron {len(found)} servo(s). "
                    "Asigna los IDs reales a los servos; las parejas se forman en la interfaz."
                )
                if not found:
                    self.status.set(
                        "La busqueda rapida (IDs 0-20) no encontro servos. "
                        "Si usas IDs mas altos, escribe cada ID y pulsa Comprobar."
                    )
            elif kind == "probe_result":
                checks = event[1]
                self.probe_btn.config(state="normal" if not self.routine_running else "disabled")
                names = SERVO_NAMES
                lines = []
                ok_count = 0
                for index, servo_id, ok, model in checks:
                    if ok:
                        ok_count += 1
                        lines.append(f"{names[index]} - ID {servo_id}: RESPONDE (modelo {model})")
                    else:
                        lines.append(f"{names[index]} - ID {servo_id}: SIN RESPUESTA")
                self.status.set(
                    f"Comprobacion: {ok_count} de {len(checks)} IDs escritos responden."
                )
                messagebox.showinfo(
                    "Resultado de IDs escritos",
                    "\n".join(lines) +
                    "\n\nSIN RESPUESTA no significa que haya perdido el ID. "
                    "Puede haber varios servos con ID de fabrica 1, "
                    "colisiones, alimentacion insuficiente o cableado. "
                    "Comprueba CADA servo por separado (solo uno conectado)."
                )
            elif kind == "id_changed":
                _, old_id, new_id, model = event
                self.status.set(f"ID cambiado: {old_id} -> {new_id} (modelo {model})")
                messagebox.showinfo(
                    "ID modificado",
                    f"El servo respondio con su nuevo ID {new_id}.\n\n"
                    "Apaga los 12 V antes de cambiar de servo.\n"
                    "Cuando todos tengan IDs distintos, conecta hasta ocho, "
                    "segun lo que soporte tu alimentacion."
                )
                self.scan()
            elif kind == "position":
                _, index, servo_id, deg = event
                row = self.servo_rows[index]
                if row["id"].get().strip() == str(servo_id):
                    row["actual"].set(f"Real: {deg:.1f}°")
                    row["angle"].set(f"{deg:.1f}")
                    row["slider"].set(round(deg))
            elif kind == "read_error":
                _, index, servo_id = event
                self.servo_rows[index]["actual"].set("Sin respuesta")
                self.status.set(f"No se pudo leer el ID {servo_id}")
            elif kind == "read_outside":
                _, index, servo_id, pos = event
                self.servo_rows[index]["actual"].set(f"Posicion {pos} (fuera de 0-4095)")
                self.status.set(f"ID {servo_id}: verifica modo/rango de posicion")
            elif kind == "routine_job_started":
                _, run_id, name, count, repeats = event
                self.set_parallel_plan_status(run_id, "Ejecutando", f"0/{count} pasos")
                self.status.set(f'Iniciada "{name}": {count} pasos × {repeats} vuelta(s)')
            elif kind == "routine_job_step":
                _, run_id, step_index, repetition, count, repeats, name = event
                self.set_parallel_plan_status(
                    run_id, "Ejecutando",
                    f"Vuelta {repetition + 1}/{repeats}, paso {step_index + 1}/{count}"
                )
                if run_id == self.editor_play_id and self.routine_window is not None \
                        and self.routine_window.winfo_exists():
                    items = self.routine_tree.get_children()
                    if step_index < len(items):
                        self.routine_tree.selection_set(items[step_index])
                        self.routine_tree.see(items[step_index])
                self.status.set(
                    f"Rutina {run_id}: vuelta {repetition + 1}/{repeats}, "
                    f"paso {step_index + 1}/{count} ({name})"
                )
            elif kind == "routine_job_done":
                _, run_id, result, detail = event
                self.running_job_ids.discard(run_id)
                self.running_job_data.pop(run_id, None)
                if run_id == self.editor_play_id:
                    self.editor_play_id = None
                status = {"completed": "Terminada", "stopped": "Detenida",
                          "error": "Error"}.get(result, result)
                self.set_parallel_plan_status(run_id, status, detail)
                self.set_routine_ui(bool(self.running_job_ids))
                self.status.set(f"Rutina {run_id}: {status.lower()} - {detail}")
                if result == "error":
                    messagebox.showerror("Fallo de rutina", f"Rutina {run_id}: {detail}")
            elif kind == "routine_batch_error":
                _, run_ids, detail = event
                for run_id in run_ids:
                    self.running_job_ids.discard(run_id)
                    self.running_job_data.pop(run_id, None)
                    if run_id == self.editor_play_id:
                        self.editor_play_id = None
                    self.set_parallel_plan_status(run_id, "Error", detail)
                self.set_routine_ui(bool(self.running_job_ids))
                self.status.set("No se iniciaron las rutinas nuevas: " + detail)
                messagebox.showerror("No se pudieron iniciar las rutinas", detail)
            elif kind == "sent":
                self.status.set("Orden aceptada por IDs: " + ", ".join(map(str, event[1])) +
                                ". Usa Leer para comprobar el angulo REAL.")
            elif kind == "info":
                self.status.set(event[1])
            elif kind == "error":
                self.status.set("ERROR: " + event[1])
                self.scan_btn.config(state="normal" if self.connected else "disabled")
                self.probe_btn.config(state="normal" if self.connected else "disabled")
                messagebox.showerror("Error de comunicacion", event[1])
        self.root.after(80, self.process_events)

    # -------- Editor, almacenamiento y ejecucion de rutinas --------

    def mark_routine_dirty(self, *_):
        self.routine_dirty = True

    def open_routine_editor(self):
        if self.routine_window is not None and self.routine_window.winfo_exists():
            self.routine_window.lift()
            self.routine_window.focus_force()
            return
        dirty_before_opening = self.routine_dirty

        win = tk.Toplevel(self.root)
        self.routine_window = win
        win.title("Editor de rutinas · STS3215 · 8 servos")
        win.geometry("1180x860")
        win.minsize(950, 700)
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", self.close_routine_editor)

        title = tk.Frame(win, bg=BG)
        title.pack(fill="x", padx=18, pady=(14, 8))
        self.label(title, "RUTINAS PROGRAMABLES", size=17, bold=True,
                   bg=BG).pack(anchor="w")
        self.label(title,
            "Cada paso captura los OBJETIVOS actuales (no las posiciones reales). "
            "Los IDs y angulos quedan guardados en cada paso, con independencia "
            "del modo espejo/igual usado para capturarlos.",
            bg=BG, fg=MUTED, size=10, wraplength=1120,
            justify="left").pack(anchor="w", pady=(3, 0))

        details = tk.Frame(win, bg=PANEL, padx=12, pady=9)
        details.pack(fill="x", padx=18, pady=(0, 8))
        self.label(details, "Nombre de rutina", size=10).pack(side="left")
        tk.Entry(details, textvariable=self.routine_name_var, width=27,
                 font=("Segoe UI", 11)).pack(side="left", padx=(7, 18))
        self.label(details, "Repeticiones", size=10).pack(side="left")
        tk.Spinbox(details, from_=1, to=100, width=5,
                   textvariable=self.routine_repeats_var,
                   font=("Segoe UI", 11)).pack(side="left", padx=(7, 17))
        self.routine_count_label = self.label(details, "0 pasos", fg=GREEN)
        self.routine_count_label.pack(side="right")

        file_tools = tk.Frame(win, bg=BG)
        file_tools.pack(fill="x", padx=18, pady=(0, 8))
        self.button(file_tools, "Nueva", self.new_routine,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 8))
        self.button(file_tools, "Abrir rutina (.json)", self.load_routine,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 8))
        self.button(file_tools, "Guardar", self.save_routine,
                    bg=GREEN).pack(side="left", padx=(0, 8))
        self.button(file_tools, "Guardar como...", lambda: self.save_routine(True),
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 8))

        playback = tk.Frame(win, bg=PANEL, padx=13, pady=10)
        playback.pack(fill="x", padx=18, pady=(0, 8))
        self.play_routine_btn = self.button(
            playback, "▶ Ejecutar rutina", self.play_routine, bg=GREEN
        )
        self.play_routine_btn.pack(side="left")
        self.editor_stop_btn = self.button(
            playback, "■ Detener secuencia", self.stop_routine,
            bg="#813d4a", fg=TEXT
        )
        self.editor_stop_btn.pack(side="left", padx=(10, 0))
        self.button(playback, "Abrir rutinas en paralelo", self.open_parallel_manager,
                    bg="#b09cff").pack(side="left", padx=(10, 0))
        self.label(playback,
            "Detener cancela los pasos siguientes; NO detiene de golpe "
            "un movimiento ya enviado.",
            size=9, fg=DANGER, wraplength=560).pack(side="right")
        central = tk.Frame(win, bg=BG)
        central.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        central.grid_columnconfigure(0, weight=3)
        central.grid_columnconfigure(1, weight=2)
        central.grid_rowconfigure(0, weight=1)

        left = tk.Frame(central, bg=PANEL, padx=10, pady=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.label(left, "Secuencia de pasos", bold=True,
                   size=12).pack(anchor="w", pady=(0, 7))
        tree_wrap = tk.Frame(left, bg=PANEL)
        tree_wrap.pack(fill="both", expand=True)
        style = ttk.Style(win)
        style.configure("Rutina.Treeview", background=PANEL2,
                        fieldbackground=PANEL2, foreground=TEXT,
                        rowheight=29, font=("Segoe UI", 9))
        style.configure("Rutina.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.map("Rutina.Treeview", background=[("selected", "#3c6090")],
                  foreground=[("selected", "white")])
        cols = ("num", "name", "targets", "wait", "speed", "acc")
        tree = ttk.Treeview(tree_wrap, columns=cols, show="headings",
                            selectmode="browse", style="Rutina.Treeview")
        self.routine_tree = tree
        col_defs = [
            ("num", "#", 35, "center"),
            ("name", "Paso", 115, "w"),
            ("targets", "Objetivos guardados", 335, "w"),
            ("wait", "Espera (s)", 78, "center"),
            ("speed", "Vel.", 58, "center"),
            ("acc", "Acel.", 55, "center"),
        ]
        for col, title_text, width, alignment in col_defs:
            tree.heading(col, text=title_text)
            tree.column(col, width=width, minwidth=40 if col != "num" else 28,
                        anchor=alignment, stretch=(col == "targets"))
        scrollbar = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", self.routine_step_selected)

        left_buttons = tk.Frame(left, bg=PANEL)
        left_buttons.pack(fill="x", pady=(10, 0))
        self.button(left_buttons, "Eliminar", self.delete_routine_step,
                    bg="#703d4a", fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(left_buttons, "Subir ↑", lambda: self.shift_routine_step(-1),
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(left_buttons, "Bajar ↓", lambda: self.shift_routine_step(1),
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(left_buttons, "Ver paso en controles (sin mover)",
                    self.show_routine_step_in_controls,
                    bg=PANEL2, fg=TEXT).pack(side="right")

        right = tk.Frame(central, bg=PANEL, padx=12, pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.label(right, "Crear o modificar un paso", size=12,
                   bold=True).pack(anchor="w")
        self.label(right, "Selecciona los servos que participaran en el paso:",
                   size=9, fg=MUTED).pack(anchor="w", pady=(6, 2))
        selection = tk.Frame(right, bg=PANEL)
        selection.pack(fill="x", pady=(2, 6))
        self.routine_servo_vars = []
        self.routine_angle_vars = []
        for index, slot in enumerate(SERVO_NAMES):
            checked = bool(self.servo_rows[index]["id"].get().strip())
            var = tk.BooleanVar(value=checked)
            angle_var = tk.StringVar(value=self.servo_rows[index]["angle"].get())
            self.routine_servo_vars.append(var)
            self.routine_angle_vars.append(angle_var)
            servo_field = tk.Frame(selection, bg=PANEL)
            servo_field.grid(row=index // 2, column=index % 2,
                             padx=(0, 10), pady=4, sticky="w")
            tk.Checkbutton(
                servo_field, text=f"Servo {index+1} ({slot})", variable=var,
                bg=PANEL, fg=TEXT, activebackground=PANEL,
                activeforeground=TEXT, selectcolor=PANEL2,
                highlightthickness=0, font=("Segoe UI", 10)
            ).pack(side="left")
            tk.Entry(servo_field, textvariable=angle_var, width=7,
                     justify="center", font=("Segoe UI", 10)).pack(
                         side="left", padx=(4, 1))
            self.label(servo_field, "°", size=10).pack(side="left")
        select_tools = tk.Frame(right, bg=PANEL)
        select_tools.pack(fill="x", pady=(0, 6))
        self.button(select_tools, "Usar objetivos actuales",
                    self.copy_targets_to_routine_editor,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(select_tools, "Seleccionar con ID",
                    self.select_configured_routine_servos,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(select_tools, "Ninguno", self.clear_routine_servo_selection,
                    bg=PANEL2, fg=TEXT).pack(side="left")

        fields = tk.Frame(right, bg=PANEL)
        fields.pack(fill="x", pady=(5, 6))
        fields.columnconfigure(1, weight=1)
        self.routine_step_name = tk.StringVar(value="Paso 1")
        self.routine_wait = tk.StringVar(value="2.0")
        self.routine_speed = tk.StringVar(value=str(self.speed.get()))
        self.routine_acc = tk.StringVar(value=str(self.acc.get()))
        for i, (label_text, variable) in enumerate((
            ("Nombre del paso", self.routine_step_name),
            ("Espera DESPUES (s)", self.routine_wait),
            ("Velocidad", self.routine_speed),
            ("Aceleracion", self.routine_acc),
        )):
            self.label(fields, label_text, size=10).grid(
                row=i, column=0, sticky="w", pady=6, padx=(0, 8))
            tk.Entry(fields, textvariable=variable, width=18,
                     font=("Segoe UI", 10)).grid(
                         row=i, column=1, sticky="ew", pady=6)

        buttons = tk.Frame(right, bg=PANEL)
        buttons.pack(fill="x", pady=(10, 7))
        self.button(buttons, "+ Añadir paso", self.add_routine_step,
                    bg=GREEN).pack(fill="x", pady=(0, 6))
        self.button(buttons, "Reemplazar paso seleccionado",
                    self.replace_routine_step, bg=BLUE).pack(fill="x")
        self.label(right,
            "Angulos: 0 a 360°. 'Usar objetivos actuales' copia los "
            "valores calculados con espejo/igual. La espera inicia al "
            "terminar de enviar las ordenes, sin confirmar llegada.",
            size=9, fg=MUTED, wraplength=375,
            justify="left").pack(anchor="w", pady=(4, 0))

        self.routine_file_label = tk.StringVar()
        tk.Label(win, textvariable=self.routine_file_label,
                 bg="#263550", fg=TEXT, anchor="w",
                 font=("Segoe UI", 9), padx=14,
                 pady=8).pack(side="bottom", fill="x")
        # Algunos widgets escriben el StringVar al inicializarse;
        # abrir el editor por si solo NO es una modificacion de la rutina.
        self.routine_dirty = dirty_before_opening
        self.refresh_routine_tree()
        self.refresh_routine_file_label()
        self.set_routine_ui(self.routine_running)

    def close_routine_editor(self):
        if self.routine_window is not None and self.routine_window.winfo_exists():
            self.routine_window.destroy()
        self.routine_window = None

    def refresh_routine_file_label(self):
        if self.routine_window is not None and self.routine_window.winfo_exists():
            state = " · Cambios sin guardar" if self.routine_dirty else ""
            path = self.routine_path or "Sin guardar: elige Guardar o Guardar como..."
            self.routine_file_label.set("Archivo: " + path + state)

    def refresh_routine_tree(self, select_index=None):
        if self.routine_window is None or not self.routine_window.winfo_exists():
            return
        tree = self.routine_tree
        if select_index is None:
            select_index = self.selected_routine_index()
        for item in tree.get_children():
            tree.delete(item)
        for ix, step in enumerate(self.routine_steps):
            targets_summary = ", ".join(
                f'{t["slot"]}[{t["id"]}]={t["angle_deg"]:g}°'
                for t in step["targets"]
            )
            tree.insert("", "end", iid=str(ix), values=(
                ix + 1, step["name"], targets_summary,
                f'{step["wait_s"]:g}', step["speed"], step["acc"]
            ))
        if select_index is not None and 0 <= select_index < len(self.routine_steps):
            tree.selection_set(str(select_index))
            tree.focus(str(select_index))
            tree.see(str(select_index))
        self.routine_count_label.config(text=f"{len(self.routine_steps)} pasos")
        self.refresh_routine_file_label()

    def selected_routine_index(self):
        if self.routine_window is None or not self.routine_window.winfo_exists():
            return None
        selection = self.routine_tree.selection()
        return int(selection[0]) if selection else None

    def routine_step_selected(self, _event=None):
        ix = self.selected_routine_index()
        if ix is None or ix >= len(self.routine_steps):
            return
        step = self.routine_steps[ix]
        self.routine_step_name.set(step["name"])
        self.routine_wait.set(str(step["wait_s"]))
        self.routine_speed.set(str(step["speed"]))
        self.routine_acc.set(str(step["acc"]))
        targets_by_name = {t["slot"]: t for t in step["targets"]}
        for i, slot in enumerate(SERVO_NAMES):
            self.routine_servo_vars[i].set(slot in targets_by_name)
            if slot in targets_by_name:
                self.routine_angle_vars[i].set(
                    f'{targets_by_name[slot]["angle_deg"]:g}'
                )

    def copy_targets_to_routine_editor(self):
        """Copiar objetivos desde controles aplicando sus modos de pareja."""
        for pair in self.pairs:
            self.sync_pair_display(pair)
        for i, row in enumerate(self.servo_rows):
            self.routine_angle_vars[i].set(row["angle"].get())

    def select_configured_routine_servos(self):
        for var, row in zip(self.routine_servo_vars, self.servo_rows):
            var.set(bool(row["id"].get().strip()))

    def clear_routine_servo_selection(self):
        for var in self.routine_servo_vars:
            var.set(False)

    def capture_routine_step(self):
        name = self.routine_step_name.get().strip()
        try:
            wait_s = float(self.routine_wait.get().replace(",", "."))
            speed = int(self.routine_speed.get().strip())
            acc = int(self.routine_acc.get().strip())
        except ValueError:
            raise ValueError("Revisa nombre, espera, velocidad y aceleracion")
        selected_indices = [i for i, var in enumerate(self.routine_servo_vars)
                            if var.get()]
        if not selected_indices:
            raise ValueError("Marca uno o varios servos para este paso")
        # Se guardan los angulos de ESTE editor; copiar desde controles
        # previamente permite usar los modos espejo/igual existentes.
        targets = []
        for i in selected_indices:
            try:
                servo_id = int(self.servo_rows[i]["id"].get().strip())
            except ValueError:
                raise ValueError(f"Escribe el ID del servo {SERVO_NAMES[i]} en controles")
            try:
                angle = float(self.routine_angle_vars[i].get().strip().replace(",", "."))
                deg_to_pos(angle)
            except (ValueError, OverflowError):
                raise ValueError(f"Angulo invalido en {SERVO_NAMES[i]} (0 a 360°)")
            targets.append({"slot": SERVO_NAMES[i], "id": servo_id,
                            "angle_deg": angle})
        raw = {"format": ROUTINE_FORMAT, "version": ROUTINE_VERSION,
               "name": "Temporal", "repeats": 1,
               "steps": [{"name": name, "wait_s": wait_s, "speed": speed,
                          "acc": acc, "targets": targets}]}
        return validate_routine_document(raw)["steps"][0]

    def add_routine_step(self):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten la rutina antes de editarla")
            return
        if len(self.routine_steps) >= MAX_STEPS:
            messagebox.showwarning("Maximo de pasos", f"Limite: {MAX_STEPS} pasos")
            return
        try:
            step = self.capture_routine_step()
        except ValueError as exc:
            messagebox.showwarning("Paso incorrecto", str(exc))
            return
        self.routine_steps.append(step)
        self.mark_routine_dirty()
        self.refresh_routine_tree(select_index=len(self.routine_steps) - 1)

    def replace_routine_step(self):
        if self.routine_running:
            return
        ix = self.selected_routine_index()
        if ix is None:
            messagebox.showwarning("Selecciona paso", "Selecciona el paso a reemplazar")
            return
        try:
            step = self.capture_routine_step()
        except ValueError as exc:
            messagebox.showwarning("Paso incorrecto", str(exc))
            return
        self.routine_steps[ix] = step
        self.mark_routine_dirty()
        self.refresh_routine_tree(select_index=ix)

    def delete_routine_step(self):
        if self.routine_running:
            return
        ix = self.selected_routine_index()
        if ix is None:
            return
        self.routine_steps.pop(ix)
        self.mark_routine_dirty()
        self.refresh_routine_tree(select_index=min(ix, len(self.routine_steps) - 1))

    def shift_routine_step(self, delta):
        if self.routine_running:
            return
        ix = self.selected_routine_index()
        if ix is None or not 0 <= ix + delta < len(self.routine_steps):
            return
        self.routine_steps[ix], self.routine_steps[ix + delta] = (
            self.routine_steps[ix + delta], self.routine_steps[ix]
        )
        self.mark_routine_dirty()
        self.refresh_routine_tree(select_index=ix + delta)

    def show_routine_step_in_controls(self):
        ix = self.selected_routine_index()
        if ix is None:
            messagebox.showwarning("Selecciona paso", "Elige un paso de la lista")
            return
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten la rutina antes de modificar objetivos")
            return
        step = self.routine_steps[ix]
        for target in step["targets"]:
            i = SERVO_NAMES.index(target["slot"])
            self.set_target(i, target["angle_deg"])
        # El ultimo par puede tener el objetivo original, aunque los modos de
        # la ventana principal hayan cambiado desde que se guardo el paso.
        self.status.set(f'Paso {ix+1} cargado a controles. NO se movio ningun servo.')

    def current_routine_document(self):
        try:
            repeats = int(self.routine_repeats_var.get().strip())
        except ValueError:
            raise ValueError("Repeticiones debe ser un numero entero entre 1 y 100")
        raw = {"format": ROUTINE_FORMAT, "version": ROUTINE_VERSION,
               "name": self.routine_name_var.get(), "repeats": repeats,
               "steps": self.routine_steps}
        return validate_routine_document(raw)

    def new_routine(self):
        if self.routine_running:
            return
        if self.routine_dirty and not messagebox.askyesno(
            "Crear rutina", "Hay cambios sin guardar. ¿Crear una rutina nueva?",
            parent=self.routine_window
        ):
            return
        self.routine_steps = []
        self.routine_path = None
        self.routine_name_var.set("Mi rutina")
        self.routine_repeats_var.set("1")
        self.routine_step_name.set("Paso 1")
        self.routine_dirty = False
        self.refresh_routine_tree()
        self.refresh_routine_file_label()

    def save_routine(self, force_new=False):
        try:
            data = self.current_routine_document()
        except ValueError as exc:
            messagebox.showerror("Rutina invalida", str(exc), parent=self.routine_window)
            return
        path = self.routine_path
        if force_new or not path:
            try:
                os.makedirs(ROUTINE_DIR, exist_ok=True)
                base_dir = ROUTINE_DIR
            except OSError:
                base_dir = os.path.expanduser("~")
            suggested = "".join(c if c.isalnum() or c in " -_" else "_"
                                for c in data["name"]).strip() or "rutina"
            path = filedialog.asksaveasfilename(
                parent=self.routine_window,
                title="Guardar rutina STS3215", initialdir=base_dir,
                initialfile=suggested + ".json", defaultextension=".json",
                filetypes=[("Rutina STS3215 (.json)", "*.json")]
            )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write("\n")
        except OSError as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self.routine_window)
            return
        self.routine_path = path
        self.routine_steps = data["steps"]
        self.routine_dirty = False
        self.refresh_routine_file_label()
        self.status.set(f"Rutina guardada: {os.path.basename(path)}")

    def load_routine(self):
        if self.routine_running:
            messagebox.showwarning("Rutina activa", "Deten la rutina antes de cargar otra")
            return
        if self.routine_dirty and not messagebox.askyesno(
            "Abrir otra rutina", "Hay cambios sin guardar. ¿Descartarlos?",
            parent=self.routine_window
        ):
            return
        path = filedialog.askopenfilename(
            parent=self.routine_window, title="Abrir rutina STS3215",
            initialdir=ROUTINE_DIR if os.path.isdir(ROUTINE_DIR) else
                       os.path.dirname(os.path.abspath(__file__)),
            filetypes=[("Rutina STS3215 (.json)", "*.json"),
                       ("Archivos JSON", "*.json")]
        )
        if not path:
            return
        try:
            if os.path.getsize(path) > 2_000_000:
                raise ValueError("El archivo es demasiado grande")
            with open(path, "r", encoding="utf-8") as inp:
                data = validate_routine_document(json.load(inp))
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("No se pudo abrir la rutina", str(exc),
                                 parent=self.routine_window)
            return
        self.routine_steps = data["steps"]
        self.routine_name_var.set(data["name"])
        self.routine_repeats_var.set(str(data["repeats"]))
        self.routine_path = path
        self.routine_dirty = False
        self.refresh_routine_tree()
        self.refresh_routine_file_label()
        self.status.set(f"Rutina cargada: {os.path.basename(path)}")

    def play_routine(self):
        try:
            doc = self.current_routine_document()
        except ValueError as exc:
            messagebox.showwarning("Rutina invalida", str(exc))
            return
        self.next_parallel_id += 1
        run_id = f"editor-{self.next_parallel_id}"
        if self.start_routine_batch([{"run_id": run_id, "data": doc}]):
            self.editor_play_id = run_id

    def start_routine_batch(self, plans):
        """Inicia varias rutinas; reserva todos sus IDs antes de encolar."""
        if not self.connected or self.worker is None or not self.worker.is_alive():
            messagebox.showwarning("Sin conexion", "Conecta COM3 antes de ejecutar")
            return False
        if not plans:
            messagebox.showwarning("Sin rutinas", "Selecciona al menos una rutina")
            return False
        if len(plans) > MAX_PARALLEL:
            messagebox.showwarning("Demasiadas rutinas", "Maximo 16 rutinas a la vez")
            return False
        normalized = []
        busy = {sid: data["name"] for data in self.running_job_data.values()
                for sid in ConcurrentRoutines.ids_of(data)}
        mismatches = set()
        try:
            for plan in plans:
                run_id = str(plan["run_id"])
                if run_id in self.running_job_ids:
                    raise ValueError(f"La rutina {run_id} ya esta ejecutandose")
                data = validate_routine_document(plan["data"])
                if not data["steps"]:
                    raise ValueError(f'La rutina "{data["name"]}" esta vacia')
                for step in data["steps"]:
                    for target in step["targets"]:
                        sid = target["id"]
                        if sid in busy:
                            raise ValueError(
                                f'Conflicto ID {sid}: "{data["name"]}" y '
                                f'"{busy[sid]}". No se pueden controlar '
                                "los mismos servos desde dos rutinas."
                            )
                        idx = SERVO_NAMES.index(target["slot"])
                        current_id = self.servo_rows[idx]["id"].get().strip()
                        if current_id != str(sid):
                            mismatches.add((target["slot"], sid, current_id or "vacio"))
                for sid in ConcurrentRoutines.ids_of(data):
                    busy[sid] = data["name"]
                normalized.append({"run_id": run_id, "data": data})
            if len(self.running_job_ids) + len(normalized) > MAX_PARALLEL:
                raise ValueError("Hay mas de 16 rutinas en ejecucion")
        except ValueError as exc:
            messagebox.showwarning("No se pueden ejecutar", str(exc))
            return False
        if mismatches:
            examples = "\n".join(f"{slot}: guardado {sid}, en controles {actual}"
                                  for slot, sid, actual in sorted(mismatches)[:12])
            if not messagebox.askyesno(
                "IDs guardados diferentes",
                "Las rutinas usan los IDs GUARDADOS en sus archivos, "
                "no los valores actuales de los controles.\n\n"
                + examples + "\n\n¿Ejecutar con los IDs guardados?",
                parent=self.parallel_window if self.parallel_window and
                       self.parallel_window.winfo_exists() else self.root
            ):
                return False
        for item in normalized:
            run_id = item["run_id"]
            self.running_job_ids.add(run_id)
            self.running_job_data[run_id] = item["data"]
            self.set_parallel_plan_status(run_id, "En cola", "Esperando controlador")
        self.set_routine_ui(True)
        # El worker es el UNICO que accede a COM3.
        self.commands.put(("start_routines", normalized))
        self.status.set(f"Preparando {len(normalized)} rutina(s) en paralelo...")
        return True

    def stop_routine(self):
        """Detiene TODAS las rutinas, nunca interrumpe un movimiento ya enviado."""
        if not self.routine_running:
            return
        if self.commands is not None:
            self.commands.put(("stop_routines", None))
        self.status.set("Deteniendo todas las rutinas; se cancelan ordenes pendientes. "
                        "El movimiento actual puede continuar.")

    # -------- Gestor de rutinas paralelas y grupos guardados --------

    def open_parallel_manager(self):
        if self.parallel_window is not None and self.parallel_window.winfo_exists():
            self.parallel_window.lift()
            self.parallel_window.focus_force()
            return
        win = tk.Toplevel(self.root)
        self.parallel_window = win
        win.title("Rutinas en paralelo · STS3215 · COM3")
        win.geometry("1060x610")
        win.minsize(850, 500)
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", self.close_parallel_manager)
        header = tk.Frame(win, bg=BG)
        header.pack(fill="x", padx=16, pady=(16, 9))
        self.label(header, "EJECUCION DE RUTINAS EN PARALELO", size=16,
                   bold=True, bg=BG).pack(anchor="w")
        self.label(header,
            "Carga varias rutinas JSON y ejecutalas juntas, o inicia otras mientras "
            "ya corre una. Cada rutina conserva sus propios tiempos y repeticiones.",
            size=10, fg=MUTED, bg=BG, wraplength=1010,
            justify="left").pack(anchor="w", pady=(5, 0))
        tools = tk.Frame(win, bg=PANEL, padx=12, pady=10)
        tools.pack(fill="x", padx=16, pady=(0, 8))
        for label, command, color in (
            ("+ Cargar rutinas (.json)", self.add_parallel_files, BLUE),
            ("+ Rutina del editor", self.add_editor_to_parallel, GREEN),
            ("Abrir grupo", self.load_parallel_group, PANEL2),
            ("Guardar grupo", self.save_parallel_group, PANEL2),
        ):
            self.button(tools, label, command, bg=color,
                        fg=BG if color in (BLUE, GREEN) else TEXT).pack(
                            side="left", padx=(0, 9))
        table_frame = tk.Frame(win, bg=PANEL, padx=11, pady=11)
        table_frame.pack(fill="both", expand=True, padx=16)
        self.label(table_frame, "Rutinas disponibles (seleccion multiple con Ctrl o Shift)",
                   size=11, bold=True).pack(anchor="w", pady=(0, 6))
        table_area = tk.Frame(table_frame, bg=PANEL)
        table_area.pack(fill="both", expand=True)
        columns = ("name", "source", "ids", "repeat", "progress", "status")
        tree = ttk.Treeview(table_area, columns=columns,
                            show="headings", selectmode="extended",
                            style="Rutina.Treeview")
        self.parallel_tree = tree
        for key, title, width in (
            ("name", "Rutina", 175), ("source", "Origen", 195),
            ("ids", "IDs", 130), ("repeat", "Reps.", 60),
            ("progress", "Progreso", 190), ("status", "Estado", 110),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w" if key in
                        ("name", "source", "progress") else "center",
                        stretch=key in ("name", "progress", "source"))
        scroll = ttk.Scrollbar(table_area, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        play = tk.Frame(win, bg=PANEL, padx=12, pady=10)
        play.pack(fill="x", padx=16, pady=(9, 8))
        for label, command, color, fg in (
            ("▶ Ejecutar seleccionadas", self.run_parallel_selected, GREEN, BG),
            ("▶ Ejecutar todas disponibles", self.run_parallel_all, BLUE, BG),
            ("■ Detener seleccionadas", self.stop_parallel_selected, "#813d4a", TEXT),
            ("■ Detener todas", self.stop_routine, "#813d4a", TEXT),
            ("Quitar seleccionadas", self.remove_parallel_selected, PANEL2, TEXT),
        ):
            self.button(play, label, command, bg=color, fg=fg).pack(
                side="left", padx=(0, 7))
        self.label(win,
            "SEGURIDAD: las rutinas simultaneas NO pueden compartir un mismo ID. "
            "Si coinciden, se rechaza el inicio. COM3 es un bus compartido: "
            "las ordenes se intercalan, no son simultaneas fisicamente. "
            "Detener no es paro de emergencia.",
            fg=DANGER, bg=BG, size=9, wraplength=1030,
            justify="left").pack(fill="x", padx=18, pady=(1, 9))
        self.refresh_parallel_tree()

    def close_parallel_manager(self):
        if self.parallel_window is not None and self.parallel_window.winfo_exists():
            self.parallel_window.destroy()
        self.parallel_window = None

    def set_parallel_plan_status(self, run_id, status, progress):
        for plan in self.parallel_plans:
            if plan["run_id"] == run_id:
                plan["status"] = status
                plan["progress"] = progress
                break
        self.refresh_parallel_tree()

    def refresh_parallel_tree(self):
        if self.parallel_window is None or not self.parallel_window.winfo_exists():
            return
        tree = self.parallel_tree
        selected = set(tree.selection())
        for iid in tree.get_children():
            tree.delete(iid)
        for plan in self.parallel_plans:
            data = plan["data"]
            ids = sorted(ConcurrentRoutines.ids_of(data))
            tree.insert("", "end", iid=plan["run_id"], values=(
                data["name"], plan["source"], ", ".join(map(str, ids)),
                data["repeats"], plan["progress"], plan["status"]
            ))
        for iid in selected:
            if tree.exists(iid):
                tree.selection_add(iid)

    def add_parallel_plan(self, data, source):
        data = validate_routine_document(data)
        if not data["steps"]:
            raise ValueError(f'Rutina "{data["name"]}" sin pasos')
        if len(self.parallel_plans) >= MAX_PARALLEL:
            raise ValueError("Maximo 16 rutinas en la lista")
        self.next_parallel_id += 1
        plan = {"run_id": f"plan-{self.next_parallel_id}",
                "data": data, "source": source,
                "status": "Lista", "progress": "—"}
        self.parallel_plans.append(plan)
        self.refresh_parallel_tree()
        return plan

    def add_editor_to_parallel(self):
        try:
            data = self.current_routine_document()
            self.add_parallel_plan(data, "Editor (copia)")
        except ValueError as exc:
            messagebox.showwarning("No se pudo agregar", str(exc))

    def add_parallel_files(self):
        paths = filedialog.askopenfilenames(
            parent=self.parallel_window, title="Elegir varias rutinas STS3215",
            initialdir=ROUTINE_DIR if os.path.isdir(ROUTINE_DIR) else
                       os.path.dirname(os.path.abspath(__file__)),
            filetypes=[("Rutinas STS3215", "*.json")]
        )
        errors = []
        for path in paths:
            try:
                if os.path.getsize(path) > 2_000_000:
                    raise ValueError("Archivo demasiado grande")
                with open(path, "r", encoding="utf-8") as stream:
                    data = json.load(stream)
                self.add_parallel_plan(data, os.path.basename(path))
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")
        if errors:
            messagebox.showwarning("Algunas rutinas no se cargaron", "\n".join(errors))

    def selected_parallel_plans(self):
        if self.parallel_window is None or not self.parallel_window.winfo_exists():
            return []
        choices = set(self.parallel_tree.selection())
        return [plan for plan in self.parallel_plans
                if plan["run_id"] in choices]

    def run_parallel_selected(self):
        choices = [plan for plan in self.selected_parallel_plans()
                   if plan["run_id"] not in self.running_job_ids]
        self.start_routine_batch(choices)

    def run_parallel_all(self):
        choices = [plan for plan in self.parallel_plans
                   if plan["run_id"] not in self.running_job_ids]
        self.start_routine_batch(choices)

    def stop_parallel_selected(self):
        run_ids = [plan["run_id"] for plan in self.selected_parallel_plans()
                   if plan["run_id"] in self.running_job_ids]
        if run_ids and self.commands is not None:
            self.commands.put(("stop_routines", run_ids))
            self.status.set(f"Solicitada detencion de {len(run_ids)} rutina(s)")

    def remove_parallel_selected(self):
        chosen = set(self.parallel_tree.selection())
        if chosen & self.running_job_ids:
            messagebox.showwarning("Rutinas activas", "Deten las rutinas "
                                   "seleccionadas antes de quitarlas")
            return
        self.parallel_plans = [p for p in self.parallel_plans
                               if p["run_id"] not in chosen]
        self.refresh_parallel_tree()

    def save_parallel_group(self):
        if not self.parallel_plans:
            messagebox.showwarning("Grupo vacio", "Agrega rutinas antes de guardar")
            return
        file_path = filedialog.asksaveasfilename(
            parent=self.parallel_window, title="Guardar grupo paralelo",
            initialdir=ROUTINE_DIR if os.path.isdir(ROUTINE_DIR) else
                       os.path.dirname(os.path.abspath(__file__)),
            initialfile="grupo_paralelo.json", defaultextension=".json",
            filetypes=[("Grupo paralelo STS3215", "*.json")]
        )
        if not file_path:
            return
        group = {"format": GROUP_FORMAT, "version": 1,
                 "routines": [{"source": plan["source"], "data": plan["data"]}
                              for plan in self.parallel_plans]}
        try:
            with open(file_path, "w", encoding="utf-8") as stream:
                json.dump(group, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
        except OSError as exc:
            messagebox.showerror("Error al guardar grupo", str(exc))
            return
        self.status.set("Grupo guardado: " + os.path.basename(file_path))

    def load_parallel_group(self):
        path = filedialog.askopenfilename(
            parent=self.parallel_window, title="Abrir grupo paralelo",
            initialdir=ROUTINE_DIR if os.path.isdir(ROUTINE_DIR) else
                       os.path.dirname(os.path.abspath(__file__)),
            filetypes=[("Grupo paralelo STS3215", "*.json")]
        )
        if not path:
            return
        try:
            if os.path.getsize(path) > 8_000_000:
                raise ValueError("Grupo demasiado grande")
            with open(path, "r", encoding="utf-8") as stream:
                group = json.load(stream)
            if not isinstance(group, dict) or group.get("format") != GROUP_FORMAT \
                    or group.get("version") != 1:
                raise ValueError("No es un grupo paralelo STS3215 compatible")
            items = group.get("routines")
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_PARALLEL:
                raise ValueError("El grupo debe incluir entre 1 y 16 rutinas")
            checked = []
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Entrada incorrecta en grupo")
                data = validate_routine_document(item.get("data"))
                if not data["steps"]:
                    raise ValueError("No se permiten rutinas vacias")
                source = item.get("source", "Grupo guardado")
                if not isinstance(source, str) or len(source) > 160:
                    source = "Grupo guardado"
                checked.append((data, source))
            if len(self.parallel_plans) + len(checked) > MAX_PARALLEL:
                raise ValueError("Quita rutinas de la lista antes de importar el grupo")
            for data, source in checked:
                self.add_parallel_plan(data, source)
            self.status.set("Grupo cargado: " + os.path.basename(path))
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("No se pudo abrir grupo", str(exc))

    def close(self):
        if self.closing:
            return
        if self.routine_dirty and self.routine_steps and not messagebox.askyesno(
            "Rutina sin guardar", "Hay cambios en la rutina sin guardar. "
            "Si cierras la aplicacion, se perderan. ¿Cerrar de todos modos?"
        ):
            return
        self.closing = True
        if self.worker and self.worker.is_alive():
            self.disconnect()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ServoGUI(root)
    root.mainloop()
