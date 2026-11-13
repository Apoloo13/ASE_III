# # -*- coding: utf-8 -*-
# """Unified 8-Servo GUI Controller & Trajectory Comparator for FEETECH STS3215-12V.

# Controls all 8 servos of the Orofacial Robotic Simulator:
#     - Corner 5-Bar Mechanisms: DER_TOP (ID 5), DER_BOTTOM (ID 6), IZQ_TOP (ID 7), IZQ_BOTTOM (ID 8)
#     - Chin / Jaw Mechanism:    JAW_LEFT (ID 1), JAW_RIGHT (ID 2)
#     - Upper Lip 3-Link Piston: UP_PISTON (ID 9)
#     - Lower Lip Rack & Pinion: LOW_RACK (ID 10)

# Features:
#     - Compatible with both `sms_sts` and `sts` in `scservo_sdk` / `ftservo-python-sdk`
#     - Group toggles to drive all 8 servos or isolate specific mechanisms
#     - Records real encoder feedback during movement, reconstructs the achieved anatomical
#       landmark trajectories (`BOCA_DER`, `BOCA_IZQ`, `BOCA_SUP_EXT`, `BOCA_INF_EXT`, `BARBILLA`)
#       via Forward Kinematics in dimensionless eye-distance units, and exports `robot_measured_<SYL>.csv`
#     - Built-in interactive plotter (matching `orofacial_analysis.py` conventions: inverted Y axis,
#       ±1 SD shaded human cohort band, black dashed `--` robot curve, and RMSE/MAE error metrics)
# """
# from __future__ import annotations

# import json
# import queue
# import re
# import threading
# import time
# import tkinter as tk
# from pathlib import Path
# from tkinter import filedialog, messagebox, ttk

# import matplotlib.pyplot as plt
# import numpy as np
# import pandas as pd

# try:
#     import scservo_sdk as scs
#     from scservo_sdk import COMM_SUCCESS, PortHandler
#     if hasattr(scs, "sms_sts"):
#         STSDriver = scs.sms_sts
#     elif hasattr(scs, "sts"):
#         STSDriver = scs.sts
#     else:
#         raise ImportError("No se encontro 'sms_sts' ni 'sts' en scservo_sdk.")
#     try:
#         from scservo_sdk import GroupSyncWrite
#     except ImportError:
#         GroupSyncWrite = None
# except ImportError as exc:
#     raise SystemExit(
#         f"Error de importacion: {exc}\n"
#         "Instala con: python -m pip install ftservo-python-sdk pyserial numpy pandas matplotlib"
#     ) from exc


# # ==============================================================================
# # 1. REGISTROS STS3215, CONFIGURACION DE 8 SERVOS Y PARAMETROS CINEMATICOS
# # ==============================================================================
# ADDR_SCS_TORQUE_ENABLE    = 40
# ADDR_STS_GOAL_ACC         = 41
# ADDR_STS_GOAL_POSITION    = 42
# ADDR_STS_GOAL_SPEED       = 46
# ADDR_STS_LOCK             = 55
# ADDR_STS_PRESENT_POSITION = 56

# DEFAULT_COM   = "COM4"
# BAUDRATE      = 1000000
# STEPS_PER_DEG = 4096.0 / 360.0  # 11.37778 ticks/deg
# HOME_TICK_180 = 2048            # 180.0 deg neutral

# MIN_SPEED_STEPS       = 120
# SAFE_DEFAULT_MAX_STEP = 1200    # ~105 deg/s default cap
# SAFE_HARD_LIMIT_STEP  = 1800    # Hardware protection cap
# SAFE_MAX_ACC_UNIT     = 100
# SPEED_HEADROOM        = 1.15

# MIN_SPEED_MULT      = 0.20      # 5x slow motion
# MAX_SAFE_SPEED_MULT = 1.00      # 1.0x real-time human speed
# DEFAULT_SPEED_MULT  = 0.33      # 3x slow motion default for initial safety check

# DEFAULT_TRAJ_DIR = Path("orofacial_results/mouth_trajectories")
# FALLBACK_CORNER_DIR = Path("orofacial_results/servo_trajectories")
# FALLBACK_CENTER_DIR = Path("orofacial_results/center_lips_trajectories")

# SERVO_ORDER = (
#     "DER_TOP", "IZQ_TOP",
#     "DER_BOTTOM", "IZQ_BOTTOM",
#     "JAW_LEFT", "JAW_RIGHT",
#     "UP_PISTON", "LOW_RACK",
# )

# SERVO_CONFIG = {
#     "DER_TOP": {
#         "id": 5, "group": "corners", "label": "Esquina Der. Sup (5-Barras)",
#         "home_tick": 2048, "dir": -1, "min_tick": 1138, "max_tick": 2958,
#         "min_deg": 100.0, "max_deg": 260.0,
#         "dtheta_col": "DER_dtheta1_from_90_deg",
#         "omega_col":  "DER_omega1_speed_degs",
#         "alpha_col":  "DER_alpha1_accel_degs2",
#     },
#     "DER_BOTTOM": {
#         "id": 6, "group": "corners", "label": "Esquina Der. Inf (5-Barras)",
#         "home_tick": 2048, "dir": -1, "min_tick": 1138, "max_tick": 2958,
#         "min_deg": 100.0, "max_deg": 260.0,
#         "dtheta_col": "DER_dtheta2_from_neg90_deg",
#         "omega_col":  "DER_omega2_speed_degs",
#         "alpha_col":  "DER_alpha2_accel_degs2",
#     },
#     "IZQ_TOP": {
#         "id": 7, "group": "corners", "label": "Esquina Izq. Sup (5-Barras)",
#         "home_tick": 2048, "dir": +1, "min_tick": 1138, "max_tick": 2958,
#         "min_deg": 100.0, "max_deg": 260.0,
#         "dtheta_col": "IZQ_dtheta1_from_90_deg",
#         "omega_col":  "IZQ_omega1_speed_degs",
#         "alpha_col":  "IZQ_alpha1_accel_degs2",
#     },
#     "IZQ_BOTTOM": {
#         "id": 8, "group": "corners", "label": "Esquina Izq. Inf (5-Barras)",
#         "home_tick": 2048, "dir": +1, "min_tick": 1138, "max_tick": 2958,
#         "min_deg": 100.0, "max_deg": 260.0,
#         "dtheta_col": "IZQ_dtheta2_from_neg90_deg",
#         "omega_col":  "IZQ_omega2_speed_degs",
#         "alpha_col":  "IZQ_alpha2_accel_degs2",
#     },
#     "JAW_LEFT": {
#         "id": 1, "group": "jaw", "label": "Mandibula Izq. (180°->195°)",
#         "home_tick": 2048, "dir": +1, "min_tick": 2048, "max_tick": 2219,
#         "min_deg": 180.0, "max_deg": 195.0,
#         "dtheta_col": "JAW_dtheta_deg",
#         "omega_col":  "JAW_omega_speed_degs",
#         "alpha_col":  "JAW_alpha_accel_degs2",
#     },
#     "JAW_RIGHT": {
#         "id": 2, "group": "jaw", "label": "Mandibula Der. (180°->165°)",
#         "home_tick": 2048, "dir": -1, "min_tick": 1877, "max_tick": 2048,
#         "min_deg": 165.0, "max_deg": 180.0,
#         "dtheta_col": "JAW_dtheta_deg",
#         "omega_col":  "JAW_omega_speed_degs",
#         "alpha_col":  "JAW_alpha_accel_degs2",
#     },
#     "UP_PISTON": {
#         "id": 9, "group": "upper", "label": "Labio Sup. Piston (180°->140°)",
#         "home_tick": 2048, "dir": -1, "min_tick": 1593, "max_tick": 2048,
#         "min_deg": 140.0, "max_deg": 180.0,
#         "dtheta_col": "UP_dtheta_deg",
#         "omega_col":  "UP_omega_speed_degs",
#         "alpha_col":  "UP_alpha_accel_degs2",
#     },
#     "LOW_RACK": {
#         "id": 10, "group": "rack", "label": "Labio Inf. Cremallera (81°..150°)",
#         "home_tick": 1422, "dir": +1, "min_tick": 922, "max_tick": 1707,
#         "min_deg": 81.0, "max_deg": 150.0,
#         "dtheta_col": "LOW_dtheta_deg",
#         "omega_col":  "LOW_omega_speed_degs",
#         "alpha_col":  "LOW_alpha_accel_degs2",
#     },
# }

# # Default Forward-Kinematics parameters (overridden automatically if active_mechanism_params.json exists)
# DEFAULT_FK_PARAMS = {
#     "eye_corner_scale_mm": 35.0,
#     "L0": 24.80, "L1": 23.50, "L2": 23.50, "L3": 100.97, "L4": 63.31,
#     "psi_deg": 71.00, "alpha_deg": 8.44,
#     "jaw_radius_mm": 35.0 / np.sin(np.radians(15.0)),
#     "pinion_pitch_diam_mm": 22.10, "rack_tilt_deg": 12.50, "low_gain": 1.0,
#     "up_L1": 33.24, "up_L2": 46.14, "up_L3": 43.50, "up_theta0_deg": 45.0,
#     "up_offset_x": 19.00, "up_gain": 3.0,
# }

# POINT_OPTIONS = [
#     ("ALL_5", "TODOS (Panel 5 Puntos Actuados: XY + Tiempo)"),
#     ("BOCA_DER", "BOCA_DER · Right mouth corner (291) [Esquina Der. IDs 5,6]"),
#     ("BOCA_IZQ", "BOCA_IZQ · Left mouth corner (61) [Esquina Izq. IDs 7,8]"),
#     ("BOCA_SUP_EXT", "BOCA_SUP_EXT · Upper outer lip (0) [Piston Sup. ID 9]"),
#     ("BOCA_INF_EXT", "BOCA_INF_EXT · Lower outer lip (17) [Cremallera ID 10 + Mandibula]"),
#     ("BARBILLA", "BARBILLA · Chin (152) [Mandibula IDs 1,2]"),
#     ("SERVOS_8", "SERVOS · Angulo Comando vs Real Medido (8 Motores)"),
# ]

# POINT_LABELS = {
#     "BOCA_SUP_EXT": "Upper outer lip (0)",
#     "BOCA_INF_EXT": "Lower outer lip (17)",
#     "BOCA_IZQ": "Left mouth corner (61)",
#     "BOCA_DER": "Right mouth corner (291)",
#     "BARBILLA": "Chin (152)",
# }
# POINT_COLORS = {
#     "BOCA_SUP_EXT": "#1f77b4",
#     "BOCA_INF_EXT": "#ff7f0e",
#     "BOCA_IZQ": "#9467bd",
#     "BOCA_DER": "#8c564b",
#     "BARBILLA": "#e377c2",
# }

# BG     = "#0d1524"
# PANEL  = "#182338"
# PANEL2 = "#202f48"
# TEXT   = "#eaf1fb"
# MUTED  = "#a6b6cf"
# BLUE   = "#4ea8ff"
# GREEN  = "#49d9ac"
# WARN   = "#e6bb68"
# DANGER = "#f29aa2"
# BORDER = "#30415b"


# # ==============================================================================
# # 2. CONVERSIONES Y CINEMATICA DIRECTA (FORWARD KINEMATICS PARA VALIDACION)
# # ==============================================================================
# def scs_lobyte(val: int) -> int:
#     return int(val) & 0xFF


# def scs_hibyte(val: int) -> int:
#     return (int(val) >> 8) & 0xFF


# def ticks_to_servo_deg(ticks: int) -> float:
#     return float(ticks / STEPS_PER_DEG)


# def servo_deg_to_ticks(deg: float, cfg: dict | None = None) -> int:
#     raw = round(float(deg) * STEPS_PER_DEG)
#     if cfg is not None:
#         return int(np.clip(raw, cfg["min_tick"], cfg["max_tick"]))
#     return int(np.clip(raw, 50, 4045))


# def dtheta_to_ticks(dtheta_deg: float, cfg: dict) -> int:
#     ticks = round(cfg["home_tick"] + cfg["dir"] * dtheta_deg * STEPS_PER_DEG)
#     return int(np.clip(ticks, cfg["min_tick"], cfg["max_tick"]))


# def dtheta_to_servo_deg(dtheta_deg: float, cfg: dict) -> float:
#     return ticks_to_servo_deg(dtheta_to_ticks(dtheta_deg, cfg))


# def ticks_to_dtheta_deg(ticks: int, cfg: dict) -> float:
#     return float((ticks - cfg["home_tick"]) * cfg["dir"] / STEPS_PER_DEG)


# def safe_speed_degs_to_steps(omega_degs: float, time_scale: float, max_speed_cap: int) -> int:
#     safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
#     steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
#     return int(np.clip(steps_s, MIN_SPEED_STEPS, safe_cap))


# def safe_accel_degs2_to_unit(alpha_degs2: float, time_scale: float) -> int:
#     acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
#     return int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))


# def extract_syllable_name(csv_path: Path) -> str:
#     for prefix in ("mouth_trajectory_", "servo_trajectory_", "center_lips_trajectory_"):
#         if csv_path.stem.lower().startswith(prefix):
#             return csv_path.stem[len(prefix):].upper()
#     return csv_path.stem.upper()


# def solve_5bar_fk(dtheta1_deg: float, dtheta2_deg: float, side: str, fk: dict) -> tuple[float, float]:
#     """Forward kinematics for the 5-bar linkage: returns frontal (Delta_X, Delta_Y) in eye-distance units."""
#     L0, L1, L2, L3, L4 = fk["L0"], fk["L1"], fk["L2"], fk["L3"], fk["L4"]

#     def get_P(th1_deg: float, th2_deg: float):
#         t1, t2 = np.radians(th1_deg), np.radians(th2_deg)
#         A = np.array([L1 * np.cos(t1), L0 + L1 * np.sin(t1)])
#         B = np.array([L2 * np.cos(t2), L2 * np.sin(t2)])
#         d_vec = B - A
#         d = np.linalg.norm(d_vec)
#         if d <= abs(L3 - L4) or d >= (L3 + L4):
#             return np.array([62.901, -30.684])
#         a = (L3**2 - L4**2 + d**2) / (2.0 * d)
#         h = np.sqrt(max(L3**2 - a**2, 0.0))
#         mid = A + (a / d) * d_vec
#         perp = np.array([-d_vec[1] / d, d_vec[0] / d])
#         P1, P2 = mid + h * perp, mid - h * perp
#         return P1 if P1[0] >= P2[0] else P2

#     P_home = get_P(90.0, -90.0)
#     P_curr = get_P(90.0 + dtheta1_deg, -90.0 + dtheta2_deg)
#     du, dv = P_curr[0] - P_home[0], P_curr[1] - P_home[1]

#     psi = np.radians(fk["psi_deg"])
#     alpha = np.radians(fk["alpha_deg"])
#     du_horiz = du * np.cos(alpha) - dv * np.sin(alpha)
#     dv_vert  = du * np.sin(alpha) + dv * np.cos(alpha)

#     dX_medial = du_horiz * np.cos(psi)
#     dX_front_mm = -dX_medial if side.upper() == "DER" else dX_medial
#     dY_front_mm = dv_vert

#     scale = fk["eye_corner_scale_mm"]
#     return float(dX_front_mm / scale), float(-dY_front_mm / scale)


# def reconstruct_measured_landmarks(df_traj: pd.DataFrame, df_fb: pd.DataFrame, fk: dict) -> pd.DataFrame:
#     """Reconstructs achieved anatomical Delta_X / Delta_Y (in eye-distance units) from measured servo angles."""
#     scale = fk["eye_corner_scale_mm"]
#     n = len(df_fb)
#     out = {"phase_pct": df_fb["phase_pct"].to_numpy(dtype=float)}

#     # 1. BOCA_DER and BOCA_IZQ from 5-bar encoders
#     for side in ("DER", "IZQ"):
#         top_col = f"{side}_TOP_meas_dtheta_deg"
#         bot_col = f"{side}_BOTTOM_meas_dtheta_deg"
#         if top_col in df_fb.columns and bot_col in df_fb.columns and df_fb[top_col].notna().any():
#             dx_list, dy_list = [], []
#             for dt1, dt2 in zip(df_fb[top_col], df_fb[bot_col]):
#                 if np.isfinite(dt1) and np.isfinite(dt2):
#                     dx, dy = solve_5bar_fk(float(dt1), float(dt2), side, fk)
#                 else:
#                     dx, dy = np.nan, np.nan
#                 dx_list.append(dx)
#                 dy_list.append(dy)
#             out[f"BOCA_{side}_Delta_X"] = np.array(dx_list)
#             out[f"BOCA_{side}_Delta_Y"] = np.array(dy_list)

#     # 2. BARBILLA from Jaw encoders (ID 1 & ID 2)
#     jaw_cols = [c for c in ("JAW_LEFT_meas_dtheta_deg", "JAW_RIGHT_meas_dtheta_deg") if c in df_fb.columns]
#     if jaw_cols and df_fb[jaw_cols].notna().any().any():
#         dtheta_jaw = df_fb[jaw_cols].mean(axis=1).to_numpy(dtype=float)
#         opening_mm = fk["jaw_radius_mm"] * np.sin(np.radians(np.clip(dtheta_jaw, 0.0, 20.0)))
#         out["BARBILLA_Delta_X"] = np.zeros(n)
#         out["BARBILLA_Delta_Y"] = opening_mm / scale  # +Y is downward
#         dy_jaw_ach_mm = -opening_mm
#     else:
#         dy_jaw_ach_mm = df_traj["JAW_dy_achieved_mm"].to_numpy(dtype=float) if "JAW_dy_achieved_mm" in df_traj.columns else np.zeros(n)

#     # 3. BOCA_INF_EXT from Lower Lip Rack (ID 10) + Jaw
#     if "LOW_RACK_meas_dtheta_deg" in df_fb.columns and df_fb["LOW_RACK_meas_dtheta_deg"].notna().any():
#         dtheta_rack = df_fb["LOW_RACK_meas_dtheta_deg"].to_numpy(dtype=float)
#         mm_per_deg = (np.pi * fk["pinion_pitch_diam_mm"]) / 360.0
#         s_rack_mm = dtheta_rack * mm_per_deg
#         tilt_rad = np.radians(fk["rack_tilt_deg"])
#         dy_low_mm = dy_jaw_ach_mm + (s_rack_mm * np.cos(tilt_rad)) / max(fk["low_gain"], 1e-6)
#         out["BOCA_INF_EXT_Delta_X"] = np.zeros(n)
#         out["BOCA_INF_EXT_Delta_Y"] = -dy_low_mm / scale

#     # 4. BOCA_SUP_EXT from Upper Lip 3-Link Piston (ID 9)
#     if "UP_PISTON_meas_dtheta_deg" in df_fb.columns and df_fb["UP_PISTON_meas_dtheta_deg"].notna().any():
#         dtheta_up = df_fb["UP_PISTON_meas_dtheta_deg"].to_numpy(dtype=float)
#         L1, L2, off_x = fk["up_L1"], fk["up_L2"], fk["up_offset_x"]
#         th0 = np.radians(fk["up_theta0_deg"])
#         y_B0 = L1 * np.sin(th0) - np.sqrt(max(L2**2 - (L1 * np.cos(th0) - off_x)**2, 0.0))
#         th_arr = np.radians(fk["up_theta0_deg"] + dtheta_up)
#         y_B_meas = L1 * np.sin(th_arr) - np.sqrt(np.maximum(L2**2 - (L1 * np.cos(th_arr) - off_x)**2, 0.0))
#         ds_meas_mm = (y_B_meas - y_B0) / max(fk["up_gain"], 1e-6)
#         out["BOCA_SUP_EXT_Delta_X"] = np.zeros(n)
#         out["BOCA_SUP_EXT_Delta_Y"] = -ds_meas_mm / scale

