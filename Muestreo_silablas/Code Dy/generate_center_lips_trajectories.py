"""Trajectory Generator for Chin/Jaw (IDs 1 & 2), Lower Lip Rack (ID 10), and Upper Lip Piston (ID 9).

Configured Hardware Ranges:
    - Left Jaw Servo  (ID 1):  180.0 deg (2048 ticks) Closed  --> 195.0 deg (2219 ticks) Fully Open (35 mm)
    - Right Jaw Servo (ID 2):  180.0 deg (2048 ticks) Closed  --> 165.0 deg (1877 ticks) Fully Open (35 mm)
    - Upper Lip Piston (ID 9): 180.0 deg (2048 ticks) Down    --> 140.0 deg (1593 ticks) Fully Up   (12.3 mm)
    - Lower Lip Rack  (ID 10):  81.0 deg (922 ticks)  Down    <-> 150.0 deg (1707 ticks) Fully Up   (13.3 mm)
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. CHIN / JAW PARAMETERS (BILATERAL CIRCULAR ARC: ID 1 LEFT, ID 2 RIGHT)
# ==============================================================================
JAW_HOME_DEG         = 180.0  # Fully closed (teeth touching) on both ID 1 and ID 2
JAW_MAX_DELTA_DEG    = 15.0   # 15° rotation -> ID 1 = 195°, ID 2 = 165°
JAW_MAX_OPENING_MM   = 35.0   # 35 mm opening at front center tooth when rotated 15°

# Effective circular radius from jaw servo axis to front center tooth: R = 35 / sin(15°) = 135.23 mm
JAW_RADIUS_MM        = JAW_MAX_OPENING_MM / np.sin(np.radians(JAW_MAX_DELTA_DEG))
JAW_GAIN             = 1.0    # Scale multiplier for chin movement (1.0 = exact 1:1 human scale)

# ==============================================================================
# 2. LOWER LIP PARAMETERS (RACK & PINION ON ID 10: 81° DOWN <-> 150° UP)
# ==============================================================================
PINION_PITCH_DIAM_MM  = 22.10  # Pitch diameter Dp (mm)
RACK_LENGTH_MM        = 29.50  # Total rack length (mm)
RACK_FORWARD_TILT_DEG = 12.50  # Forward tilt angle toward camera from vertical Y-axis (deg)

PINION_CIRCUMFERENCE_MM = np.pi * PINION_PITCH_DIAM_MM
DEG_PER_MM_RACK         = 360.0 / PINION_CIRCUMFERENCE_MM  # ~5.1851 deg/mm
MM_PER_DEG_RACK         = PINION_CIRCUMFERENCE_MM / 360.0  # ~0.1929 mm/deg

LOW_MIN_SERVO_DEG  = 81.0    # Fully DOWN limit (922 ticks)
LOW_MAX_SERVO_DEG  = 150.0   # Fully UP limit (1707 ticks)
LOW_HOME_SERVO_DEG = 125.0   # Neutral resting angle inside [81°, 150°] (1422 ticks)
                             # Allows -8.5 mm downward compensation (to 81°) and +4.8 mm upward (to 150°)

LOW_MIN_DISP_MM = (LOW_MIN_SERVO_DEG - LOW_HOME_SERVO_DEG) * MM_PER_DEG_RACK
LOW_MAX_DISP_MM = (LOW_MAX_SERVO_DEG - LOW_HOME_SERVO_DEG) * MM_PER_DEG_RACK
LOW_GAIN        = 1.0        # 1.0 = exact difference (BOCA_INF_EXT - BARBILLA)

# ==============================================================================
# 3. UPPER LIP PARAMETERS (3-LINK PISTON ON ID 9: 180° DOWN -> 140° UP)
# ==============================================================================
UP_L1_CRANK_MM   = 33.24  # Link 1: Servo center to first joint A (mm)
UP_L2_COUPLER_MM = 46.14  # Link 2: First joint A to slider pin joint B (mm)
UP_L3_PISTON_MM  = 43.50  # Link 3: Slider pin joint B to curved lip tip (mm)

UP_THETA0_DEG       = 45.0   # Crank angle (deg) when servo is at 180° (fully down)
UP_MAX_DTHETA_DEG   = 40.0   # Max allowed rotation (180° -> 140° = 40° range, ~12.3 mm lift)
UP_SLIDER_OFFSET_MM = 19.00  # Horizontal offset from servo shaft to vertical slider rail (mm)
UP_RAIL_TILT_DEG    = 0.0
UP_GAIN             = 3.0    # Amplification gain for upper lip lift (set 1.0 for raw human mm)

# ==============================================================================
# 4. GENERAL SCALING, SMOOTHING & SYLLABLES
# ==============================================================================
EYE_CORNER_SCALE_MM = 35.0
DEFAULT_DURATION_MS = 550.0
SMOOTH_SIGMA_STEPS  = 2.2

SYLLABLES = ["RA", "RE", "RI", "RO", "RU", "SA", "SE", "SI", "SO", "SU", "TA", "TE", "TI", "TO", "TU"]


# ==============================================================================
# 5. SMOOTHING & INVERSE KINEMATICS SOLVERS
# ==============================================================================
def smooth_curve(y: np.ndarray, sigma: float = SMOOTH_SIGMA_STEPS) -> np.ndarray:
    if sigma <= 0:
        return y.copy()
    radius = int(np.ceil(3.0 * sigma))
    x_kernel = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x_kernel / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(y, pad_width=radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def solve_jaw_ik(dy_jaw_front_mm: np.ndarray):
    """
    Solves the circular-arc jaw IK for ID 1 (Left: 180°->195°) and ID 2 (Right: 180°->165°).
    In physical coordinates (+Y upward), jaw opening occurs when dy_jaw_front_mm < 0.
    """
    # Shift baseline so frame 0 starts at 0.0 mm closed (180° on both servos)
    dy_jaw_shifted = (dy_jaw_front_mm - dy_jaw_front_mm[0]) * JAW_GAIN

    # Downward opening magnitude O_jaw in [0.0, 35.0] mm
    opening_raw_mm = -dy_jaw_shifted
    opening_mm = np.clip(opening_raw_mm, 0.0, JAW_MAX_OPENING_MM)
    clamped = (opening_raw_mm < 0.0) | (opening_raw_mm > JAW_MAX_OPENING_MM)

    # Circular arc IK: dtheta_jaw in [0.0°, 15.0°]
    sin_arg = np.clip(opening_mm / JAW_RADIUS_MM, 0.0, 1.0)
    dtheta_jaw_deg = np.clip(np.degrees(np.arcsin(sin_arg)), 0.0, JAW_MAX_DELTA_DEG)

    # Left (ID 1) rotates 180° -> 195° (+dtheta); Right (ID 2) rotates 180° -> 165° (-dtheta)
    jaw_left_id1_deg  = JAW_HOME_DEG + dtheta_jaw_deg
    jaw_right_id2_deg = JAW_HOME_DEG - dtheta_jaw_deg

    # Actual vertical jaw displacement achieved in physical +Y (upward) coordinates (<= 0 mm)
    dy_jaw_achieved_mm = -opening_mm

    return opening_mm, dy_jaw_achieved_mm, dtheta_jaw_deg, jaw_left_id1_deg, jaw_right_id2_deg, clamped


def solve_rack_pinion_ik(dy_lip_front_mm: np.ndarray, dy_jaw_achieved_mm: np.ndarray):
    """
    Moves the Lower Lip Rack & Pinion (ID 10) ONLY by the difference between
    the center lower lip (BOCA_INF_EXT) and the achieved chin/jaw position (BARBILLA).
    """
    tilt_rad = np.radians(RACK_FORWARD_TILT_DEG)

    # Shift lower lip so frame 0 aligns with neutral closed mouth
    dy_lip_shifted = dy_lip_front_mm - dy_lip_front_mm[0]

    # Residual difference: how much the lower lip moves relative to the moving jaw
    dy_rel_mm = (dy_lip_shifted - dy_jaw_achieved_mm) * LOW_GAIN

    # Project onto the 12.5° forward-tilted rack
    s_rack_raw_mm = dy_rel_mm / np.cos(tilt_rad)
    s_rack_mm = np.clip(s_rack_raw_mm, LOW_MIN_DISP_MM, LOW_MAX_DISP_MM)
    clamped = (s_rack_raw_mm < LOW_MIN_DISP_MM) | (s_rack_raw_mm > LOW_MAX_DISP_MM)

    dz_forward_mm = s_rack_mm * np.sin(tilt_rad)

    dtheta_rack_deg = s_rack_mm * DEG_PER_MM_RACK
    servo_target_deg = np.clip(LOW_HOME_SERVO_DEG + dtheta_rack_deg, LOW_MIN_SERVO_DEG, LOW_MAX_SERVO_DEG)
    dtheta_rack_deg = servo_target_deg - LOW_HOME_SERVO_DEG

    return s_rack_mm, dz_forward_mm, dtheta_rack_deg, servo_target_deg, dy_rel_mm, clamped


def get_upper_piston_limits():
    th_min = np.radians(UP_THETA0_DEG)
    th_max = np.radians(UP_THETA0_DEG + UP_MAX_DTHETA_DEG)

    x_A0, y_A0 = UP_L1_CRANK_MM * np.cos(th_min), UP_L1_CRANK_MM * np.sin(th_min)
    y_B_min = y_A0 - np.sqrt(UP_L2_COUPLER_MM**2 - (x_A0 - UP_SLIDER_OFFSET_MM)**2)

    x_A1, y_A1 = UP_L1_CRANK_MM * np.cos(th_max), UP_L1_CRANK_MM * np.sin(th_max)
    y_B_max = y_A1 - np.sqrt(UP_L2_COUPLER_MM**2 - (x_A1 - UP_SLIDER_OFFSET_MM)**2)

    return y_B_min, y_B_max


def solve_upper_piston_ik(dy_up_front_mm: np.ndarray):
    y_B_min, y_B_max = get_upper_piston_limits()
    max_stroke_mm = y_B_max - y_B_min
    rail_tilt_rad = np.radians(UP_RAIL_TILT_DEG)

    dy_shifted_mm = (dy_up_front_mm - np.min(dy_up_front_mm)) * UP_GAIN
    ds_raw_mm = dy_shifted_mm / np.cos(rail_tilt_rad)

    ds_piston_mm = np.clip(ds_raw_mm, 0.0, max_stroke_mm)
    clamped = (ds_raw_mm < 0.0) | (ds_raw_mm > max_stroke_mm)

    y_B_arr = y_B_min + ds_piston_mm
    y_tip_arr = y_B_arr - UP_L3_PISTON_MM
    theta_up_deg = np.zeros_like(ds_piston_mm)

    for i, y_B_target in enumerate(y_B_arr):
        d_B = np.hypot(UP_SLIDER_OFFSET_MM, y_B_target)
        phi_B = np.arctan2(y_B_target, UP_SLIDER_OFFSET_MM)
        cos_alpha = (UP_L1_CRANK_MM**2 + d_B**2 - UP_L2_COUPLER_MM**2) / (2.0 * UP_L1_CRANK_MM * d_B)
        cos_alpha = np.clip(cos_alpha, -1.0, 1.0)
        theta_up_deg[i] = np.degrees(phi_B + np.arccos(cos_alpha))

    dtheta_up_deg = np.clip(theta_up_deg - UP_THETA0_DEG, 0.0, UP_MAX_DTHETA_DEG)
    servo_target_deg = 180.0 - dtheta_up_deg

    return ds_piston_mm, y_B_arr, y_tip_arr, theta_up_deg, dtheta_up_deg, servo_target_deg, clamped


# ==============================================================================
# 6. BATCH PROCESSING & DERIVATIVE COMPUTATION
# ==============================================================================
def get_syllable_duration_ms(results_root: Path, syllable: str, fallback_ms: float) -> float:
    dur_csv = results_root / "quality_control" / syllable / "participant_durations.csv"
    if dur_csv.is_file():
        df_dur = pd.read_csv(dur_csv)
        if "mean_duration_ms" in df_dur.columns and df_dur["mean_duration_ms"].notna().any():
            return float(df_dur["mean_duration_ms"].mean())
    return fallback_ms


def process_syllable(csv_path: Path, results_root: Path, out_dir: Path, duration_override_ms: float | None):
    df = pd.read_csv(csv_path)
    syllable = str(df["syllable"].dropna().iloc[0]).upper() if "syllable" in df.columns else csv_path.parent.name.upper()

    mean_df = df.groupby("phase_pct", as_index=False).mean(numeric_only=True).sort_values("phase_pct")
    phases = mean_df["phase_pct"].to_numpy(dtype=float)

    duration_ms = duration_override_ms or get_syllable_duration_ms(results_root, syllable, DEFAULT_DURATION_MS)
    time_ms = (phases / 100.0) * duration_ms
    time_s  = time_ms / 1000.0

    # Convert CSV Y (positive downward) into physical vertical Y (positive upward, mm)
    dy_low_lip_mm = smooth_curve(-mean_df["BOCA_INF_EXT_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)
    dy_jaw_mm     = smooth_curve(-mean_df["BARBILLA_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)
    dy_up_lip_mm  = smooth_curve(-mean_df["BOCA_SUP_EXT_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)

    # --- 1. Chin / Jaw (ID 1 Left: 180°->195°, ID 2 Right: 180°->165°) ---
    jaw_open_mm, dy_jaw_ach_mm, dtheta_jaw_deg, jaw_id1_deg, jaw_id2_deg, jaw_clamped = solve_jaw_ik(dy_jaw_mm)
    jaw_lin_speed_mms  = np.gradient(jaw_open_mm, time_s)
    jaw_lin_accel_mms2 = np.gradient(jaw_lin_speed_mms, time_s)
    jaw_omega_degs     = np.gradient(dtheta_jaw_deg, time_s)
    jaw_alpha_degs2    = np.gradient(jaw_omega_degs, time_s)

    # --- 2. Lower Lip Rack & Pinion (ID 10: 81°..150°, compensating difference from Jaw) ---
    s_rack_mm, dz_low_mm, dtheta_rack_deg, low_servo_deg, dy_rel_low_mm, rack_clamped = solve_rack_pinion_ik(
        dy_low_lip_mm, dy_jaw_ach_mm
    )
    rack_lin_speed_mms  = np.gradient(s_rack_mm, time_s)
    rack_lin_accel_mms2 = np.gradient(rack_lin_speed_mms, time_s)
    rack_omega_degs     = np.gradient(dtheta_rack_deg, time_s)
    rack_alpha_degs2    = np.gradient(rack_omega_degs, time_s)

    # --- 3. Upper Lip Piston (ID 9: 180°..140°) ---
    ds_up_mm, y_B_mm, y_tip_mm, theta_up_deg, dtheta_up_deg, up_servo_deg, up_clamped = solve_upper_piston_ik(
        dy_up_lip_mm
    )
    up_lin_speed_mms  = np.gradient(ds_up_mm, time_s)
    up_lin_accel_mms2 = np.gradient(up_lin_speed_mms, time_s)
    up_omega_degs     = np.gradient(dtheta_up_deg, time_s)
    up_alpha_degs2    = np.gradient(up_omega_degs, time_s)

    out_df = pd.DataFrame({
        "phase_pct": phases,
        "time_ms": np.round(time_ms, 3),
        "time_s": np.round(time_s, 5),

        # Chin / Jaw Columns (ID 1 Left & ID 2 Right)
        "JAW_opening_mm": jaw_open_mm,
        "JAW_dy_achieved_mm": dy_jaw_ach_mm,
        "JAW_lin_speed_mms": jaw_lin_speed_mms,
        "JAW_lin_accel_mms2": jaw_lin_accel_mms2,
        "JAW_dtheta_deg": dtheta_jaw_deg,
        "JAW_LEFT_ID1_servo_deg": jaw_id1_deg,
        "JAW_RIGHT_ID2_servo_deg": jaw_id2_deg,
        "JAW_omega_speed_degs": jaw_omega_degs,
        "JAW_alpha_accel_degs2": jaw_alpha_degs2,
        "JAW_clamped": jaw_clamped,

        # Lower Lip Rack & Pinion Columns (ID 10: moves only difference from Jaw)
        "LOW_dy_lip_global_mm": dy_low_lip_mm,
        "LOW_dy_rel_from_jaw_mm": dy_rel_low_mm,
        "LOW_rack_pos_mm": s_rack_mm,
        "LOW_dz_forward_mm": dz_low_mm,
        "LOW_rack_speed_mms": rack_lin_speed_mms,
        "LOW_rack_accel_mms2": rack_lin_accel_mms2,
        "LOW_dtheta_deg": dtheta_rack_deg,
        "LOW_ID10_servo_deg": low_servo_deg,
        "LOW_omega_speed_degs": rack_omega_degs,
        "LOW_alpha_accel_degs2": rack_alpha_degs2,
        "LOW_clamped": rack_clamped,

        # Upper Lip Piston Columns (ID 9: 180° down to 140° up)
        "UP_dy_lip_global_mm": dy_up_lip_mm,
        "UP_piston_disp_mm": ds_up_mm,
        "UP_pinB_y_mm": y_B_mm,
        "UP_tip_y_mm": y_tip_mm,
        "UP_piston_speed_mms": up_lin_speed_mms,
        "UP_piston_accel_mms2": up_lin_accel_mms2,
        "UP_theta_crank_deg": theta_up_deg,
        "UP_dtheta_deg": dtheta_up_deg,
        "UP_ID9_servo_deg": up_servo_deg,
        "UP_omega_speed_degs": up_omega_degs,
        "UP_alpha_accel_degs2": up_alpha_degs2,
        "UP_clamped": up_clamped,
    })

    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"center_lips_trajectory_{syllable}.csv"
    out_df.to_csv(out_csv, index=False)

    plot_center_lips_profiles(out_df, syllable, duration_ms, out_dir / f"center_lips_profile_{syllable}.png")
    print(
        f"[{syllable}] T={duration_ms:.0f} ms | "
        f"Jaw(ID1/2): max {jaw_open_mm.max():.1f}mm ({dtheta_jaw_deg.max():.1f}°) | "
        f"Rack(ID10): {low_servo_deg.min():.1f}°..{low_servo_deg.max():.1f}° | "
        f"Upper(ID9): {up_servo_deg.max():.1f}°..{up_servo_deg.min():.1f}°"
    )


def plot_center_lips_profiles(df: pd.DataFrame, syllable: str, duration_ms: float, out_png: Path):
    t_ms = df["time_ms"].to_numpy()
    fig, axs = plt.subplots(4, 1, figsize=(10, 12), sharex=True)

    # 1. Linear Displacements (mm)
    axs[0].plot(t_ms, -df["JAW_opening_mm"], color="tab:green", lw=2, label="Chin / Jaw Drop (ID 1 & 2, mm)")
    axs[0].plot(t_ms, df["LOW_rack_pos_mm"], color="tab:blue", lw=2, label="Lower Lip Rack Compensation (ID 10, diff from Jaw)")
    axs[0].plot(t_ms, df["UP_piston_disp_mm"], color="tab:orange", lw=2, label=f"Upper Lip Piston Lift (ID 9, Gain={UP_GAIN}x)")
    axs[0].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[0].set_ylabel("Linear Disp (mm)")
    axs[0].set_title(f"{syllable}: Jaw (ID 1 & 2), Lower Rack (ID 10) & Upper Piston (ID 9) (T = {duration_ms:.0f} ms)")
    axs[0].grid(True, alpha=0.25)
    axs[0].legend(loc="best", fontsize=8)

    # 2. Target Servo Angles (deg)
    axs[1].plot(t_ms, df["JAW_LEFT_ID1_servo_deg"], color="tab:green", lw=2, label="Left Jaw ID 1 (180° -> 195°)")
    axs[1].plot(t_ms, df["JAW_RIGHT_ID2_servo_deg"], color="darkgreen", lw=2, ls="--", label="Right Jaw ID 2 (180° -> 165°)")
    axs[1].plot(t_ms, df["LOW_ID10_servo_deg"], color="tab:blue", lw=2, label=f"Lower Rack ID 10 (Home={LOW_HOME_SERVO_DEG:.0f}°, 81°..150°)")
    axs[1].plot(t_ms, df["UP_ID9_servo_deg"], color="tab:orange", lw=2, label="Upper Piston ID 9 (180° -> 140°)")
    axs[1].set_ylabel("Servo Angle (deg)")
    axs[1].grid(True, alpha=0.25)
    axs[1].legend(loc="best", fontsize=8)

    # 3. Angular Speeds (deg/s)
    axs[2].plot(t_ms, df["JAW_omega_speed_degs"], color="tab:green", lw=2, label=r"Jaw Speed $\omega$ (ID 1 & 2)")
    axs[2].plot(t_ms, df["LOW_omega_speed_degs"], color="tab:blue", lw=2, label=r"Lower Rack Speed $\omega$ (ID 10)")
    axs[2].plot(t_ms, df["UP_omega_speed_degs"], color="tab:orange", lw=2, label=r"Upper Piston Speed $\omega$ (ID 9)")
    axs[2].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[2].set_ylabel("Angular Speed (deg/s)")
    axs[2].grid(True, alpha=0.25)
    axs[2].legend(loc="best", fontsize=8)

    # 4. Angular Accelerations (deg/s^2)
    axs[3].plot(t_ms, df["JAW_alpha_accel_degs2"], color="tab:green", lw=2, label=r"Jaw Accel $\alpha$ (ID 1 & 2)")
    axs[3].plot(t_ms, df["LOW_alpha_accel_degs2"], color="tab:blue", lw=2, label=r"Lower Rack Accel $\alpha$ (ID 10)")
    axs[3].plot(t_ms, df["UP_alpha_accel_degs2"], color="tab:orange", lw=2, label=r"Upper Piston Accel $\alpha$ (ID 9)")
    axs[3].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[3].set_ylabel("Angular Accel (deg/s²)")
    axs[3].set_xlabel("Time (ms)")
    axs[3].grid(True, alpha=0.25)
    axs[3].legend(loc="best", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate trajectories for Jaw (ID 1,2), Rack (ID 10), and Piston (ID 9).")
    parser.add_argument("--results-root", type=Path, default=Path("orofacial_results"),
                        help="Path to orofacial_results folder")
    parser.add_argument("--syllable", type=str, default="ALL",
                        help="Syllable name (e.g. SA, SE) or ALL")
    parser.add_argument("--duration-ms", type=float, default=None,
                        help="Optional fixed duration in ms")
    args = parser.parse_args()

    results_root = args.results_root.expanduser().resolve()
    comp_root = results_root / "comparison"
    out_dir = results_root / "center_lips_trajectories"

    syllables = SYLLABLES if args.syllable.upper() == "ALL" else [args.syllable.upper()]

    for syl in syllables:
        csv_path = comp_root / syl / "participant_curves.csv"
        if not csv_path.is_file():
            print(f"[{syl}] Skipped (not found: {csv_path})")
            continue
        process_syllable(csv_path, results_root, out_dir, args.duration_ms)


if __name__ == "__main__":
    main()