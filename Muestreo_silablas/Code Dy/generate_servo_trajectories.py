"""Batch Inverse Kinematics & Motion Profile Generator (Position, Velocity, Acceleration).

Reads:
    orofacial_results/comparison/<SYL>/participant_curves.csv
    orofacial_results/quality_control/<SYL>/participant_durations.csv (if available)

Outputs (per syllable):
    1) orofacial_results/servo_trajectories/servo_trajectory_<SYL>.csv
       -> Contains time_ms, time_s, phase_pct, Cartesian (u, v, speed, accel),
          and Servo (theta, omega_speed, alpha_accel) for both RIGHT (DER) and LEFT (IZQ) sides.
    2) orofacial_results/servo_trajectories/robot_<SYL>.csv
       -> Ready for validation with:
          python orofacial_analysis.py --mode reference --syllable <SYL> --robot ...
    3) orofacial_results/servo_trajectories/kinematics_profile_<SYL>.png
       -> 3-panel plot of Servo Position (deg), Speed (deg/s), and Acceleration (deg/s^2).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. MECHANISM GEOMETRY & ORIENTATION (Option B: Origin at Bottom Shaft O2)
# ==============================================================================
L0 = 24.80   # Distance between servo shafts O2 -> O1 (mm)
L1 = 23.50   # Top servo horn length (mm)
L2 = 23.50   # Bottom servo horn length (mm)
L3 = 100.97  # Top passive coupler length (mm)
L4 = 63.31   # Bottom passive coupler length (mm)

O2 = np.array([0.0, 0.0])
O1 = np.array([0.0, L0])

# Neutral closed-mouth home position (when theta1 = +90 deg, theta2 = -90 deg)
P_HOME = np.array([62.901, -30.684])

# Measured 3D Mounting Angles in the Robot Head
PSI_DEG   = 71.00  # Angle of mechanism plane relative to frontal X-axis (deg)
ALPHA_DEG = 8.44   # Angle of servo shaft line O2->O1 relative to vertical Y-axis (deg)

# Scale factor: inner eye-corner distance (landmarks 133 <-> 362) in mm
EYE_CORNER_SCALE_MM = 35.0

# Default syllable duration (ms) if participant_durations.csv is not found
DEFAULT_DURATION_MS = 550.0

# Strain safety thresholds (deg)
BETA_MIN, BETA_MAX = 25.0, 155.0
GAMMA_MIN = 25.0

SYLLABLES = ["RA", "RE", "RI", "RO", "RU", "SA", "SE", "SI", "SO", "SU", "TA", "TE", "TI", "TO", "TU"]


# ==============================================================================
# 2. CORE INVERSE KINEMATICS & PROJECTION FUNCTIONS
# ==============================================================================
def solve_ik_local(u: float, v: float, enforce_strain: bool = True):
    """Solves Option B inverse kinematics for target (u, v) in mm."""
    P = np.array([u, v], dtype=float)
    v1, v2 = P - O1, P - O2
    d1, d2 = np.linalg.norm(v1), np.linalg.norm(v2)

    if not (abs(L3 - L1) < d1 < (L1 + L3)) or not (abs(L4 - L2) < d2 < (L2 + L4)):
        return None

    cos_a1 = np.clip((L1**2 + d1**2 - L3**2) / (2 * L1 * d1), -1.0, 1.0)
    cos_a2 = np.clip((L2**2 + d2**2 - L4**2) / (2 * L2 * d2), -1.0, 1.0)

    theta1 = np.arctan2(v1[1], v1[0]) + np.arccos(cos_a1)
    theta2 = np.arctan2(v2[1], v2[0]) - np.arccos(cos_a2)

    A = O1 + L1 * np.array([np.cos(theta1), np.sin(theta1)])
    B = O2 + L2 * np.array([np.cos(theta2), np.sin(theta2)])

    beta1 = np.degrees(np.arccos(np.clip((L1**2 + L3**2 - d1**2) / (2 * L1 * L3), -1.0, 1.0)))
    beta2 = np.degrees(np.arccos(np.clip((L2**2 + L4**2 - d2**2) / (2 * L2 * L4), -1.0, 1.0)))
    D_AB  = np.linalg.norm(A - B)
    gamma = np.degrees(np.arccos(np.clip((L3**2 + L4**2 - D_AB**2) / (2 * L3 * L4), -1.0, 1.0)))

    strain_ok = (
        (BETA_MIN <= beta1 <= BETA_MAX) and
        (BETA_MIN <= beta2 <= BETA_MAX) and
        (gamma >= GAMMA_MIN) and
        (A[1] > B[1] + 10.0)
    )
    if enforce_strain and not strain_ok:
        return None

    return {
        "u": u, "v": v,
        "theta1": np.degrees(theta1),
        "theta2": np.degrees(theta2),
        "beta1": beta1, "beta2": beta2, "gamma": gamma,
        "strain_ok": strain_ok
    }


def build_safe_workspace_cloud(grid_size: int = 250) -> np.ndarray:
    """Pre-computes all strain-free (u, v) points for nearest-neighbor safety clamping."""
    us = np.linspace(25.0, 85.0, grid_size)
    vs = np.linspace(-75.0, 5.0, grid_size)
    valid = [
        (u, v) for u in us for v in vs
        if solve_ik_local(u, v, enforce_strain=True) is not None
    ]
    return np.array(valid)


def frontal_to_local_uv(dX_front_mm: float, dY_front_mm: float, side: str) -> tuple[float, float]:
    """Projects frontal camera displacement (mm, +Y_front = UP) into tilted cheek plane (u, v)."""
    psi = np.radians(PSI_DEG)
    alpha = np.radians(ALPHA_DEG)

    # Mirror horizontal medial direction for right (DER) vs left (IZQ) cheek
    dX_medial = -dX_front_mm if side.upper() == "DER" else dX_front_mm

    du_horiz = dX_medial / np.cos(psi)
    dv_vert  = dY_front_mm

    du =  du_horiz * np.cos(alpha) + dv_vert * np.sin(alpha)
    dv = -du_horiz * np.sin(alpha) + dv_vert * np.cos(alpha)

    return float(P_HOME[0] + du), float(P_HOME[1] + dv)


def local_uv_to_frontal(u: float, v: float, side: str) -> tuple[float, float]:
    """Projects local mechanism (u, v) back into frontal camera (dX_front_mm, dY_front_mm)."""
    psi = np.radians(PSI_DEG)
    alpha = np.radians(ALPHA_DEG)

    du = u - P_HOME[0]
    dv = v - P_HOME[1]

    du_horiz = du * np.cos(alpha) - dv * np.sin(alpha)
    dv_vert  = du * np.sin(alpha) + dv * np.cos(alpha)

    dX_medial   = du_horiz * np.cos(psi)
    dX_front_mm = -dX_medial if side.upper() == "DER" else dX_medial
    dY_front_mm = dv_vert

    return float(dX_front_mm), float(dY_front_mm)


# ==============================================================================
# 3. COHORT LOADER & KINEMATIC DERIVATIVES (POSITION, SPEED, ACCELERATION)
# ==============================================================================
def get_syllable_duration_ms(results_root: Path, syllable: str, fallback_ms: float) -> float:
    """Reads mean syllable duration (ms) from quality_control/<SYL>/participant_durations.csv."""
    dur_csv = results_root / "quality_control" / syllable / "participant_durations.csv"
    if dur_csv.is_file():
        df_dur = pd.read_csv(dur_csv)
        if "mean_duration_ms" in df_dur.columns and df_dur["mean_duration_ms"].notna().any():
            return float(df_dur["mean_duration_ms"].mean())
    return fallback_ms


def process_syllable(csv_path: Path, results_root: Path, out_dir: Path,
                     safe_cloud: np.ndarray, duration_override_ms: float | None = None):
    df = pd.read_csv(csv_path)
    syllable = str(df["syllable"].dropna().iloc[0]).upper() if "syllable" in df.columns else csv_path.parent.name.upper()

    # Average across all participants for each phase_pct (0..100), matching orofacial_time_panel.py
    mean_df = df.groupby("phase_pct", as_index=False).mean(numeric_only=True).sort_values("phase_pct")
    phases = mean_df["phase_pct"].to_numpy(dtype=float)

    # Determine real-time vector in milliseconds and seconds
    duration_ms = duration_override_ms or get_syllable_duration_ms(results_root, syllable, DEFAULT_DURATION_MS)
    time_ms = (phases / 100.0) * duration_ms
    time_s  = time_ms / 1000.0

    traj_data = {
        "phase_pct": phases,
        "time_ms": np.round(time_ms, 3),
        "time_s": np.round(time_s, 5),
    }
    robot_val_data = {"phase_pct": phases}

    for side in ("DER", "IZQ"):
        dx_csv = mean_df[f"BOCA_{side}_Delta_X"].to_numpy(dtype=float)
        dy_csv = mean_df[f"BOCA_{side}_Delta_Y"].to_numpy(dtype=float)

        # Convert to physical frontal mm (negate Y because CSV Y increases downward)
        dX_front_mm =  dx_csv * EYE_CORNER_SCALE_MM
        dY_front_mm = -dy_csv * EYE_CORNER_SCALE_MM

        u_arr, v_arr = np.zeros_like(phases), np.zeros_like(phases)
        t1_arr, t2_arr = np.zeros_like(phases), np.zeros_like(phases)
        b1_arr, b2_arr, gam_arr = np.zeros_like(phases), np.zeros_like(phases), np.zeros_like(phases)
        clamped_arr = np.zeros(len(phases), dtype=bool)
        rob_dx_csv, rob_dy_csv = np.zeros_like(phases), np.zeros_like(phases)

        for i, (dx_m, dy_m) in enumerate(zip(dX_front_mm, dY_front_mm)):
            u_raw, v_raw = frontal_to_local_uv(dx_m, dy_m, side=side)
            sol = solve_ik_local(u_raw, v_raw, enforce_strain=True)

            if sol is None:
                clamped_arr[i] = True
                dists = np.linalg.norm(safe_cloud - np.array([u_raw, v_raw]), axis=1)
                u_safe, v_safe = safe_cloud[np.argmin(dists)]
                sol = solve_ik_local(u_safe, v_safe, enforce_strain=False)

            u_arr[i], v_arr[i] = sol["u"], sol["v"]
            t1_arr[i], t2_arr[i] = sol["theta1"], sol["theta2"]
            b1_arr[i], b2_arr[i], gam_arr[i] = sol["beta1"], sol["beta2"], sol["gamma"]

            ach_dx_mm, ach_dy_mm = local_uv_to_frontal(sol["u"], sol["v"], side=side)
            rob_dx_csv[i] =  ach_dx_mm / EYE_CORNER_SCALE_MM
            rob_dy_csv[i] = -ach_dy_mm / EYE_CORNER_SCALE_MM

        # --- Compute Linear Velocity (mm/s) and Acceleration (mm/s^2) ---
        vu_mms = np.gradient(u_arr, time_s)
        vv_mms = np.gradient(v_arr, time_s)
        lin_speed_mms = np.hypot(vu_mms, vv_mms)

        au_mms2 = np.gradient(vu_mms, time_s)
        av_mms2 = np.gradient(vv_mms, time_s)
        lin_accel_mms2 = np.hypot(au_mms2, av_mms2)

        # --- Compute Angular Velocity (deg/s) and Acceleration (deg/s^2) ---
        omega1_degs = np.gradient(t1_arr, time_s)
        omega2_degs = np.gradient(t2_arr, time_s)

        alpha1_degs2 = np.gradient(omega1_degs, time_s)
        alpha2_degs2 = np.gradient(omega2_degs, time_s)

        # Store in main trajectory dictionary
        traj_data[f"{side}_u_mm"] = u_arr
        traj_data[f"{side}_v_mm"] = v_arr
        traj_data[f"{side}_lin_speed_mms"] = lin_speed_mms
        traj_data[f"{side}_lin_accel_mms2"] = lin_accel_mms2

        traj_data[f"{side}_theta1_deg"] = t1_arr
        traj_data[f"{side}_theta2_deg"] = t2_arr
        traj_data[f"{side}_dtheta1_from_90_deg"] = t1_arr - 90.0
        traj_data[f"{side}_dtheta2_from_neg90_deg"] = t2_arr + 90.0

        traj_data[f"{side}_omega1_speed_degs"] = omega1_degs
        traj_data[f"{side}_omega2_speed_degs"] = omega2_degs
        traj_data[f"{side}_alpha1_accel_degs2"] = alpha1_degs2
        traj_data[f"{side}_alpha2_accel_degs2"] = alpha2_degs2

        traj_data[f"{side}_beta1_deg"] = b1_arr
        traj_data[f"{side}_beta2_deg"] = b2_arr
        traj_data[f"{side}_gamma_deg"] = gam_arr
        traj_data[f"{side}_clamped"] = clamped_arr

        robot_val_data[f"BOCA_{side}_Delta_X"] = rob_dx_csv
        robot_val_data[f"BOCA_{side}_Delta_Y"] = rob_dy_csv

    out_dir.mkdir(parents=True, exist_ok=True)
    traj_df = pd.DataFrame(traj_data)
    robot_df = pd.DataFrame(robot_val_data)

    traj_csv = out_dir / f"servo_trajectory_{syllable}.csv"
    robot_csv = out_dir / f"robot_{syllable}.csv"
    traj_df.to_csv(traj_csv, index=False)
    robot_df.to_csv(robot_csv, index=False)

    plot_kinematic_profiles(traj_df, syllable, duration_ms, out_dir / f"kinematics_profile_{syllable}.png")
    print(f"[{syllable}] Duration: {duration_ms:.1f} ms | Saved -> {traj_csv.name}")


def plot_kinematic_profiles(df: pd.DataFrame, syllable: str, duration_ms: float, out_png: Path):
    """Generates a 3-panel plot of Position (deg), Velocity (deg/s), and Acceleration (deg/s^2)."""
    t_ms = df["time_ms"].to_numpy()
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    # 1. Angular Position Change from Neutral (deg)
    ax1.plot(t_ms, df["DER_dtheta1_from_90_deg"], color="tab:purple", lw=2, label="Top Servo 1 (from +90°)")
    ax1.plot(t_ms, df["DER_dtheta2_from_neg90_deg"], color="tab:blue", lw=2, label="Bottom Servo 2 (from -90°)")
    ax1.axhline(0, color="k", lw=0.7, alpha=0.4)
    ax1.set_ylabel("Angle Offset (deg)")
    ax1.set_title(f"{syllable} (Right Mechanism): Angular Position, Speed & Acceleration (T = {duration_ms:.0f} ms)")
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best")

    # 2. Angular Velocity / Speed (deg/s)
    ax2.plot(t_ms, df["DER_omega1_speed_degs"], color="tab:purple", lw=2, label=r"$\omega_1$ Top Servo Speed")
    ax2.plot(t_ms, df["DER_omega2_speed_degs"], color="tab:blue", lw=2, label=r"$\omega_2$ Bottom Servo Speed")
    ax2.axhline(0, color="k", lw=0.7, alpha=0.4)
    ax2.set_ylabel("Angular Speed (deg/s)")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="best")

    # 3. Angular Acceleration (deg/s^2)
    ax3.plot(t_ms, df["DER_alpha1_accel_degs2"], color="tab:purple", lw=2, label=r"$\alpha_1$ Top Servo Accel")
    ax3.plot(t_ms, df["DER_alpha2_accel_degs2"], color="tab:blue", lw=2, label=r"$\alpha_2$ Bottom Servo Accel")
    ax3.axhline(0, color="k", lw=0.7, alpha=0.4)
    ax3.set_ylabel("Angular Accel (deg/s²)")
    ax3.set_xlabel("Time (ms)")
    ax3.grid(True, alpha=0.25)
    ax3.legend(loc="best")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate servo position, speed, and acceleration CSVs.")
    parser.add_argument("--results-root", type=Path, default=Path("orofacial_results"),
                        help="Path to orofacial_results folder")
    parser.add_argument("--syllable", type=str, default="ALL",
                        help="Syllable name (e.g. SA, SE) or ALL")
    parser.add_argument("--duration-ms", type=float, default=None,
                        help="Optional fixed duration in ms (overrides participant_durations.csv)")
    args = parser.parse_args()

    results_root = args.results_root.expanduser().resolve()
    comp_root = results_root / "comparison"
    out_dir = results_root / "servo_trajectories"

    syllables = SYLLABLES if args.syllable.upper() == "ALL" else [args.syllable.upper()]
    print("Pre-computing strain-free 5-bar workspace cloud...")
    safe_cloud = build_safe_workspace_cloud()

    for syl in syllables:
        csv_path = comp_root / syl / "participant_curves.csv"
        if not csv_path.is_file():
            print(f"[{syl}] Skipped (not found: {csv_path})")
            continue
        process_syllable(csv_path, results_root, out_dir, safe_cloud, args.duration_ms)


if __name__ == "__main__":
    main()