#     return pd.DataFrame(out)


# # ==============================================================================
# # 3. HILO DE COMUNICACION SERIE (8 SERVOS)
# # ==============================================================================
# class ServoWorker(threading.Thread):
#     def __init__(self, com_port: str, messages: queue.Queue, events: queue.Queue, stop_event: threading.Event):
#         super().__init__(daemon=True)
#         self.com_port = com_port
#         self.messages = messages
#         self.events = events
#         self.stop_event = stop_event
#         self.monitoring = False

#     def emit(self, *payload):
#         self.events.put(payload)

#     def write_pos_ex(self, servo, cfg: dict, pos_ticks: int, speed_steps: int, acc_unit: int):
#         safe_pos = int(np.clip(pos_ticks, cfg["min_tick"], cfg["max_tick"]))
#         safe_spd = int(np.clip(speed_steps, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
#         safe_acc = int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))
#         servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 1)
#         return servo.WritePosEx(cfg["id"], safe_pos, safe_spd, safe_acc)

#     def read_pos(self, servo, servo_id: int) -> tuple[int, int]:
#         pos, comm, _ = servo.ReadPos(servo_id)
#         return pos, comm

#     def read_all_positions(self, servo, servo_map: dict):
#         readings = {}
#         for name, cfg in servo_map.items():
#             pos, comm = self.read_pos(servo, cfg["id"])
#             if comm == COMM_SUCCESS:
#                 readings[name] = {
#                     "ok": True,
#                     "id": cfg["id"],
#                     "ticks": pos,
#                     "deg": ticks_to_servo_deg(pos),
#                     "dtheta": ticks_to_dtheta_deg(pos, cfg),
#                 }
#             else:
#                 readings[name] = {"ok": False, "id": cfg["id"]}
#         self.emit("positions", readings)

#     def release_all_torque(self, servo, servo_map: dict):
#         for cfg in servo_map.values():
#             servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

#     def run(self):
#         port = None
#         servo = None
#         try:
#             port = PortHandler(self.com_port)
#             servo = STSDriver(port)
#             if not port.openPort():
#                 raise RuntimeError(f"No se pudo abrir el puerto {self.com_port}")
#             if not port.setBaudRate(BAUDRATE):
#                 raise RuntimeError(f"No se pudo configurar {BAUDRATE} baudios")
#             self.emit("connected", self.com_port)

#             while True:
#                 timeout = 0.08 if self.monitoring else None
#                 try:
#                     action = self.messages.get(timeout=timeout)
#                 except queue.Empty:
#                     if self.monitoring:
#                         self.read_all_positions(servo, SERVO_CONFIG)
#                     continue

#                 cmd = action[0]
#                 if cmd == "disconnect":
#                     break

#                 try:
#                     if cmd == "ping_all":
#                         servo_map = action[1]
#                         status = {}
#                         for name, cfg in servo_map.items():
#                             pos, comm = self.read_pos(servo, cfg["id"])
#                             if comm == COMM_SUCCESS:
#                                 status[name] = {
#                                     "ok": True,
#                                     "id": cfg["id"],
#                                     "ticks": pos,
#                                     "deg": ticks_to_servo_deg(pos),
#                                     "dtheta": ticks_to_dtheta_deg(pos, cfg),
#                                 }
#                             else:
#                                 status[name] = {"ok": False, "id": cfg["id"]}
#                         self.emit("ping_result", status)

#                     elif cmd == "set_monitor":
#                         enable, servo_map = action[1], action[2]
#                         self.monitoring = bool(enable)
#                         if self.monitoring:
#                             self.release_all_torque(servo, servo_map)
#                             self.emit("info", "Monitor en vivo ACTIVO (torque liberado en los 8 servos).")
#                         else:
#                             self.emit("info", "Monitor en vivo detenido.")
#                         self.emit("monitor_state", self.monitoring)

#                     elif cmd == "read_once":
#                         self.read_all_positions(servo, action[1])

#                     elif cmd == "go_home":
#                         active_map, speed_cap = action[1], action[2]
#                         self.monitoring = False
#                         self.emit("monitor_state", False)
#                         safe_home_speed = min(400, int(speed_cap))
#                         self.emit("info", f"Moviendo {len(active_map)} servo(s) activos a su posicion Home neutral...")
#                         for cfg in active_map.values():
#                             self.write_pos_ex(servo, cfg, cfg["home_tick"], speed_steps=safe_home_speed, acc_unit=10)
#                         time.sleep(0.9)
#                         self.read_all_positions(servo, SERVO_CONFIG)
#                         self.emit("info", "Servos activos posicionados en Home neutral.")

#                     elif cmd == "move_single":
#                         servo_map, name, target_deg, speed_cap = action[1:]
#                         self.monitoring = False
#                         self.emit("monitor_state", False)
#                         cfg = servo_map[name]
#                         ticks = servo_deg_to_ticks(target_deg, cfg)
#                         safe_spd = min(350, int(speed_cap))
#                         self.write_pos_ex(servo, cfg, ticks, speed_steps=safe_spd, acc_unit=12)
#                         time.sleep(0.15)
#                         self.read_all_positions(servo, servo_map)
#                         self.emit("info", f"{name} (ID {cfg['id']}) enviado a {ticks_to_servo_deg(ticks):.1f}° ({ticks} ticks)")

#                     elif cmd == "release":
#                         self.monitoring = False
#                         self.emit("monitor_state", False)
#                         self.release_all_torque(servo, action[1])
#                         self.emit("info", "Torque liberado en todos los servos.")

#                     elif cmd == "play_csv":
#                         csv_path, time_scale, max_speed_cap, save_feedback, active_map = action[1:]
#                         self.monitoring = False
#                         self.emit("monitor_state", False)
#                         self.stop_event.clear()
#                         self.run_trajectory(
#                             port, servo, Path(csv_path), float(time_scale), int(max_speed_cap), bool(save_feedback), active_map
#                         )

#                 except Exception as exc:
#                     self.emit("error", f"{cmd}: {exc}")

#         except Exception as exc:
#             self.emit("error", f"Conexion: {exc}")
#         finally:
#             if port is not None and servo is not None:
#                 try:
#                     self.release_all_torque(servo, SERVO_CONFIG)
#                 except Exception:
#                     pass
#                 try:
#                     port.closePort()
#                 except Exception:
#                     pass
#             self.emit("disconnected")

#     def load_merged_dataframe(self, csv_path: Path) -> pd.DataFrame:
#         """Loads a unified mouth_trajectory CSV or automatically merges corner + center CSVs if separated."""
#         df = pd.read_csv(csv_path)
#         syl = extract_syllable_name(csv_path)
#         parent = csv_path.parent.parent

#         # If user loaded a corner-only CSV, check if a matching center_lips CSV exists
#         if "JAW_dtheta_deg" not in df.columns:
#             center_cand = parent / "center_lips_trajectories" / f"center_lips_trajectory_{syl}.csv"
#             if center_cand.is_file():
#                 df_c = pd.read_csv(center_cand)
#                 extra_cols = [c for c in df_c.columns if c not in df.columns]
#                 df = pd.concat([df, df_c[extra_cols]], axis=1)

#         # If user loaded a center-only CSV, check if a matching corner CSV exists
#         if "DER_dtheta1_from_90_deg" not in df.columns:
#             corner_cand = parent / "servo_trajectories" / f"servo_trajectory_{syl}.csv"
#             if corner_cand.is_file():
#                 df_k = pd.read_csv(corner_cand)
#                 extra_cols = [c for c in df_k.columns if c not in df.columns]
#                 df = pd.concat([df, df_k[extra_cols]], axis=1)

#         return df

#     def run_trajectory(
#         self,
#         port: PortHandler,
#         servo,
#         csv_path: Path,
#         time_scale: float,
#         max_speed_cap: int,
#         save_feedback: bool,
#         active_map: dict,
#     ):
#         df = self.load_merged_dataframe(csv_path)
#         for col in ("time_s", "time_ms", "phase_pct"):
#             if col not in df.columns:
#                 raise ValueError(f"El CSV no contiene la columna requerida '{col}'")

#         # Filter active_map to servos whose columns are present in df
#         run_map = {
#             name: cfg for name, cfg in active_map.items()
#             if cfg["dtheta_col"] in df.columns
#         }
#         if not run_map:
#             raise ValueError("Ninguno de los servos seleccionados tiene columnas en este archivo CSV.")

#         time_scale = max(1.0, float(time_scale))
#         safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
#         total_ms = float(df["time_ms"].iloc[-1]) * time_scale
#         syl_name = extract_syllable_name(csv_path)

#         self.emit("playback_started", syl_name, len(df), time_scale, total_ms, len(run_map))

#         # 1. Pre-position active servos to 0% initial pose
#         init_speed = min(400, safe_cap)
#         for name, cfg in run_map.items():
#             init_dtheta = float(df[cfg["dtheta_col"]].iloc[0])
#             init_ticks = dtheta_to_ticks(init_dtheta, cfg)
#             self.write_pos_ex(servo, cfg, init_ticks, speed_steps=init_speed, acc_unit=10)

#         t_wait = time.perf_counter()
#         while (time.perf_counter() - t_wait) < 0.8:
#             if self.stop_event.is_set():
#                 self.release_all_torque(servo, run_map)
#                 self.emit("playback_stopped", "Reproduccion cancelada antes de iniciar.")
#                 return
#             time.sleep(0.02)

#         # 2. Stream all 101 steps synchronously
#         sync_write = getattr(servo, "groupSyncWrite", None)
#         feedback_rows = []
#         total_rows = len(df)
#         t_start = time.perf_counter()

#         for idx, row in df.iterrows():
#             if self.stop_event.is_set():
#                 self.release_all_torque(servo, run_map)
#                 self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
#                 return

#             target_time_s = float(row["time_s"]) * time_scale
#             if sync_write is not None:
#                 sync_write.clearParam()

#             log_item = {
#                 "phase_pct": float(row["phase_pct"]),
#                 "time_ms": float(row["time_ms"]) * time_scale,
#             }
#             cmd_snapshot = {}
#             direct_queue = []

#             for name, cfg in run_map.items():
#                 dtheta = float(row[cfg["dtheta_col"]])
#                 omega  = float(row[cfg["omega_col"]])
#                 alpha  = float(row[cfg["alpha_col"]])

#                 pos_ticks   = dtheta_to_ticks(dtheta, cfg)
#                 speed_steps = safe_speed_degs_to_steps(omega, time_scale, safe_cap)
#                 acc_unit    = safe_accel_degs2_to_unit(alpha, time_scale)

#                 if sync_write is not None and hasattr(servo, "SyncWritePosEx"):
#                     servo.SyncWritePosEx(cfg["id"], pos_ticks, speed_steps, acc_unit)
#                 else:
#                     direct_queue.append((cfg, pos_ticks, speed_steps, acc_unit))

#                 cmd_deg = ticks_to_servo_deg(pos_ticks)
#                 log_item[f"{name}_target_dtheta_deg"] = dtheta
#                 log_item[f"{name}_cmd_deg"]   = cmd_deg
#                 log_item[f"{name}_cmd_ticks"] = pos_ticks
#                 log_item[f"{name}_cmd_speed"] = speed_steps
#                 log_item[f"{name}_cmd_acc"]   = acc_unit
#                 cmd_snapshot[name] = {
#                     "cmd_deg": cmd_deg,
#                     "cmd_ticks": pos_ticks,
#                     "cmd_speed": speed_steps,
#                 }

#             while (time.perf_counter() - t_start) < target_time_s:
#                 if self.stop_event.is_set():
#                     break

#             if self.stop_event.is_set():
#                 self.release_all_torque(servo, run_map)
#                 self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
#                 return

#             if sync_write is not None and hasattr(servo, "SyncWritePosEx"):
#                 sync_write.txPacket()
#             else:
#                 for cfg_i, pticks, ssteps, aunit in direct_queue:
#                     self.write_pos_ex(servo, cfg_i, pticks, ssteps, aunit)

#             meas_snapshot = {}
#             for name, cfg in run_map.items():
#                 pos_meas, comm = self.read_pos(servo, cfg["id"])
#                 if comm == COMM_SUCCESS:
#                     meas_deg = ticks_to_servo_deg(pos_meas)
#                     meas_dtheta = ticks_to_dtheta_deg(pos_meas, cfg)
#                     log_item[f"{name}_meas_ticks"] = pos_meas
#                     log_item[f"{name}_meas_deg"] = meas_deg
#                     log_item[f"{name}_meas_dtheta_deg"] = meas_dtheta
#                     meas_snapshot[name] = {
#                         "ok": True,
#                         "id": cfg["id"],
#                         "ticks": pos_meas,
#                         "deg": meas_deg,
#                         "dtheta": meas_dtheta,
#                     }
#                 else:
#                     log_item[f"{name}_meas_ticks"] = np.nan
#                     log_item[f"{name}_meas_deg"] = np.nan
#                     log_item[f"{name}_meas_dtheta_deg"] = np.nan
#                     meas_snapshot[name] = {"ok": False, "id": cfg["id"]}

#             feedback_rows.append(log_item)

#             if idx % 3 == 0 or idx == total_rows - 1:
#                 self.emit(
#                     "playback_step",
#                     float(row["phase_pct"]),
#                     idx + 1,
#                     total_rows,
#                     cmd_snapshot,
#                     meas_snapshot,
#                 )

#         elapsed_ms = (time.perf_counter() - t_start) * 1000.0
#         df_fb = pd.DataFrame(feedback_rows)
#         df_meas_landmarks = reconstruct_measured_landmarks(df, df_fb, DEFAULT_FK_PARAMS)

#         out_csv_msg = ""
#         if save_feedback and not df_fb.empty:
#             out_fb_csv = csv_path.with_name(f"mouth_feedback_{syl_name}.csv")
#             out_rob_csv = csv_path.with_name(f"robot_measured_{syl_name}.csv")
#             df_fb.to_csv(out_fb_csv, index=False)
#             df_meas_landmarks.to_csv(out_rob_csv, index=False)
#             out_csv_msg = f" | Guardados: {out_fb_csv.name} y {out_rob_csv.name}"

#         self.emit(
#             "playback_finished",
#             syl_name,
#             elapsed_ms,
#             out_csv_msg,
#             df,
#             df_fb,
#             df_meas_landmarks,
#         )


# # ==============================================================================
# # 4. INTERFAZ GRAFICA UNIFICADA DE 8 SERVOS + COMPARADOR DE TRAYECTORIAS
# # ==============================================================================
# class UnifiedMouthServoGUI:
#     def __init__(self, root: tk.Tk):
#         self.root = root
#         self.root.title("Control Orofacial Unificado FEETECH STS3215 · 8 Servos + Comparador de Trayectorias")
#         self.root.geometry("1280x940")
#         self.root.minsize(1080, 780)
#         self.root.configure(bg=BG)
#         self.root.protocol("WM_DELETE_WINDOW", self.close)

#         self.events = queue.Queue()
#         self.commands: queue.Queue | None = None
#         self.worker: ServoWorker | None = None
#         self.stop_event = threading.Event()

#         self.connected = False
#         self.playing = False
#         self.monitoring = False
#         self.closing = False

#         self.port_var = tk.StringVar(value=DEFAULT_COM)
#         self.traj_dir = Path(__file__).resolve().parent / DEFAULT_TRAJ_DIR
#         self.syllable_files: dict[str, Path] = {}
#         self.selected_syllable = tk.StringVar(value="")
#         self.csv_info_var = tk.StringVar(value="Selecciona una silaba o carga un archivo CSV.")

#         # Active mechanism group checkboxes
#         self.use_corners_var = tk.BooleanVar(value=True)
#         self.use_jaw_var     = tk.BooleanVar(value=True)
#         self.use_upper_var   = tk.BooleanVar(value=True)
#         self.use_rack_var    = tk.BooleanVar(value=True)

#         self.speed_mult_var = tk.DoubleVar(value=DEFAULT_SPEED_MULT)
#         self.speed_label_var = tk.StringVar()
#         self.max_steps_var = tk.IntVar(value=SAFE_DEFAULT_MAX_STEP)
#         self.max_steps_label_var = tk.StringVar()

#         self.save_log_var = tk.BooleanVar(value=True)
#         self.auto_plot_var = tk.BooleanVar(value=True)
#         self.selected_point_var = tk.StringVar(value=POINT_OPTIONS[0][1])

#         self.progress_var = tk.DoubleVar(value=0.0)
#         self.progress_text_var = tk.StringVar(value="Fase: 0% (En espera)")
#         self.status_var = tk.StringVar(value="Desconectado. Verifica el puerto COM y presiona Conectar.")

#         # Last recorded run data for instant interactive comparison plotting
#         self.last_syl: str | None = None
#         self.last_df_traj: pd.DataFrame | None = None
#         self.last_df_fb: pd.DataFrame | None = None
#         self.last_df_meas: pd.DataFrame | None = None

#         self.servo_cards: dict[str, dict] = {}
#         self.quick_syl_buttons: list[tk.Button] = []

#         self.configure_ttk_styles()
#         self.build_ui()
#         self.refresh_syllable_list()
#         self.update_speed_labels()
#         self.set_connected_ui(False)
#         self.root.after(60, self.process_events)

#     def configure_ttk_styles(self):
#         style = ttk.Style()
#         style.theme_use("clam")
#         style.configure(
#             "Safe.Horizontal.TProgressbar",
#             troughcolor=PANEL2,
#             background=GREEN,
#             bordercolor=BORDER,
#             lightcolor=GREEN,
#             darkcolor=GREEN,
#             thickness=16,
#         )
#         style.configure(
#             "Syllable.TCombobox",
#             fieldbackground="#e7eef9",
#             background=PANEL2,
#             foreground="#172033",
#         )

#     def label(self, parent, text, size=10, fg=TEXT, bold=False, **kw):
#         return tk.Label(
#             parent,
#             text=text,
#             font=("Segoe UI", size, "bold" if bold else "normal"),
#             fg=fg,
#             bg=kw.pop("bg", PANEL),
#             **kw,
#         )

#     def button(self, parent, text, command, bg=BLUE, fg=BG, padx=11, pady=6, **kw):
#         return tk.Button(
#             parent,
#             text=text,
#             command=command,
#             bg=bg,
#             fg=fg,
#             activebackground=GREEN,
#             activeforeground=BG,
#             relief="flat",
#             font=("Segoe UI", 9, "bold"),
#             cursor="hand2",
#             padx=padx,
#             pady=pady,
#             **kw,
#         )

#     def get_active_servo_map(self) -> dict:
#         enabled_groups = set()
#         if self.use_corners_var.get():
#             enabled_groups.add("corners")
#         if self.use_jaw_var.get():
#             enabled_groups.add("jaw")
#         if self.use_upper_var.get():
#             enabled_groups.add("upper")
#         if self.use_rack_var.get():
#             enabled_groups.add("rack")
#         return {k: v for k, v in SERVO_CONFIG.items() if v["group"] in enabled_groups}

