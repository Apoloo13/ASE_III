# """4-Servo Feetech STS3215-12V Controller (IDs 5, 6, 7, 8).

# Usage:
#     1) Live monitor (compact single-line format for PowerShell):
#        python play_sts3215_4servos.py --port COM4 --check

#     2) Move all 4 servos smoothly to neutral 180.0 deg (2048 ticks):
#        python play_sts3215_4servos.py --port COM4 --go-home

#     3) Play a syllable in slow motion first (3x slower) to verify clearance:
#        python play_sts3215_4servos.py --port COM4 --csv orofacial_results/servo_trajectories/servo_trajectory_SA.csv --time-scale 3.0

#     4) Play a syllable at real-time 1.0x human speed:
#        python play_sts3215_4servos.py --port COM4 --csv orofacial_results/servo_trajectories/servo_trajectory_SA.csv
# """
# from __future__ import annotations

# import argparse
# import time
# from pathlib import Path
# import numpy as np
# import pandas as pd

# from scservo_sdk import (
#     PortHandler,
#     PacketHandler,
#     GroupSyncWrite,
#     COMM_SUCCESS,
#     SCS_LOBYTE,
#     SCS_HIBYTE,
# )

# # ==============================================================================
# # 1. STS3215 REGISTER ADDRESSES & HARDWARE CONFIGURATION
# # ==============================================================================
# ADDR_SCS_TORQUE_ENABLE    = 40
# ADDR_STS_GOAL_ACC         = 41
# ADDR_STS_GOAL_POSITION    = 42
# ADDR_STS_GOAL_SPEED       = 46
# ADDR_STS_LOCK             = 55
# ADDR_STS_PRESENT_POSITION = 56

# PROTOCOL_END = 0
# BAUDRATE = 1000000
# STEPS_PER_DEG = 4096.0 / 360.0  # 11.37778 ticks/deg
# HOME_TICK_180 = 2048            # 180.0 deg neutral position

# MAX_SPEED_STEPS = 3400
# MIN_SPEED_STEPS = 120
# SPEED_HEADROOM  = 1.15

# SERVO_CONFIG = {
#     "DER_TOP":    {"id": 5, "home_tick": HOME_TICK_180, "dir": -1},  # Right cheek upper (straight up = 180°)
#     "DER_BOTTOM": {"id": 6, "home_tick": HOME_TICK_180, "dir": -1},  # Right cheek lower (straight down = 180°)
#     "IZQ_TOP":    {"id": 7, "home_tick": HOME_TICK_180, "dir": +1},  # Left cheek upper  (straight up = 180°)
#     "IZQ_BOTTOM": {"id": 8, "home_tick": HOME_TICK_180, "dir": +1},  # Left cheek lower  (straight down = 180°)
# }


# # ==============================================================================
# # 2. CONVERSION & REGISTER HELPER FUNCTIONS
# # ==============================================================================
# def dtheta_to_servo_deg(dtheta_deg: float, direction: int) -> float:
#     return 180.0 + direction * dtheta_deg


# def dtheta_to_ticks(dtheta_deg: float, home_tick: int, direction: int) -> int:
#     ticks = round(home_tick + direction * dtheta_deg * STEPS_PER_DEG)
#     return int(np.clip(ticks, 50, 4045))


# def ticks_to_servo_deg(ticks: int) -> float:
#     return float(ticks / STEPS_PER_DEG)


# def ticks_to_dtheta_deg(ticks: int, home_tick: int, direction: int) -> float:
#     return float((ticks - home_tick) * direction / STEPS_PER_DEG)


# def speed_degs_to_steps(omega_degs: float, time_scale: float = 1.0) -> int:
#     steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
#     return int(np.clip(steps_s, MIN_SPEED_STEPS, MAX_SPEED_STEPS))


# def accel_degs2_to_unit(alpha_degs2: float, time_scale: float = 1.0) -> int:
#     acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
#     return int(np.clip(acc_unit, 1, 254))


# def write_pos_ex(port: PortHandler, ph: PacketHandler, servo_id: int, pos_ticks: int, speed_steps: int, acc_unit: int):
#     ph.write1ByteTxRx(port, servo_id, ADDR_STS_GOAL_ACC, acc_unit)
#     ph.write2ByteTxRx(port, servo_id, ADDR_STS_GOAL_SPEED, speed_steps)
#     ph.write2ByteTxRx(port, servo_id, ADDR_STS_GOAL_POSITION, pos_ticks)


# def read_pos(port: PortHandler, ph: PacketHandler, servo_id: int) -> tuple[int, int]:
#     raw_pos, comm, _ = ph.read2ByteTxRx(port, servo_id, ADDR_STS_PRESENT_POSITION)
#     if raw_pos & 0x8000:
#         raw_pos = -(raw_pos & 0x7FFF)
#     return raw_pos, comm


# # ==============================================================================
# # 3. DIAGNOSTIC, CALIBRATION & PLAYBACK MODES
# # ==============================================================================
# def check_servos(port: PortHandler, ph: PacketHandler):
#     print("\n--- STS3215 4-SERVO LIVE ANGLE MONITOR ---")
#     print("Push DER_TOP(ID5) and IZQ_TOP(ID7) slightly forward toward the mouth to verify tick direction.")
#     print("Press Ctrl+C to exit.\n")

#     for cfg in SERVO_CONFIG.values():
#         ph.write1ByteTxRx(port, cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

#     try:
#         while True:
#             status = []
#             for name, cfg in SERVO_CONFIG.items():
#                 pos, comm = read_pos(port, ph, cfg["id"])
#                 if comm == COMM_SUCCESS:
#                     deg = ticks_to_servo_deg(pos)
#                     status.append(f"ID{cfg['id']}:{deg:5.1f}°[{pos:4d}]")
#                 else:
#                     status.append(f"ID{cfg['id']}:OFF")
#             print(" | ".join(status) + "   ", end="\r", flush=True)
#             time.sleep(0.05)
#     except KeyboardInterrupt:
#         print("\nMonitor closed.")


# def set_center_180(port: PortHandler, ph: PacketHandler):
#     print("\nSetting current physical position of all 4 servos to 180.0° (2048 ticks)...")
#     for name, cfg in SERVO_CONFIG.items():
#         sid = cfg["id"]
#         ph.write1ByteTxRx(port, sid, ADDR_STS_LOCK, 0)
#         comm, _ = ph.write1ByteTxRx(port, sid, ADDR_SCS_TORQUE_ENABLE, 128)
#         time.sleep(0.05)
#         ph.write1ByteTxRx(port, sid, ADDR_STS_LOCK, 1)
#         pos, comm_r = read_pos(port, ph, sid)
#         if comm == COMM_SUCCESS and comm_r == COMM_SUCCESS:
#             print(f"  [OK] {name} (ID {sid}) -> {ticks_to_servo_deg(pos):.1f}° ({pos} ticks)")
#         else:
#             print(f"  [ERR] {name} (ID {sid}) failed to respond.")


# def go_home_180(port: PortHandler, ph: PacketHandler):
#     print("\nMoving all 4 servos smoothly to neutral 180.0° (2048 ticks)...")
#     for cfg in SERVO_CONFIG.values():
#         write_pos_ex(port, ph, cfg["id"], cfg["home_tick"], speed_steps=400, acc_unit=10)
#     time.sleep(1.0)
#     print("Done.")


# def play_trajectory(port: PortHandler, ph: PacketHandler, csv_path: Path, time_scale: float = 1.0):
#     df = pd.read_csv(csv_path)
#     total_ms = float(df["time_ms"].iloc[-1]) * time_scale
#     print(f"\nLoaded {csv_path.name} ({len(df)} steps | Time scale: {time_scale:.1f}x | Total time: {total_ms:.0f} ms)")

