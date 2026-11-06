"""4-Servo Feetech STS3215-12V Controller (IDs 5, 6, 7, 8).

Usage:
    1) Live monitor (compact single-line format for PowerShell):
       python play_sts3215_4servos.py --port COM4 --check

    2) Move all 4 servos smoothly to neutral 180.0 deg (2048 ticks):
       python play_sts3215_4servos.py --port COM4 --go-home

    3) Play a syllable in slow motion first (3x slower) to verify clearance:
       python play_sts3215_4servos.py --port COM4 --csv orofacial_results/servo_trajectories/servo_trajectory_SA.csv --time-scale 3.0

    4) Play a syllable at real-time 1.0x human speed:
       python play_sts3215_4servos.py --port COM4 --csv orofacial_results/servo_trajectories/servo_trajectory_SA.csv
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
import numpy as np
import pandas as pd

from scservo_sdk import (
    PortHandler,
    PacketHandler,
    GroupSyncWrite,
    COMM_SUCCESS,
    SCS_LOBYTE,
    SCS_HIBYTE,
)

# ==============================================================================
# 1. STS3215 REGISTER ADDRESSES & HARDWARE CONFIGURATION
# ==============================================================================
ADDR_SCS_TORQUE_ENABLE    = 40
ADDR_STS_GOAL_ACC         = 41
ADDR_STS_GOAL_POSITION    = 42
ADDR_STS_GOAL_SPEED       = 46
ADDR_STS_LOCK             = 55
ADDR_STS_PRESENT_POSITION = 56

PROTOCOL_END = 0
BAUDRATE = 1000000
STEPS_PER_DEG = 4096.0 / 360.0  # 11.37778 ticks/deg
HOME_TICK_180 = 2048            # 180.0 deg neutral position

MAX_SPEED_STEPS = 3400
MIN_SPEED_STEPS = 120
SPEED_HEADROOM  = 1.15

SERVO_CONFIG = {
    "DER_TOP":    {"id": 5, "home_tick": HOME_TICK_180, "dir": -1},  # Right cheek upper (straight up = 180°)
    "DER_BOTTOM": {"id": 6, "home_tick": HOME_TICK_180, "dir": -1},  # Right cheek lower (straight down = 180°)
    "IZQ_TOP":    {"id": 7, "home_tick": HOME_TICK_180, "dir": +1},  # Left cheek upper  (straight up = 180°)
    "IZQ_BOTTOM": {"id": 8, "home_tick": HOME_TICK_180, "dir": +1},  # Left cheek lower  (straight down = 180°)
}


# ==============================================================================
# 2. CONVERSION & REGISTER HELPER FUNCTIONS
# ==============================================================================
def dtheta_to_servo_deg(dtheta_deg: float, direction: int) -> float:
    return 180.0 + direction * dtheta_deg


def dtheta_to_ticks(dtheta_deg: float, home_tick: int, direction: int) -> int:
    ticks = round(home_tick + direction * dtheta_deg * STEPS_PER_DEG)
    return int(np.clip(ticks, 50, 4045))


def ticks_to_servo_deg(ticks: int) -> float:
    return float(ticks / STEPS_PER_DEG)


def ticks_to_dtheta_deg(ticks: int, home_tick: int, direction: int) -> float:
    return float((ticks - home_tick) * direction / STEPS_PER_DEG)


def speed_degs_to_steps(omega_degs: float, time_scale: float = 1.0) -> int:
    steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
    return int(np.clip(steps_s, MIN_SPEED_STEPS, MAX_SPEED_STEPS))


def accel_degs2_to_unit(alpha_degs2: float, time_scale: float = 1.0) -> int:
    acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
    return int(np.clip(acc_unit, 1, 254))


def write_pos_ex(port: PortHandler, ph: PacketHandler, servo_id: int, pos_ticks: int, speed_steps: int, acc_unit: int):
    ph.write1ByteTxRx(port, servo_id, ADDR_STS_GOAL_ACC, acc_unit)
    ph.write2ByteTxRx(port, servo_id, ADDR_STS_GOAL_SPEED, speed_steps)
    ph.write2ByteTxRx(port, servo_id, ADDR_STS_GOAL_POSITION, pos_ticks)


def read_pos(port: PortHandler, ph: PacketHandler, servo_id: int) -> tuple[int, int]:
    raw_pos, comm, _ = ph.read2ByteTxRx(port, servo_id, ADDR_STS_PRESENT_POSITION)
    if raw_pos & 0x8000:
        raw_pos = -(raw_pos & 0x7FFF)
    return raw_pos, comm


# ==============================================================================
# 3. DIAGNOSTIC, CALIBRATION & PLAYBACK MODES
# ==============================================================================
def check_servos(port: PortHandler, ph: PacketHandler):
    print("\n--- STS3215 4-SERVO LIVE ANGLE MONITOR ---")
    print("Push DER_TOP(ID5) and IZQ_TOP(ID7) slightly forward toward the mouth to verify tick direction.")
    print("Press Ctrl+C to exit.\n")

    for cfg in SERVO_CONFIG.values():
        ph.write1ByteTxRx(port, cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

    try:
        while True:
            status = []
            for name, cfg in SERVO_CONFIG.items():
                pos, comm = read_pos(port, ph, cfg["id"])
                if comm == COMM_SUCCESS:
                    deg = ticks_to_servo_deg(pos)
                    status.append(f"ID{cfg['id']}:{deg:5.1f}°[{pos:4d}]")
                else:
                    status.append(f"ID{cfg['id']}:OFF")
            print(" | ".join(status) + "   ", end="\r", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nMonitor closed.")


def set_center_180(port: PortHandler, ph: PacketHandler):
    print("\nSetting current physical position of all 4 servos to 180.0° (2048 ticks)...")
    for name, cfg in SERVO_CONFIG.items():
        sid = cfg["id"]
        ph.write1ByteTxRx(port, sid, ADDR_STS_LOCK, 0)
        comm, _ = ph.write1ByteTxRx(port, sid, ADDR_SCS_TORQUE_ENABLE, 128)
        time.sleep(0.05)
        ph.write1ByteTxRx(port, sid, ADDR_STS_LOCK, 1)
        pos, comm_r = read_pos(port, ph, sid)
        if comm == COMM_SUCCESS and comm_r == COMM_SUCCESS:
            print(f"  [OK] {name} (ID {sid}) -> {ticks_to_servo_deg(pos):.1f}° ({pos} ticks)")
        else:
            print(f"  [ERR] {name} (ID {sid}) failed to respond.")


def go_home_180(port: PortHandler, ph: PacketHandler):
    print("\nMoving all 4 servos smoothly to neutral 180.0° (2048 ticks)...")
    for cfg in SERVO_CONFIG.values():
        write_pos_ex(port, ph, cfg["id"], cfg["home_tick"], speed_steps=400, acc_unit=10)
    time.sleep(1.0)
    print("Done.")


def play_trajectory(port: PortHandler, ph: PacketHandler, csv_path: Path, time_scale: float = 1.0):
    df = pd.read_csv(csv_path)
    total_ms = float(df["time_ms"].iloc[-1]) * time_scale
    print(f"\nLoaded {csv_path.name} ({len(df)} steps | Time scale: {time_scale:.1f}x | Total time: {total_ms:.0f} ms)")

    print("Moving all 4 servos to initial 0% syllable pose...")
    for name, cfg in SERVO_CONFIG.items():
        side, tier = name.split("_")
        col = f"{side}_dtheta1_from_90_deg" if tier == "TOP" else f"{side}_dtheta2_from_neg90_deg"
        init_ticks = dtheta_to_ticks(float(df[col].iloc[0]), cfg["home_tick"], cfg["dir"])
        write_pos_ex(port, ph, cfg["id"], init_ticks, speed_steps=400, acc_unit=10)
    time.sleep(0.8)

    sync_write = GroupSyncWrite(port, ph, ADDR_STS_GOAL_ACC, 7)
    feedback_rows = []
    t_start = time.perf_counter()

    for _, row in df.iterrows():
        target_time_s = float(row["time_s"]) * time_scale
        sync_write.clearParam()
        log_item = {"phase_pct": row["phase_pct"], "time_ms": float(row["time_ms"]) * time_scale}

        for name, cfg in SERVO_CONFIG.items():
            side, tier = name.split("_")
            m_idx = "1" if tier == "TOP" else "2"
            ref_str = "90" if m_idx == "1" else "neg90"

            dtheta = float(row[f"{side}_dtheta{m_idx}_from_{ref_str}_deg"])
            omega  = float(row[f"{side}_omega{m_idx}_speed_degs"])
            alpha  = float(row[f"{side}_alpha{m_idx}_accel_degs2"])

            pos_ticks   = dtheta_to_ticks(dtheta, cfg["home_tick"], cfg["dir"])
            speed_steps = speed_degs_to_steps(omega, time_scale)
            acc_unit    = accel_degs2_to_unit(alpha, time_scale)

            param_bytes = [
                acc_unit & 0xFF,
                SCS_LOBYTE(pos_ticks),
                SCS_HIBYTE(pos_ticks),
                0,
                0,
                SCS_LOBYTE(speed_steps),
                SCS_HIBYTE(speed_steps),
            ]
            sync_write.addParam(cfg["id"], param_bytes)

            log_item[f"{name}_cmd_deg"]   = dtheta_to_servo_deg(dtheta, cfg["dir"])
            log_item[f"{name}_cmd_ticks"] = pos_ticks
            log_item[f"{name}_cmd_speed"] = speed_steps
            log_item[f"{name}_cmd_acc"]   = acc_unit

        while (time.perf_counter() - t_start) < target_time_s:
            pass

        sync_write.txPacket()

        for name, cfg in SERVO_CONFIG.items():
            pos_meas, comm = read_pos(port, ph, cfg["id"])
            if comm == COMM_SUCCESS:
                log_item[f"{name}_meas_deg"] = ticks_to_servo_deg(pos_meas)
                log_item[f"{name}_meas_dtheta_deg"] = ticks_to_dtheta_deg(pos_meas, cfg["home_tick"], cfg["dir"])
            else:
                log_item[f"{name}_meas_deg"] = np.nan
                log_item[f"{name}_meas_dtheta_deg"] = np.nan

        feedback_rows.append(log_item)

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Finished 4-servo playback in {elapsed_ms:.1f} ms.")

    out_csv = csv_path.with_name(csv_path.stem + "_4servo_feedback.csv")
    pd.DataFrame(feedback_rows).to_csv(out_csv, index=False)
    print(f"Saved hardware execution log -> {out_csv}")


def main():
    parser = argparse.ArgumentParser(description="4-Servo STS3215-12V Trajectory Controller")
    parser.add_argument("--port", type=str, default="COM4", help="COM port (default: COM4)")
    parser.add_argument("--check", action="store_true", help="Live monitor of angles (deg) and ticks")
    parser.add_argument("--set-center", action="store_true", help="Calibrate current pose as 180.0° (2048 ticks)")
    parser.add_argument("--go-home", action="store_true", help="Move all 4 servos to 180.0° (2048 ticks)")
    parser.add_argument("--csv", type=Path, help="Path to servo_trajectory_<SYL>.csv")
    parser.add_argument("--time-scale", type=float, default=1.0, help="Slow-motion multiplier (e.g. 3.0 = 3x slower)")
    args = parser.parse_args()

    port = PortHandler(args.port)
    ph = PacketHandler(PROTOCOL_END)

    if not port.openPort():
        raise SystemExit(f"Could not open port {args.port}")
    if not port.setBaudRate(BAUDRATE):
        raise SystemExit(f"Could not set baudrate {BAUDRATE}")

    try:
        if args.check:
            check_servos(port, ph)
        elif args.set_center:
            set_center_180(port, ph)
        elif args.go_home:
            go_home_180(port, ph)
        elif args.csv:
            play_trajectory(port, ph, args.csv.expanduser().resolve(), args.time_scale)
        else:
            print("Specify one of: --check, --set-center, --go-home, or --csv <file>")
    finally:
        port.closePort()


if __name__ == "__main__":
    main()