#     def build_ui(self):
#         head = tk.Frame(self.root, bg=BG, padx=20, pady=10)
#         head.pack(fill="x")
#         self.label(
#             head,
#             "CONTROL OROFACIAL UNIFICADO STS3215 · 8 SERVOS + VALIDACION CINEMATICA",
#             size=16,
#             bold=True,
#             bg=BG,
#         ).pack(anchor="w")
#         self.label(
#             head,
#             "Esquinas 5-Barras (IDs 5,6,7,8) · Mandibula (IDs 1,2) · Labio Sup. Piston (ID 9) · Labio Inf. Cremallera (ID 10)",
#             size=9,
#             fg=MUTED,
#             bg=BG,
#         ).pack(anchor="w", pady=(2, 0))

#         toolbar = tk.Frame(self.root, bg=PANEL, padx=14, pady=9, highlightbackground=BORDER, highlightthickness=1)
#         toolbar.pack(fill="x", padx=20, pady=(0, 8))

#         self.label(toolbar, "Puerto:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))
#         self.port_entry = tk.Entry(
#             toolbar,
#             textvariable=self.port_var,
#             width=8,
#             font=("Segoe UI", 10, "bold"),
#             justify="center",
#             relief="flat",
#             bg="#e7eef9",
#             fg="#172033",
#         )
#         self.port_entry.pack(side="left", padx=(0, 10), ipady=3)

#         self.connect_btn = self.button(toolbar, "Conectar", self.connect, bg=GREEN)
#         self.connect_btn.pack(side="left", padx=(0, 7))

#         self.disc_btn = self.button(toolbar, "Desconectar", self.disconnect, bg=PANEL2, fg=TEXT)
#         self.disc_btn.pack(side="left", padx=(0, 7))

#         self.ping_btn = self.button(toolbar, "Comprobar 8 Servos", self.ping_servos, bg=BLUE)
#         self.ping_btn.pack(side="left", padx=(0, 7))

#         self.home_btn = self.button(toolbar, "Ir a Home Neutral", self.go_home, bg=BLUE)
#         self.home_btn.pack(side="left", padx=(0, 7))

#         self.monitor_btn = self.button(toolbar, "Monitor en Vivo (OFF)", self.toggle_monitor, bg=PANEL2, fg=TEXT)
#         self.monitor_btn.pack(side="left", padx=(0, 7))

#         self.stop_btn = self.button(
#             toolbar,
#             "PARO / Liberar Torque",
#             self.emergency_stop,
#             bg="#9e2a3b",
#             fg="#ffffff",
#         )
#         self.stop_btn.pack(side="right")

#         scroll_container = tk.Frame(self.root, bg=BG)
#         scroll_container.pack(fill="both", expand=True, padx=20)
#         canvas = tk.Canvas(scroll_container, bg=BG, highlightthickness=0, borderwidth=0)
#         scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
#         canvas.configure(yscrollcommand=scrollbar.set)
#         scrollbar.pack(side="right", fill="y")
#         canvas.pack(side="left", fill="both", expand=True)

#         content = tk.Frame(canvas, bg=BG)
#         window_id = canvas.create_window((0, 0), window=content, anchor="nw")
#         content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
#         canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

#         self.build_syllable_and_comparison_panel(content)

#         grid_frame = tk.Frame(content, bg=BG)
#         grid_frame.pack(fill="both", expand=True, pady=(4, 6))
#         grid_frame.grid_columnconfigure(0, weight=1, uniform="servos")
#         grid_frame.grid_columnconfigure(1, weight=1, uniform="servos")

#         for idx, name in enumerate(SERVO_ORDER):
#             self.build_servo_card(grid_frame, idx, name, SERVO_CONFIG[name])

#         tk.Label(
#             self.root,
#             textvariable=self.status_var,
#             anchor="w",
#             bg="#263550",
#             fg="#f6f9ff",
#             font=("Segoe UI", 10),
#             padx=17,
#             pady=8,
#         ).pack(side="bottom", fill="x")

#     def build_syllable_and_comparison_panel(self, parent):
#         panel = tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightbackground=BORDER, highlightthickness=1)
#         panel.pack(fill="x", pady=(0, 6))

#         top_row = tk.Frame(panel, bg=PANEL)
#         top_row.pack(fill="x")

#         self.label(top_row, "REPRODUCCION Y GRUPOS ACTIVOS", size=12, bold=True).pack(side="left", padx=(0, 14))
#         self.label(top_row, "Silaba:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))

#         self.syl_combo = ttk.Combobox(
#             top_row,
#             textvariable=self.selected_syllable,
#             state="readonly",
#             width=14,
#             font=("Segoe UI", 10, "bold"),
#             style="Syllable.TCombobox",
#         )
#         self.syl_combo.pack(side="left", padx=(0, 8))
#         self.syl_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_syllable_selected())

#         self.button(top_row, "Carpeta...", self.choose_folder, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
#         self.button(top_row, "CSV...", self.choose_csv_file, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
#         self.button(top_row, "Recargar", self.refresh_syllable_list, bg=PANEL2, fg=TEXT).pack(side="left")

#         # Group filter checkboxes
#         grp_row = tk.Frame(panel, bg=PANEL2, padx=10, pady=6)
#         grp_row.pack(fill="x", pady=(8, 4))
#         self.label(grp_row, "Mecanismos a mover:", size=9, bold=True, bg=PANEL2).pack(side="left", padx=(0, 10))
#         for var, txt in (
#             (self.use_corners_var, "Esquinas 5-Barras (IDs 5, 6, 7, 8)"),
#             (self.use_jaw_var, "Mandibula / Chin (IDs 1, 2)"),
#             (self.use_upper_var, "Labio Sup. Piston (ID 9)"),
#             (self.use_rack_var, "Labio Inf. Cremallera (ID 10)"),
#         ):
#             tk.Checkbutton(
#                 grp_row, text=txt, variable=var, bg=PANEL2, fg=TEXT,
#                 activebackground=PANEL2, activeforeground=GREEN, selectcolor=PANEL,
#                 highlightthickness=0, font=("Segoe UI", 9, "bold"),
#             ).pack(side="left", padx=(0, 14))

#         self.quick_syl_frame = tk.Frame(panel, bg=PANEL)
#         self.quick_syl_frame.pack(fill="x", pady=(6, 2))

#         self.label(panel, "", size=9, fg=GREEN, textvariable=self.csv_info_var).pack(anchor="w", pady=(2, 6))

#         sliders_row = tk.Frame(panel, bg=PANEL)
#         sliders_row.pack(fill="x", pady=(2, 6))
#         sliders_row.grid_columnconfigure(0, weight=3)
#         sliders_row.grid_columnconfigure(1, weight=2)

#         speed_box = tk.Frame(sliders_row, bg=PANEL2, padx=12, pady=8)
#         speed_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

#         spd_top = tk.Frame(speed_box, bg=PANEL2)
#         spd_top.pack(fill="x")
#         self.label(spd_top, "Velocidad de Reproduccion (0.20x a 1.00x Max)", size=9, bold=True, bg=PANEL2).pack(side="left")
#         tk.Label(spd_top, textvariable=self.speed_label_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=GREEN).pack(side="right")

#         self.speed_slider = tk.Scale(
#             speed_box, from_=MIN_SPEED_MULT, to=MAX_SAFE_SPEED_MULT, resolution=0.01,
#             orient="horizontal", variable=self.speed_mult_var, showvalue=False, sliderlength=18,
#             bg=PANEL2, fg=TEXT, troughcolor="#384d6c", highlightthickness=0, activebackground=GREEN,
#             command=lambda _v: self.update_speed_labels(),
#         )
#         self.speed_slider.pack(fill="x", pady=(4, 4))

#         presets = tk.Frame(speed_box, bg=PANEL2)
#         presets.pack(fill="x")
#         for mult, title in ((0.25, "0.25x"), (0.33, "0.33x (Seguro)"), (0.50, "0.50x"), (0.75, "0.75x"), (1.00, "1.00x (Real)")):
#             self.button(presets, title, lambda m=mult: self.set_speed_preset(m), bg=PANEL, fg=TEXT, padx=7, pady=2).pack(side="left", padx=(0, 4))

#         cap_box = tk.Frame(sliders_row, bg=PANEL2, padx=12, pady=8)
#         cap_box.grid(row=0, column=1, sticky="nsew")
#         cap_top = tk.Frame(cap_box, bg=PANEL2)
#         cap_top.pack(fill="x")
#         self.label(cap_top, "Tope Max. Motor", size=9, bold=True, bg=PANEL2).pack(side="left")
#         tk.Label(cap_top, textvariable=self.max_steps_label_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=WARN).pack(side="right")

#         self.cap_slider = tk.Scale(
#             cap_box, from_=300, to=SAFE_HARD_LIMIT_STEP, resolution=50,
#             orient="horizontal", variable=self.max_steps_var, showvalue=False, sliderlength=18,
#             bg=PANEL2, fg=TEXT, troughcolor="#384d6c", highlightthickness=0, activebackground=WARN,
#             command=lambda _v: self.update_speed_labels(),
#         )
#         self.cap_slider.pack(fill="x", pady=(4, 4))

#         # Play + Progress bar row
#         play_row = tk.Frame(panel, bg=PANEL)
#         play_row.pack(fill="x", pady=(4, 6))

#         self.play_btn = self.button(
#             play_row, "▶ REPRODUCIR Y GRABAR TRAYECTORIA", self.play_selected_syllable,
#             bg=GREEN, fg=BG, padx=16, pady=8,
#         )
#         self.play_btn.pack(side="left", padx=(0, 12))

#         prog_frame = tk.Frame(play_row, bg=PANEL)
#         prog_frame.pack(side="left", fill="x", expand=True)
#         tk.Label(prog_frame, textvariable=self.progress_text_var, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, anchor="w").pack(fill="x")
#         self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100.0, style="Safe.Horizontal.TProgressbar")
#         self.progress_bar.pack(fill="x", pady=(2, 0))

#         # Post-Playback Trajectory Comparison Row (orofacial_analysis.py style)
#         cmp_box = tk.Frame(panel, bg=PANEL2, padx=12, pady=8, highlightbackground=BORDER, highlightthickness=1)
#         cmp_box.pack(fill="x", pady=(4, 0))

#         self.label(cmp_box, "COMPARAR TRAYECTORIA (CSV vs Servos):", size=9, bold=True, bg=PANEL2, fg=GREEN).pack(side="left", padx=(0, 8))
#         self.point_combo = ttk.Combobox(
#             cmp_box,
#             textvariable=self.selected_point_var,
#             values=[label for _, label in POINT_OPTIONS],
#             state="readonly",
#             width=46,
#             font=("Segoe UI", 9, "bold"),
#             style="Syllable.TCombobox",
#         )
#         self.point_combo.pack(side="left", padx=(0, 8))

#         self.button(
#             cmp_box, "📊 Graficar Punto Seleccionado", self.plot_selected_point_comparison,
#             bg=BLUE, fg=BG, padx=12, pady=5,
#         ).pack(side="left", padx=(0, 8))

#         self.button(
#             cmp_box, "📂 Comparar CSV Previo...", self.load_and_compare_feedback_file,
#             bg=PANEL, fg=TEXT, padx=10, pady=5,
#         ).pack(side="left", padx=(0, 10))

#         tk.Checkbutton(
#             cmp_box, text="Graficar al terminar", variable=self.auto_plot_var,
#             bg=PANEL2, fg=TEXT, activebackground=PANEL2, selectcolor=PANEL,
#             highlightthickness=0, font=("Segoe UI", 9),
#         ).pack(side="right")

#     def build_servo_card(self, parent, index: int, name: str, cfg: dict):
#         box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=9)
#         box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=5, pady=4)

#         top = tk.Frame(box, bg=PANEL)
#         top.pack(fill="x")
#         dir_str = "+1" if cfg["dir"] > 0 else "-1"
#         home_deg = ticks_to_servo_deg(cfg["home_tick"])
#         self.label(top, f"{name} · ID {cfg['id']}", size=11, bold=True).pack(side="left")
#         self.label(top, f"({cfg['label']} · Home {home_deg:.0f}° · dir {dir_str})", size=8, fg=MUTED).pack(side="left", padx=(6, 0))

#         real_var = tk.StringVar(value="Real: Sin leer")
#         tk.Label(top, textvariable=real_var, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=GREEN).pack(side="right")

#         tele_frame = tk.Frame(box, bg=PANEL2, padx=8, pady=5)
#         tele_frame.pack(fill="x", pady=(5, 5))
#         cmd_var = tk.StringVar(value="Cmd CSV: —")
#         dtheta_var = tk.StringVar(value="Δθ Real: —")
#         tk.Label(tele_frame, textvariable=cmd_var, font=("Segoe UI", 8), bg=PANEL2, fg=MUTED).pack(side="left")
#         tk.Label(tele_frame, textvariable=dtheta_var, font=("Segoe UI", 8, "bold"), bg=PANEL2, fg=BLUE).pack(side="right")

#         min_d, max_d = cfg["min_deg"], cfg["max_deg"]
#         ctrl_top = tk.Frame(box, bg=PANEL)
#         ctrl_top.pack(fill="x")
#         self.label(ctrl_top, f"Rango seguro ({min_d:.0f}° a {max_d:.0f}°):", size=8, fg=MUTED).pack(side="left")
#         angle_var = tk.StringVar(value=f"{home_deg:.1f}")
#         angle_entry = tk.Entry(
#             ctrl_top, textvariable=angle_var, width=7, font=("Segoe UI", 9, "bold"),
#             justify="center", relief="flat", bg="#e7eef9", fg="#172033",
#         )
#         angle_entry.pack(side="right")
#         angle_entry.bind("<Return>", lambda _e, n=name: self.move_single_servo(n))

#         slider = tk.Scale(
#             box, from_=min_d, to=max_d, orient="horizontal", resolution=1,
#             showvalue=False, sliderlength=14, bg=PANEL, fg=TEXT, troughcolor="#384d6c",
#             highlightthickness=0, activebackground=BLUE,
#             command=lambda val, v=angle_var: v.set(f"{float(val):.1f}"),
#         )
#         slider.set(round(home_deg))
#         slider.pack(fill="x", pady=(2, 4))
#         slider.bind("<ButtonRelease-1>", lambda _e, n=name: self.move_single_servo(n))

#         btn_row = tk.Frame(box, bg=PANEL)
#         btn_row.pack(fill="x")
#         self.button(btn_row, "-3°", lambda n=name: self.nudge_servo(n, -3.0), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
#         self.button(btn_row, "+3°", lambda n=name: self.nudge_servo(n, 3.0), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
#         self.button(btn_row, f"Home ({home_deg:.0f}°)", lambda n=name, h=home_deg: self.set_and_move_servo(n, h), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
#         self.button(btn_row, "Mover", lambda n=name: self.move_single_servo(n), bg=BLUE, fg=BG, padx=8, pady=3).pack(side="left", padx=(0, 4))
#         self.button(btn_row, "Leer", self.read_once, bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="right")

#         self.servo_cards[name] = {
#             "real_var": real_var,
#             "cmd_var": cmd_var,
#             "dtheta_var": dtheta_var,
#             "angle_var": angle_var,
#             "slider": slider,
#         }

#     # ==========================================================================
#     # 5. GRAFICADOR DE COMPARACION (ESTILO orofacial_analysis.py)
#     # ==========================================================================
#     def get_selected_point_code(self) -> str:
#         sel = self.selected_point_var.get()
#         for code, label in POINT_OPTIONS:
#             if label == sel:
#                 return code
#         return "ALL_5"

#     def plot_selected_point_comparison(self):
#         if self.last_df_traj is None or self.last_df_fb is None or self.last_df_meas is None:
#             # Try loading from the currently selected syllable if a previous feedback file exists on disk
#             syl = self.selected_syllable.get()
#             csv_path = self.syllable_files.get(syl)
#             if csv_path and csv_path.exists():
#                 fb_cand = csv_path.with_name(f"mouth_feedback_{syl}.csv")
#                 if fb_cand.is_file():
#                     self.last_syl = syl
#                     self.last_df_traj = pd.read_csv(csv_path)
#                     self.last_df_fb = pd.read_csv(fb_cand)
#                     self.last_df_meas = reconstruct_measured_landmarks(self.last_df_traj, self.last_df_fb, DEFAULT_FK_PARAMS)
#                 else:
#                     messagebox.showinfo(
#                         "Sin datos grabados",
#                         "Reproduce primero una silaba (o usa '📂 Comparar CSV Previo...') para comparar la trayectoria.",
#                     )
#                     return
#             else:
#                 return

#         code = self.get_selected_point_code()
#         syl = self.last_syl or "SYL"
#         df_traj = self.last_df_traj
#         df_fb = self.last_df_fb
#         df_meas = self.last_df_meas
#         phase = df_traj["phase_pct"].to_numpy(dtype=float)

#         if code == "SERVOS_8":
#             self.plot_servo_tracking_figure(syl, df_fb)
#             return

#         points = ["BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_IZQ", "BOCA_DER", "BARBILLA"] if code == "ALL_5" else [code]

#         if len(points) == 1:
#             pt = points[0]
#             fig, (ax_xy, ax_t) = plt.subplots(1, 2, figsize=(12.5, 5.2))
#             self._draw_point_xy_and_time(ax_xy, ax_t, pt, phase, df_traj, df_meas)
#             fig.suptitle(f"{syl} · Comparacion de Trayectoria: {POINT_LABELS[pt]} (Estilo orofacial_analysis.py)", fontsize=13, fontweight="bold")
#             fig.tight_layout(rect=(0, 0, 1, 0.94))
#             plt.show()
#         else:
#             fig, axs = plt.subplots(2, 5, figsize=(18, 7.5))
#             for idx, pt in enumerate(points):
#                 self._draw_point_xy_and_time(axs[0, idx], axs[1, idx], pt, phase, df_traj, df_meas)
#             fig.suptitle(
#                 f"{syl} · Comparacion Completa: Humano (Media 50 Part. ±1 SD) vs Objetivo IK vs Robot Real Medido",
#                 fontsize=14, fontweight="bold",
#             )
#             fig.tight_layout(rect=(0, 0, 1, 0.94))
#             plt.show()

#     def _draw_point_xy_and_time(self, ax_xy, ax_t, pt: str, phase: np.ndarray, df_traj: pd.DataFrame, df_meas: pd.DataFrame):
#         color = POINT_COLORS.get(pt, "#1f77b4")
#         hx_col, hy_col = f"HUMAN_{pt}_Delta_X_mean", f"HUMAN_{pt}_Delta_Y_mean"
#         hsdx_col, hsdy_col = f"HUMAN_{pt}_Delta_X_sd", f"HUMAN_{pt}_Delta_Y_sd"
#         tx_col, ty_col = f"ROBOT_TARGET_{pt}_Delta_X", f"ROBOT_TARGET_{pt}_Delta_Y"
#         mx_col, my_col = f"{pt}_Delta_X", f"{pt}_Delta_Y"

#         has_human = hx_col in df_traj.columns and hy_col in df_traj.columns
#         has_target = tx_col in df_traj.columns and ty_col in df_traj.columns
#         has_meas = mx_col in df_meas.columns and my_col in df_meas.columns and df_meas[my_col].notna().any()

