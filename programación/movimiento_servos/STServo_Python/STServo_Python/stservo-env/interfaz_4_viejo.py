# -*- coding: utf-8 -*-
"""Interfaz corregida para 4 servos FEETECH STS3215-12V en Bus Servo Adapter (A).

Dos parejas logicas, una por cada conector fisico. Los conectores comparten
bus: todos los servos necesitan IDs UNICOS. La placa no informa en que
conector se encuentra cada ID; el usuario los asigna visualmente.

Requisitos:
    python -m pip install ftservo-python-sdk pyserial
Ejecutar:
    python interfaz_4_servos_STS3215_espejo_COM3.py
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

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


class ServoWorker(threading.Thread):
    """Un solo hilo posee y utiliza el puerto serie; Tkinter nunca lo toca."""

    def __init__(self, messages, events):
        super().__init__(daemon=True)
        self.messages = messages
        self.events = events
        self.enabled = set()

    def emit(self, *payload):
        self.events.put(payload)

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
                action = self.messages.get()
                cmd = action[0]
                if cmd == "disconnect":
                    break

                try:
                    if cmd == "scan":
                        self.emit("info", "Buscando IDs 0-20; no desconectes la placa...")
                        found = []
                        for servo_id in range(ESCANEAR_DESDE, ESCANEAR_HASTA + 1):
                            model, result, error = servo.ping(servo_id)
                            if result == COMM_SUCCESS and error == 0:
                                found.append((servo_id, model))
                        self.emit("scan_result", found)

                    elif cmd == "probe_ids":
                        # Comprueba solo los IDs indicados en la interfaz.
                        # Sirve incluso para IDs superiores al rango de escaneo rapido.
                        checks = []
                        for index, servo_id in action[1]:
                            model, result, error = servo.ping(servo_id)
                            ok = result == COMM_SUCCESS and error == 0
                            checks.append((index, servo_id, ok, model if ok else None))
                        self.emit("probe_result", checks)

                    elif cmd == "change_id":
                        # OPERACION PERSISTENTE: solo un servo fisico conectado.
                        old_id, new_id = action[1:]
                        if old_id == new_id:
                            raise ValueError("El ID nuevo debe ser diferente")
                        model, result, error = servo.ping(old_id)
                        if result != COMM_SUCCESS or error != 0:
                            raise RuntimeError(
                                f"El ID original {old_id} no responde. "
                                "Usa Buscar servos con UNO solo conectado."
                            )
                        model, result, error = servo.ping(new_id)
                        if result == COMM_SUCCESS:
                            raise RuntimeError(
                                f"El ID destino {new_id} ya responde. "
                                "No se puede reutilizar."
                            )
                        # Desbloquear, escribir el registro 5 y volver a bloquear.
                        result, error = servo.unLockEprom(old_id)
                        if result != COMM_SUCCESS or error != 0:
                            raise RuntimeError(
                                f"No se pudo desbloquear la memoria del ID {old_id}"
                            )
                        write_result, write_error = servo.write1ByteTxRx(
                            old_id, SMS_STS_ID_ADDR, new_id
                        )
                        # Tras cambiar el ID, la respuesta de escritura puede
                        # llegar con el ID anterior, el nuevo o expirar.
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
                                self.emit("info", "ADVERTENCIA: nuevo ID detectado, "
                                          "pero no se confirmo el bloqueo de EPROM")
                            self.enabled.discard(old_id)
                            self.emit("id_changed", old_id, new_id, model)
                        else:
                            # No reintentar la escritura a ciegas: examinar el
                            # servo individualmente antes de otra modificacion.
                            try:
                                servo.LockEprom(old_id)
                            except Exception:
                                pass
                            raise RuntimeError(
                                "No se pudo verificar el ID nuevo. No repitas "
                                "la escritura sin buscar antes el ID real "
                                "con un solo servo conectado."
                            )

                    elif cmd == "read":
                        for row_index, servo_id in action[1]:
                            position, result, error = servo.ReadPos(servo_id)
                            if result != COMM_SUCCESS or error != 0:
                                self.emit("read_error", row_index, servo_id)
                            elif 0 <= position <= 4095:
                                self.emit("position", row_index, servo_id, pos_to_deg(position))
                            else:
                                self.emit("read_outside", row_index, servo_id, position)

                    elif cmd == "move":
                        # Lista de (id, angulo) y parametros de movimiento.
                        targets, speed, acc = action[1:]
                        for servo_id, _ in targets:
                            if servo_id not in self.enabled:
                                result, error = servo.write1ByteTxRx(
                                    servo_id, TORQUE_ENABLE_ADDR, 1
                                )
                                if result != COMM_SUCCESS or error != 0:
                                    raise RuntimeError(
                                        f"No se pudo activar torque en ID {servo_id}"
                                    )
                                self.enabled.add(servo_id)

                        # Usar la MISMA instruccion que ya funciona para
                        # mover un servo: WritePosEx, con acuse individual.
                        # El antiguo SyncWrite no esperaba respuesta de cada
                        # servo, por lo que podia aparentar exito sin moverlos.
                        # Estas ordenes se envian consecutivamente (NO son
                        # un movimiento exactamente simultaneo).
                        enviados = []
                        for servo_id, deg in targets:
                            result, error = servo.WritePosEx(
                                servo_id, deg_to_pos(deg), speed, acc
                            )
                            if result != COMM_SUCCESS or error != 0:
                                raise RuntimeError(
                                    f"El ID {servo_id} no confirmo WritePosEx; "
                                    f"se enviaron previamente {enviados}. "
                                    "Comprueba IDs y alimentacion."
                                )
                            enviados.append(servo_id)
                        self.emit("sent", enviados)

                    elif cmd == "release":
                        # Soltar torque SOLO en motores habilitados por la interfaz.
                        failures = []
                        for servo_id in list(self.enabled):
                            result, error = servo.write1ByteTxRx(
                                servo_id, TORQUE_ENABLE_ADDR, 0
                            )
                            if result == COMM_SUCCESS and error == 0:
                                self.enabled.discard(servo_id)
                            else:
                                failures.append(servo_id)
                        if failures:
                            raise RuntimeError(
                                f"No se pudo liberar torque en IDs {failures}"
                            )
                        self.emit("info", "Torque liberado en los servos controlados")

                except Exception as exc:
                    self.emit("error", f"{cmd}: {exc}")
        except Exception as exc:
            self.emit("error", f"Conexion: {exc}")
        finally:
            # Al desconectar se intenta liberar los servos activados por la app.
            if port is not None:
                try:
                    for servo_id in list(self.enabled):
                        servo.write1ByteTxRx(servo_id, TORQUE_ENABLE_ADDR, 0)
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
        self.root.title("Control FEETECH STS3215 · 4 servos en espejo · COM3")
        self.root.geometry("1130x890")
        self.root.minsize(940, 740)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.commands = None
        self.worker = None
        self.connected = False
        self.closing = False
        self.ids_found = []
        self.servo_rows = []
        # Una opcion independiente por cada pareja.
        # El segundo motor usa 360 - angulo_del_primero.
        self.mirror_vars = [tk.BooleanVar(value=True), tk.BooleanVar(value=True)]
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
                   "2 parejas · 4 motores · 1 bus compartido · COM3 · 1,000,000 baudios",
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

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=20)
        content.grid_columnconfigure(0, weight=1, uniform="pairs")
        content.grid_columnconfigure(1, weight=1, uniform="pairs")
        content.grid_rowconfigure(0, weight=1)

        self.build_pair(content, 0, "PAREJA A · CONECTOR 1", 0)
        self.build_pair(content, 1, "PAREJA B · CONECTOR 2", 2)

        bottom = tk.Frame(self.root, bg=PANEL, padx=14, pady=12)
        bottom.pack(fill="x", padx=20, pady=(12, 8))
        self.button(bottom, "Mover los 4 (aplicar espejo)",
                    lambda: self.send_move([0, 1, 2, 3]), bg=GREEN).pack(side="left")
        self.button(bottom, "Leer todas las posiciones", self.read_all,
                    bg=PANEL2, fg=TEXT).pack(side="left", padx=10)

        note = self.label(self.root,
            "Los dos conectores comparten bus. Los IDs escritos no reprograman los servos. "
            "Buscar servos explora IDs 0-20; Comprobar IDs escritos verifica los que asignes. "
            "Asigna IDs de manera permanente con SOLO un servo fisico conectado. "
            "Mover pareja usa la posicion del motor superior y aplica el espejo. "
            "Las ordenes se envian una detras de otra, con confirmacion por ID. "
            "Al desconectar se libera el torque.",
            bg=BG, fg=MUTED, size=9, wraplength=1000, justify="left")
        note.pack(fill="x", padx=22, pady=(2, 7))
        tk.Label(self.root, textvariable=self.status, anchor="w", bg="#263550",
                 fg="#f6f9ff", font=("Segoe UI", 10), padx=17,
                 pady=10).pack(side="bottom", fill="x")
        self.set_connected_ui(False)

    def build_pair(self, parent, col, title, first_row):
        box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER,
                       highlightthickness=1)
        box.grid(row=0, column=col, sticky="nsew", padx=(0, 7) if col == 0
                 else (7, 0))
        box.grid_columnconfigure(0, weight=1)
        self.label(box, title, size=13, bold=True).pack(anchor="w", padx=15, pady=(12, 3))
        self.label(box, "Escribe los IDs REALES; el servo superior es el maestro.",
                   fg=MUTED, size=9).pack(anchor="w", padx=15, pady=(0, 7))
        for row_index in (first_row, first_row + 1):
            self.build_servo_row(box, row_index)
        pair_idx = first_row // 2
        mirror = tk.Checkbutton(
            box, text="Espejo automatico (segundo = 360° - primero)",
            variable=self.mirror_vars[pair_idx], bg=PANEL, fg=GREEN,
            activebackground=PANEL, activeforeground=GREEN,
            selectcolor=PANEL2, highlightthickness=0,
            font=("Segoe UI", 10, "bold"),
            command=lambda j=first_row: self.sync_mirror_display(j)
        )
        mirror.pack(anchor="w", padx=14, pady=(7, 0))
        self.label(
            box, "Ejemplo: maestro 170° → segundo 190°. Desmarca para poner dos angulos libres.",
            fg=MUTED, size=9
        ).pack(anchor="w", padx=15, pady=(0, 7))
        controls = tk.Frame(box, bg=PANEL)
        controls.pack(fill="x", padx=13, pady=(5, 14))
        self.button(controls, "Mover pareja",
                    lambda j=first_row: self.send_move([j, j + 1]),
                    bg=BLUE).pack(side="left", padx=(0, 8))
        self.button(controls, "Leer pareja",
                    lambda j=first_row: self.read_rows([j, j + 1]),
                    bg=PANEL2, fg=TEXT).pack(side="left")

    def build_servo_row(self, parent, index):
        card = tk.Frame(parent, bg=PANEL2, padx=12, pady=9)
        card.pack(fill="x", padx=13, pady=6)
        top = tk.Frame(card, bg=PANEL2)
        top.pack(fill="x")
        name = ("A1", "A2", "B1", "B2")[index]
        self.label(top, "Servo " + name, size=11, bold=True,
                   bg=PANEL2).pack(side="left")
        self.label(top, "   ID:", size=10, fg=MUTED,
                   bg=PANEL2).pack(side="left")
        id_var = tk.StringVar(value="2" if index == 0 else "")
        tk.Entry(top, textvariable=id_var, width=5, font=("Segoe UI", 11),
                 justify="center", relief="flat", bg="#e7eef9",
                 fg="#172033").pack(side="left", padx=6)
        pos_var = tk.StringVar(value="Sin leer")
        tk.Label(top, textvariable=pos_var, font=("Segoe UI", 9),
                 bg=PANEL2, fg=GREEN).pack(side="right")

        middle = tk.Frame(card, bg=PANEL2)
        middle.pack(fill="x", pady=(10, 3))
        self.label(middle, "Objetivo (°)", size=9, bg=PANEL2,
                   fg=MUTED).pack(side="left")
        angle_var = tk.StringVar(value="180")
        angle_entry = tk.Entry(middle, textvariable=angle_var, width=8,
                               font=("Segoe UI", 11), justify="center",
                               relief="flat", bg="#e7eef9", fg="#172033")
        angle_entry.pack(side="right")
        angle_entry.bind("<Return>", lambda ev, i=index: self.move_from_control(i))
        slider = tk.Scale(card, from_=0, to=360, orient="horizontal",
                          resolution=1, showvalue=False, sliderlength=16,
                          bg=PANEL2, fg=TEXT, troughcolor="#384d6c",
                          highlightthickness=0, activebackground=GREEN)
        slider.set(180)
        slider.pack(fill="x")
        slider.bind("<ButtonRelease-1>", lambda ev, i=index: self.move_from_control(i))

        commands = tk.Frame(card, bg=PANEL2)
        commands.pack(fill="x", pady=(3, 0))
        self.button(commands, "-10°", lambda i=index: self.nudge(i, -10),
                    bg=PANEL, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(commands, "+10°", lambda i=index: self.nudge(i, 10),
                    bg=PANEL, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(commands, "Mover", lambda i=index: self.move_from_control(i),
                    bg=BLUE).pack(side="left", padx=(0, 5))
        self.button(commands, "Leer", lambda i=index: self.read_rows([i]),
                    bg=PANEL, fg=TEXT).pack(side="left")
        self.servo_rows.append(dict(id=id_var, angle=angle_var,
                                    slider=slider, actual=pos_var))
        slider.configure(command=lambda val, i=index: self.slider_changed(i, val))

    def set_connected_ui(self, connected):
        self.connected = connected
        self.connect_btn.config(state="disabled" if connected else "normal")
        for btn in (self.scan_btn, self.probe_btn, self.id_btn,
                    self.disc_btn, self.release_btn):
            btn.config(state="normal" if connected else "disabled")

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
            self.status.set("Desconectando; liberando torque de servos activados...")
            self.commands.put(("disconnect",))
            self.disc_btn.config(state="disabled")

    def scan(self):
        if self.connected:
            self.scan_btn.config(state="disabled")
            self.commands.put(("scan",))

    def release(self):
        if self.connected:
            self.commands.put(("release",))

    def probe_ids(self):
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
                messagebox.showwarning("ID incorrecto", f"El ID de {('A1', 'A2', 'B1', 'B2')[index]} no es numerico")
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

    def sync_mirror_display(self, first_row):
        if not self.mirror_vars[first_row // 2].get():
            return
        try:
            master = float(self.servo_rows[first_row]["angle"].get().replace(",", "."))
            deg_to_pos(master)
            self.set_target(first_row + 1, 360.0 - master)
        except ValueError:
            pass

    def slider_changed(self, index, raw_value):
        degree = float(raw_value)
        self.servo_rows[index]["angle"].set(f"{degree:g}")
        # Mostrar inmediatamente el objetivo reflejado mientras se arrastra.
        if index in (0, 2) and self.mirror_vars[index // 2].get():
            self.set_target(index + 1, 360.0 - degree)

    def move_from_control(self, index):
        # Cuando se mueve el maestro y hay espejo, mover a los dos.
        # La fila inferior sigue disponiendo de control independiente.
        if index in (0, 2) and self.mirror_vars[index // 2].get():
            self.send_move([index, index + 1])
        else:
            self.send_move([index])

    def get_ids_and_targets(self, row_indices):
        ids_seen = set()
        targets = []
        for i in row_indices:
            row = self.servo_rows[i]
            try:
                servo_id = int(row["id"].get().strip())
            except ValueError:
                raise ValueError(f"Escribe el ID de {('A1','A2','B1','B2')[i]}")
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
                raise ValueError(f"ID no valido en {('A1','A2','B1','B2')[i]}")
            if not (0 <= servo_id <= 253):
                raise ValueError(f"ID fuera de rango: {servo_id}")
            result.append((i, servo_id))
        if len({ident for _, ident in result}) != len(result):
            raise ValueError("Hay IDs duplicados entre los servos seleccionados")
        return result

    def send_move(self, row_indices):
        if not self.connected:
            self.status.set("Conecta primero a COM3")
            return
        try:
            # Si seleccionamos una pareja (o las dos), aplicar espejo.
            # No modifica los limites, ID ni calibracion del servo.
            if 0 in row_indices and 1 in row_indices:
                self.sync_mirror_display(0)
            if 2 in row_indices and 3 in row_indices:
                self.sync_mirror_display(2)
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
        if not self.connected:
            return
        try:
            row_ids = self.get_ids_for_read(row_indices)
            self.commands.put(("read", row_ids))
            self.status.set("Leyendo posiciones...")
        except ValueError as exc:
            messagebox.showwarning("Verifica IDs", str(exc))

    def read_all(self):
        self.read_rows([0, 1, 2, 3])

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
                self.scan_btn.config(state="normal")
                self.auto_fill_ids(found)
                self.status.set(
                    f"Se detectaron {len(found)} servo(s). "
                    "Revisa manualmente a que pareja fisica pertenece cada ID."
                )
                if len(found) < 4:
                    self.status.set(
                        f"Busqueda rapida (IDs 0-20): respondieron {len(found)} ID(s): "
                        f"{self.ids_found}. Esto NO confirma IDs duplicados. "
                        "Usa 'Comprobar IDs escritos' para un diagnostico exacto."
                    )
            elif kind == "probe_result":
                checks = event[1]
                self.probe_btn.config(state="normal")
                names = ("A1", "A2", "B1", "B2")
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
                    "Cuando todos tengan IDs distintos, conecta los cuatro."
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

    def close(self):
        if self.closing:
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
