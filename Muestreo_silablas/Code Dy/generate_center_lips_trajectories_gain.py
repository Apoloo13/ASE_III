"""Standalone Trajectory Generator for Center Upper Lip (Piston) & Lower Lip (Rack & Pinion).

Fixes included:
    1) Shifts upper-lip curve baseline by the full-curve minimum so rounded vowels (SO, SU)
       never flatline against the 180.0 deg mechanical stop.
    2) Adds UP_GAIN (default 5.0x) and LOW_GAIN (default 2.0x) so sub-millimeter human skin
       displacements scale into visible mechanical strokes within [140 deg, 180 deg].
    3) Applies Gaussian trajectory smoothing before differentiation to eliminate acceleration spikes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. LOWER LIP PARAMETERS (RACK & PINION + JAW COMPENSATION)
# ==============================================================================
PINION_PITCH_DIAM_MM = 22.10   # Pitch diameter Dp (mm)
RACK_LENGTH_MM       = 29.50   # Total physical rack length (mm)
RACK_TILT_DEG        = 12.50   # Backward tilt angle from vertical Y-axis (deg)

PINION_CIRCUMFERENCE_MM = np.pi * PINION_PITCH_DIAM_MM
DEG_PER_MM_RACK         = 360.0 / PINION_CIRCUMFERENCE_MM  # ~5.1851 deg/mm

JAW_COMPENSATION_FACTOR = 1.0  # 1.0 = rack compensates difference between lower lip and chin
LOW_GAIN                = 2.0  # Amplification gain for lower lip rack stroke
MAX_RACK_DISP_MM        = 14.0

# ==============================================================================
# 2. UPPER LIP PARAMETERS (3-LINK PISTON, 180° DOWN -> 140° UP)
# ==============================================================================
UP_L1_CRANK_MM   = 33.24  # Link 1: Servo center to first joint A (mm)
UP_L2_COUPLER_MM = 46.14  # Link 2: First joint A to slider pin joint B (mm)
UP_L3_PISTON_MM  = 43.50  # Link 3: Slider pin joint B to curved lip tip (mm)

UP_THETA0_DEG       = 45.0   # Crank angle (deg) when servo is at 180° (fully down)
UP_MAX_DTHETA_DEG   = 40.0   # Max allowed rotation (180° -> 140° = 40° range, ~12.3 mm lift)
UP_SLIDER_OFFSET_MM = 19.00  # Horizontal offset from servo shaft to vertical slider rail (mm)
UP_RAIL_TILT_DEG    = 0.0

# Mechanical amplification factor for the upper lip (scales 1.3 mm raw skin motion -> ~6.5 mm piston lift)
UP_GAIN = 5.0

# ==============================================================================
# 3. GENERAL SCALING, SMOOTHING & SYLLABLES
# ==============================================================================
EYE_CORNER_SCALE_MM = 35.0   # Inner eye-corner scale (mm)
DEFAULT_DURATION_MS = 550.0
SMOOTH_SIGMA_STEPS  = 2.2    # Gaussian smoothing width (in phase_pct steps) for clean speed/accel

SYLLABLES = ["RA", "RE", "RI", "RO", "RU", "SA", "SE", "SI", "SO", "SU", "TA", "TE", "TI", "TO", "TU"]


# ==============================================================================
# 4. SMOOTHING & INVERSE KINEMATICS SOLVERS
# ==============================================================================
def smooth_curve(y: np.ndarray, sigma: float = SMOOTH_SIGMA_STEPS) -> np.ndarray:
    """Applies a zero-phase Gaussian smoothing filter using pure NumPy (no SciPy needed)."""
    if sigma <= 0:
        return y.copy()
    radius = int(np.ceil(3.0 * sigma))
    x_kernel = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x_kernel / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(y, pad_width=radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def solve_rack_pinion_ik(dy_lip_front_mm: np.ndarray, dy_jaw_front_mm: np.ndarray):
    tilt_rad = np.radians(RACK_TILT_DEG)
    dy_rel_mm = (dy_lip_front_mm - (JAW_COMPENSATION_FACTOR * dy_jaw_front_mm)) * LOW_GAIN

    s_rack_raw_mm = dy_rel_mm / np.cos(tilt_rad)
    s_rack_mm = np.clip(s_rack_raw_mm, -MAX_RACK_DISP_MM, MAX_RACK_DISP_MM)
    clamped = np.abs(s_rack_raw_mm) > MAX_RACK_DISP_MM

    dtheta_rack_deg = s_rack_mm * DEG_PER_MM_RACK
    return s_rack_mm, dtheta_rack_deg, dy_rel_mm, clamped


def get_upper_piston_limits():
    """Calculates pin B vertical coordinates at 180° (fully down) and 140° (+40° fully up)."""
    th_min = np.radians(UP_THETA0_DEG)
    th_max = np.radians(UP_THETA0_DEG + UP_MAX_DTHETA_DEG)

    x_A0, y_A0 = UP_L1_CRANK_MM * np.cos(th_min), UP_L1_CRANK_MM * np.sin(th_min)
    y_B_min = y_A0 - np.sqrt(UP_L2_COUPLER_MM**2 - (x_A0 - UP_SLIDER_OFFSET_MM)**2)

    x_A1, y_A1 = UP_L1_CRANK_MM * np.cos(th_max), UP_L1_CRANK_MM * np.sin(th_max)
    y_B_max = y_A1 - np.sqrt(UP_L2_COUPLER_MM**2 - (x_A1 - UP_SLIDER_OFFSET_MM)**2)

    return y_B_min, y_B_max  # ~12.29 mm max stroke


def solve_upper_piston_ik(dy_up_front_mm: np.ndarray):
    """
    Shifts the syllable curve so its global minimum sits at 0.0 mm (180.0 deg),
    scales by UP_GAIN, and solves the 3-link piston IK within [180.0 deg, 140.0 deg].
    """
    y_B_min, y_B_max = get_upper_piston_limits()
    max_stroke_mm = y_B_max - y_B_min
    rail_tilt_rad = np.radians(UP_RAIL_TILT_DEG)

    # Shift by the global minimum of the curve so negative dips (like in "SO") never flatline!
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
    servo_target_deg = 180.0 - dtheta_up_deg  # 180° fully down -> 140° fully up

    return ds_piston_mm, y_B_arr, y_tip_arr, theta_up_deg, dtheta_up_deg, servo_target_deg, clamped


# ==============================================================================
# 5. BATCH PROCESSING & DERIVATIVE COMPUTATION
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

    # Extract raw CSV Y (negated so +Y is physical upward in mm) and smooth before IK
    dy_low_lip_mm = smooth_curve(-mean_df["BOCA_INF_EXT_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)
    dy_jaw_mm     = smooth_curve(-mean_df["BARBILLA_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)
    dy_up_lip_mm  = smooth_curve(-mean_df["BOCA_SUP_EXT_Delta_Y"].to_numpy(dtype=float) * EYE_CORNER_SCALE_MM)

    # --- 1. Lower Lip (Rack & Pinion) ---
    s_rack_mm, dtheta_rack_deg, dy_rel_low_mm, rack_clamped = solve_rack_pinion_ik(dy_low_lip_mm, dy_jaw_mm)
    rack_lin_speed_mms  = np.gradient(s_rack_mm, time_s)
    rack_lin_accel_mms2 = np.gradient(rack_lin_speed_mms, time_s)
    rack_omega_degs     = np.gradient(dtheta_rack_deg, time_s)
    rack_alpha_degs2    = np.gradient(rack_omega_degs, time_s)

    # --- 2. Upper Lip (3-Link Piston, 180° -> 140°) ---
    ds_up_mm, y_B_mm, y_tip_mm, theta_up_deg, dtheta_up_deg, up_servo_deg, up_clamped = solve_upper_piston_ik(dy_up_lip_mm)
    up_lin_speed_mms  = np.gradient(ds_up_mm, time_s)
    up_lin_accel_mms2 = np.gradient(up_lin_speed_mms, time_s)
    up_omega_degs     = np.gradient(dtheta_up_deg, time_s)
    up_alpha_degs2    = np.gradient(up_omega_degs, time_s)

    out_df = pd.DataFrame({
        "phase_pct": phases,
        "time_ms": np.round(time_ms, 3),
        "time_s": np.round(time_s, 5),

        # Lower Lip (Rack & Pinion)
        "LOW_dy_lip_global_mm": dy_low_lip_mm,
        "LOW_dy_jaw_global_mm": dy_jaw_mm,
        "LOW_dy_rel_compensated_mm": dy_rel_low_mm,
        "LOW_rack_pos_mm": s_rack_mm,
        "LOW_rack_speed_mms": rack_lin_speed_mms,
        "LOW_rack_accel_mms2": rack_lin_accel_mms2,
        "LOW_dtheta_deg": dtheta_rack_deg,
        "LOW_servo_deg_from_180": 180.0 + dtheta_rack_deg,
        "LOW_omega_speed_degs": rack_omega_degs,
        "LOW_alpha_accel_degs2": rack_alpha_degs2,
        "LOW_clamped": rack_clamped,

        # Upper Lip (Piston, 180° down to 140° up)
        "UP_dy_lip_global_mm": dy_up_lip_mm,
        "UP_piston_disp_mm": ds_up_mm,
        "UP_pinB_y_mm": y_B_mm,
        "UP_tip_y_mm": y_tip_mm,
        "UP_piston_speed_mms": up_lin_speed_mms,
        "UP_piston_accel_mms2": up_lin_accel_mms2,
        "UP_theta_crank_deg": theta_up_deg,
        "UP_dtheta_deg": dtheta_up_deg,
        "UP_servo_deg_180_to_140": up_servo_deg,
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
        f"Upper Lift: {ds_up_mm.max():.1f} mm ({up_servo_deg.max():.1f}° -> {up_servo_deg.min():.1f}°) | "
        f"Saved -> {out_csv.name}"
    )


def plot_center_lips_profiles(df: pd.DataFrame, syllable: str, duration_ms: float, out_png: Path):
    t_ms = df["time_ms"].to_numpy()
    fig, axs = plt.subplots(4, 1, figsize=(10, 11), sharex=True)

    axs[0].plot(t_ms, df["LOW_rack_pos_mm"], color="tab:blue", lw=2, label=f"Lower Lip Rack Travel (Gain={LOW_GAIN}x)")
    axs[0].plot(t_ms, df["UP_piston_disp_mm"], color="tab:orange", lw=2, label=f"Upper Lip Piston Lift (Gain={UP_GAIN}x, Max=12.3 mm)")
    axs[0].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[0].set_ylabel("Linear Disp (mm)")
    axs[0].set_title(f"{syllable}: Center Upper & Lower Lip Kinematics (Duration = {duration_ms:.0f} ms)")
    axs[0].grid(True, alpha=0.25)
    axs[0].legend(loc="best")

    axs[1].plot(t_ms, df["LOW_servo_deg_from_180"], color="tab:blue", lw=2, label="Lower Pinion Servo Angle (deg)")
    axs[1].plot(t_ms, df["UP_servo_deg_180_to_140"], color="tab:orange", lw=2, label="Upper Piston Servo Angle (180° down -> 140° up)")
    axs[1].axhline(180.0, color="k", lw=0.7, ls="--", alpha=0.5, label="180° Down Limit")
    axs[1].axhline(140.0, color="tab:red", lw=0.7, ls=":", alpha=0.6, label="140° Upper Limit")
    axs[1].set_ylabel("Servo Angle (deg)")
    axs[1].grid(True, alpha=0.25)
    axs[1].legend(loc="best")

    axs[2].plot(t_ms, df["LOW_omega_speed_degs"], color="tab:blue", lw=2, label=r"Lower Pinion Speed $\omega$ (deg/s)")
    axs[2].plot(t_ms, df["UP_omega_speed_degs"], color="tab:orange", lw=2, label=r"Upper Crank Speed $\omega$ (deg/s)")
    axs[2].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[2].set_ylabel("Angular Speed (deg/s)")
    axs[2].grid(True, alpha=0.25)
    axs[2].legend(loc="best")

    axs[3].plot(t_ms, df["LOW_alpha_accel_degs2"], color="tab:blue", lw=2, label=r"Lower Pinion Accel $\alpha$ (deg/s²)")
    axs[3].plot(t_ms, df["UP_alpha_accel_degs2"], color="tab:orange", lw=2, label=r"Upper Crank Accel $\alpha$ (deg/s²)")
    axs[3].axhline(0, color="k", lw=0.7, alpha=0.4)
    axs[3].set_ylabel("Angular Accel (deg/s²)")
    axs[3].set_xlabel("Time (ms)")
    axs[3].grid(True, alpha=0.25)
    axs[3].legend(loc="best")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate trajectories for Upper Lip Piston & Lower Lip Rack/Pinion.")
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