#         # --- Top/Left Subplot: 2D XY Trajectory (Inverted Y-axis like orofacial_analysis.py) ---
#         if has_human:
#             hx, hy = df_traj[hx_col].to_numpy(), df_traj[hy_col].to_numpy()
#             ax_xy.plot(hx, hy, color=color, lw=2.4, label="Human mean (n=50)")
#             ax_xy.scatter([hx[0]], [hy[0]], color=color, s=22, zorder=5)
#             ax_xy.scatter([hx[-1]], [hy[-1]], color=color, marker="x", s=34, zorder=5)

#         if has_target:
#             tx, ty = df_traj[tx_col].to_numpy(), df_traj[ty_col].to_numpy()
#             ax_xy.plot(tx, ty, color="#2ca02c", ls=":", lw=2.0, label="Target IK (CSV)")

#         if has_meas:
#             mx, my = df_meas[mx_col].to_numpy(), df_meas[my_col].to_numpy()
#             ax_xy.plot(mx, my, "--", color="black", lw=2.0, label="Robot Medido (FK)")

#         ax_xy.axhline(0, color="black", alpha=0.25, lw=0.6)
#         ax_xy.axvline(0, color="black", alpha=0.25, lw=0.6)
#         ax_xy.set_title(f"{POINT_LABELS[pt]} · XY", fontsize=10, fontweight="bold")
#         ax_xy.set_xlabel("Delta X (eye-distance units)", fontsize=8)
#         ax_xy.set_ylabel("Delta Y (+ downward)", fontsize=8)
#         ax_xy.invert_yaxis()
#         ax_xy.set_aspect("equal", adjustable="datalim")
#         ax_xy.grid(alpha=0.18)
#         ax_xy.legend(fontsize=7, loc="best")

#         # --- Bottom/Right Subplot: Time-Normalized Curve vs Selected Interval (0..100%) ---
#         rmse_txt = ""
#         if has_human:
#             hy = df_traj[hy_col].to_numpy()
#             ax_t.plot(phase, hy, color=color, lw=2.2, label="Human ΔY mean")
#             if hsdy_col in df_traj.columns:
#                 hsd = df_traj[hsdy_col].to_numpy()
#                 ax_t.fill_between(phase, hy - hsd, hy + hsd, color=color, alpha=0.16, label="±1 SD")
#             if pt in ("BOCA_DER", "BOCA_IZQ"):
#                 hx = df_traj[hx_col].to_numpy()
#                 ax_t.plot(phase, hx, color="#7c47a9", lw=1.6, alpha=0.8, label="Human ΔX mean")

#         if has_target:
#             ty = df_traj[ty_col].to_numpy()
#             ax_t.plot(phase, ty, color="#2ca02c", ls=":", lw=1.8, label="Target IK ΔY")

#         if has_meas:
#             my = df_meas[my_col].to_numpy()
#             ax_t.plot(phase, my, "--", color="black", lw=2.0, label="Robot Real ΔY")
#             if pt in ("BOCA_DER", "BOCA_IZQ"):
#                 mx = df_meas[mx_col].to_numpy()
#                 ax_t.plot(phase, mx, "-.", color="#444444", lw=1.4, label="Robot Real ΔX")
#             if has_human:
#                 err_y = my - df_traj[hy_col].to_numpy()
#                 rmse_y = float(np.sqrt(np.nanmean(err_y**2)))
#                 mae_y = float(np.nanmean(np.abs(err_y)))
#                 rmse_txt = f" | RMSE_Y={rmse_y:.4f}, MAE_Y={mae_y:.4f}"

#         ax_t.axhline(0, color="black", alpha=0.35, lw=0.7)
#         ax_t.set_title(f"vs Fase (0-100%){rmse_txt}", fontsize=9)
#         ax_t.set_xlabel("Selected interval (%)", fontsize=8)
#         ax_t.set_ylabel("Delta (eye-distance units)", fontsize=8)
#         ax_t.set_xlim(0, 100)
#         ax_t.grid(alpha=0.18)
#         ax_t.legend(fontsize=7, loc="best")

#     def plot_servo_tracking_figure(self, syl: str, df_fb: pd.DataFrame):
#         fig, axs = plt.subplots(4, 2, figsize=(13, 10), sharex=True)
#         phase = df_fb["phase_pct"].to_numpy(dtype=float)

#         for idx, name in enumerate(SERVO_ORDER):
#             ax = axs.flat[idx]
#             cfg = SERVO_CONFIG[name]
#             cmd_col = f"{name}_cmd_deg"
#             meas_col = f"{name}_meas_deg"
#             if cmd_col in df_fb.columns:
#                 ax.plot(phase, df_fb[cmd_col], color="#1f77b4", lw=2.0, label="Comando CSV (deg)")
#             if meas_col in df_fb.columns and df_fb[meas_col].notna().any():
#                 ax.plot(phase, df_fb[meas_col], "--", color="#d62728", lw=1.8, label="Real Encoder (deg)")
#                 err = df_fb[meas_col] - df_fb[cmd_col]
#                 rmse_deg = float(np.sqrt(np.nanmean(err**2)))
#                 ax.set_title(f"{name} (ID {cfg['id']}) · RMSE = {rmse_deg:.2f}°", fontsize=9, fontweight="bold")
#             else:
#                 ax.set_title(f"{name} (ID {cfg['id']}) · No medido", fontsize=9)
#             ax.grid(alpha=0.22)
#             ax.set_ylabel("Grados (°)", fontsize=8)
#             if idx == 0:
#                 ax.legend(fontsize=8, loc="best")

#         for ax in axs[-1, :]:
#             ax.set_xlabel("Selected interval (%)")

#         fig.suptitle(f"{syl} · Seguimiento Angular de los 8 Servos STS3215 (Comando vs Encoder Real)", fontsize=13, fontweight="bold")
#         fig.tight_layout(rect=(0, 0, 1, 0.95))
#         plt.show()

#     def load_and_compare_feedback_file(self):
#         fb_file = filedialog.askopenfilename(
#             title="Seleccionar archivo mouth_feedback_<SYL>.csv",
#             filetypes=[("Feedback CSV", "*feedback*.csv"), ("Todos los CSV", "*.csv")],
#         )
#         if not fb_file:
#             return
#         fb_path = Path(fb_file).resolve()
#         syl = re.sub(r"^mouth_feedback_|_4servo_feedback$|_center_feedback$", "", fb_path.stem, flags=re.IGNORECASE).upper()
#         traj_cand = fb_path.parent / f"mouth_trajectory_{syl}.csv"
#         if not traj_cand.is_file() and syl in self.syllable_files:
#             traj_cand = self.syllable_files[syl]
#         if not traj_cand.is_file():
#             messagebox.showwarning("Falta CSV base", f"No se encontro el archivo base mouth_trajectory_{syl}.csv.")
#             return

#         self.last_syl = syl
#         self.last_df_traj = pd.read_csv(traj_cand)
#         self.last_df_fb = pd.read_csv(fb_path)
#         self.last_df_meas = reconstruct_measured_landmarks(self.last_df_traj, self.last_df_fb, DEFAULT_FK_PARAMS)
#         self.plot_selected_point_comparison()

#     # ==========================================================================
#     # 6. CONTROLES DE LA INTERFAZ Y EVENTOS
#     # ==========================================================================
#     def set_speed_preset(self, mult: float):
#         self.speed_mult_var.set(round(float(np.clip(mult, MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT)), 2))
#         self.update_speed_labels()

#     def get_time_scale(self) -> float:
#         mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
#         return 1.0 / mult

#     def update_speed_labels(self):
#         mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
#         time_scale = 1.0 / mult
#         self.speed_label_var.set(f"{mult:.2f}x ({round(mult*100)}%) · time_scale={time_scale:.2f}x")
#         cap = int(np.clip(self.max_steps_var.get(), 300, SAFE_HARD_LIMIT_STEP))
#         self.max_steps_label_var.set(f"{cap} pasos/s (~{cap / STEPS_PER_DEG:.0f}°/s)")
#         self.update_csv_summary()

#     def refresh_syllable_list(self):
#         self.syllable_files.clear()
#         script_dir = Path(__file__).resolve().parent
#         search_dirs = [
#             self.traj_dir,
#             script_dir / DEFAULT_TRAJ_DIR,
#             Path.cwd() / DEFAULT_TRAJ_DIR,
#             script_dir / FALLBACK_CORNER_DIR,
#             Path.cwd() / FALLBACK_CORNER_DIR,
#             script_dir / FALLBACK_CENTER_DIR,
#             script_dir,
#             Path.cwd(),
#         ]
#         found_paths = []
#         for folder in search_dirs:
#             if folder.exists() and folder.is_dir():
#                 for pat in ("mouth_trajectory_*.csv", "servo_trajectory_*.csv", "center_lips_trajectory_*.csv"):
#                     matches = [p for p in sorted(folder.glob(pat)) if "feedback" not in p.stem]
#                     if matches:
#                         found_paths.extend(matches)
#                         self.traj_dir = folder
#                         break
#             if found_paths:
#                 break

#         for path in found_paths:
#             syl = extract_syllable_name(path)
#             self.syllable_files[syl] = path.resolve()

#         for widget in self.quick_syl_frame.winfo_children():
#             widget.destroy()
#         self.quick_syl_buttons.clear()

#         syl_names = sorted(self.syllable_files.keys())
#         self.syl_combo["values"] = syl_names

#         if syl_names:
#             self.label(self.quick_syl_frame, "Silabas:", size=9, fg=MUTED).pack(side="left", padx=(0, 6))
#             for syl in syl_names:
#                 btn = self.button(
#                     self.quick_syl_frame, syl, lambda s=syl: self.select_syllable_by_name(s),
#                     bg=PANEL2, fg=TEXT, padx=9, pady=2,
#                 )
#                 btn.pack(side="left", padx=(0, 4))
#                 self.quick_syl_buttons.append(btn)

#             if self.selected_syllable.get() not in self.syllable_files:
#                 self.selected_syllable.set(syl_names[0])
#             self.on_syllable_selected()
#         else:
#             self.selected_syllable.set("")
#             self.csv_info_var.set(
#                 "Ejecuta primero 'python generate_all_mouth_trajectories.py' o selecciona la carpeta con 'Carpeta...'."
#             )

#     def select_syllable_by_name(self, syl: str):
#         self.selected_syllable.set(syl)
#         self.on_syllable_selected()

#     def on_syllable_selected(self):
#         self.update_csv_summary()

#     def update_csv_summary(self):
#         syl = self.selected_syllable.get()
#         path = self.syllable_files.get(syl)
#         if not path or not path.exists():
#             return
#         try:
#             df = pd.read_csv(path)
#             base_ms = float(df["time_ms"].iloc[-1])
#             scaled_ms = base_ms * self.get_time_scale()
#             n_part = int(df["n_participants"].iloc[0]) if "n_participants" in df.columns else 50
#             self.csv_info_var.set(
#                 f"Archivo: {path.name}  |  Media validada: n={n_part} participantes  |  "
#                 f"Duracion base (1.0x): {base_ms:.0f} ms  |  Duracion actual: {scaled_ms:.0f} ms ({scaled_ms/1000.0:.2f} s)"
#             )
#         except Exception as exc:
#             self.csv_info_var.set(f"Error al leer {path.name}: {exc}")

#     def choose_folder(self):
#         folder = filedialog.askdirectory(title="Seleccionar carpeta de trayectorias CSV")
#         if folder:
#             self.traj_dir = Path(folder)
#             self.refresh_syllable_list()

#     def choose_csv_file(self):
#         file_path = filedialog.askopenfilename(
#             title="Seleccionar archivo CSV de trayectoria",
#             filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
#         )
#         if file_path:
#             path = Path(file_path).resolve()
#             syl = extract_syllable_name(path)
#             self.syllable_files[syl] = path
#             self.syl_combo["values"] = sorted(self.syllable_files.keys())
#             self.selected_syllable.set(syl)
#             self.on_syllable_selected()

#     def set_connected_ui(self, connected: bool):
#         self.connected = connected
#         self.connect_btn.config(state="disabled" if connected else "normal")
#         self.port_entry.config(state="disabled" if connected else "normal")
#         state = "normal" if connected else "disabled"
#         for btn in (self.disc_btn, self.ping_btn, self.home_btn, self.monitor_btn, self.stop_btn, self.play_btn):
#             btn.config(state=state)

#     def connect(self):
#         if self.connected or (self.worker and self.worker.is_alive()):
#             return
#         com = self.port_var.get().strip()
#         if not com:
#             messagebox.showwarning("Puerto vacio", "Escribe el puerto COM (ej. COM4).")
#             return
#         self.commands = queue.Queue()
#         self.stop_event.clear()
#         self.worker = ServoWorker(com, self.commands, self.events, self.stop_event)
#         self.status_var.set(f"Conectando a {com} a {BAUDRATE} baudios...")
#         self.connect_btn.config(state="disabled")
#         self.worker.start()

#     def disconnect(self):
#         if self.worker and self.worker.is_alive():
#             self.stop_event.set()
#             self.status_var.set("Desconectando y liberando torque...")
#             self.commands.put(("disconnect",))
#             self.disc_btn.config(state="disabled")

#     def ping_servos(self):
#         if self.connected and not self.playing:
#             self.commands.put(("ping_all", SERVO_CONFIG))

#     def read_once(self):
#         if self.connected and not self.playing:
#             self.commands.put(("read_once", SERVO_CONFIG))

#     def go_home(self):
#         if not self.connected or self.playing:
#             return
#         active_map = self.get_active_servo_map()
#         if not active_map:
#             messagebox.showwarning("Sin mecanismos activos", "Marca al menos un grupo de mecanismos.")
#             return
#         self.commands.put(("go_home", active_map, int(self.max_steps_var.get())))

#     def toggle_monitor(self):
#         if not self.connected or self.playing:
#             return
#         self.commands.put(("set_monitor", not self.monitoring, SERVO_CONFIG))

#     def emergency_stop(self):
#         if not self.connected:
#             return
#         self.stop_event.set()
#         self.commands.put(("release", SERVO_CONFIG))

#     def set_and_move_servo(self, name: str, deg: float):
#         cfg = SERVO_CONFIG[name]
#         deg = float(np.clip(deg, cfg["min_deg"], cfg["max_deg"]))
#         card = self.servo_cards[name]
#         card["angle_var"].set(f"{deg:.1f}")
#         card["slider"].set(round(deg))
#         self.move_single_servo(name)

#     def nudge_servo(self, name: str, delta: float):
#         cfg = SERVO_CONFIG[name]
#         card = self.servo_cards[name]
#         try:
#             curr = float(card["angle_var"].get().replace(",", "."))
#         except ValueError:
#             curr = ticks_to_servo_deg(cfg["home_tick"])
#         self.set_and_move_servo(name, float(np.clip(curr + delta, cfg["min_deg"], cfg["max_deg"])))

#     def move_single_servo(self, name: str):
#         if not self.connected or self.playing:
#             return
#         cfg = SERVO_CONFIG[name]
#         card = self.servo_cards[name]
#         try:
#             deg = float(card["angle_var"].get().replace(",", "."))
#         except ValueError:
#             return
#         deg = float(np.clip(deg, cfg["min_deg"], cfg["max_deg"]))
#         card["angle_var"].set(f"{deg:.1f}")
#         card["slider"].set(round(deg))
#         self.commands.put(("move_single", SERVO_CONFIG, name, deg, int(self.max_steps_var.get())))

#     def play_selected_syllable(self):
#         if not self.connected or self.playing:
#             return
#         syl = self.selected_syllable.get()
#         csv_path = self.syllable_files.get(syl)
#         if not csv_path or not csv_path.exists():
#             messagebox.showwarning("Sin archivo CSV", "Selecciona una silaba valida o carga un archivo CSV.")
#             return
#         active_map = self.get_active_servo_map()
#         if not active_map:
#             messagebox.showwarning("Sin mecanismos", "Selecciona al menos un grupo de mecanismos para reproducir.")
#             return

#         time_scale = self.get_time_scale()
#         max_speed_cap = int(np.clip(self.max_steps_var.get(), MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
#         self.playing = True
#         self.play_btn.config(state="disabled")
#         self.progress_var.set(0.0)
#         self.commands.put(
#             ("play_csv", csv_path, time_scale, max_speed_cap, self.save_log_var.get(), active_map)
#         )

#     def update_servo_cards_from_readings(self, readings: dict):
#         for name, info in readings.items():
#             card = self.servo_cards.get(name)
#             cfg = SERVO_CONFIG.get(name)
#             if not card or not cfg:
#                 continue
#             if info.get("ok"):
#                 deg = info["deg"]
#                 ticks = info["ticks"]
#                 dtheta = info["dtheta"]
#                 card["real_var"].set(f"Real: {deg:5.1f}° [{ticks:4d}]")
#                 card["dtheta_var"].set(f"Δθ Real: {dtheta:+5.1f}°")
#                 if not self.playing:
#                     card["angle_var"].set(f"{deg:.1f}")
#                     card["slider"].set(int(np.clip(round(deg), cfg["min_deg"], cfg["max_deg"])))
#             else:
#                 card["real_var"].set("OFFLINE")
#                 card["dtheta_var"].set("Δθ Real: OFF")

#     def process_events(self):
#         while True:
#             try:
#                 event = self.events.get_nowait()
#             except queue.Empty:
#                 break

#             kind = event[0]
#             if kind == "connected":
#                 com = event[1]
#                 self.set_connected_ui(True)
#                 self.status_var.set(f"Puerto {com} conectado. Comprobando los 8 servos...")
#                 self.ping_servos()

#             elif kind == "disconnected":
#                 self.playing = False
#                 self.monitoring = False
#                 self.set_connected_ui(False)
#                 self.monitor_btn.config(text="Monitor en Vivo (OFF)", bg=PANEL2, fg=TEXT)
#                 self.worker = None
#                 self.status_var.set("Puerto serie desconectado y torque liberado.")
#                 if self.closing:
#                     self.root.destroy()
#                     return

#             elif kind == "ping_result":
#                 status = event[1]
#                 self.update_servo_cards_from_readings(status)
#                 ok_count = sum(1 for v in status.values() if v.get("ok"))
#                 self.status_var.set(f"Comprobacion completada: {ok_count} de 8 servos responden (IDs 1, 2, 5, 6, 7, 8, 9, 10).")

#             elif kind == "positions":
#                 self.update_servo_cards_from_readings(event[1])

#             elif kind == "monitor_state":
#                 self.monitoring = event[1]
#                 if self.monitoring:
#                     self.monitor_btn.config(text="Monitor en Vivo (ACTIVO)", bg=GREEN, fg=BG)
#                 else:
#                     self.monitor_btn.config(text="Monitor en Vivo (OFF)", bg=PANEL2, fg=TEXT)

#             elif kind == "playback_started":
#                 _, syl_name, total_steps, time_scale, total_ms, n_servos = event
#                 mult = 1.0 / time_scale
#                 self.progress_var.set(0.0)
#                 self.progress_text_var.set(
#                     f"Reproduciendo '{syl_name}' en {n_servos} servos ({total_steps} pasos | {mult:.2f}x | {total_ms:.0f} ms)"
#                 )
#                 self.status_var.set(f"Moviendo {n_servos} servos para silaba '{syl_name}' a {mult:.2f}x...")

