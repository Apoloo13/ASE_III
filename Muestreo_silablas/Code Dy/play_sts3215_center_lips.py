"""STS3215-12V Controller for Chin/Jaw (IDs 1 & 2), Lower Lip Rack (ID 10), & Upper Lip Piston (ID 9).

Configured Servo Map:
    - JAW_LEFT  (ID 1):  180.0° (2048) Closed --> 195.0° (2219) Fully Open
    - JAW_RIGHT (ID 2):  180.0° (2048) Closed --> 165.0° (1877) Fully Open
    - UP_PISTON (ID 9):  180.0° (2048) Down   --> 140.0° (1593) Fully Up
    - LOW_RACK  (ID 10): 125.0° (1422) Home   |   81.0° (922) Down <--> 150.0° (1707) Up

Usage examples:
    1) Live angle & tick monitor for all 4 servos (torque OFF):
       python play_sts3215_center_lips.py --port COM4 --mode all --check

    2) Test ONLY the Jaw servos (ID 1 & ID 2) in 2x slow motion:
       python play_sts3215_center_lips.py --port COM4 --mode jaw --csv ./orofacial_results/center_lips_trajectories/center_lips_trajectory_SA.csv --time-scale 2.0

    3) Run Jaw + Lower Rack + Upper Piston all together synchronously:
       python play_sts3215_center_lips.py --port COM4 --mode all --csv ./orofacial_results/center_lips_trajectories/center_lips_trajectory_SA.csv
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
import numpy as np
import pandas as pd

import scservo_sdk as scs
from scservo_sdk import PortHandler, COMM_SUCCESS

if hasattr(scs, "sts"):
    STSDriver = scs.sts
elif hasattr(scs, "sms_sts"):
    STSDriver = scs.sms_sts
else:
    raise ImportError(f"Could not find 'sts' or 'sms_sts' in scservo_sdk. Available: {dir(scs)}")

# ==============================================================================
# 1. STS3215 REGISTER ADDRESSES & SERVO CONFIGURATION (IDs 1, 2, 9, 10)
# ==============================================================================
ADDR_SCS_TORQUE_ENABLE = 40
ADDR_STS_LOCK          = 55

BAUDRATE      = 1000000
STEPS_PER_DEG = 4096.0 / 360.0  # 11.37778 ticks/deg
HOME_TICK_180 = 2048            # 180.0 deg neutral center

MAX_SPEED_STEPS = 3400
MIN_SPEED_STEPS = 120
SPEED_HEADROOM  = 1.15

CENTER_SERVO_CONFIG = {
    "JAW_LEFT": {
        "id": 1,                     # Left Jaw Servo ID
        "home_tick": HOME_TICK_180,  # 180.0° = 2048 ticks (Fully Closed, teeth touching)
        "dir": +1,                   # +1 maps +dtheta_jaw (0..15°) from 180.0° up to 195.0°
        "min_tick": 2048,            # Hard stop at 180.0° (Closed = 2048 ticks)
        "max_tick": 2219,            # Hard stop at 195.0° (Fully Open = 2219 ticks)
        "dtheta_col": "JAW_dtheta_deg",
        "omega_col":  "JAW_omega_speed_degs",
        "alpha_col":  "JAW_alpha_accel_degs2",
    },
    "JAW_RIGHT": {
        "id": 2,                     # Right Jaw Servo ID
        "home_tick": HOME_TICK_180,  # 180.0° = 2048 ticks (Fully Closed, teeth touching)
        "dir": -1,                   # -1 maps +dtheta_jaw (0..15°) from 180.0° down to 165.0°
        "min_tick": 1877,            # Hard stop at 165.0° (Fully Open = 1877 ticks)
        "max_tick": 2048,            # Hard stop at 180.0° (Closed = 2048 ticks)
        "dtheta_col": "JAW_dtheta_deg",
        "omega_col":  "JAW_omega_speed_degs",
        "alpha_col":  "JAW_alpha_accel_degs2",
    },
    "UP_PISTON": {
        "id": 9,                     # Upper Lip Piston Servo ID
        "home_tick": HOME_TICK_180,  # 180.0° = 2048 ticks (Fully DOWN)
        "dir": -1,                   # -1 maps +dtheta_up lift from 180.0° down toward 140.0°
        "min_tick": 1593,            # Hard stop at 140.0° (Fully UP = 1593 ticks)
        "max_tick": 2048,            # Hard stop at 180.0° (Fully DOWN = 2048 ticks)
        "dtheta_col": "UP_dtheta_deg",
        "omega_col":  "UP_omega_speed_degs",
        "alpha_col":  "UP_alpha_accel_degs2",
    },
    "LOW_RACK": {
        "id": 10,                    # Lower Lip Rack & Pinion Servo ID (changed to ID 10)
        "home_tick": 1422,           # 125.0° neutral resting position (1422 ticks)
        "dir": +1,                   # +1: +dtheta moves UP toward 150°, -dtheta moves DOWN toward 81°
        "min_tick": 922,             # Hard stop at 81.0° (Fully DOWN = 922 ticks)
        "max_tick": 1707,            # Hard stop at 150.0° (Fully UP = 1707 ticks)
        "dtheta_col": "LOW_dtheta_deg",
        "omega_col":  "LOW_omega_speed_degs",
        "alpha_col":  "LOW_alpha_accel_degs2",
    },
}


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def get_active_servos(mode: str) -> dict:
    if mode == "jaw":
        return {k: CENTER_SERVO_CONFIG[k] for k in ("JAW_LEFT", "JAW_RIGHT")}
    if mode == "rack":
        return {"LOW_RACK": CENTER_SERVO_CONFIG["LOW_RACK"]}
    if mode == "upper":
        return {"UP_PISTON": CENTER_SERVO_CONFIG["UP_PISTON"]}
    return CENTER_SERVO_CONFIG


def dtheta_to_ticks(dtheta_deg: float, cfg: dict) -> int:
    ticks = round(cfg["home_tick"] + cfg["dir"] * dtheta_deg * STEPS_PER_DEG)
    return int(np.clip(ticks, cfg["min_tick"], cfg["max_tick"]))


def ticks_to_servo_deg(ticks: int) -> float:
    return float(ticks / STEPS_PER_DEG)


def ticks_to_dtheta_deg(ticks: int, cfg: dict) -> float:
    return float((ticks - cfg["home_tick"]) * cfg["dir"] / STEPS_PER_DEG)


def speed_degs_to_steps(omega_degs: float, time_scale: float = 1.0) -> int:
    steps_s = round((abs(omega_degs) / time_scale) * STEPS_PER_DEG * SPEED_HEADROOM)
    return int(np.clip(steps_s, MIN_SPEED_STEPS, MAX_SPEED_STEPS))


def accel_degs2_to_unit(alpha_degs2: float, time_scale: float = 1.0) -> int:
    acc_unit = round(((abs(alpha_degs2) / (time_scale**2)) * STEPS_PER_DEG) / 100.0)
    return int(np.clip(acc_unit, 1, 254))


# ==============================================================================
# 3. DIAGNOSTIC, HOME & PLAYBACK FUNCTIONS
# ==============================================================================
def check_servos(servo, active_servos: dict):
    print("\n--- CENTER LIPS & JAW STS3215 LIVE MONITOR ---")
    print("Press Ctrl+C to exit.\n")

    for cfg in active_servos.values():
        servo.write1ByteTxRx(cfg["id"], ADDR_SCS_TORQUE_ENABLE, 0)

    try:
        while True:
            status = []
            for name, cfg in active_servos.items():
                pos, comm, _ = servo.ReadPos(cfg["id"])
                if comm == COMM_SUCCESS:
                    deg = ticks_to_servo_deg(pos)
                    status.append(f"{name}(ID{cfg['id']}):{deg:5.1f}°[{pos:4d}]")
                else:
                    status.append(f"{name}(ID{cfg['id']}):OFF")
            print(" | ".join(status) + "   ", end="\r", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nMonitor closed.")


def go_home(servo, active_servos: dict):
    print("\nMoving active servo(s) smoothly to closed-mouth home position...")
    servo.groupSyncWrite.clearParam()
    for name, cfg in active_servos.items():
        servo.SyncWritePosEx(cfg["id"], cfg["home_tick"], 350, 10)
        print(f"  -> {name} (ID {cfg['id']}): target {ticks_to_servo_deg(cfg['home_tick']):.1f}° ({cfg['home_tick']} ticks)")
    servo.groupSyncWrite.txPacket()
    time.sleep(1.0)
    print("Done.")


def play_trajectory(servo, active_servos: dict, csv_path: Path, time_scale: float = 1.0):
    df = pd.read_csv(csv_path)
    total_ms = float(df["time_ms"].iloc[-1]) * time_scale
    print(f"\nLoaded {csv_path.name} ({len(df)} steps | Time scale: {time_scale:.1f}x | Total time: {total_ms:.0f} ms)")

    # 1. Pre-position all active servos synchronously to the 0% initial frame
    print("Moving to initial 0% syllable pose...")
    servo.groupSyncWrite.clearParam()
    for name, cfg in active_servos.items():
        init_dtheta = float(df[cfg["dtheta_col"]].iloc[0])
        init_ticks = dtheta_to_ticks(init_dtheta, cfg)
        servo.SyncWritePosEx(cfg["id"], init_ticks, 350, 10)
    servo.groupSyncWrite.txPacket()
    time.sleep(0.8)

    # 2. Stream all 101 steps synchronously
    feedback_rows = []
    t_start = time.perf_counter()

    for _, row in df.iterrows():
        target_time_s = float(row["time_s"]) * time_scale
        servo.groupSyncWrite.clearParam()
        log_item = {"phase_pct": row["phase_pct"], "time_ms": float(row["time_ms"]) * time_scale}

        for name, cfg in active_servos.items():
            dtheta = float(row[cfg["dtheta_col"]])
            omega  = float(row[cfg["omega_col"]])
            alpha  = float(row[cfg["alpha_col"]])

            pos_ticks   = dtheta_to_ticks(dtheta, cfg)
            speed_steps = speed_degs_to_steps(omega, time_scale)
            acc_unit    = accel_degs2_to_unit(alpha, time_scale)

            servo.SyncWritePosEx(cfg["id"], pos_ticks, speed_steps, acc_unit)

            log_item[f"{name}_cmd_deg"]   = ticks_to_servo_deg(pos_ticks)
            log_item[f"{name}_cmd_ticks"] = pos_ticks
            log_item[f"{name}_cmd_speed"] = speed_steps
            log_item[f"{name}_cmd_acc"]   = acc_unit

        while (time.perf_counter() - t_start) < target_time_s:
            pass

        servo.groupSyncWrite.txPacket()

        for name, cfg in active_servos.items():
            pos_meas, comm, _ = servo.ReadPos(cfg["id"])
            if comm == COMM_SUCCESS:
                log_item[f"{name}_meas_deg"] = ticks_to_servo_deg(pos_meas)
                log_item[f"{name}_meas_dtheta_deg"] = ticks_to_dtheta_deg(pos_meas, cfg)
            else:
                log_item[f"{name}_meas_deg"] = np.nan
                log_item[f"{name}_meas_dtheta_deg"] = np.nan

        feedback_rows.append(log_item)

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Playback finished in {elapsed_ms:.1f} ms.")

    out_csv = csv_path.with_name(csv_path.stem + "_center_feedback.csv")
    pd.DataFrame(feedback_rows).to_csv(out_csv, index=False)
    print(f"Saved hardware execution log -> {out_csv}")


def main():
    parser = argparse.ArgumentParser(description="STS3215 Controller for Jaw (ID 1,2), Rack (ID 10), and Piston (ID 9)")
    parser.add_argument("--port", type=str, default="COM4", help="Serial port (default: COM4)")
    parser.add_argument("--mode", choices=["jaw", "rack", "upper", "all"], default="all",
                        help="Which mechanism(s) to drive: 'jaw' (ID 1,2), 'rack' (ID 10), 'upper' (ID 9), or 'all'")
    parser.add_argument("--check", action="store_true", help="Live monitor of angles and ticks")
    parser.add_argument("--go-home", action="store_true", help="Move smoothly to closed-mouth home pose")
    parser.add_argument("--csv", type=Path, help="Path to center_lips_trajectory_<SYL>.csv")
    parser.add_argument("--time-scale", type=float, default=1.0, help="Slow-motion multiplier (e.g. 2.0 = 2x slower)")
    args = parser.parse_args()

    active_servos = get_active_servos(args.mode)
    port = PortHandler(args.port)

    if not port.openPort():
        raise SystemExit(f"Could not open port {args.port}")
    if not port.setBaudRate(BAUDRATE):
        raise SystemExit(f"Could not set baudrate {BAUDRATE}")

    servo = STSDriver(port)

    try:
        if args.check:
            check_servos(servo, active_servos)
        elif args.go_home:
            go_home(servo, active_servos)
        elif args.csv:
            play_trajectory(servo, active_servos, args.csv.expanduser().resolve(), args.time_scale)
        else:
            print("Specify one of: --check, --go-home, or --csv <file>")
    finally:
        port.closePort()


if __name__ == "__main__":
    main()