#     print("Moving all 4 servos to initial 0% syllable pose...")
#     for name, cfg in SERVO_CONFIG.items():
#         side, tier = name.split("_")
#         col = f"{side}_dtheta1_from_90_deg" if tier == "TOP" else f"{side}_dtheta2_from_neg90_deg"
#         init_ticks = dtheta_to_ticks(float(df[col].iloc[0]), cfg["home_tick"], cfg["dir"])
#         write_pos_ex(port, ph, cfg["id"], init_ticks, speed_steps=400, acc_unit=10)
#     time.sleep(0.8)

#     sync_write = GroupSyncWrite(port, ph, ADDR_STS_GOAL_ACC, 7)
#     feedback_rows = []
#     t_start = time.perf_counter()

#     for _, row in df.iterrows():
#         target_time_s = float(row["time_s"]) * time_scale
#         sync_write.clearParam()
#         log_item = {"phase_pct": row["phase_pct"], "time_ms": float(row["time_ms"]) * time_scale}

#         for name, cfg in SERVO_CONFIG.items():
#             side, tier = name.split("_")
#             m_idx = "1" if tier == "TOP" else "2"
#             ref_str = "90" if m_idx == "1" else "neg90"

#             dtheta = float(row[f"{side}_dtheta{m_idx}_from_{ref_str}_deg"])
#             omega  = float(row[f"{side}_omega{m_idx}_speed_degs"])
#             alpha  = float(row[f"{side}_alpha{m_idx}_accel_degs2"])

#             pos_ticks   = dtheta_to_ticks(dtheta, cfg["home_tick"], cfg["dir"])
#             speed_steps = speed_degs_to_steps(omega, time_scale)
#             acc_unit    = accel_degs2_to_unit(alpha, time_scale)

#             param_bytes = [
#                 acc_unit & 0xFF,
#                 SCS_LOBYTE(pos_ticks),
#                 SCS_HIBYTE(pos_ticks),
#                 0,
#                 0,
#                 SCS_LOBYTE(speed_steps),
#                 SCS_HIBYTE(speed_steps),
#             ]
#             sync_write.addParam(cfg["id"], param_bytes)

#             log_item[f"{name}_cmd_deg"]   = dtheta_to_servo_deg(dtheta, cfg["dir"])
#             log_item[f"{name}_cmd_ticks"] = pos_ticks
#             log_item[f"{name}_cmd_speed"] = speed_steps
#             log_item[f"{name}_cmd_acc"]   = acc_unit

#         while (time.perf_counter() - t_start) < target_time_s:
#             pass

#         sync_write.txPacket()

#         for name, cfg in SERVO_CONFIG.items():
#             pos_meas, comm = read_pos(port, ph, cfg["id"])
#             if comm == COMM_SUCCESS:
#                 log_item[f"{name}_meas_deg"] = ticks_to_servo_deg(pos_meas)
#                 log_item[f"{name}_meas_dtheta_deg"] = ticks_to_dtheta_deg(pos_meas, cfg["home_tick"], cfg["dir"])
#             else:
#                 log_item[f"{name}_meas_deg"] = np.nan
#                 log_item[f"{name}_meas_dtheta_deg"] = np.nan

#         feedback_rows.append(log_item)

#     elapsed_ms = (time.perf_counter() - t_start) * 1000.0
#     print(f"Finished 4-servo playback in {elapsed_ms:.1f} ms.")

#     out_csv = csv_path.with_name(csv_path.stem + "_4servo_feedback.csv")
#     pd.DataFrame(feedback_rows).to_csv(out_csv, index=False)
#     print(f"Saved hardware execution log -> {out_csv}")


# def main():
#     parser = argparse.ArgumentParser(description="4-Servo STS3215-12V Trajectory Controller")
#     parser.add_argument("--port", type=str, default="COM4", help="COM port (default: COM4)")
#     parser.add_argument("--check", action="store_true", help="Live monitor of angles (deg) and ticks")
#     parser.add_argument("--set-center", action="store_true", help="Calibrate current pose as 180.0° (2048 ticks)")
#     parser.add_argument("--go-home", action="store_true", help="Move all 4 servos to 180.0° (2048 ticks)")
#     parser.add_argument("--csv", type=Path, help="Path to servo_trajectory_<SYL>.csv")
#     parser.add_argument("--time-scale", type=float, default=1.0, help="Slow-motion multiplier (e.g. 3.0 = 3x slower)")
#     args = parser.parse_args()

#     port = PortHandler(args.port)
#     ph = PacketHandler(PROTOCOL_END)

#     if not port.openPort():
#         raise SystemExit(f"Could not open port {args.port}")
#     if not port.setBaudRate(BAUDRATE):
#         raise SystemExit(f"Could not set baudrate {BAUDRATE}")

#     try:
#         if args.check:
#             check_servos(port, ph)
#         elif args.set_center:
#             set_center_180(port, ph)
#         elif args.go_home:
#             go_home_180(port, ph)
#         elif args.csv:
#             play_trajectory(port, ph, args.csv.expanduser().resolve(), args.time_scale)
#         else:
#             print("Specify one of: --check, --set-center, --go-home, or --csv <file>")
#     finally:
#         port.closePort()


# if __name__ == "__main__":
#     main()
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""Interfaz grafica para control y reproduccion de silabas con 4 servos FEETECH STS3215-12V.