#             elif kind == "playback_step":
#                 _, phase_pct, step_idx, total_steps, cmd_snap, meas_snap = event
#                 self.progress_var.set(phase_pct)
#                 self.progress_text_var.set(f"Fase: {phase_pct:5.1f}%  (Paso {step_idx}/{total_steps})")
#                 for name, cinfo in cmd_snap.items():
#                     card = self.servo_cards.get(name)
#                     if card:
#                         card["cmd_var"].set(
#                             f"Cmd: {cinfo['cmd_deg']:5.1f}° [{cinfo['cmd_ticks']:4d}] · {cinfo['cmd_speed']} st/s"
#                         )
#                 self.update_servo_cards_from_readings(meas_snap)

#             elif kind == "playback_finished":
#                 _, syl_name, elapsed_ms, out_csv_msg, df_traj, df_fb, df_meas = event
#                 self.playing = False
#                 if self.connected:
#                     self.play_btn.config(state="normal")
#                 self.progress_var.set(100.0)
#                 self.progress_text_var.set(f"Completado: 100% ({elapsed_ms:.0f} ms) · Lista comparacion de trayectoria")
#                 self.status_var.set(f"Silaba '{syl_name}' finalizada en {elapsed_ms:.1f} ms{out_csv_msg}")

#                 self.last_syl = syl_name
#                 self.last_df_traj = df_traj
#                 self.last_df_fb = df_fb
#                 self.last_df_meas = df_meas

#                 if self.auto_plot_var.get():
#                     self.root.after(150, self.plot_selected_point_comparison)

#             elif kind == "playback_stopped":
#                 self.playing = False
#                 if self.connected:
#                     self.play_btn.config(state="normal")
#                 self.progress_text_var.set("Reproduccion detenida por el usuario")
#                 self.status_var.set(event[1])

#             elif kind == "info":
#                 self.status_var.set(event[1])

#             elif kind == "error":
#                 self.playing = False
#                 if self.connected:
#                     self.play_btn.config(state="normal")
#                 self.status_var.set("ERROR: " + event[1])
#                 messagebox.showerror("Error", event[1])

#         self.root.after(60, self.process_events)

#     def close(self):
#         if self.closing:
#             return
#         self.closing = True
#         self.stop_event.set()
#         if self.worker and self.worker.is_alive():
#             self.disconnect()
#         else:
#             self.root.destroy()


# if __name__ == "__main__":
#     root = tk.Tk()
#     app = UnifiedMouthServoGUI(root)
#     root.mainloop()
# -*- coding: utf-8 -*-
"""Unified 8-Servo GUI Controller & Trajectory Comparator for FEETECH STS3215-12V.

Controls all 8 servos of the Orofacial Robotic Simulator:
    - Corner 5-Bar Mechanisms: DER_TOP (ID 5), DER_BOTTOM (ID 6), IZQ_TOP (ID 7), IZQ_BOTTOM (ID 8)
    - Chin / Jaw Mechanism:    JAW_LEFT (ID 1), JAW_RIGHT (ID 2)
    - Upper Lip 3-Link Piston: UP_PISTON (ID 9)
    - Lower Lip Rack & Pinion: LOW_RACK (ID 10)

Features:
    - Real-Time Amplitude Gain Slider (Global Master Gain + Per-Subsystem Fine Gains)
      that scales angular displacement (dtheta), angular velocity (omega), and angular
      acceleration (alpha) on the fly while strictly respecting physical tick limits.
    - Compatible with both `sms_sts` and `sts` in `scservo_sdk` / `ftservo-python-sdk`
    - Group toggles to drive all 8 servos or isolate specific mechanisms
    - Records real encoder feedback during movement, reconstructs the achieved anatomical
      landmark trajectories (`BOCA_DER`, `BOCA_IZQ`, `BOCA_SUP_EXT`, `BOCA_INF_EXT`, `BARBILLA`)
      via Forward Kinematics in dimensionless eye-distance units, and exports `robot_measured_<SYL>.csv`
    - Built-in interactive plotter (matching `orofacial_analysis.py` conventions: inverted Y axis,
      ±1 SD shaded human cohort band, black dashed `--` robot curve, and RMSE/MAE error metrics)
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import scservo_sdk as scs
    from scservo_sdk import COMM_SUCCESS, PortHandler
    if hasattr(scs, "sms_sts"):
        STSDriver = scs.sms_sts
    elif hasattr(scs, "sts"):
        STSDriver = scs.sts
    else:
        raise ImportError("No se encontro 'sms_sts' ni 'sts' en scservo_sdk.")
    try:
        from scservo_sdk import GroupSyncWrite
    except ImportError:
        GroupSyncWrite = None
except ImportError as exc:
    raise SystemExit(
        f"Error de importacion: {exc}\n"
        "Instala con: python -m pip install ftservo-python-sdk pyserial numpy pandas matplotlib"
    ) from exc


# ==============================================================================
# 1. REGISTROS STS3215, CONFIGURACION DE 8 SERVOS Y PARAMETROS CINEMATICOS
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
HOME_TICK_180 = 2048            # 180.0 deg neutral

MIN_SPEED_STEPS       = 120
SAFE_DEFAULT_MAX_STEP = 1200    # ~105 deg/s default cap
SAFE_HARD_LIMIT_STEP  = 1800    # Hardware protection cap
SAFE_MAX_ACC_UNIT     = 100
SPEED_HEADROOM        = 1.15

MIN_SPEED_MULT      = 0.20      # 5x slow motion
MAX_SAFE_SPEED_MULT = 1.00      # 1.0x real-time human speed
DEFAULT_SPEED_MULT  = 0.33      # 3x slow motion default for initial safety check

# Limites para la Ganancia de Amplitud en Tiempo Real
MIN_AMP_GAIN        = 0.20      # 20% de la amplitud del CSV
MAX_AMP_GAIN        = 4.00      # Hasta 400% de la amplitud (siempre limitado por min_tick/max_tick)
DEFAULT_AMP_GAIN    = 1.00      # 1.00x por defecto

DEFAULT_TRAJ_DIR = Path("orofacial_results/mouth_trajectories")
FALLBACK_CORNER_DIR = Path("orofacial_results/servo_trajectories")
FALLBACK_CENTER_DIR = Path("orofacial_results/center_lips_trajectories")

SERVO_ORDER = (
    "DER_TOP", "IZQ_TOP",
    "DER_BOTTOM", "IZQ_BOTTOM",
    "JAW_LEFT", "JAW_RIGHT",
    "UP_PISTON", "LOW_RACK",
)

SERVO_CONFIG = {
    "DER_TOP": {
        "id": 5, "group": "corners", "label": "Esquina Der. Sup (5-Barras)",
        "home_tick": 2048, "dir": -1, "min_tick": 1138, "max_tick": 2958,
        "min_deg": 100.0, "max_deg": 260.0,
        "dtheta_col": "DER_dtheta1_from_90_deg",
        "omega_col":  "DER_omega1_speed_degs",
        "alpha_col":  "DER_alpha1_accel_degs2",
    },
    "DER_BOTTOM": {
        "id": 6, "group": "corners", "label": "Esquina Der. Inf (5-Barras)",
        "home_tick": 2048, "dir": -1, "min_tick": 1138, "max_tick": 2958,
        "min_deg": 100.0, "max_deg": 260.0,
        "dtheta_col": "DER_dtheta2_from_neg90_deg",
        "omega_col":  "DER_omega2_speed_degs",
        "alpha_col":  "DER_alpha2_accel_degs2",
    },
    "IZQ_TOP": {
        "id": 7, "group": "corners", "label": "Esquina Izq. Sup (5-Barras)",
        "home_tick": 2048, "dir": +1, "min_tick": 1138, "max_tick": 2958,
        "min_deg": 100.0, "max_deg": 260.0,
        "dtheta_col": "IZQ_dtheta1_from_90_deg",
        "omega_col":  "IZQ_omega1_speed_degs",
        "alpha_col":  "IZQ_alpha1_accel_degs2",
    },
    "IZQ_BOTTOM": {
        "id": 8, "group": "corners", "label": "Esquina Izq. Inf (5-Barras)",
        "home_tick": 2048, "dir": +1, "min_tick": 1138, "max_tick": 2958,
        "min_deg": 100.0, "max_deg": 260.0,
        "dtheta_col": "IZQ_dtheta2_from_neg90_deg",
        "omega_col":  "IZQ_omega2_speed_degs",
        "alpha_col":  "IZQ_alpha2_accel_degs2",
    },
    "JAW_LEFT": {
        "id": 1, "group": "jaw", "label": "Mandibula Izq. (180°->185°)",
        "home_tick": 2048, "dir": +1, "min_tick": 2048, "max_tick": 2105,
        "min_deg": 180.0, "max_deg": 185.0,
        "dtheta_col": "JAW_dtheta_deg",
        "omega_col":  "JAW_omega_speed_degs",
        "alpha_col":  "JAW_alpha_accel_degs2",
    },
    "JAW_RIGHT": {
        "id": 2, "group": "jaw", "label": "Mandibula Der. (90°->85°)",
        "home_tick": 1024, "dir": -1, "min_tick": 967, "max_tick": 1024,
        "min_deg": 85.0, "max_deg": 90.0,
        "dtheta_col": "JAW_dtheta_deg",
        "omega_col":  "JAW_omega_speed_degs",
        "alpha_col":  "JAW_alpha_accel_degs2",
    },
    # "JAW_LEFT": {
    #     "id": 1, "group": "jaw", "label": "Mandibula Izq. (180°->195°)",
    #     "home_tick": 2048, "dir": +1, "min_tick": 2048, "max_tick": 2219,
    #     "min_deg": 180.0, "max_deg": 195.0,
    #     "dtheta_col": "JAW_dtheta_deg",
    #     "omega_col":  "JAW_omega_speed_degs",
    #     "alpha_col":  "JAW_alpha_accel_degs2",
    # },
    # "JAW_RIGHT": {
    #     "id": 2, "group": "jaw", "label": "Mandibula Der. (180°->165°)",
    #     "home_tick": 2048, "dir": -1, "min_tick": 1877, "max_tick": 2048,
    #     "min_deg": 165.0, "max_deg": 180.0,
    #     "dtheta_col": "JAW_dtheta_deg",
    #     "omega_col":  "JAW_omega_speed_degs",
    #     "alpha_col":  "JAW_alpha_accel_degs2",
    # },
    "UP_PISTON": {
        "id": 9, "group": "upper", "label": "Labio Sup. Piston (180°->140°)",
        "home_tick": 2048, "dir": -1, "min_tick": 1593, "max_tick": 2048,
        "min_deg": 140.0, "max_deg": 180.0,
        "dtheta_col": "UP_dtheta_deg",
        "omega_col":  "UP_omega_speed_degs",
        "alpha_col":  "UP_alpha_accel_degs2",
    },
    "LOW_RACK": {
        "id": 10, "group": "rack", "label": "Labio Inf. Cremallera (81°..150°)",
        "home_tick": 859, "dir": +1, "min_tick": 580, "max_tick": 1138,
        "min_deg": 51.0, "max_deg": 100.0,
        "dtheta_col": "LOW_dtheta_deg",
        "omega_col":  "LOW_omega_speed_degs",
        "alpha_col":  "LOW_alpha_accel_degs2",
    },
}

# Default Forward-Kinematics parameters (overridden automatically if active_mechanism_params.json exists)
DEFAULT_FK_PARAMS = {
    "eye_corner_scale_mm": 35.0,
    "L0": 24.80, "L1": 23.50, "L2": 23.50, "L3": 100.97, "L4": 63.31,
    "psi_deg": 71.00, "alpha_deg": 8.44,
    # "jaw_radius_mm": 35.0 / np.sin(np.radians(15.0)),
    "jaw_radius_mm": 35.0 / np.sin(np.radians(5.0)),
    "pinion_pitch_diam_mm": 22.10, "rack_tilt_deg": 12.50, "low_gain": 1.0,
    "up_L1": 33.24, "up_L2": 46.14, "up_L3": 43.50, "up_theta0_deg": 45.0,
    "up_offset_x": 19.00, "up_gain": 3.0,
}

POINT_OPTIONS = [
    ("ALL_5", "TODOS (Panel 5 Puntos Actuados: XY + Tiempo)"),
    ("BOCA_DER", "BOCA_DER · Right mouth corner (291) [Esquina Der. IDs 5,6]"),
    ("BOCA_IZQ", "BOCA_IZQ · Left mouth corner (61) [Esquina Izq. IDs 7,8]"),
    ("BOCA_SUP_EXT", "BOCA_SUP_EXT · Upper outer lip (0) [Piston Sup. ID 9]"),
    ("BOCA_INF_EXT", "BOCA_INF_EXT · Lower outer lip (17) [Cremallera ID 10 + Mandibula]"),
    ("BARBILLA", "BARBILLA · Chin (152) [Mandibula IDs 1,2]"),
    ("SERVOS_8", "SERVOS · Angulo Comando vs Real Medido (8 Motores)"),
]

POINT_LABELS = {
    "BOCA_SUP_EXT": "Upper outer lip (0)",
    "BOCA_INF_EXT": "Lower outer lip (17)",
    "BOCA_IZQ": "Left mouth corner (61)",
    "BOCA_DER": "Right mouth corner (291)",
    "BARBILLA": "Chin (152)",
}
POINT_COLORS = {
    "BOCA_SUP_EXT": "#1f77b4",
    "BOCA_INF_EXT": "#ff7f0e",
    "BOCA_IZQ": "#9467bd",
    "BOCA_DER": "#8c564b",
    "BARBILLA": "#e377c2",
}

BG     = "#0d1524"
PANEL  = "#182338"
PANEL2 = "#202f48"
TEXT   = "#eaf1fb"
MUTED  = "#a6b6cf"
BLUE   = "#4ea8ff"
GREEN  = "#49d9ac"
WARN   = "#e6bb68"
DANGER = "#f29aa2"
PURPLE = "#b88cff"
BORDER = "#30415b"


# ==============================================================================
# 2. CONVERSIONES Y CINEMATICA DIRECTA (FORWARD KINEMATICS PARA VALIDACION)
# ==============================================================================
def scs_lobyte(val: int) -> int:
    return int(val) & 0xFF


def scs_hibyte(val: int) -> int:
    return (int(val) >> 8) & 0xFF


def ticks_to_servo_deg(ticks: int) -> float:
    return float(ticks / STEPS_PER_DEG)


def servo_deg_to_ticks(deg: float, cfg: dict | None = None) -> int:
    raw = round(float(deg) * STEPS_PER_DEG)
    if cfg is not None:
        return int(np.clip(raw, cfg["min_tick"], cfg["max_tick"]))
    return int(np.clip(raw, 50, 4045))


def dtheta_to_ticks(dtheta_deg: float, cfg: dict) -> int:
    ticks = round(cfg["home_tick"] + cfg["dir"] * dtheta_deg * STEPS_PER_DEG)
    return int(np.clip(ticks, cfg["min_tick"], cfg["max_tick"]))


def dtheta_to_servo_deg(dtheta_deg: float, cfg: dict) -> float:
    return ticks_to_servo_deg(dtheta_to_ticks(dtheta_deg, cfg))


def ticks_to_dtheta_deg(ticks: int, cfg: dict) -> float:
    return float((ticks - cfg["home_tick"]) * cfg["dir"] / STEPS_PER_DEG)


def safe_speed_degs_to_steps(omega_degs: float, time_scale: float, max_speed_cap: int) -> int:
    safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
    steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
    return int(np.clip(steps_s, MIN_SPEED_STEPS, safe_cap))


def safe_accel_degs2_to_unit(alpha_degs2: float, time_scale: float) -> int:
    acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
    return int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))


def extract_syllable_name(csv_path: Path) -> str:
    for prefix in ("mouth_trajectory_", "servo_trajectory_", "center_lips_trajectory_"):
        if csv_path.stem.lower().startswith(prefix):
            return csv_path.stem[len(prefix):].upper()
    return csv_path.stem.upper()


def solve_5bar_fk(dtheta1_deg: float, dtheta2_deg: float, side: str, fk: dict) -> tuple[float, float]:
    """Forward kinematics for the 5-bar linkage: returns frontal (Delta_X, Delta_Y) in eye-distance units."""
    L0, L1, L2, L3, L4 = fk["L0"], fk["L1"], fk["L2"], fk["L3"], fk["L4"]

    def get_P(th1_deg: float, th2_deg: float):
        t1, t2 = np.radians(th1_deg), np.radians(th2_deg)
        A = np.array([L1 * np.cos(t1), L0 + L1 * np.sin(t1)])
        B = np.array([L2 * np.cos(t2), L2 * np.sin(t2)])
        d_vec = B - A
        d = np.linalg.norm(d_vec)
        if d <= abs(L3 - L4) or d >= (L3 + L4):
            return np.array([62.901, -30.684])
        a = (L3**2 - L4**2 + d**2) / (2.0 * d)
        h = np.sqrt(max(L3**2 - a**2, 0.0))
        mid = A + (a / d) * d_vec
        perp = np.array([-d_vec[1] / d, d_vec[0] / d])
        P1, P2 = mid + h * perp, mid - h * perp
        return P1 if P1[0] >= P2[0] else P2

    P_home = get_P(90.0, -90.0)
    P_curr = get_P(90.0 + dtheta1_deg, -90.0 + dtheta2_deg)
    du, dv = P_curr[0] - P_home[0], P_curr[1] - P_home[1]

    psi = np.radians(fk["psi_deg"])
    alpha = np.radians(fk["alpha_deg"])
    du_horiz = du * np.cos(alpha) - dv * np.sin(alpha)
    dv_vert  = du * np.sin(alpha) + dv * np.cos(alpha)

    dX_medial = du_horiz * np.cos(psi)
    dX_front_mm = -dX_medial if side.upper() == "DER" else dX_medial
    dY_front_mm = dv_vert

    scale = fk["eye_corner_scale_mm"]
    return float(dX_front_mm / scale), float(-dY_front_mm / scale)


def reconstruct_measured_landmarks(df_traj: pd.DataFrame, df_fb: pd.DataFrame, fk: dict) -> pd.DataFrame:
    """Reconstructs achieved anatomical Delta_X / Delta_Y (in eye-distance units) from measured servo angles."""
    scale = fk["eye_corner_scale_mm"]
    n = len(df_fb)
    out = {"phase_pct": df_fb["phase_pct"].to_numpy(dtype=float)}

    # 1. BOCA_DER and BOCA_IZQ from 5-bar encoders
    for side in ("DER", "IZQ"):
        top_col = f"{side}_TOP_meas_dtheta_deg"
        bot_col = f"{side}_BOTTOM_meas_dtheta_deg"
        if top_col in df_fb.columns and bot_col in df_fb.columns and df_fb[top_col].notna().any():
            dx_list, dy_list = [], []
            for dt1, dt2 in zip(df_fb[top_col], df_fb[bot_col]):
                if np.isfinite(dt1) and np.isfinite(dt2):
                    dx, dy = solve_5bar_fk(float(dt1), float(dt2), side, fk)
                else:
                    dx, dy = np.nan, np.nan
                dx_list.append(dx)
                dy_list.append(dy)
            out[f"BOCA_{side}_Delta_X"] = np.array(dx_list)
            out[f"BOCA_{side}_Delta_Y"] = np.array(dy_list)

    # 2. BARBILLA from Jaw encoders (ID 1 & ID 2)
    jaw_cols = [c for c in ("JAW_LEFT_meas_dtheta_deg", "JAW_RIGHT_meas_dtheta_deg") if c in df_fb.columns]
    if jaw_cols and df_fb[jaw_cols].notna().any().any():
        dtheta_jaw = df_fb[jaw_cols].mean(axis=1).to_numpy(dtype=float)
        # opening_mm = fk["jaw_radius_mm"] * np.sin(np.radians(np.clip(dtheta_jaw, 0.0, 20.0)))
        opening_mm = fk["jaw_radius_mm"] * np.sin(np.radians(np.clip(dtheta_jaw, 0.0, 5.5)))
        out["BARBILLA_Delta_X"] = np.zeros(n)
        out["BARBILLA_Delta_Y"] = opening_mm / scale  # +Y is downward
        dy_jaw_ach_mm = -opening_mm
    else:
        dy_jaw_ach_mm = df_traj["JAW_dy_achieved_mm"].to_numpy(dtype=float) if "JAW_dy_achieved_mm" in df_traj.columns else np.zeros(n)

    # 3. BOCA_INF_EXT from Lower Lip Rack (ID 10) + Jaw
    if "LOW_RACK_meas_dtheta_deg" in df_fb.columns and df_fb["LOW_RACK_meas_dtheta_deg"].notna().any():
        dtheta_rack = df_fb["LOW_RACK_meas_dtheta_deg"].to_numpy(dtype=float)
        mm_per_deg = (np.pi * fk["pinion_pitch_diam_mm"]) / 360.0
        s_rack_mm = dtheta_rack * mm_per_deg
        tilt_rad = np.radians(fk["rack_tilt_deg"])
        dy_low_mm = dy_jaw_ach_mm + (s_rack_mm * np.cos(tilt_rad)) / max(fk["low_gain"], 1e-6)
        out["BOCA_INF_EXT_Delta_X"] = np.zeros(n)
        out["BOCA_INF_EXT_Delta_Y"] = -dy_low_mm / scale

    # 4. BOCA_SUP_EXT from Upper Lip 3-Link Piston (ID 9)
    if "UP_PISTON_meas_dtheta_deg" in df_fb.columns and df_fb["UP_PISTON_meas_dtheta_deg"].notna().any():
        dtheta_up = df_fb["UP_PISTON_meas_dtheta_deg"].to_numpy(dtype=float)
        L1, L2, off_x = fk["up_L1"], fk["up_L2"], fk["up_offset_x"]
        th0 = np.radians(fk["up_theta0_deg"])
        y_B0 = L1 * np.sin(th0) - np.sqrt(max(L2**2 - (L1 * np.cos(th0) - off_x)**2, 0.0))
        th_arr = np.radians(fk["up_theta0_deg"] + dtheta_up)
        y_B_meas = L1 * np.sin(th_arr) - np.sqrt(np.maximum(L2**2 - (L1 * np.cos(th_arr) - off_x)**2, 0.0))
        ds_meas_mm = (y_B_meas - y_B0) / max(fk["up_gain"], 1e-6)
        out["BOCA_SUP_EXT_Delta_X"] = np.zeros(n)
        out["BOCA_SUP_EXT_Delta_Y"] = -ds_meas_mm / scale

    return pd.DataFrame(out)


# ==============================================================================
# 3. HILO DE COMUNICACION SERIE (8 SERVOS + GANANCIA EN TIEMPO REAL)
# ==============================================================================
class ServoWorker(threading.Thread):
    def __init__(
        self,
        com_port: str,
        messages: queue.Queue,
        events: queue.Queue,
        stop_event: threading.Event,
        live_gains: dict,
    ):
        super().__init__(daemon=True)
        self.com_port = com_port
        self.messages = messages
        self.events = events
        self.stop_event = stop_event
        self.live_gains = live_gains  # Diccionario compartido actualizado en tiempo real desde la GUI
        self.monitoring = False

    def emit(self, *payload):
        self.events.put(payload)

    def get_effective_gain(self, group_name: str) -> float:
        """Calcula Ganancia_Global * Ganancia_Subsistema en tiempo real."""
        master = float(self.live_gains.get("master", 1.0))
        sub = float(self.live_gains.get(group_name, 1.0))
        return max(0.0, master * sub)

    def write_pos_ex(self, servo, cfg: dict, pos_ticks: int, speed_steps: int, acc_unit: int):
        safe_pos = int(np.clip(pos_ticks, cfg["min_tick"], cfg["max_tick"]))
        safe_spd = int(np.clip(speed_steps, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
        safe_acc = int(np.clip(acc_unit, 1, SAFE_MAX_ACC_UNIT))
        servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 1)
        return servo.WritePosEx(cfg["id"], safe_pos, safe_spd, safe_acc)

    def read_pos(self, servo, servo_id: int) -> tuple[int, int]:
        pos, comm, _ = servo.ReadPos(servo_id)
        return pos, comm

    def read_all_positions(self, servo, servo_map: dict):
        readings = {}
        for name, cfg in servo_map.items():
            pos, comm = self.read_pos(servo, cfg["id"])
            if comm == COMM_SUCCESS:
                readings[name] = {
                    "ok": True,
                    "id": cfg["id"],
                    "ticks": pos,
                    "deg": ticks_to_servo_deg(pos),
                    "dtheta": ticks_to_dtheta_deg(pos, cfg),
                }
            else:
                readings[name] = {"ok": False, "id": cfg["id"]}
        self.emit("positions", readings)

    def release_all_torque(self, servo, servo_map: dict):
        for cfg in servo_map.values():
            servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

    def run(self):
        port = None
        servo = None
        try:
            port = PortHandler(self.com_port)
            servo = STSDriver(port)
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
                                    "dtheta": ticks_to_dtheta_deg(pos, cfg),
                                }
                            else:
                                status[name] = {"ok": False, "id": cfg["id"]}
                        self.emit("ping_result", status)

                    elif cmd == "set_monitor":
                        enable, servo_map = action[1], action[2]
                        self.monitoring = bool(enable)
                        if self.monitoring:
                            self.release_all_torque(servo, servo_map)
                            self.emit("info", "Monitor en vivo ACTIVO (torque liberado en los 8 servos).")
                        else:
                            self.emit("info", "Monitor en vivo detenido.")
                        self.emit("monitor_state", self.monitoring)

                    elif cmd == "read_once":
                        self.read_all_positions(servo, action[1])

                    elif cmd == "go_home":
                        active_map, speed_cap = action[1], action[2]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        safe_home_speed = min(400, int(speed_cap))
                        self.emit("info", f"Moviendo {len(active_map)} servo(s) activos a su posicion Home neutral...")
                        for cfg in active_map.values():
                            self.write_pos_ex(servo, cfg, cfg["home_tick"], speed_steps=safe_home_speed, acc_unit=10)
                        time.sleep(0.9)
                        self.read_all_positions(servo, SERVO_CONFIG)
                        self.emit("info", "Servos activos posicionados en Home neutral.")

                    elif cmd == "move_single":
                        servo_map, name, target_deg, speed_cap = action[1:]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        cfg = servo_map[name]
                        ticks = servo_deg_to_ticks(target_deg, cfg)
                        safe_spd = min(350, int(speed_cap))
                        self.write_pos_ex(servo, cfg, ticks, speed_steps=safe_spd, acc_unit=12)
                        time.sleep(0.15)
                        self.read_all_positions(servo, servo_map)
                        self.emit("info", f"{name} (ID {cfg['id']}) enviado a {ticks_to_servo_deg(ticks):.1f}° ({ticks} ticks)")

                    elif cmd == "release":
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        self.release_all_torque(servo, action[1])
                        self.emit("info", "Torque liberado en todos los servos.")

                    elif cmd == "play_csv":
                        csv_path, time_scale, max_speed_cap, save_feedback, active_map = action[1:]
                        self.monitoring = False
                        self.emit("monitor_state", False)
                        self.stop_event.clear()
                        self.run_trajectory(
                            port, servo, Path(csv_path), float(time_scale), int(max_speed_cap), bool(save_feedback), active_map
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

    def load_merged_dataframe(self, csv_path: Path) -> pd.DataFrame:
        """Loads a unified mouth_trajectory CSV or automatically merges corner + center CSVs if separated."""
        df = pd.read_csv(csv_path)
        syl = extract_syllable_name(csv_path)
        parent = csv_path.parent.parent

        if "JAW_dtheta_deg" not in df.columns:
            center_cand = parent / "center_lips_trajectories" / f"center_lips_trajectory_{syl}.csv"
            if center_cand.is_file():
                df_c = pd.read_csv(center_cand)
                extra_cols = [c for c in df_c.columns if c not in df.columns]
                df = pd.concat([df, df_c[extra_cols]], axis=1)

        if "DER_dtheta1_from_90_deg" not in df.columns:
            corner_cand = parent / "servo_trajectories" / f"servo_trajectory_{syl}.csv"
            if corner_cand.is_file():
                df_k = pd.read_csv(corner_cand)
                extra_cols = [c for c in df_k.columns if c not in df.columns]
                df = pd.concat([df, df_k[extra_cols]], axis=1)

        return df

    def run_trajectory(
        self,
        port: PortHandler,
        servo,
        csv_path: Path,
        time_scale: float,
        max_speed_cap: int,
        save_feedback: bool,
        active_map: dict,
    ):
        df = self.load_merged_dataframe(csv_path)
        for col in ("time_s", "time_ms", "phase_pct"):
            if col not in df.columns:
                raise ValueError(f"El CSV no contiene la columna requerida '{col}'")

        run_map = {
            name: cfg for name, cfg in active_map.items()
            if cfg["dtheta_col"] in df.columns
        }
        if not run_map:
            raise ValueError("Ninguno de los servos seleccionados tiene columnas en este archivo CSV.")

        time_scale = max(1.0, float(time_scale))
        safe_cap = int(np.clip(max_speed_cap, MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
        total_ms = float(df["time_ms"].iloc[-1]) * time_scale
        syl_name = extract_syllable_name(csv_path)

        master_g = float(self.live_gains.get("master", 1.0))
        self.emit("playback_started", syl_name, len(df), time_scale, total_ms, len(run_map), master_g)

        # 1. Pre-position active servos to 0% initial pose (scaled by live amplitude gain)
        init_speed = min(400, safe_cap)
        for name, cfg in run_map.items():
            gain = self.get_effective_gain(cfg["group"])
            init_dtheta = float(df[cfg["dtheta_col"]].iloc[0]) * gain
            init_ticks = dtheta_to_ticks(init_dtheta, cfg)
            self.write_pos_ex(servo, cfg, init_ticks, speed_steps=init_speed, acc_unit=10)

        t_wait = time.perf_counter()
        while (time.perf_counter() - t_wait) < 0.8:
            if self.stop_event.is_set():
                self.release_all_torque(servo, run_map)
                self.emit("playback_stopped", "Reproduccion cancelada antes de iniciar.")
                return
            time.sleep(0.02)

        # 2. Stream all 101 steps synchronously (reading live amplitude gain at every step!)
        sync_write = getattr(servo, "groupSyncWrite", None)
        feedback_rows = []
        total_rows = len(df)
        t_start = time.perf_counter()

        for idx, row in df.iterrows():
            if self.stop_event.is_set():
                self.release_all_torque(servo, run_map)
                self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
                return

            target_time_s = float(row["time_s"]) * time_scale
            if sync_write is not None:
                sync_write.clearParam()

            log_item = {
                "phase_pct": float(row["phase_pct"]),
                "time_ms": float(row["time_ms"]) * time_scale,
                "amp_gain_master": float(self.live_gains.get("master", 1.0)),
            }
            cmd_snapshot = {}
            direct_queue = []

            for name, cfg in run_map.items():
                # Lee la ganancia en tiempo real en cada instante (permite mover el slider en vivo)
                gain = self.get_effective_gain(cfg["group"])

                dtheta = float(row[cfg["dtheta_col"]]) * gain
                omega  = float(row[cfg["omega_col"]]) * gain
                alpha  = float(row[cfg["alpha_col"]]) * gain

                pos_ticks   = dtheta_to_ticks(dtheta, cfg)
                speed_steps = safe_speed_degs_to_steps(omega, time_scale, safe_cap)
                acc_unit    = safe_accel_degs2_to_unit(alpha, time_scale)

                if sync_write is not None and hasattr(servo, "SyncWritePosEx"):
                    servo.SyncWritePosEx(cfg["id"], pos_ticks, speed_steps, acc_unit)
                else:
                    direct_queue.append((cfg, pos_ticks, speed_steps, acc_unit))

                cmd_deg = ticks_to_servo_deg(pos_ticks)
                log_item[f"{name}_gain_used"] = gain
                log_item[f"{name}_target_dtheta_deg"] = dtheta
                log_item[f"{name}_cmd_deg"]   = cmd_deg
                log_item[f"{name}_cmd_ticks"] = pos_ticks
                log_item[f"{name}_cmd_speed"] = speed_steps
                log_item[f"{name}_cmd_acc"]   = acc_unit
                cmd_snapshot[name] = {
                    "cmd_deg": cmd_deg,
                    "cmd_ticks": pos_ticks,
                    "cmd_speed": speed_steps,
                    "gain": gain,
                }

            while (time.perf_counter() - t_start) < target_time_s:
                if self.stop_event.is_set():
                    break

            if self.stop_event.is_set():
                self.release_all_torque(servo, run_map)
                self.emit("playback_stopped", "PARO DE EMERGENCIA: Reproduccion abortada y torque liberado.")
                return

            if sync_write is not None and hasattr(servo, "SyncWritePosEx"):
                sync_write.txPacket()
            else:
                for cfg_i, pticks, ssteps, aunit in direct_queue:
                    self.write_pos_ex(servo, cfg_i, pticks, ssteps, aunit)

            meas_snapshot = {}
            for name, cfg in run_map.items():
                pos_meas, comm = self.read_pos(servo, cfg["id"])
                if comm == COMM_SUCCESS:
                    meas_deg = ticks_to_servo_deg(pos_meas)
                    meas_dtheta = ticks_to_dtheta_deg(pos_meas, cfg)
                    log_item[f"{name}_meas_ticks"] = pos_meas
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
                    log_item[f"{name}_meas_ticks"] = np.nan
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
        df_fb = pd.DataFrame(feedback_rows)
        df_meas_landmarks = reconstruct_measured_landmarks(df, df_fb, DEFAULT_FK_PARAMS)

        out_csv_msg = ""
        if save_feedback and not df_fb.empty:
            out_fb_csv = csv_path.with_name(f"mouth_feedback_{syl_name}.csv")
            out_rob_csv = csv_path.with_name(f"robot_measured_{syl_name}.csv")
            df_fb.to_csv(out_fb_csv, index=False)
            df_meas_landmarks.to_csv(out_rob_csv, index=False)
            out_csv_msg = f" | Guardados: {out_fb_csv.name} y {out_rob_csv.name}"

        self.emit(
            "playback_finished",
            syl_name,
            elapsed_ms,
            out_csv_msg,
            df,
            df_fb,
            df_meas_landmarks,
        )


# ==============================================================================
# 4. INTERFAZ GRAFICA UNIFICADA DE 8 SERVOS + GANANCIA DE AMPLITUD EN VIVO
# ==============================================================================
class UnifiedMouthServoGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Control Orofacial Unificado FEETECH STS3215 · 8 Servos + Ganancia de Amplitud en Tiempo Real")
        self.root.geometry("1320x980")
        self.root.minsize(1100, 820)
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

        # Active mechanism group checkboxes
        self.use_corners_var = tk.BooleanVar(value=True)
        self.use_jaw_var     = tk.BooleanVar(value=True)
        self.use_upper_var   = tk.BooleanVar(value=True)
        self.use_rack_var    = tk.BooleanVar(value=True)

        # Speed & Motor Cap Variables
        self.speed_mult_var = tk.DoubleVar(value=DEFAULT_SPEED_MULT)
        self.speed_label_var = tk.StringVar()
        self.max_steps_var = tk.IntVar(value=SAFE_DEFAULT_MAX_STEP)
        self.max_steps_label_var = tk.StringVar()

        # Real-Time Amplitude Gain Variables (Master + Per-Subsystem)
        self.amp_gain_master_var  = tk.DoubleVar(value=DEFAULT_AMP_GAIN)
        self.amp_gain_label_var   = tk.StringVar()
        self.amp_gain_corners_var = tk.DoubleVar(value=1.00)
        self.amp_gain_jaw_var     = tk.DoubleVar(value=1.00)
        self.amp_gain_upper_var   = tk.DoubleVar(value=1.00)
        self.amp_gain_rack_var    = tk.DoubleVar(value=1.00)

        # Shared thread-safe dictionary read by ServoWorker on every step
        self.live_gains = {
            "master": 1.00,
            "corners": 1.00,
            "jaw": 1.00,
            "upper": 1.00,
            "rack": 1.00,
        }

        self.save_log_var = tk.BooleanVar(value=True)
        self.auto_plot_var = tk.BooleanVar(value=True)
        self.selected_point_var = tk.StringVar(value=POINT_OPTIONS[0][1])

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="Fase: 0% (En espera)")
        self.status_var = tk.StringVar(value="Desconectado. Verifica el puerto COM y presiona Conectar.")

        # Last recorded run data for instant interactive comparison plotting
        self.last_syl: str | None = None
        self.last_df_traj: pd.DataFrame | None = None
        self.last_df_fb: pd.DataFrame | None = None
        self.last_df_meas: pd.DataFrame | None = None

        self.servo_cards: dict[str, dict] = {}
        self.quick_syl_buttons: list[tk.Button] = []

        self.configure_ttk_styles()
        self.build_ui()
        self.refresh_syllable_list()
        self.update_speed_labels()
        self.update_gain_labels()
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

    def label(self, parent, text, size=10, fg=TEXT, bold=False, **kw):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=fg,
            bg=kw.pop("bg", PANEL),
            **kw,
        )

    def button(self, parent, text, command, bg=BLUE, fg=BG, padx=11, pady=6, **kw):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=GREEN,
            activeforeground=BG,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=padx,
            pady=pady,
            **kw,
        )

    def get_active_servo_map(self) -> dict:
        enabled_groups = set()
        if self.use_corners_var.get():
            enabled_groups.add("corners")
        if self.use_jaw_var.get():
            enabled_groups.add("jaw")
        if self.use_upper_var.get():
            enabled_groups.add("upper")
        if self.use_rack_var.get():
            enabled_groups.add("rack")
        return {k: v for k, v in SERVO_CONFIG.items() if v["group"] in enabled_groups}

    def build_ui(self):
        head = tk.Frame(self.root, bg=BG, padx=20, pady=10)
        head.pack(fill="x")
        self.label(
            head,
            "CONTROL OROFACIAL UNIFICADO STS3215 · 8 SERVOS + GANANCIA DE AMPLITUD EN TIEMPO REAL",
            size=16,
            bold=True,
            bg=BG,
        ).pack(anchor="w")
        self.label(
            head,
            "Esquinas 5-Barras (IDs 5,6,7,8) · Mandibula (IDs 1,2) · Labio Sup. Piston (ID 9) · Labio Inf. Cremallera (ID 10)",
            size=9,
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(2, 0))

        toolbar = tk.Frame(self.root, bg=PANEL, padx=14, pady=9, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=20, pady=(0, 8))

        self.label(toolbar, "Puerto:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))
        self.port_entry = tk.Entry(
            toolbar,
            textvariable=self.port_var,
            width=8,
            font=("Segoe UI", 10, "bold"),
            justify="center",
            relief="flat",
            bg="#e7eef9",
            fg="#172033",
        )
        self.port_entry.pack(side="left", padx=(0, 10), ipady=3)

        self.connect_btn = self.button(toolbar, "Conectar", self.connect, bg=GREEN)
        self.connect_btn.pack(side="left", padx=(0, 7))

        self.disc_btn = self.button(toolbar, "Desconectar", self.disconnect, bg=PANEL2, fg=TEXT)
        self.disc_btn.pack(side="left", padx=(0, 7))

        self.ping_btn = self.button(toolbar, "Comprobar 8 Servos", self.ping_servos, bg=BLUE)
        self.ping_btn.pack(side="left", padx=(0, 7))

        self.home_btn = self.button(toolbar, "Ir a Home Neutral", self.go_home, bg=BLUE)
        self.home_btn.pack(side="left", padx=(0, 7))

        self.monitor_btn = self.button(toolbar, "Monitor en Vivo (OFF)", self.toggle_monitor, bg=PANEL2, fg=TEXT)
        self.monitor_btn.pack(side="left", padx=(0, 7))

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

        self.build_syllable_and_comparison_panel(content)

        grid_frame = tk.Frame(content, bg=BG)
        grid_frame.pack(fill="both", expand=True, pady=(4, 6))
        grid_frame.grid_columnconfigure(0, weight=1, uniform="servos")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="servos")

        for idx, name in enumerate(SERVO_ORDER):
            self.build_servo_card(grid_frame, idx, name, SERVO_CONFIG[name])

        tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg="#263550",
            fg="#f6f9ff",
            font=("Segoe UI", 10),
            padx=17,
            pady=8,
        ).pack(side="bottom", fill="x")

    def build_syllable_and_comparison_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="x", pady=(0, 6))

        top_row = tk.Frame(panel, bg=PANEL)
        top_row.pack(fill="x")

        self.label(top_row, "REPRODUCCION Y GRUPOS ACTIVOS", size=12, bold=True).pack(side="left", padx=(0, 14))
        self.label(top_row, "Silaba:", size=10, fg=MUTED).pack(side="left", padx=(0, 6))

        self.syl_combo = ttk.Combobox(
            top_row,
            textvariable=self.selected_syllable,
            state="readonly",
            width=14,
            font=("Segoe UI", 10, "bold"),
            style="Syllable.TCombobox",
        )
        self.syl_combo.pack(side="left", padx=(0, 8))
        self.syl_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_syllable_selected())

        self.button(top_row, "Carpeta...", self.choose_folder, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(top_row, "CSV...", self.choose_csv_file, bg=PANEL2, fg=TEXT).pack(side="left", padx=(0, 5))
        self.button(top_row, "Recargar", self.refresh_syllable_list, bg=PANEL2, fg=TEXT).pack(side="left")

        # Group filter checkboxes
        grp_row = tk.Frame(panel, bg=PANEL2, padx=10, pady=6)
        grp_row.pack(fill="x", pady=(8, 4))
        self.label(grp_row, "Mecanismos a mover:", size=9, bold=True, bg=PANEL2).pack(side="left", padx=(0, 10))
        for var, txt in (
            (self.use_corners_var, "Esquinas 5-Barras (IDs 5, 6, 7, 8)"),
            (self.use_jaw_var, "Mandibula / Chin (IDs 1, 2)"),
            (self.use_upper_var, "Labio Sup. Piston (ID 9)"),
            (self.use_rack_var, "Labio Inf. Cremallera (ID 10)"),
        ):
            tk.Checkbutton(
                grp_row, text=txt, variable=var, bg=PANEL2, fg=TEXT,
                activebackground=PANEL2, activeforeground=GREEN, selectcolor=PANEL,
                highlightthickness=0, font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(0, 14))

        self.quick_syl_frame = tk.Frame(panel, bg=PANEL)
        self.quick_syl_frame.pack(fill="x", pady=(6, 2))

        self.label(panel, "", size=9, fg=GREEN, textvariable=self.csv_info_var).pack(anchor="w", pady=(2, 6))

        # --- SLIDERS ROW: SPEED, MOTOR CAP & REAL-TIME AMPLITUDE GAIN ---
        sliders_row = tk.Frame(panel, bg=PANEL)
        sliders_row.pack(fill="x", pady=(2, 6))
        sliders_row.grid_columnconfigure(0, weight=3)
        sliders_row.grid_columnconfigure(1, weight=2)
        sliders_row.grid_columnconfigure(2, weight=4)

        # 1) Speed Box
        speed_box = tk.Frame(sliders_row, bg=PANEL2, padx=10, pady=8)
        speed_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        spd_top = tk.Frame(speed_box, bg=PANEL2)
        spd_top.pack(fill="x")
        self.label(spd_top, "Velocidad Reprod. (0.20x-1.00x)", size=9, bold=True, bg=PANEL2).pack(side="left")
        tk.Label(spd_top, textvariable=self.speed_label_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=GREEN).pack(side="right")

        self.speed_slider = tk.Scale(
            speed_box, from_=MIN_SPEED_MULT, to=MAX_SAFE_SPEED_MULT, resolution=0.01,
            orient="horizontal", variable=self.speed_mult_var, showvalue=False, sliderlength=16,
            bg=PANEL2, fg=TEXT, troughcolor="#384d6c", highlightthickness=0, activebackground=GREEN,
            command=lambda _v: self.update_speed_labels(),
        )
        self.speed_slider.pack(fill="x", pady=(4, 4))

        presets = tk.Frame(speed_box, bg=PANEL2)
        presets.pack(fill="x")
        for mult, title in ((0.25, "0.25x"), (0.33, "0.33x"), (0.50, "0.50x"), (0.75, "0.75x"), (1.00, "1.00x")):
            self.button(presets, title, lambda m=mult: self.set_speed_preset(m), bg=PANEL, fg=TEXT, padx=6, pady=2).pack(side="left", padx=(0, 3))

        # 2) Motor Speed Cap Box
        cap_box = tk.Frame(sliders_row, bg=PANEL2, padx=10, pady=8)
        cap_box.grid(row=0, column=1, sticky="nsew", padx=(0, 6))
        cap_top = tk.Frame(cap_box, bg=PANEL2)
        cap_top.pack(fill="x")
        self.label(cap_top, "Tope Max. Motor", size=9, bold=True, bg=PANEL2).pack(side="left")
        tk.Label(cap_top, textvariable=self.max_steps_label_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=WARN).pack(side="right")

        self.cap_slider = tk.Scale(
            cap_box, from_=300, to=SAFE_HARD_LIMIT_STEP, resolution=50,
            orient="horizontal", variable=self.max_steps_var, showvalue=False, sliderlength=16,
            bg=PANEL2, fg=TEXT, troughcolor="#384d6c", highlightthickness=0, activebackground=WARN,
            command=lambda _v: self.update_speed_labels(),
        )
        self.cap_slider.pack(fill="x", pady=(4, 4))
        self.label(cap_box, "Protege engranes (pasos/s).", size=8, fg=MUTED, bg=PANEL2).pack(anchor="w")

        # 3) Real-Time Amplitude Gain Box (Master + Per-Subsystem Multipliers)
        gain_box = tk.Frame(sliders_row, bg=PANEL2, padx=10, pady=8, highlightbackground=PURPLE, highlightthickness=1)
        gain_box.grid(row=0, column=2, sticky="nsew")

        gain_top = tk.Frame(gain_box, bg=PANEL2)
        gain_top.pack(fill="x")
        self.label(gain_top, "Ganancia de Amplitud en Tiempo Real", size=9, bold=True, bg=PANEL2, fg=PURPLE).pack(side="left")
        tk.Label(gain_top, textvariable=self.amp_gain_label_var, font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=PURPLE).pack(side="right")

        self.gain_slider = tk.Scale(
            gain_box, from_=MIN_AMP_GAIN, to=MAX_AMP_GAIN, resolution=0.05,
            orient="horizontal", variable=self.amp_gain_master_var, showvalue=False, sliderlength=16,
            bg=PANEL2, fg=TEXT, troughcolor="#384d6c", highlightthickness=0, activebackground=PURPLE,
            command=lambda _v: self.update_gain_labels(),
        )
        self.gain_slider.pack(fill="x", pady=(4, 4))

        gain_presets = tk.Frame(gain_box, bg=PANEL2)
        gain_presets.pack(fill="x")
        self.label(gain_presets, "Global:", size=8, fg=MUTED, bg=PANEL2).pack(side="left", padx=(0, 4))
        for g_val, g_txt in ((0.5, "0.5x"), (1.0, "1.0x"), (1.5, "1.5x"), (2.0, "2.0x"), (2.5, "2.5x"), (3.0, "3.0x")):
            self.button(
                gain_presets, g_txt, lambda g=g_val: self.set_master_gain_preset(g),
                bg=PANEL, fg=TEXT, padx=6, pady=2,
            ).pack(side="left", padx=(0, 3))

        # Per-subsystem fine gain multipliers row
        sub_gain_row = tk.Frame(gain_box, bg=PANEL2)
        sub_gain_row.pack(fill="x", pady=(5, 0))
        self.label(sub_gain_row, "Por Subsistema:", size=8, fg=MUTED, bg=PANEL2).pack(side="left", padx=(0, 6))
        for sub_lbl, sub_var in (
            ("Esquinas:", self.amp_gain_corners_var),
            ("Mandíbula:", self.amp_gain_jaw_var),
            ("Lab.Sup:", self.amp_gain_upper_var),
            ("Lab.Inf:", self.amp_gain_rack_var),
        ):
            self.label(sub_gain_row, sub_lbl, size=8, fg=TEXT, bg=PANEL2).pack(side="left", padx=(2, 2))
            sp = tk.Spinbox(
                sub_gain_row, from_=0.20, to=4.00, increment=0.10, textvariable=sub_var,
                width=4, font=("Segoe UI", 8, "bold"), justify="center", relief="flat",
                bg="#e7eef9", fg="#172033", command=self.update_gain_labels,
            )
            sp.pack(side="left", padx=(0, 6))
            sp.bind("<Return>", lambda _e: self.update_gain_labels())
            sp.bind("<FocusOut>", lambda _e: self.update_gain_labels())

        # Play + Progress bar row
        play_row = tk.Frame(panel, bg=PANEL)
        play_row.pack(fill="x", pady=(4, 6))

        self.play_btn = self.button(
            play_row, "▶ REPRODUCIR Y GRABAR TRAYECTORIA", self.play_selected_syllable,
            bg=GREEN, fg=BG, padx=16, pady=8,
        )
        self.play_btn.pack(side="left", padx=(0, 12))

        prog_frame = tk.Frame(play_row, bg=PANEL)
        prog_frame.pack(side="left", fill="x", expand=True)
        tk.Label(prog_frame, textvariable=self.progress_text_var, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, anchor="w").pack(fill="x")
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100.0, style="Safe.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(2, 0))

        # Post-Playback Trajectory Comparison Row (orofacial_analysis.py style)
        cmp_box = tk.Frame(panel, bg=PANEL2, padx=12, pady=8, highlightbackground=BORDER, highlightthickness=1)
        cmp_box.pack(fill="x", pady=(4, 0))

        self.label(cmp_box, "COMPARAR TRAYECTORIA (CSV vs Servos):", size=9, bold=True, bg=PANEL2, fg=GREEN).pack(side="left", padx=(0, 8))
        self.point_combo = ttk.Combobox(
            cmp_box,
            textvariable=self.selected_point_var,
            values=[label for _, label in POINT_OPTIONS],
            state="readonly",
            width=46,
            font=("Segoe UI", 9, "bold"),
            style="Syllable.TCombobox",
        )
        self.point_combo.pack(side="left", padx=(0, 8))

        self.button(
            cmp_box, "📊 Graficar Punto Seleccionado", self.plot_selected_point_comparison,
            bg=BLUE, fg=BG, padx=12, pady=5,
        ).pack(side="left", padx=(0, 8))

        self.button(
            cmp_box, "📂 Comparar CSV Previo...", self.load_and_compare_feedback_file,
            bg=PANEL, fg=TEXT, padx=10, pady=5,
        ).pack(side="left", padx=(0, 10))

        tk.Checkbutton(
            cmp_box, text="Graficar al terminar", variable=self.auto_plot_var,
            bg=PANEL2, fg=TEXT, activebackground=PANEL2, selectcolor=PANEL,
            highlightthickness=0, font=("Segoe UI", 9),
        ).pack(side="right")

    def build_servo_card(self, parent, index: int, name: str, cfg: dict):
        box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=9)
        box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=5, pady=4)

        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x")
        dir_str = "+1" if cfg["dir"] > 0 else "-1"
        home_deg = ticks_to_servo_deg(cfg["home_tick"])
        self.label(top, f"{name} · ID {cfg['id']}", size=11, bold=True).pack(side="left")
        self.label(top, f"({cfg['label']} · Home {home_deg:.0f}° · dir {dir_str})", size=8, fg=MUTED).pack(side="left", padx=(6, 0))

        real_var = tk.StringVar(value="Real: Sin leer")
        tk.Label(top, textvariable=real_var, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=GREEN).pack(side="right")

        tele_frame = tk.Frame(box, bg=PANEL2, padx=8, pady=5)
        tele_frame.pack(fill="x", pady=(5, 5))
        cmd_var = tk.StringVar(value="Cmd CSV: —")
        dtheta_var = tk.StringVar(value="Δθ Real: —")
        tk.Label(tele_frame, textvariable=cmd_var, font=("Segoe UI", 8), bg=PANEL2, fg=MUTED).pack(side="left")
        tk.Label(tele_frame, textvariable=dtheta_var, font=("Segoe UI", 8, "bold"), bg=PANEL2, fg=BLUE).pack(side="right")

        min_d, max_d = cfg["min_deg"], cfg["max_deg"]
        ctrl_top = tk.Frame(box, bg=PANEL)
        ctrl_top.pack(fill="x")
        self.label(ctrl_top, f"Rango seguro ({min_d:.0f}° a {max_d:.0f}°):", size=8, fg=MUTED).pack(side="left")
        angle_var = tk.StringVar(value=f"{home_deg:.1f}")
        angle_entry = tk.Entry(
            ctrl_top, textvariable=angle_var, width=7, font=("Segoe UI", 9, "bold"),
            justify="center", relief="flat", bg="#e7eef9", fg="#172033",
        )
        angle_entry.pack(side="right")
        angle_entry.bind("<Return>", lambda _e, n=name: self.move_single_servo(n))

        slider = tk.Scale(
            box, from_=min_d, to=max_d, orient="horizontal", resolution=1,
            showvalue=False, sliderlength=14, bg=PANEL, fg=TEXT, troughcolor="#384d6c",
            highlightthickness=0, activebackground=BLUE,
            command=lambda val, v=angle_var: v.set(f"{float(val):.1f}"),
        )
        slider.set(round(home_deg))
        slider.pack(fill="x", pady=(2, 4))
        slider.bind("<ButtonRelease-1>", lambda _e, n=name: self.move_single_servo(n))

        btn_row = tk.Frame(box, bg=PANEL)
        btn_row.pack(fill="x")
        self.button(btn_row, "-3°", lambda n=name: self.nudge_servo(n, -3.0), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
        self.button(btn_row, "+3°", lambda n=name: self.nudge_servo(n, 3.0), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
        self.button(btn_row, f"Home ({home_deg:.0f}°)", lambda n=name, h=home_deg: self.set_and_move_servo(n, h), bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="left", padx=(0, 4))
        self.button(btn_row, "Mover", lambda n=name: self.move_single_servo(n), bg=BLUE, fg=BG, padx=8, pady=3).pack(side="left", padx=(0, 4))
        self.button(btn_row, "Leer", self.read_once, bg=PANEL2, fg=TEXT, padx=8, pady=3).pack(side="right")

        self.servo_cards[name] = {
            "real_var": real_var,
            "cmd_var": cmd_var,
            "dtheta_var": dtheta_var,
            "angle_var": angle_var,
            "slider": slider,
        }

    # ==========================================================================
    # 5. GRAFICADOR DE COMPARACION (ESTILO orofacial_analysis.py)
    # ==========================================================================
    def get_selected_point_code(self) -> str:
        sel = self.selected_point_var.get()
        for code, label in POINT_OPTIONS:
            if label == sel:
                return code
        return "ALL_5"

    def plot_selected_point_comparison(self):
        if self.last_df_traj is None or self.last_df_fb is None or self.last_df_meas is None:
            syl = self.selected_syllable.get()
            csv_path = self.syllable_files.get(syl)
            if csv_path and csv_path.exists():
                fb_cand = csv_path.with_name(f"mouth_feedback_{syl}.csv")
                if fb_cand.is_file():
                    self.last_syl = syl
                    self.last_df_traj = pd.read_csv(csv_path)
                    self.last_df_fb = pd.read_csv(fb_cand)
                    self.last_df_meas = reconstruct_measured_landmarks(self.last_df_traj, self.last_df_fb, DEFAULT_FK_PARAMS)
                else:
                    messagebox.showinfo(
                        "Sin datos grabados",
                        "Reproduce primero una silaba (o usa '📂 Comparar CSV Previo...') para comparar la trayectoria.",
                    )
                    return
            else:
                return

        code = self.get_selected_point_code()
        syl = self.last_syl or "SYL"
        df_traj = self.last_df_traj
        df_fb = self.last_df_fb
        df_meas = self.last_df_meas
        phase = df_traj["phase_pct"].to_numpy(dtype=float)

        if code == "SERVOS_8":
            self.plot_servo_tracking_figure(syl, df_fb)
            return

        points = ["BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_IZQ", "BOCA_DER", "BARBILLA"] if code == "ALL_5" else [code]

        if len(points) == 1:
            pt = points[0]
            fig, (ax_xy, ax_t) = plt.subplots(1, 2, figsize=(12.5, 5.2))
            self._draw_point_xy_and_time(ax_xy, ax_t, pt, phase, df_traj, df_meas)
            fig.suptitle(f"{syl} · Comparacion de Trayectoria: {POINT_LABELS[pt]} (Estilo orofacial_analysis.py)", fontsize=13, fontweight="bold")
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            plt.show()
        else:
            fig, axs = plt.subplots(2, 5, figsize=(18, 7.5))
            for idx, pt in enumerate(points):
                self._draw_point_xy_and_time(axs[0, idx], axs[1, idx], pt, phase, df_traj, df_meas)
            fig.suptitle(
                f"{syl} · Comparacion Completa: Humano (Media 50 Part. ±1 SD) vs Objetivo IK vs Robot Real Medido",
                fontsize=14, fontweight="bold",
            )
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            plt.show()

    def _draw_point_xy_and_time(self, ax_xy, ax_t, pt: str, phase: np.ndarray, df_traj: pd.DataFrame, df_meas: pd.DataFrame):
        color = POINT_COLORS.get(pt, "#1f77b4")
        hx_col, hy_col = f"HUMAN_{pt}_Delta_X_mean", f"HUMAN_{pt}_Delta_Y_mean"
        hsdx_col, hsdy_col = f"HUMAN_{pt}_Delta_X_sd", f"HUMAN_{pt}_Delta_Y_sd"
        tx_col, ty_col = f"ROBOT_TARGET_{pt}_Delta_X", f"ROBOT_TARGET_{pt}_Delta_Y"
        mx_col, my_col = f"{pt}_Delta_X", f"{pt}_Delta_Y"

        has_human = hx_col in df_traj.columns and hy_col in df_traj.columns
        has_target = tx_col in df_traj.columns and ty_col in df_traj.columns
        has_meas = mx_col in df_meas.columns and my_col in df_meas.columns and df_meas[my_col].notna().any()

        if has_human:
            hx, hy = df_traj[hx_col].to_numpy(), df_traj[hy_col].to_numpy()
            ax_xy.plot(hx, hy, color=color, lw=2.4, label="Human mean (n=50)")
            ax_xy.scatter([hx[0]], [hy[0]], color=color, s=22, zorder=5)
            ax_xy.scatter([hx[-1]], [hy[-1]], color=color, marker="x", s=34, zorder=5)

        if has_target:
            tx, ty = df_traj[tx_col].to_numpy(), df_traj[ty_col].to_numpy()
            ax_xy.plot(tx, ty, color="#2ca02c", ls=":", lw=2.0, label="Target IK Base (CSV)")

        if has_meas:
            mx, my = df_meas[mx_col].to_numpy(), df_meas[my_col].to_numpy()
            ax_xy.plot(mx, my, "--", color="black", lw=2.0, label="Robot Medido (FK)")

        ax_xy.axhline(0, color="black", alpha=0.25, lw=0.6)
        ax_xy.axvline(0, color="black", alpha=0.25, lw=0.6)
        ax_xy.set_title(f"{POINT_LABELS[pt]} · XY", fontsize=10, fontweight="bold")
        ax_xy.set_xlabel("Delta X (eye-distance units)", fontsize=8)
        ax_xy.set_ylabel("Delta Y (+ downward)", fontsize=8)
        ax_xy.invert_yaxis()
        ax_xy.set_aspect("equal", adjustable="datalim")
        ax_xy.grid(alpha=0.18)
        ax_xy.legend(fontsize=7, loc="best")

        rmse_txt = ""
        if has_human:
            hy = df_traj[hy_col].to_numpy()
            ax_t.plot(phase, hy, color=color, lw=2.2, label="Human ΔY mean")
            if hsdy_col in df_traj.columns:
                hsd = df_traj[hsdy_col].to_numpy()
                ax_t.fill_between(phase, hy - hsd, hy + hsd, color=color, alpha=0.16, label="±1 SD")
            if pt in ("BOCA_DER", "BOCA_IZQ"):
                hx = df_traj[hx_col].to_numpy()
                ax_t.plot(phase, hx, color="#7c47a9", lw=1.6, alpha=0.8, label="Human ΔX mean")

        if has_target:
            ty = df_traj[ty_col].to_numpy()
            ax_t.plot(phase, ty, color="#2ca02c", ls=":", lw=1.8, label="Target IK Base ΔY")

        if has_meas:
            my = df_meas[my_col].to_numpy()
            ax_t.plot(phase, my, "--", color="black", lw=2.0, label="Robot Real ΔY")
            if pt in ("BOCA_DER", "BOCA_IZQ"):
                mx = df_meas[mx_col].to_numpy()
                ax_t.plot(phase, mx, "-.", color="#444444", lw=1.4, label="Robot Real ΔX")
            if has_human:
                err_y = my - df_traj[hy_col].to_numpy()
                rmse_y = float(np.sqrt(np.nanmean(err_y**2)))
                mae_y = float(np.nanmean(np.abs(err_y)))
                rmse_txt = f" | RMSE_Y={rmse_y:.4f}, MAE_Y={mae_y:.4f}"

        ax_t.axhline(0, color="black", alpha=0.35, lw=0.7)
        ax_t.set_title(f"vs Fase (0-100%){rmse_txt}", fontsize=9)
        ax_t.set_xlabel("Selected interval (%)", fontsize=8)
        ax_t.set_ylabel("Delta (eye-distance units)", fontsize=8)
        ax_t.set_xlim(0, 100)
        ax_t.grid(alpha=0.18)
        ax_t.legend(fontsize=7, loc="best")

    def plot_servo_tracking_figure(self, syl: str, df_fb: pd.DataFrame):
        fig, axs = plt.subplots(4, 2, figsize=(13, 10), sharex=True)
        phase = df_fb["phase_pct"].to_numpy(dtype=float)

        for idx, name in enumerate(SERVO_ORDER):
            ax = axs.flat[idx]
            cfg = SERVO_CONFIG[name]
            cmd_col = f"{name}_cmd_deg"
            meas_col = f"{name}_meas_deg"
            gain_col = f"{name}_gain_used"
            g_str = f" (Gain={df_fb[gain_col].iloc[-1]:.2f}x)" if gain_col in df_fb.columns else ""
            if cmd_col in df_fb.columns:
                ax.plot(phase, df_fb[cmd_col], color="#1f77b4", lw=2.0, label=f"Comando{g_str} (deg)")
            if meas_col in df_fb.columns and df_fb[meas_col].notna().any():
                ax.plot(phase, df_fb[meas_col], "--", color="#d62728", lw=1.8, label="Real Encoder (deg)")
                err = df_fb[meas_col] - df_fb[cmd_col]
                rmse_deg = float(np.sqrt(np.nanmean(err**2)))
                ax.set_title(f"{name} (ID {cfg['id']}){g_str} · RMSE = {rmse_deg:.2f}°", fontsize=9, fontweight="bold")
            else:
                ax.set_title(f"{name} (ID {cfg['id']}) · No medido", fontsize=9)
            ax.grid(alpha=0.22)
            ax.set_ylabel("Grados (°)", fontsize=8)
            if idx == 0:
                ax.legend(fontsize=8, loc="best")

        for ax in axs[-1, :]:
            ax.set_xlabel("Selected interval (%)")

        fig.suptitle(f"{syl} · Seguimiento Angular de los 8 Servos STS3215 (Comando Escalado vs Encoder Real)", fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        plt.show()

    def load_and_compare_feedback_file(self):
        fb_file = filedialog.askopenfilename(
            title="Seleccionar archivo mouth_feedback_<SYL>.csv",
            filetypes=[("Feedback CSV", "*feedback*.csv"), ("Todos los CSV", "*.csv")],
        )
        if not fb_file:
            return
        fb_path = Path(fb_file).resolve()
        syl = re.sub(r"^mouth_feedback_|_4servo_feedback$|_center_feedback$", "", fb_path.stem, flags=re.IGNORECASE).upper()
        traj_cand = fb_path.parent / f"mouth_trajectory_{syl}.csv"
        if not traj_cand.is_file() and syl in self.syllable_files:
            traj_cand = self.syllable_files[syl]
        if not traj_cand.is_file():
            messagebox.showwarning("Falta CSV base", f"No se encontro el archivo base mouth_trajectory_{syl}.csv.")
            return

        self.last_syl = syl
        self.last_df_traj = pd.read_csv(traj_cand)
        self.last_df_fb = pd.read_csv(fb_path)
        self.last_df_meas = reconstruct_measured_landmarks(self.last_df_traj, self.last_df_fb, DEFAULT_FK_PARAMS)
        self.plot_selected_point_comparison()

    # ==========================================================================
    # 6. CONTROLES DE LA INTERFAZ Y EVENTOS (VELOCIDAD Y GANANCIA EN VIVO)
    # ==========================================================================
    def set_speed_preset(self, mult: float):
        self.speed_mult_var.set(round(float(np.clip(mult, MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT)), 2))
        self.update_speed_labels()

    def set_master_gain_preset(self, gain: float):
        self.amp_gain_master_var.set(round(float(np.clip(gain, MIN_AMP_GAIN, MAX_AMP_GAIN)), 2))
        self.update_gain_labels()

    def update_gain_labels(self):
        """Sincroniza inmediatamente los sliders/spinboxes de ganancia con el diccionario en vivo del ServoWorker."""
        master_g = float(np.clip(self.amp_gain_master_var.get(), MIN_AMP_GAIN, MAX_AMP_GAIN))
        self.amp_gain_label_var.set(f"Global: {master_g:.2f}x ({round(master_g * 100)}%)")

        def _safe_float(var: tk.DoubleVar, default: float = 1.0) -> float:
            try:
                return float(np.clip(var.get(), 0.10, 5.00))
            except Exception:
                return default

        self.live_gains["master"]  = master_g
        self.live_gains["corners"] = _safe_float(self.amp_gain_corners_var, 1.0)
        self.live_gains["jaw"]     = _safe_float(self.amp_gain_jaw_var, 1.0)
        self.live_gains["upper"]   = _safe_float(self.amp_gain_upper_var, 1.0)
        self.live_gains["rack"]    = _safe_float(self.amp_gain_rack_var, 1.0)

    def get_time_scale(self) -> float:
        mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
        return 1.0 / mult

    def update_speed_labels(self):
        mult = float(np.clip(self.speed_mult_var.get(), MIN_SPEED_MULT, MAX_SAFE_SPEED_MULT))
        time_scale = 1.0 / mult
        self.speed_label_var.set(f"{mult:.2f}x ({round(mult*100)}%) · scale={time_scale:.2f}x")
        cap = int(np.clip(self.max_steps_var.get(), 300, SAFE_HARD_LIMIT_STEP))
        self.max_steps_label_var.set(f"{cap} pasos/s (~{cap / STEPS_PER_DEG:.0f}°/s)")
        self.update_csv_summary()

    def refresh_syllable_list(self):
        self.syllable_files.clear()
        script_dir = Path(__file__).resolve().parent
        search_dirs = [
            self.traj_dir,
            script_dir / DEFAULT_TRAJ_DIR,
            Path.cwd() / DEFAULT_TRAJ_DIR,
            script_dir / FALLBACK_CORNER_DIR,
            Path.cwd() / FALLBACK_CORNER_DIR,
            script_dir / FALLBACK_CENTER_DIR,
            script_dir,
            Path.cwd(),
        ]
        found_paths = []
        for folder in search_dirs:
            if folder.exists() and folder.is_dir():
                for pat in ("mouth_trajectory_*.csv", "servo_trajectory_*.csv", "center_lips_trajectory_*.csv"):
                    matches = [p for p in sorted(folder.glob(pat)) if "feedback" not in p.stem]
                    if matches:
                        found_paths.extend(matches)
                        self.traj_dir = folder
                        break
            if found_paths:
                break

        for path in found_paths:
            syl = extract_syllable_name(path)
            self.syllable_files[syl] = path.resolve()

        for widget in self.quick_syl_frame.winfo_children():
            widget.destroy()
        self.quick_syl_buttons.clear()

        syl_names = sorted(self.syllable_files.keys())
        self.syl_combo["values"] = syl_names

        if syl_names:
            self.label(self.quick_syl_frame, "Silabas:", size=9, fg=MUTED).pack(side="left", padx=(0, 6))
            for syl in syl_names:
                btn = self.button(
                    self.quick_syl_frame, syl, lambda s=syl: self.select_syllable_by_name(s),
                    bg=PANEL2, fg=TEXT, padx=9, pady=2,
                )
                btn.pack(side="left", padx=(0, 4))
                self.quick_syl_buttons.append(btn)

            if self.selected_syllable.get() not in self.syllable_files:
                self.selected_syllable.set(syl_names[0])
            self.on_syllable_selected()
        else:
            self.selected_syllable.set("")
            self.csv_info_var.set(
                "Ejecuta primero 'python generate_all_mouth_trajectories.py' o selecciona la carpeta con 'Carpeta...'."
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
            scaled_ms = base_ms * self.get_time_scale()
            n_part = int(df["n_participants"].iloc[0]) if "n_participants" in df.columns else 50
            self.csv_info_var.set(
                f"Archivo: {path.name}  |  Media validada: n={n_part} participantes  |  "
                f"Duracion base (1.0x): {base_ms:.0f} ms  |  Duracion actual: {scaled_ms:.0f} ms ({scaled_ms/1000.0:.2f} s)"
            )
        except Exception as exc:
            self.csv_info_var.set(f"Error al leer {path.name}: {exc}")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de trayectorias CSV")
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
        for btn in (self.disc_btn, self.ping_btn, self.home_btn, self.monitor_btn, self.stop_btn, self.play_btn):
            btn.config(state=state)

    def connect(self):
        if self.connected or (self.worker and self.worker.is_alive()):
            return
        com = self.port_var.get().strip()
        if not com:
            messagebox.showwarning("Puerto vacio", "Escribe el puerto COM (ej. COM4).")
            return
        self.update_gain_labels()
        self.commands = queue.Queue()
        self.stop_event.clear()
        self.worker = ServoWorker(com, self.commands, self.events, self.stop_event, self.live_gains)
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
        if not self.connected or self.playing:
            return
        active_map = self.get_active_servo_map()
        if not active_map:
            messagebox.showwarning("Sin mecanismos activos", "Marca al menos un grupo de mecanismos.")
            return
        self.commands.put(("go_home", active_map, int(self.max_steps_var.get())))

    def toggle_monitor(self):
        if not self.connected or self.playing:
            return
        self.commands.put(("set_monitor", not self.monitoring, SERVO_CONFIG))

    def emergency_stop(self):
        if not self.connected:
            return
        self.stop_event.set()
        self.commands.put(("release", SERVO_CONFIG))

    def set_and_move_servo(self, name: str, deg: float):
        cfg = SERVO_CONFIG[name]
        deg = float(np.clip(deg, cfg["min_deg"], cfg["max_deg"]))
        card = self.servo_cards[name]
        card["angle_var"].set(f"{deg:.1f}")
        card["slider"].set(round(deg))
        self.move_single_servo(name)

    def nudge_servo(self, name: str, delta: float):
        cfg = SERVO_CONFIG[name]
        card = self.servo_cards[name]
        try:
            curr = float(card["angle_var"].get().replace(",", "."))
        except ValueError:
            curr = ticks_to_servo_deg(cfg["home_tick"])
        self.set_and_move_servo(name, float(np.clip(curr + delta, cfg["min_deg"], cfg["max_deg"])))

    def move_single_servo(self, name: str):
        if not self.connected or self.playing:
            return
        cfg = SERVO_CONFIG[name]
        card = self.servo_cards[name]
        try:
            deg = float(card["angle_var"].get().replace(",", "."))
        except ValueError:
            return
        deg = float(np.clip(deg, cfg["min_deg"], cfg["max_deg"]))
        card["angle_var"].set(f"{deg:.1f}")
        card["slider"].set(round(deg))
        self.commands.put(("move_single", SERVO_CONFIG, name, deg, int(self.max_steps_var.get())))

    def play_selected_syllable(self):
        if not self.connected or self.playing:
            return
        syl = self.selected_syllable.get()
        csv_path = self.syllable_files.get(syl)
        if not csv_path or not csv_path.exists():
            messagebox.showwarning("Sin archivo CSV", "Selecciona una silaba valida o carga un archivo CSV.")
            return
        active_map = self.get_active_servo_map()
        if not active_map:
            messagebox.showwarning("Sin mecanismos", "Selecciona al menos un grupo de mecanismos para reproducir.")
            return

        self.update_gain_labels()
        time_scale = self.get_time_scale()
        max_speed_cap = int(np.clip(self.max_steps_var.get(), MIN_SPEED_STEPS, SAFE_HARD_LIMIT_STEP))
        self.playing = True
        self.play_btn.config(state="disabled")
        self.progress_var.set(0.0)
        self.commands.put(
            ("play_csv", csv_path, time_scale, max_speed_cap, self.save_log_var.get(), active_map)
        )

    def update_servo_cards_from_readings(self, readings: dict):
        for name, info in readings.items():
            card = self.servo_cards.get(name)
            cfg = SERVO_CONFIG.get(name)
            if not card or not cfg:
                continue
            if info.get("ok"):
                deg = info["deg"]
                ticks = info["ticks"]
                dtheta = info["dtheta"]
                card["real_var"].set(f"Real: {deg:5.1f}° [{ticks:4d}]")
                card["dtheta_var"].set(f"Δθ Real: {dtheta:+5.1f}°")
                if not self.playing:
                    card["angle_var"].set(f"{deg:.1f}")
                    card["slider"].set(int(np.clip(round(deg), cfg["min_deg"], cfg["max_deg"])))
            else:
                card["real_var"].set("OFFLINE")
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
                self.status_var.set(f"Puerto {com} conectado. Comprobando los 8 servos...")
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
                self.status_var.set(f"Comprobacion completada: {ok_count} de 8 servos responden (IDs 1, 2, 5, 6, 7, 8, 9, 10).")

            elif kind == "positions":
                self.update_servo_cards_from_readings(event[1])

            elif kind == "monitor_state":
                self.monitoring = event[1]
                if self.monitoring:
                    self.monitor_btn.config(text="Monitor en Vivo (ACTIVO)", bg=GREEN, fg=BG)
                else:
                    self.monitor_btn.config(text="Monitor en Vivo (OFF)", bg=PANEL2, fg=TEXT)

            elif kind == "playback_started":
                _, syl_name, total_steps, time_scale, total_ms, n_servos, master_g = event
                mult = 1.0 / time_scale
                self.progress_var.set(0.0)
                self.progress_text_var.set(
                    f"Reproduciendo '{syl_name}' ({n_servos} servos | Vel: {mult:.2f}x | Amp Gain: {master_g:.2f}x | {total_ms:.0f} ms)"
                )
                self.status_var.set(
                    f"Moviendo {n_servos} servos para '{syl_name}' (Velocidad={mult:.2f}x, Ganancia Global={master_g:.2f}x)..."
                )

            elif kind == "playback_step":
                _, phase_pct, step_idx, total_steps, cmd_snap, meas_snap = event
                self.progress_var.set(phase_pct)
                self.progress_text_var.set(
                    f"Fase: {phase_pct:5.1f}% (Paso {step_idx}/{total_steps}) · Ganancia Global: {self.live_gains['master']:.2f}x"
                )
                for name, cinfo in cmd_snap.items():
                    card = self.servo_cards.get(name)
                    if card:
                        card["cmd_var"].set(
                            f"Cmd ({cinfo['gain']:.2f}x): {cinfo['cmd_deg']:5.1f}° [{cinfo['cmd_ticks']:4d}] · {cinfo['cmd_speed']} st/s"
                        )
                self.update_servo_cards_from_readings(meas_snap)

            elif kind == "playback_finished":
                _, syl_name, elapsed_ms, out_csv_msg, df_traj, df_fb, df_meas = event
                self.playing = False
                if self.connected:
                    self.play_btn.config(state="normal")
                self.progress_var.set(100.0)
                self.progress_text_var.set(f"Completado: 100% ({elapsed_ms:.0f} ms) · Lista comparacion de trayectoria")
                self.status_var.set(f"Silaba '{syl_name}' finalizada en {elapsed_ms:.1f} ms{out_csv_msg}")

                self.last_syl = syl_name
                self.last_df_traj = df_traj
                self.last_df_fb = df_fb
                self.last_df_meas = df_meas

                if self.auto_plot_var.get():
                    self.root.after(150, self.plot_selected_point_comparison)

            elif kind == "playback_stopped":
                self.playing = False
                if self.connected:
                    self.play_btn.config(state="normal")
                self.progress_text_var.set("Reproduccion detenida por el usuario")
                self.status_var.set(event[1])

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
    app = UnifiedMouthServoGUI(root)
    root.mainloop()