Compatible directamente con ftservo-python-sdk 2.0.1 (usa sms_sts igual que interfaz_8_servos_nuevo.py).
"""

from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import numpy as np
    import pandas as pd
    from scservo_sdk import COMM_SUCCESS, PortHandler, sms_sts
    try:
        from scservo_sdk import GroupSyncWrite
    except ImportError:
        GroupSyncWrite = None
except ImportError as exc:
    raise SystemExit(
        f"Error de importacion real: {exc}\n"
        "Instala en este Python con: python -m pip install ftservo-python-sdk pyserial numpy pandas"
    ) from exc

# ==============================================================================
# 1. REGISTROS STS3215, CONFIGURACION FISICA Y LIMITES DE SEGURIDAD
# ==============================================================================
ADDR_SCS_TORQUE_ENABLE    = 40
ADDR_STS_GOAL_ACC         = 41
ADDR_STS_GOAL_POSITION    = 42
ADDR_STS_GOAL_SPEED       = 46
ADDR_STS_LOCK             = 55
ADDR_STS_PRESENT_POSITION = 56

DEFAULT_COM   = "COM4"
BAUDRATE      = 1000000
STEPS_PER_DEG = 4096.0 / 360.0  # 11.37778 ticks/deg
HOME_TICK_180 = 2048            # Posicion neutral 180.0°

# Limites de seguridad para proteger los servos y el mecanismo orofacial
MIN_SPEED_STEPS       = 120
SAFE_DEFAULT_MAX_STEP = 1200    # Limite seguro por defecto (~105°/s)
SAFE_HARD_LIMIT_STEP  = 1500    # Tope maximo permitido en la UI (igual que interfaz_8_servos_nuevo.py)
SAFE_MAX_ACC_UNIT     = 100     # Tope seguro de aceleracion (evita tirones bruscos de 254)
SPEED_HEADROOM        = 1.15
MIN_SAFE_TICK         = 50
MAX_SAFE_TICK         = 4045

# Escala de velocidad de reproduccion (0.20x camara lenta -> 1.00x velocidad humana maxima)
MIN_SPEED_MULT        = 0.20    # Equivale a time_scale = 5.0 (5x mas lento)
MAX_SAFE_SPEED_MULT   = 1.00    # Equivale a time_scale = 1.0 (nunca supera tiempo real)
DEFAULT_SPEED_MULT    = 0.33    # Equivale a time_scale ~ 3.0 (recomendado para verificar holgura)

DEFAULT_TRAJ_DIR = Path("orofacial_results/servo_trajectories")

SERVO_ORDER = ("DER_TOP", "IZQ_TOP", "DER_BOTTOM", "IZQ_BOTTOM")
SERVO_CONFIG = {
    "DER_TOP":    {"id": 5, "home_tick": HOME_TICK_180, "dir": -1, "label": "Mejilla Der. Superior"},
    "DER_BOTTOM": {"id": 6, "home_tick": HOME_TICK_180, "dir": -1, "label": "Mejilla Der. Inferior"},
    "IZQ_TOP":    {"id": 7, "home_tick": HOME_TICK_180, "dir": +1, "label": "Mejilla Izq. Superior"},
    "IZQ_BOTTOM": {"id": 8, "home_tick": HOME_TICK_180, "dir": +1, "label": "Mejilla Izq. Inferior"},
}

# Paleta de colores estilo interfaz_8_servos_nuevo.py
BG     = "#0d1524"
PANEL  = "#182338"
PANEL2 = "#202f48"
TEXT   = "#eaf1fb"
MUTED  = "#a6b6cf"
BLUE   = "#4ea8ff"
GREEN  = "#49d9ac"
WARN   = "#e6bb68"
DANGER = "#f29aa2"
BORDER = "#30415b"


# ==============================================================================
# 2. FUNCIONES DE CONVERSION Y SEGURIDAD
# ==============================================================================
def scs_lobyte(val: int) -> int:
    return int(val) & 0xFF


def scs_hibyte(val: int) -> int:
    return (int(val) >> 8) & 0xFF


def dtheta_to_servo_deg(dtheta_deg: float, direction: int) -> float:
    return 180.0 + direction * dtheta_deg


def dtheta_to_ticks(dtheta_deg: float, home_tick: int, direction: int) -> int:
    ticks = round(home_tick + direction * dtheta_deg * STEPS_PER_DEG)
    return int(np.clip(ticks, MIN_SAFE_TICK, MAX_SAFE_TICK))


def servo_deg_to_ticks(deg: float) -> int:
    return int(np.clip(round(float(deg) * STEPS_PER_DEG), MIN_SAFE_TICK, MAX_SAFE_TICK))


def ticks_to_servo_deg(ticks: int) -> float:
    return float(ticks / STEPS_PER_DEG)


def ticks_to_dtheta_deg(ticks: int, home_tick: int, direction: int) -> float:
    return float((ticks - home_tick) * direction / STEPS_PER_DEG)


def safe_speed_degs_to_steps(
    omega_degs: float,
    time_scale: float = 1.0,
    max_speed_cap: int = SAFE_DEFAULT_MAX_STEP,
) -> int:
    safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
    steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
    return int(np.clip(steps_s, MIN_SPEED_STEPS, safe_cap))


def safe_accel_degs2_to_unit(alpha_degs2: float, time_scale: float = 1.0) -> int:
    acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
    return int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))


def extract_syllable_name(csv_path: Path) -> str:
    match = re.match(r"servo_trajectory_(.+)$", csv_path.stem, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return csv_path.stem.upper()


# ==============================================================================
# 3. HILO DE COMUNICACION SERIE (ServoWorker usando sms_sts)
# ==============================================================================
class ServoWorker(threading.Thread):
    """Un solo hilo posee y utiliza el puerto serie; Tkinter nunca lo toca directamente."""

    def __init__(
        self,
        com_port: str,
        messages: queue.Queue,
        events: queue.Queue,
        stop_event: threading.Event,
    ):
        super().__init__(daemon=True)
        self.com_port = com_port
        self.messages = messages
        self.events = events
        self.stop_event = stop_event
        self.monitoring = False

    def emit(self, *payload):
        self.events.put(payload)

    def write_pos_ex(
        self,
        servo: sms_sts,
        servo_id: int,
        pos_ticks: int,
        speed_steps: int,
        acc_unit: int,
    ):
        safe_pos = int(np.clip(pos_ticks, MIN_SAFE_TICK, MAX_SAFE_TICK))
        safe_spd = int(np.clip(speed_steps, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
        safe_acc = int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))
        servo.write1ByteTxRx(servo_id, ADDR_SCS_TORQUE_ENABLE, 1)
        return servo.WritePosEx(servo_id, safe_pos, safe_spd, safe_acc)

    def read_pos(self, servo: sms_sts, servo_id: int) -> tuple[int, int]:
        pos, comm, _ = servo.ReadPos(servo_id)
        return pos, comm

    def read_all_positions(self, servo: sms_sts, servo_map: dict):
        readings = {}
        for name, cfg in servo_map.items():
            pos, comm = self.read_pos(servo, cfg["id"])
            if comm == COMM_SUCCESS:
                readings[name] = {
                    "ok": True,
                    "id": cfg["id"],
                    "ticks": pos,
                    "deg": ticks_to_servo_deg(pos),
                    "dtheta": ticks_to_dtheta_deg(pos, cfg["home_tick"], cfg["dir"]),
                }
            else:
                readings[name] = {"ok": False, "id": cfg["id"]}
        self.emit("positions", readings)

    def release_all_torque(self, servo: sms_sts, servo_map: dict):
        for cfg in servo_map.values():
            servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

    def run(self):
        port = None
        servo = None
        try:
            port = PortHandler(self.com_port)
            servo = sms_sts(port)
            if not port.openPort():
                raise RuntimeError(f"No se pudo abrir el puerto {self.com_port}")
            if not port.setBaudRate(BAUDRATE):
                raise RuntimeError(f"No se pudo configurar {BAUDRATE} baudios")
            self.emit("connected", self.com_port)

            while True:
                timeout = 0.08 if self.monitoring else None
                try:
                    action = self.messages.get(timeout=timeout)
                except queue.Empty:
                    if self.monitoring:
                        self.read_all_positions(servo, SERVO_CONFIG)
                    continue

                cmd = action[0]
                if cmd == "disconnect":
                    break

                try:
                    if cmd == "ping_all":
                        servo_map = action[1]
                        status = {}
                        for name, cfg in servo_map.items():
                            pos, comm = self.read_pos(servo, cfg["id"])
                            if comm == COMM_SUCCESS:
                                status[name] = {
                                    "ok": True,
                                    "id": cfg["id"],
                                    "ticks": pos,
                                    "deg": ticks_to_servo_deg(pos),
                                    "dtheta": ticks_to_dtheta_deg(pos, cfg["home_tick"], cfg["dir"]),
                                }
                            else:
                                status[name] = {"ok": False, "id": cfg["id"]}
                        self.emit("ping_result", status)

                    elif cmd == "set_monitor":
                        enable, servo_map = action[1], action[2]
                        self.monitoring = bool(enable)
                        if self.monitoring:
                            self.release_all_torque(servo, servo_map)
                            self.emit(
                                "info",
                                "Monitor en vivo ACTIVO (torque liberado). Mueve los servos manualmente para verificar direccion.",
                            )
                        else:
                            self.emit("info", "Monitor en vivo detenido.")
                        self.emit("monitor_state", self.monitoring)

                    elif cmd == "read_once":
                        servo_map = action[1]
                        self.read_all_positions(servo, servo_map)

                    elif cmd == "go_home":
                        servo_map, speed_cap = action[1], action[2]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        safe_home_speed = min(400, int(speed_cap))
                        self.emit("info", "Moviendo los 4 servos suavemente a neutral 180.0° (2048 ticks)...")
                        for cfg in servo_map.values():
                            self.write_pos_ex(
                                servo, cfg["id"], cfg["home_tick"], speed_steps=safe_home_speed, acc_unit=10
                            )
                        time.sleep(0.9)
                        self.read_all_positions(servo, servo_map)
                        self.emit("info", "Los 4 servos estan en posicion neutral 180.0° (2048 ticks).")

                    elif cmd == "set_center":
                        servo_map = action[1]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        results = []
                        for name, cfg in servo_map.items():
                            sid = cfg["id"]
                            servo.unLockEprom(sid)
                            comm, _ = servo.write1ByteTxRx(sid, ADDR_SCS_TORQUE_ENABLE, 128)
                            time.sleep(0.05)
                            servo.LockEprom(sid)
                            pos, comm_r = self.read_pos(servo, sid)
                            ok = comm == COMM_SUCCESS and comm_r == COMM_SUCCESS
                            results.append((name, sid, ok, pos))
                        self.read_all_positions(servo, servo_map)
                        self.emit("center_calibrated", results)

                    elif cmd == "move_single":
                        servo_map, name, target_deg, speed_cap = action[1:]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        cfg = servo_map[name]
                        ticks = servo_deg_to_ticks(target_deg)
                        safe_spd = min(350, int(speed_cap))
                        self.write_pos_ex(servo, cfg["id"], ticks, speed_steps=safe_spd, acc_unit=12)
                        time.sleep(0.15)
                        self.read_all_positions(servo, servo_map)
                        self.emit("info", f"{name} (ID {cfg['id']}) enviado a {target_deg:.1f}° ({ticks} ticks)")

                    elif cmd == "release":
                        servo_map = action[1]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        self.release_all_torque(servo, servo_map)
                        self.emit("info", "Torque liberado en los 4 servos.")

                    elif cmd == "play_csv":
                        csv_path, time_scale, max_speed_cap, save_feedback, servo_map = action[1:]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        self.stop_event.clear()
                        self.run_trajectory(
                            port, servo, Path(csv_path), float(time_scale), int(max_speed_cap), bool(save_feedback), servo_map
                        )

                except Exception as exc:
                    self.emit("error", f"{cmd}: {exc}")

        except Exception as exc:
            self.emit("error", f"Conexion: {exc}")
        finally:
            if port is not None and servo is not None:
                try:
                    self.release_all_torque(servo, SERVO_CONFIG)
                except Exception:
                    pass
                try:
                    port.closePort()
                except Exception:
                    pass
            self.emit("disconnected")

    def run_trajectory(
        self,
        port: PortHandler,
        servo: sms_sts,
        csv_path: Path,
        time_scale: float,
        max_speed_cap: int,
        save_feedback: bool,
        servo_map: dict,
    ):
        df = pd.read_csv(csv_path)
        for col in ("time_s", "time_ms", "phase_pct"):
            if col not in df.columns:
                raise ValueError(f"El CSV no contiene la columna requerida '{col}'")

        time_scale = max(1.0, float(time_scale))
        safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))

        total_ms = float(df["time_ms"].iloc[-1]) * time_scale
        syl_name = extract_syllable_name(csv_path)
        self.emit("playback_started", syl_name, len(df), time_scale, total_ms)

        # 1. Mover suavemente a la pose inicial (0% de la silaba)
        init_speed = min(400, safe_cap)
        for name, cfg in servo_map.items():
            side, tier = name.split("_")
            col = f"{side}_dtheta1_from_90_deg" if tier == "TOP" else f"{side}_dtheta2_from_neg90_deg"
            init_ticks = dtheta_to_ticks(float(df[col].iloc[0]), cfg["home_tick"], cfg["dir"])
            self.write_pos_ex(servo, cfg["id"], init_ticks, speed_steps=init_speed, acc_unit=10)

        t_wait = time.perf_counter()
        while (time.perf_counter() - t_wait) < 0.8:
            if self.stop_event.is_set():
                self.release_all_torque(servo, servo_map)
                self.emit("playback_stopped", "Reproduccion cancelada antes de iniciar.")
                return
            time.sleep(0.02)

        # 2. Preparar GroupSyncWrite (si esta disponible en el SDK) o usar WritePosEx
        sync_write = None
        if GroupSyncWrite is not None:
            try:
                sync_write = GroupSyncWrite(port, servo, ADDR_STS_GOAL_ACC, 7)
            except Exception:
                sync_write = getattr(servo, "groupSyncWrite", None)
        else:
            sync_write = getattr(servo, "groupSyncWrite", None)

        feedback_rows = []
        total_rows = len(df)
        t_start = time.perf_counter()

        for idx, row in df.iterrows():
            if self.stop_event.is_set():
                self.release_all_torque(servo, servo_map)
                self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
                return

            target_time_s = float(row["time_s"]) * time_scale
            if sync_write is not None:
                sync_write.clearParam()

            log_item = {
                "phase_pct": float(row["phase_pct"]),
                "time_ms": float(row["time_ms"]) * time_scale,
            }

            cmd_snapshot = {}
            direct_queue = []
            for name, cfg in servo_map.items():
                side, tier = name.split("_")
                m_idx = "1" if tier == "TOP" else "2"
                ref_str = "90" if m_idx == "1" else "neg90"

                dtheta = float(row[f"{side}_dtheta{m_idx}_from_{ref_str}_deg"])
                omega  = float(row[f"{side}_omega{m_idx}_speed_degs"])
                alpha  = float(row[f"{side}_alpha{m_idx}_accel_degs2"])

                pos_ticks   = dtheta_to_ticks(dtheta, cfg["home_tick"], cfg["dir"])
                speed_steps = safe_speed_degs_to_steps(omega, time_scale, safe_cap)
                acc_unit    = safe_accel_degs2_to_unit(alpha, time_scale)

                if sync_write is not None:
                    param_bytes = [
                        acc_unit & 0xFF,
                        scs_lobyte(pos_ticks),
                        scs_hibyte(pos_ticks),
                        0,
                        0,
                        scs_lobyte(speed_steps),
                        scs_hibyte(speed_steps),
                    ]
                    sync_write.addParam(cfg["id"], param_bytes)
                else:
                    direct_queue.append((cfg["id"], pos_ticks, speed_steps, acc_unit))

                cmd_deg = dtheta_to_servo_deg(dtheta, cfg["dir"])
                log_item[f"{name}_cmd_deg"]   = cmd_deg
                log_item[f"{name}_cmd_ticks"] = pos_ticks
                log_item[f"{name}_cmd_speed"] = speed_steps
                log_item[f"{name}_cmd_acc"]   = acc_unit
                cmd_snapshot[name] = {
                    "cmd_deg": cmd_deg,
                    "cmd_ticks": pos_ticks,
                    "cmd_speed": speed_steps,
                }

            while (time.perf_counter() - t_start) < target_time_s:
                if self.stop_event.is_set():
                    break

            if self.stop_event.is_set():
                self.release_all_torque(servo, servo_map)
                self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
                return

            if sync_write is not None:
                sync_write.txPacket()
            else:
                for sid, pticks, ssteps, aunit in direct_queue:
                    servo.WritePosEx(sid, pticks, ssteps, aunit)

            meas_snapshot = {}
            for name, cfg in servo_map.items():
                pos_meas, comm = self.read_pos(servo, cfg["id"])
                if comm == COMM_SUCCESS:
                    meas_deg = ticks_to_servo_deg(pos_meas)
                    meas_dtheta = ticks_to_dtheta_deg(pos_meas, cfg["home_tick"], cfg["dir"])
                    log_item[f"{name}_meas_deg"] = meas_deg
                    log_item[f"{name}_meas_dtheta_deg"] = meas_dtheta
                    meas_snapshot[name] = {
                        "ok": True,
                        "id": cfg["id"],
                        "ticks": pos_meas,
                        "deg": meas_deg,
                        "dtheta": meas_dtheta,
                    }
                else:
                    log_item[f"{name}_meas_deg"] = np.nan
                    log_item[f"{name}_meas_dtheta_deg"] = np.nan
                    meas_snapshot[name] = {"ok": False, "id": cfg["id"]}

            feedback_rows.append(log_item)

            if idx % 3 == 0 or idx == total_rows - 1:
                self.emit(
                    "playback_step",
                    float(row["phase_pct"]),
                    idx + 1,
                    total_rows,
                    cmd_snapshot,
                    meas_snapshot,
                )

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        out_csv_msg = ""
        if save_feedback and feedback_rows:
            out_csv = csv_path.with_name(csv_path.stem + "_4servo_feedback.csv")
            pd.DataFrame(feedback_rows).to_csv(out_csv, index=False)
            out_csv_msg = f" | Log guardado: {out_csv.name}"

        self.emit("playback_finished", syl_name, elapsed_ms, out_csv_msg)


# ==============================================================================
# 4. INTERFAZ GRAFICA PRINCIPAL (Tkinter)
# ==============================================================================
class SyllableServoGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Control Orofacial FEETECH STS3215 · 4 Servos (IDs 5, 6, 7, 8) · Reproductor de Silabas")
        self.root.geometry("1200x880")
        self.root.minsize(1020, 740)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.events = queue.Queue()
        self.commands: queue.Queue | None = None
        self.worker: ServoWorker | None = None
        self.stop_event = threading.Event()

        self.connected = False
        self.playing = False
        self.monitoring = False
        self.closing = False

        self.port_var = tk.StringVar(value=DEFAULT_COM)
        self.traj_dir = Path(__file__).resolve().parent / DEFAULT_TRAJ_DIR
        self.syllable_files: dict[str, Path] = {}
        self.selected_syllable = tk.StringVar(value="")
        self.csv_info_var = tk.StringVar(value="Selecciona una silaba o carga un archivo CSV.")

        self.speed_mult_var = tk.DoubleVar(value=DEFAULT_SPEED_MULT)
        self.speed_label_var = tk.StringVar()
        self.max_steps_var = tk.IntVar(value=SAFE_DEFAULT_MAX_STEP)
        self.max_steps_label_var = tk.StringVar()

        self.save_log_var = tk.BooleanVar(value=True)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="Fase: 0% (En espera)")
        self.status_var = tk.StringVar(
            value="Desconectado. Verifica el puerto COM y presiona Conectar."
        )

        self.servo_cards: dict[str, dict] = {}
        self.quick_syl_buttons: list[tk.Button] = []

        self.configure_ttk_styles()
        self.build_ui()
        self.refresh_syllable_list()
        self.update_speed_labels()
        self.set_connected_ui(False)
        self.root.after(60, self.process_events)

    def configure_ttk_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Safe.Horizontal.TProgressbar",
            troughcolor=PANEL2,
            background=GREEN,
            bordercolor=BORDER,
            lightcolor=GREEN,
            darkcolor=GREEN,
            thickness=16,
        )
        style.configure(
            "Syllable.TCombobox",
            fieldbackground="#e7eef9",
            background=PANEL2,
            foreground="#172033",
        )

    def label(self, parent, text, size=11, fg=TEXT, bold=False, **kw):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=fg,
            bg=kw.pop("bg", PANEL),
            **kw,
        )

    def button(self, parent, text, command, bg=BLUE, fg=BG, padx=12, pady=7, **kw):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=GREEN,
            activeforeground=BG,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=padx,
            pady=pady,
            **kw,
        )

    def build_ui(self):
        head = tk.Frame(self.root, bg=BG, padx=20, pady=12)
        head.pack(fill="x")
        self.label(
            head,
            "CONTROL OROFACIAL STS3215 · REPRODUCTOR DE SILABAS (4 SERVOS)",
            size=17,
            bold=True,
            bg=BG,
        ).pack(anchor="w")
        self.label(
            head,
            "DER_TOP (ID 5) · DER_BOTTOM (ID 6) · IZQ_TOP (ID 7) · IZQ_BOTTOM (ID 8) · 1,000,000 baudios · Limite de velocidad seguro activo",
            size=10,
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(2, 0))

        toolbar = tk.Frame(self.root, bg=PANEL, padx=15, pady=10, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=20, pady=(0, 10))

        self.label(toolbar, "Puerto:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))
        self.port_entry = tk.Entry(
            toolbar,
            textvariable=self.port_var,
            width=8,
            font=("Segoe UI", 11, "bold"),
            justify="center",
            relief="flat",
            bg="#e7eef9",
            fg="#172033",
        )
        self.port_entry.pack(side="left", padx=(0, 10), ipady=3)

        self.connect_btn = self.button(toolbar, "Conectar", self.connect, bg=GREEN)
        self.connect_btn.pack(side="left", padx=(0, 8))

        self.disc_btn = self.button(toolbar, "Desconectar", self.disconnect, bg=PANEL2, fg=TEXT)
        self.disc_btn.pack(side="left", padx=(0, 8))

        self.ping_btn = self.button(toolbar, "Comprobar 4 Servos", self.ping_servos, bg=BLUE)
        self.ping_btn.pack(side="left", padx=(0, 8))

        self.home_btn = self.button(toolbar, "Ir a Neutral 180°", self.go_home, bg=BLUE)
        self.home_btn.pack(side="left", padx=(0, 8))

        self.monitor_btn = self.button(toolbar, "Monitor en Vivo (OFF)", self.toggle_monitor, bg=PANEL2, fg=TEXT)
        self.monitor_btn.pack(side="left", padx=(0, 8))

        self.center_btn = self.button(toolbar, "Calibrar 180° Aqui", self.calibrate_center, bg=WARN, fg=BG)
        self.center_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = self.button(
            toolbar,
            "PARO / Liberar Torque",
            self.emergency_stop,
            bg="#9e2a3b",
            fg="#ffffff",
        )
        self.stop_btn.pack(side="right")

        scroll_container = tk.Frame(self.root, bg=BG)
        scroll_container.pack(fill="both", expand=True, padx=20)
        canvas = tk.Canvas(scroll_container, bg=BG, highlightthickness=0, borderwidth=0)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

        self.build_syllable_panel(content)

        grid_frame = tk.Frame(content, bg=BG)
        grid_frame.pack(fill="both", expand=True, pady=(6, 6))
        grid_frame.grid_columnconfigure(0, weight=1, uniform="servos")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="servos")

        for idx, name in enumerate(SERVO_ORDER):
            self.build_servo_card(grid_frame, idx, name, SERVO_CONFIG[name])

        note = self.label(
            self.root,
            "SEGURIDAD ACTIVA: La velocidad de reproduccion nunca supera 1.00x (velocidad humana real) y la velocidad fisica "
            "de cada servo se limita automaticamente al tope seguro (max 1500 pasos/s, aceleracion <= 100). "
            "Usa primero 0.33x (3x mas lento) para verificar que el mecanismo tenga libre recorrido antes de subir a 1.00x.",
            bg=BG,
            fg=MUTED,
            size=9,
            wraplength=1140,
            justify="left",
        )
        note.pack(fill="x", padx=22, pady=(4, 5))

        tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg="#263550",
            fg="#f6f9ff",
            font=("Segoe UI", 10),
            padx=17,
            pady=9,
        ).pack(side="bottom", fill="x")

    def build_syllable_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL, padx=16, pady=14, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="x", pady=(0, 8))

        top_row = tk.Frame(panel, bg=PANEL)
        top_row.pack(fill="x")

        self.label(top_row, "REPRODUCCION DE SILABA", size=13, bold=True).pack(side="left", padx=(0, 16))
        self.label(top_row, "Silaba:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))

        self.syl_combo = ttk.Combobox(
            top_row,
            textvariable=self.selected_syllable,
            state="readonly",
            width=18,
            font=("Segoe UI", 11, "bold"),
            style="Syllable.TCombobox",
        )
        self.syl_combo.pack(side="left", padx=(0, 10))
        self.syl_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_syllable_selected())

        self.button(top_row, "Carpeta...", self.choose_folder, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 6))
        self.button(top_row, "CSV...", self.choose_csv_file, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 6))
        self.button(top_row, "Recargar", self.refresh_syllable_list, bg=PANEL2, fg=TEXT).pack(side="left")

        tk.Checkbutton(
            top_row,
            text="Guardar CSV de feedback (_4servo_feedback.csv)",
            variable=self.save_log_var,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=PANEL2,
            highlightthickness=0,
            font=("Segoe UI", 9),
        ).pack(side="right")

        self.quick_syl_frame = tk.Frame(panel, bg=PANEL)
        self.quick_syl_frame.pack(fill="x", pady=(8, 4))

        self.label(panel, "", size=9, fg=GREEN, textvariable=self.csv_info_var).pack(anchor="w", pady=(2, 8))

        sliders_row = tk.Frame(panel, bg=PANEL)
        sliders_row.pack(fill="x", pady=(2, 8))
        sliders_row.grid_columnconfigure(0, weight=3)
        sliders_row.grid_columnconfigure(1, weight=2)

        speed_box = tk.Frame(sliders_row, bg=PANEL2, padx=12, pady=10)
        speed_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        spd_top = tk.Frame(speed_box, bg=PANEL2)
        spd_top.pack(fill="x")
        self.label(spd_top, "Velocidad de Reproduccion (Segura: 0.20x a 1.00x Max)", size=10, bold=True, bg=PANEL2).pack(side="left")
        tk.Label(
            spd_top,
            textvariable=self.speed_label_var,
            font=("Segoe UI", 10, "bold"),
            bg=PANEL2,
            fg=GREEN,
        ).pack(side="right")

        self.speed_slider = tk.Scale(
            speed_box,
            from_=MIN_SPEED_MULT,
            to=MAX_SAFE_SPEED_MULT,
            resolution=0.01,
            orient="horizontal",
            variable=self.speed_mult_var,
            showvalue=False,
            sliderlength=20,
            bg=PANEL2,
            fg=TEXT,
            troughcolor="#384d6c",
            highlightthickness=0,
            activebackground=GREEN,
            command=lambda _v: self.update_speed_labels(),
        )
        self.speed_slider.pack(fill="x", pady=(6, 6))

        presets = tk.Frame(speed_box, bg=PANEL2)
        presets.pack(fill="x")
        self.label(presets, "Preajustes:", size=9, fg=MUTED, bg=PANEL2).pack(side="left", padx=(0, 6))
        for mult, title in (
            (0.25, "0.25x (4x Lento)"),
            (0.33, "0.33x (3x Lento · Seguro)"),
            (0.50, "0.50x (Media)"),
            (0.75, "0.75x"),
            (1.00, "1.00x (Tiempo Real Max)"),
        ):
            self.button(
                presets,
                title,
                lambda m=mult: self.set_speed_preset(m),
                bg=PANEL,
                fg=TEXT,
                padx=8,
                pady=3,
            ).pack(side="left", padx=(0, 5))

        cap_box = tk.Frame(sliders_row, bg=PANEL2, padx=12, pady=10)
        cap_box.grid(row=0, column=1, sticky="nsew")

        cap_top = tk.Frame(cap_box, bg=PANEL2)
        cap_top.pack(fill="x")
        self.label(cap_top, "Tope Max. Motor (Proteccion Hardware)", size=10, bold=True, bg=PANEL2).pack(side="left")
        tk.Label(
            cap_top,
            textvariable=self.max_steps_label_var,
            font=("Segoe UI", 10, "bold"),
            bg=PANEL2,
            fg=WARN,
        ).pack(side="right")

        self.cap_slider = tk.Scale(
            cap_box,
            from_=300,
            to=SAFE_HARD_LIMIT_STEP,
            resolution=50,
            orient="horizontal",
            variable=self.max_steps_var,
            showvalue=False,
            sliderlength=20,
            bg=PANEL2,
            fg=TEXT,
            troughcolor="#384d6c",
            highlightthickness=0,
            activebackground=WARN,
            command=lambda _v: self.update_speed_labels(),
        )
        self.cap_slider.pack(fill="x", pady=(6, 6))
        self.label(
            cap_box,
            f"Limita picos del CSV a <= {SAFE_HARD_LIMIT_STEP} pasos/s (~132°/s) y acc <= {SAFE_MAX_ACC_UNIT}.",
            size=9,
            fg=MUTED,
            bg=PANEL2,
        ).pack(anchor="w")

        play_row = tk.Frame(panel, bg=PANEL)
        play_row.pack(fill="x", pady=(4, 0))

        self.play_btn = self.button(
            play_row,
            "▶ REPRODUCIR SILABA SELECCIONADA",
            self.play_selected_syllable,
            bg=GREEN,
            fg=BG,
            padx=18,
            pady=9,
        )
        self.play_btn.pack(side="left", padx=(0, 14))

        prog_frame = tk.Frame(play_row, bg=PANEL)
        prog_frame.pack(side="left", fill="x", expand=True)
        tk.Label(
            prog_frame,
            textvariable=self.progress_text_var,
            font=("Segoe UI", 9, "bold"),
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(fill="x")
        self.progress_bar = ttk.Progressbar(
            prog_frame,
            variable=self.progress_var,
            maximum=100.0,
            style="Safe.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill="x", pady=(3, 0))

    def build_servo_card(self, parent, index: int, name: str, cfg: dict):
        box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)

        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x")
        dir_str = "+1" if cfg["dir"] > 0 else "-1"
        self.label(top, f"{name}  ·  ID {cfg['id']}", size=12, bold=True).pack(side="left")
        self.label(top, f"({cfg['label']} · dir {dir_str})", size=9, fg=MUTED).pack(side="left", padx=(8, 0))

        real_var = tk.StringVar(value="Real: Sin leer")
        tk.Label(top, textvariable=real_var, font=("Segoe UI", 10, "bold"), bg=PANEL, fg=GREEN).pack(side="right")

        tele_frame = tk.Frame(box, bg=PANEL2, padx=10, pady=7)
        tele_frame.pack(fill="x", pady=(8, 8))

        cmd_var = tk.StringVar(value="Objetivo CSV: —")
        dtheta_var = tk.StringVar(value="Δθ Real: —")
        tk.Label(tele_frame, textvariable=cmd_var, font=("Segoe UI", 9), bg=PANEL2, fg=MUTED).pack(side="left")
        tk.Label(tele_frame, textvariable=dtheta_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=BLUE).pack(side="right")

        ctrl_top = tk.Frame(box, bg=PANEL)
        ctrl_top.pack(fill="x")
        self.label(ctrl_top, "Ajuste manual seguro (120° a 240°):", size=9, fg=MUTED).pack(side="left")
        angle_var = tk.StringVar(value="180.0")
        angle_entry = tk.Entry(
            ctrl_top,
            textvariable=angle_var,
            width=7,
            font=("Segoe UI", 10, "bold"),
            justify="center",
            relief="flat",
            bg="#e7eef9",
            fg="#172033",
        )
        angle_entry.pack(side="right")
        angle_entry.bind("<Return>", lambda _e, n=name: self.move_single_servo(n))

        slider = tk.Scale(
            box,
            from_=120,
            to=240,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            sliderlength=16,
            bg=PANEL,
            fg=TEXT,
            troughcolor="#384d6c",
            highlightthickness=0,
            activebackground=BLUE,
            command=lambda val, v=angle_var: v.set(f"{float(val):.1f}"),
        )
        slider.set(180)
        slider.pack(fill="x", pady=(4, 6))
        slider.bind("<ButtonRelease-1>", lambda _e, n=name: self.move_single_servo(n))

        btn_row = tk.Frame(box, bg=PANEL)
        btn_row.pack(fill="x")
        self.button(btn_row, "-5°", lambda n=name: self.nudge_servo(n, -5.0), bg=PANEL2, fg=TEXT, padx=10, pady=4).pack(
            side="left", padx=(0, 5)
        )
        self.button(btn_row, "+5°", lambda n=name: self.nudge_servo(n, 5.0), bg=PANEL2, fg=TEXT, padx=10, pady=4).pack(
            side="left", padx=(0, 5)
        )
        self.button(btn_row, "180° Neutral", lambda n=name: self.set_and_move_servo(n, 180.0), bg=PANEL2, fg=TEXT, padx=10, pady=4).pack(
            side="left", padx=(0, 5)
        )
        self.button(btn_row, "Mover", lambda n=name: self.move_single_servo(n), bg=BLUE, fg=BG, padx=10, pady=4).pack(
            side="left", padx=(0, 5)
        )
        self.button(btn_row, "Leer", self.read_once, bg=PANEL2, fg=TEXT, padx=10, pady=4).pack(side="right")

        self.servo_cards[name] = {
            "real_var": real_var,
            "cmd_var": cmd_var,
            "dtheta_var": dtheta_var,
            "angle_var": angle_var,
            "slider": slider,
        }

    def set_speed_preset(self, mult: float):
        self.speed_mult_var.set(round(float(np.clip(mult, MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT)), 2))
        self.update_speed_labels()

    def get_time_scale(self) -> float:
        mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
        return 1.0 / mult

    def update_speed_labels(self):
        mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
        time_scale = 1.0 / mult
        pct = round(mult * 100)
        self.speed_label_var.set(f"{mult:.2f}x ({pct}%)  ·  time_scale = {time_scale:.2f}x")

        cap = int(np.clip(self.max_steps_var.get(), 300, SAFE_HARD_LIMIT_STEP))
        deg_s = cap / STEPS_PER_DEG
        self.max_steps_label_var.set(f"{cap} pasos/s (~{deg_s:.0f}°/s)")
        self.update_csv_summary()

    def refresh_syllable_list(self):
        self.syllable_files.clear()
        script_dir = Path(__file__).resolve().parent
        search_dirs = [
            self.traj_dir,
            script_dir / DEFAULT_TRAJ_DIR,
            script_dir.parent / DEFAULT_TRAJ_DIR,
            Path.cwd() / DEFAULT_TRAJ_DIR,
            script_dir,
            Path.cwd(),
        ]
        found_paths = []
        for folder in search_dirs:
            if folder.exists() and folder.is_dir():
                matches = sorted(folder.glob("servo_trajectory_*.csv"))
                if matches:
                    found_paths.extend(matches)
                    self.traj_dir = folder
                    break

        for path in found_paths:
            if "_feedback" in path.stem:
                continue
            syl = extract_syllable_name(path)
            self.syllable_files[syl] = path.resolve()

        for widget in self.quick_syl_frame.winfo_children():
            widget.destroy()
        self.quick_syl_buttons.clear()

        syl_names = sorted(self.syllable_files.keys())
        self.syl_combo["values"] = syl_names

        if syl_names:
            self.label(self.quick_syl_frame, "Acceso rapido:", size=9, fg=MUTED).pack(side="left", padx=(0, 6))
            for syl in syl_names:
                btn = self.button(
                    self.quick_syl_frame,
                    syl,
                    lambda s=syl: self.select_syllable_by_name(s),
                    bg=PANEL2,
                    fg=TEXT,
                    padx=10,
                    pady=3,
                )
                btn.pack(side="left", padx=(0, 5))
                self.quick_syl_buttons.append(btn)

            if self.selected_syllable.get() not in self.syllable_files:
                self.selected_syllable.set(syl_names[0])
            self.on_syllable_selected()
        else:
            self.selected_syllable.set("")
            self.csv_info_var.set(
                "No se encontraron archivos 'servo_trajectory_*.csv' automaticamente. Usa 'Carpeta...' o 'CSV...'."
            )

    def select_syllable_by_name(self, syl: str):
        self.selected_syllable.set(syl)
        self.on_syllable_selected()

    def on_syllable_selected(self):
        self.update_csv_summary()

    def update_csv_summary(self):
        syl = self.selected_syllable.get()
        path = self.syllable_files.get(syl)
        if not path or not path.exists():
            return
        try:
            df = pd.read_csv(path)
            base_ms = float(df["time_ms"].iloc[-1])
            time_scale = self.get_time_scale()
            scaled_ms = base_ms * time_scale
            self.csv_info_var.set(
                f"Archivo: {path.name}  |  Pasos: {len(df)}  |  Duracion base (1.0x): {base_ms:.0f} ms  |  "
                f"Duracion a velocidad actual: {scaled_ms:.0f} ms ({scaled_ms / 1000.0:.2f} s)"
            )
        except Exception as exc:
            self.csv_info_var.set(f"Error al leer {path.name}: {exc}")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta con servo_trajectory_*.csv")
        if folder:
            self.traj_dir = Path(folder)
            self.refresh_syllable_list()

    def choose_csv_file(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo CSV de trayectoria",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if file_path:
            path = Path(file_path).resolve()
            syl = extract_syllable_name(path)
            self.syllable_files[syl] = path
            self.syl_combo["values"] = sorted(self.syllable_files.keys())
            self.selected_syllable.set(syl)
            self.on_syllable_selected()

    def set_connected_ui(self, connected: bool):
        self.connected = connected
        self.connect_btn.config(state="disabled" if connected else "normal")
        self.port_entry.config(state="disabled" if connected else "normal")
        state = "normal" if connected else "disabled"
        for btn in (
            self.disc_btn,
            self.ping_btn,
            self.home_btn,
            self.monitor_btn,
            self.center_btn,
            self.stop_btn,
            self.play_btn,
        ):
            btn.config(state=state)

    def connect(self):
        if self.connected or (self.worker and self.worker.is_alive()):
            return
        com = self.port_var.get().strip()
        if not com:
            messagebox.showwarning("Puerto vacio", "Escribe el puerto COM (ej. COM4 o COM3).")
            return
        self.commands = queue.Queue()
        self.stop_event.clear()
        self.worker = ServoWorker(com, self.commands, self.events, self.stop_event)
        self.status_var.set(f"Conectando a {com} a {BAUDRATE} baudios...")
        self.connect_btn.config(state="disabled")
        self.worker.start()

    def disconnect(self):
        if self.worker and self.worker.is_alive():
            self.stop_event.set()
            self.status_var.set("Desconectando y liberando torque...")
            self.commands.put(("disconnect",))
            self.disc_btn.config(state="disabled")

    def ping_servos(self):
        if self.connected and not self.playing:
            self.commands.put(("ping_all", SERVO_CONFIG))

    def read_once(self):
        if self.connected and not self.playing:
            self.commands.put(("read_once", SERVO_CONFIG))

    def go_home(self):
        if not self.connected:
            return
        if self.playing:
            messagebox.showinfo("En reproduccion", "Deten la silaba actual antes de ir a Neutral.")
            return
        self.commands.put(("go_home", SERVO_CONFIG, int(self.max_steps_var.get())))

    def toggle_monitor(self):
        if not self.connected or self.playing:
            return
        self.commands.put(("set_monitor", not self.monitoring, SERVO_CONFIG))

    def calibrate_center(self):
        if not self.connected or self.playing:
            return
        ok = messagebox.askyesno(
            "Confirmar Calibracion de Centro 180.0°",
            "¿Deseas fijar la posicion fisica ACTUAL de los 4 servos (IDs 5, 6, 7, 8) "
            "como el centro neutral 180.0° (2048 ticks)?\n\n"
            "Asegurate de que las palancas esten fisicamente alineadas en su posicion neutral antes de confirmar.",
        )
        if ok:
            self.commands.put(("set_center", SERVO_CONFIG))

    def emergency_stop(self):
        if not self.connected:
            return
        self.stop_event.set()
        self.commands.put(("release", SERVO_CONFIG))

    def set_and_move_servo(self, name: str, deg: float):
        card = self.servo_cards[name]
        card["angle_var"].set(f"{deg:.1f}")
        card["slider"].set(round(deg))
        self.move_single_servo(name)

    def nudge_servo(self, name: str, delta: float):
        card = self.servo_cards[name]
        try:
            curr = float(card["angle_var"].get().replace(",", "."))
        except ValueError:
            curr = 180.0
        target = float(np.clip(curr + delta, 120.0, 240.0))
        self.set_and_move_servo(name, target)

    def move_single_servo(self, name: str):
        if not self.connected or self.playing:
            return
        card = self.servo_cards[name]
        try:
            deg = float(card["angle_var"].get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Angulo invalido", f"Escribe un angulo numerico para {name}.")
            return
        deg = float(np.clip(deg, 120.0, 240.0))
        card["angle_var"].set(f"{deg:.1f}")
        card["slider"].set(round(deg))
        self.commands.put(("move_single", SERVO_CONFIG, name, deg, int(self.max_steps_var.get())))

    def play_selected_syllable(self):
        if not self.connected:
            messagebox.showwarning("Sin conexion", "Conecta primero el puerto serie.")
            return
        if self.playing:
            return
        syl = self.selected_syllable.get()
        csv_path = self.syllable_files.get(syl)
        if not csv_path or not csv_path.exists():
            messagebox.showwarning("Sin archivo CSV", "Selecciona una silaba valida o carga un archivo CSV.")
            return

        time_scale = self.get_time_scale()
        max_speed_cap = int(np.clip(self.max_steps_var.get(), MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
        self.playing = True
        self.play_btn.config(state="disabled")
        self.progress_var.set(0.0)
        self.commands.put(
            ("play_csv", csv_path, time_scale, max_speed_cap, self.save_log_var.get(), SERVO_CONFIG)
        )

    def update_servo_cards_from_readings(self, readings: dict):
        for name, info in readings.items():
            card = self.servo_cards.get(name)
            if not card:
                continue
            if info.get("ok"):
                deg = info["deg"]
                ticks = info["ticks"]
                dtheta = info["dtheta"]
                card["real_var"].set(f"Real: {deg:5.1f}° [{ticks:4d}]")
                card["dtheta_var"].set(f"Δθ Real: {dtheta:+5.1f}°")
                if not self.playing:
                    card["angle_var"].set(f"{deg:.1f}")
                    card["slider"].set(int(np.clip(round(deg), 120, 240)))
            else:
                card["real_var"].set("SIN RESPUESTA")
                card["dtheta_var"].set("Δθ Real: OFF")

    def process_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            kind = event[0]
            if kind == "connected":
                com = event[1]
                self.set_connected_ui(True)
                self.status_var.set(f"Puerto {com} conectado. Comprobando los 4 servos (IDs 5, 6, 7, 8)...")
                self.ping_servos()

            elif kind == "disconnected":
                self.playing = False
                self.monitoring = False
                self.set_connected_ui(False)
                self.monitor_btn.config(text="Monitor en Vivo (OFF)", bg=PANEL2, fg=TEXT)
                self.worker = None
                self.status_var.set("Puerto serie desconectado y torque liberado.")
                if self.closing:
                    self.root.destroy()
                    return

            elif kind == "ping_result":
                status = event[1]
                self.update_servo_cards_from_readings(status)
                ok_count = sum(1 for v in status.values() if v.get("ok"))
                self.status_var.set(f"Comprobacion completada: {ok_count} de 4 servos responden (IDs 5, 6, 7, 8).")

            elif kind == "positions":
                self.update_servo_cards_from_readings(event[1])

            elif kind == "monitor_state":
                self.monitoring = event[1]
                if self.monitoring:
                    self.monitor_btn.config(text="Monitor en Vivo (ACTIVO)", bg=GREEN, fg=BG)
                else:
                    self.monitor_btn.config(text="Monitor en Vivo (OFF)", bg=PANEL2, fg=TEXT)

            elif kind == "center_calibrated":
                results = event[1]
                lines = []
                for name, sid, ok, pos in results:
                    if ok:
                        lines.append(f"[OK] {name} (ID {sid}) -> {ticks_to_servo_deg(pos):.1f}° ({pos} ticks)")
                    else:
                        lines.append(f"[ERROR] {name} (ID {sid}) no respondio.")
                messagebox.showinfo("Calibracion 180.0°", "\n".join(lines))
                self.status_var.set("Calibracion de centro 180.0° finalizada.")

            elif kind == "playback_started":
                _, syl_name, total_steps, time_scale, total_ms = event
                mult = 1.0 / time_scale
                self.progress_var.set(0.0)
                self.progress_text_var.set(
                    f"Posicionando al inicio de '{syl_name}'... ({total_steps} pasos | {mult:.2f}x | {total_ms:.0f} ms)"
                )
                self.status_var.set(f"Reproduciendo silaba '{syl_name}' a {mult:.2f}x (time_scale={time_scale:.2f}x)...")

            elif kind == "playback_step":
                _, phase_pct, step_idx, total_steps, cmd_snap, meas_snap = event
                self.progress_var.set(phase_pct)
                self.progress_text_var.set(f"Fase: {phase_pct:5.1f}%  (Paso {step_idx}/{total_steps})")
                for name, cinfo in cmd_snap.items():
                    card = self.servo_cards.get(name)
                    if card:
                        card["cmd_var"].set(
                            f"Cmd: {cinfo['cmd_deg']:5.1f}° [{cinfo['cmd_ticks']:4d}] · Vel: {cinfo['cmd_speed']} st/s"
                        )
                self.update_servo_cards_from_readings(meas_snap)

            elif kind == "playback_finished":
                _, syl_name, elapsed_ms, out_csv_msg = event
                self.playing = False
                if self.connected:
                    self.play_btn.config(state="normal")
                self.progress_var.set(100.0)
                self.progress_text_var.set(f"Completado: 100% ({elapsed_ms:.0f} ms)")
                self.status_var.set(f"Silaba '{syl_name}' reproducida en {elapsed_ms:.1f} ms{out_csv_msg}")

            elif kind == "playback_stopped":
                msg = event[1]
                self.playing = False
                if self.connected:
                    self.play_btn.config(state="normal")
                self.progress_text_var.set("Reproduccion detenida por el usuario")
                self.status_var.set(msg)

            elif kind == "info":
                self.status_var.set(event[1])

            elif kind == "error":
                self.playing = False
                if self.connected:
                    self.play_btn.config(state="normal")
                self.status_var.set("ERROR: " + event[1])
                messagebox.showerror("Error", event[1])

        self.root.after(60, self.process_events)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.disconnect()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SyllableServoGUI(root)
    root.mainloop()