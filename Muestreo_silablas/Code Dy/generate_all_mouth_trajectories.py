# -*- coding: utf-8 -*-
"""Unified Trajectory Generator for the 8-Servo Orofacial Robotic Simulator.

Combines:
    1) Bilateral 5-Bar Corner Lip Mechanisms (Right: IDs 5 & 6, Left: IDs 7 & 8)
       -> Tracks BOCA_DER (291) and BOCA_IZQ (61)
    2) Bilateral Circular-Arc Chin / Jaw Mechanism (Left: ID 1, Right: ID 2)
       -> Tracks BARBILLA (152)
    3) Upper Center Lip 3-Link Offset Slider-Crank Piston (ID 9)
       -> Tracks BOCA_SUP_EXT (0)
    4) Lower Center Lip Tilted Rack & Pinion with Jaw Compensation (ID 10)
       -> Tracks difference between BOCA_INF_EXT (17) and achieved BARBILLA (152)

Cohort Validation:
    - Reads `orofacial_results/comparison/<SYL>/participant_curves.csv`
    - Filters out any participant with missing/NaN frames
    - Computes the true 50-participant cohort mean (`_mean`) and SD (`_sd`)
      across all valid participants (1 trajectory per participant)
    - Exports:
        * `orofacial_results/mouth_trajectories/mouth_trajectory_<SYL>.csv`
          (Unified 8-servo kinematics + human mean/SD + target robot Delta_X/Y)
        * `orofacial_results/mouth_trajectories/robot_target_<SYL>.csv`
          (Formatted directly for `orofacial_analysis.py --mode reference --robot ...`)
        * `orofacial_results/mouth_trajectories/mouth_profile_<SYL>.png`
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ==============================================================================
# 1. CENTRALIZED MECHANISM PARAMETERS (EDIT HERE OR VIA JSON CONFIG)
# ==============================================================================
MECHANISM_PARAMS = {
    "general": {
        "eye_corner_scale_mm": 35.0,      # Inner eye-corner distance (landmarks 133 <-> 362) in mm
        "default_duration_ms": 550.0,     # Fallback duration if participant_durations.csv is missing
        "smooth_sigma_steps": 2.0,        # Gaussian smoothing sigma (in 0..100% phase steps; 0 = off)
        "min_expected_participants": 45,  # Warn if fewer than this many valid participants are found
    },

    # --- A. Corner Lips: Bilateral 2-DOF 5-Bar Parallel Linkage (IDs 5, 6, 7, 8) ---
    "corner_5bar": {
        "L0_ground_mm": 24.80,            # Vertical distance between bottom shaft O2(0,0) and top shaft O1(0,L0)
        "L1_top_crank_mm": 23.50,         # Top servo horn length O1 -> A (mm)
        "L2_bottom_crank_mm": 23.50,      # Bottom servo horn length O2 -> B (mm)
        "L3_top_coupler_mm": 100.97,      # Top passive coupler length A -> P (mm)
        "L4_bottom_coupler_mm": 63.31,    # Bottom passive coupler length B -> P (mm)
        "theta1_neutral_deg": 90.0,       # Math neutral angle of top horn (+90° = straight up, 180° on servo)
        "theta2_neutral_deg": -90.0,      # Math neutral angle of bottom horn (-90° = straight down, 180° on servo)
        "psi_cheek_yaw_deg": 71.00,       # Angle of 5-bar plane relative to frontal X-axis (deg)
        "alpha_mount_tilt_deg": 8.44,     # In-plane tilt of O2->O1 line relative to vertical Y-axis (deg)
        "gain_x": 1.0,                    # Horizontal displacement multiplier for BOCA_DER / BOCA_IZQ
        "gain_y": 1.0,                    # Vertical displacement multiplier for BOCA_DER / BOCA_IZQ
        "lower_lip_vertical_blend": 0.0,  # 0.0 = pure corner Y; >0 blends BOCA_INF_EXT_Delta_Y into corner Y
        "beta_min_deg": 25.0,             # Minimum safe interior elbow angle at A and B (deg)
        "beta_max_deg": 155.0,            # Maximum safe interior elbow angle at A and B (deg)
        "gamma_min_deg": 25.0,            # Minimum safe transmission angle between L3 and L4 at P (deg)
        "min_horn_clearance_mm": 10.0,    # Minimum vertical clearance A_y - B_y to prevent horn collision (mm)
    },

    # --- B. Chin / Jaw: Bilateral Circular-Arc Mechanism (Left = ID 1, Right = ID 2) ---
    "jaw": {
        "home_servo_deg": 180.0,          # Closed mouth (teeth touching) on both ID 1 and ID 2
        "left_id1_open_deg": 195.0,       # Left jaw servo (ID 1) angle at full opening (+15° from 180°)
        "right_id2_open_deg": 165.0,      # Right jaw servo (ID 2) angle at full opening (-15° from 180°)
        "max_delta_deg": 15.0,            # Max angular stroke from closed to fully open (deg)
        "max_tooth_opening_mm": 35.0,     # Vertical opening at front center tooth when rotated max_delta_deg (mm)
        "gain_y": 1.0,                    # Multiplier on BARBILLA_Delta_Y (1.0 = 1:1 human scale)
    },

    # --- C. Upper Center Lip: 3-Link Offset Slider-Crank Piston (ID 9) ---
    "upper_piston": {
        "L1_crank_mm": 33.24,             # Link 1: Servo shaft O_up to first joint A_up (mm)
        "L2_coupler_mm": 46.14,           # Link 2: First joint A_up to slider pin B_up (mm)
        "L3_piston_tip_mm": 43.50,        # Link 3: Slider pin B_up to curved upper-lip tip (mm)
        "theta0_crank_deg": 45.0,         # Math crank angle (from +X) when servo is at 180° (fully down)
        "slider_offset_x_mm": 19.00,      # Horizontal offset (e) from servo shaft to vertical slider rail (mm)
        "rail_tilt_deg": 0.0,             # In-plane tilt of the slider guide rail from vertical Y-axis (deg)
        "servo_down_limit_deg": 180.0,    # Servo ID 9 angle when fully DOWN (2048 ticks)
        "servo_up_limit_deg": 140.0,      # Servo ID 9 angle when fully UP (1593 ticks -> 40° max stroke)
        "gain_y": 3.0,                    # Amplification gain on BOCA_SUP_EXT_Delta_Y
        "shift_min_to_zero": True,        # Shifts curve minimum to 180° so rounded vowels (SO/SU) never flatline
    },

    # --- D. Lower Center Lip: Forward-Tilted Rack & Pinion on Jaw (ID 10) ---
    "lower_rack": {
        "pinion_pitch_diam_mm": 22.10,    # Pinion pitch diameter Dp (mm) -> L_rev = pi * Dp = 69.43 mm
        "rack_length_mm": 29.50,          # Total physical rack length (mm)
        "forward_tilt_deg": 12.50,        # Forward tilt toward camera relative to vertical Y-axis (deg)
        "servo_min_down_deg": 81.0,       # Servo ID 10 angle when rack is all the way DOWN (922 ticks)
        "servo_max_up_deg": 150.0,        # Servo ID 10 angle when rack is all the way UP (1707 ticks)
        "servo_home_deg": 125.0,          # Neutral resting angle on ID 10 (1422 ticks)
        "jaw_compensation_factor": 1.0,   # 1.0 = rack moves only the residual (BOCA_INF_EXT - BARBILLA_achieved)
        "gain_y": 1.0,                    # Multiplier on residual lower-lip displacement
    },
}

SYLLABLES = ["RA", "RE", "RI", "RO", "RU", "SA", "SE", "SI", "SO", "SU", "TA", "TE", "TI", "TO", "TU"]
LANDMARKS = [
    "BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_SUP_INT", "BOCA_INF_INT",
    "BOCA_IZQ", "BOCA_DER", "BARBILLA", "MANDIBULA_IZQ", "MANDIBULA_DER",
]


# ==============================================================================
# 2. SIGNAL SMOOTHING & COHORT AGGREGATION (50 PARTICIPANTS)
# ==============================================================================
def smooth_curve(y: np.ndarray, sigma: float) -> np.ndarray:
    """Zero-phase Gaussian filter using pure NumPy."""
    if sigma <= 0:
        return y.copy()
    radius = int(np.ceil(3.0 * sigma))
    x_kernel = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x_kernel / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(y, pad_width=radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def load_validated_cohort_stats(csv_path: Path, min_expected: int = 45):
    """
    Loads `participant_curves.csv`, verifies that each participant has a complete
    101-point trajectory with finite values across the main landmarks, and returns:
      - phases (0..100)
      - mean_dict: {col: 101-array of cohort mean}
      - sd_dict:   {col: 101-array of cohort SD (ddof=1)}
      - n_valid:   number of valid participants included in the mean
    """
    df = pd.read_csv(csv_path)
    if "phase_pct" not in df.columns or "participant" not in df.columns:
        raise ValueError(f"{csv_path} must contain 'participant' and 'phase_pct' columns.")

    req_cols = [f"{pt}_Delta_{ax}" for pt in LANDMARKS[:7] for ax in ("X", "Y")]
    missing = [c for c in req_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing landmark columns: {missing}")

    for c in ["phase_pct"] + req_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    valid_participants = {}
    rejected_participants = []

    for person, group in df.groupby("participant"):
        g = group.sort_values("phase_pct")
        if len(g) != 101 or g[req_cols].isna().any().any():
            rejected_participants.append(person)
            continue
        valid_participants[person] = g

    n_valid = len(valid_participants)
    if n_valid == 0:
        raise ValueError(f"No valid participant trajectories found in {csv_path}")

    if n_valid < min_expected:
        print(f"  [WARN] {csv_path.parent.name}: {n_valid} valid participants (< {min_expected}).")
    if rejected_participants:
        print(f"  [INFO] Filtered out {len(rejected_participants)} incomplete participant(s): {rejected_participants}")

    phases = next(iter(valid_participants.values()))["phase_pct"].to_numpy(dtype=float)
    mean_dict, sd_dict = {}, {}

    for col in req_cols:
        stack = np.vstack([g[col].to_numpy(dtype=float) for g in valid_participants.values()])
        mean_dict[col] = np.mean(stack, axis=0)
        sd_dict[col] = np.std(stack, axis=0, ddof=1) if n_valid > 1 else np.zeros_like(phases)

    return phases, mean_dict, sd_dict, n_valid


# ==============================================================================
# 3. MECHANISM 1: CORNER LIPS 2-DOF 5-BAR LINKAGE (IDs 5, 6, 7, 8)
# ==============================================================================
def compute_5bar_home(cfg_5bar: dict) -> np.ndarray:
    """Computes neutral P_HOME(u, v) directly from L0, L1, L2, L3, L4 and neutral horn angles."""
    L0 = cfg_5bar["L0_ground_mm"]
    L1 = cfg_5bar["L1_top_crank_mm"]
    L2 = cfg_5bar["L2_bottom_crank_mm"]
    L3 = cfg_5bar["L3_top_coupler_mm"]
    L4 = cfg_5bar["L4_bottom_coupler_mm"]
    th1 = np.radians(cfg_5bar["theta1_neutral_deg"])
    th2 = np.radians(cfg_5bar["theta2_neutral_deg"])

    A0 = np.array([L1 * np.cos(th1), L0 + L1 * np.sin(th1)])
    B0 = np.array([L2 * np.cos(th2), L2 * np.sin(th2)])

    d_AB = B0 - A0
    dist = np.linalg.norm(d_AB)
    a = (L3**2 - L4**2 + dist**2) / (2.0 * dist)
    h = np.sqrt(max(L3**2 - a**2, 0.0))
    mid = A0 + (a / dist) * d_AB
    # Right-hand intersection (+u forward toward lips)
    perp = np.array([-d_AB[1] / dist, d_AB[0] / dist])
    P1 = mid + h * perp
    P2 = mid - h * perp
    return P1 if P1[0] >= P2[0] else P2


def solve_5bar_ik_local(u: float, v: float, cfg_5bar: dict, enforce_strain: bool = True):
    """Solves Option B (origin at O2(0,0)) inverse kinematics for target (u, v) in mm."""
    L0 = cfg_5bar["L0_ground_mm"]
    L1 = cfg_5bar["L1_top_crank_mm"]
    L2 = cfg_5bar["L2_bottom_crank_mm"]
    L3 = cfg_5bar["L3_top_coupler_mm"]
    L4 = cfg_5bar["L4_bottom_coupler_mm"]

    O2 = np.array([0.0, 0.0])
    O1 = np.array([0.0, L0])
    P = np.array([u, v], dtype=float)

    v1, v2 = P - O1, P - O2
    d1, d2 = np.linalg.norm(v1), np.linalg.norm(v2)

    if not (abs(L3 - L1) < d1 < (L1 + L3)) or not (abs(L4 - L2) < d2 < (L2 + L4)):
        return None

    cos_a1 = np.clip((L1**2 + d1**2 - L3**2) / (2.0 * L1 * d1), -1.0, 1.0)
    cos_a2 = np.clip((L2**2 + d2**2 - L4**2) / (2.0 * L2 * d2), -1.0, 1.0)

    theta1 = np.arctan2(v1[1], v1[0]) + np.arccos(cos_a1)
    theta2 = np.arctan2(v2[1], v2[0]) - np.arccos(cos_a2)

    A = O1 + L1 * np.array([np.cos(theta1), np.sin(theta1)])
    B = O2 + L2 * np.array([np.cos(theta2), np.sin(theta2)])

    beta1 = np.degrees(np.arccos(np.clip((L1**2 + L3**2 - d1**2) / (2.0 * L1 * L3), -1.0, 1.0)))
    beta2 = np.degrees(np.arccos(np.clip((L2**2 + L4**2 - d2**2) / (2.0 * L2 * L4), -1.0, 1.0)))
    D_AB  = np.linalg.norm(A - B)
    gamma = np.degrees(np.arccos(np.clip((L3**2 + L4**2 - D_AB**2) / (2.0 * L3 * L4), -1.0, 1.0)))

    strain_ok = (
        (cfg_5bar["beta_min_deg"] <= beta1 <= cfg_5bar["beta_max_deg"]) and
        (cfg_5bar["beta_min_deg"] <= beta2 <= cfg_5bar["beta_max_deg"]) and
        (gamma >= cfg_5bar["gamma_min_deg"]) and
        (A[1] > B[1] + cfg_5bar["min_horn_clearance_mm"])
    )
    if enforce_strain and not strain_ok:
        return None

    return {
        "u": u, "v": v,
        "theta1": np.degrees(theta1),
        "theta2": np.degrees(theta2),
        "beta1": beta1, "beta2": beta2, "gamma": gamma,
        "strain_ok": strain_ok,
    }


def build_safe_workspace_cloud(cfg_5bar: dict, grid_size: int = 240) -> np.ndarray:
    P_home = compute_5bar_home(cfg_5bar)
    us = np.linspace(P_home[0] - 40.0, P_home[0] + 25.0, grid_size)
    vs = np.linspace(P_home[1] - 45.0, P_home[1] + 35.0, grid_size)
    valid = [
        (u, v) for u in us for v in vs
        if solve_5bar_ik_local(u, v, cfg_5bar, enforce_strain=True) is not None
    ]
    return np.array(valid)


def frontal_to_local_uv(dX_front_mm: float, dY_front_mm: float, side: str, cfg_5bar: dict, P_home: np.ndarray):
    psi = np.radians(cfg_5bar["psi_cheek_yaw_deg"])
    alpha = np.radians(cfg_5bar["alpha_mount_tilt_deg"])

    dX_medial = -dX_front_mm if side.upper() == "DER" else dX_front_mm
    du_horiz = dX_medial / np.cos(psi)
    dv_vert  = dY_front_mm

    du =  du_horiz * np.cos(alpha) + dv_vert * np.sin(alpha)
    dv = -du_horiz * np.sin(alpha) + dv_vert * np.cos(alpha)
    return float(P_home[0] + du), float(P_home[1] + dv)


def local_uv_to_frontal(u: float, v: float, side: str, cfg_5bar: dict, P_home: np.ndarray):
    psi = np.radians(cfg_5bar["psi_cheek_yaw_deg"])
    alpha = np.radians(cfg_5bar["alpha_mount_tilt_deg"])

    du = u - P_home[0]
    dv = v - P_home[1]

    du_horiz = du * np.cos(alpha) - dv * np.sin(alpha)
    dv_vert  = du * np.sin(alpha) + dv * np.cos(alpha)

    dX_medial   = du_horiz * np.cos(psi)
    dX_front_mm = -dX_medial if side.upper() == "DER" else dX_medial
    dY_front_mm = dv_vert
    return float(dX_front_mm), float(dY_front_mm)


# ==============================================================================
# 4. MECHANISMS 2, 3, 4: CHIN/JAW (IDs 1,2), RACK (ID 10), UPPER PISTON (ID 9)
# ==============================================================================
def solve_jaw_ik(dy_jaw_front_mm: np.ndarray, cfg_jaw: dict):
    max_open = cfg_jaw["max_tooth_opening_mm"]
    max_deg  = cfg_jaw["max_delta_deg"]
    home_deg = cfg_jaw["home_servo_deg"]
    radius   = max_open / np.sin(np.radians(max_deg))

    dy_jaw_shifted = (dy_jaw_front_mm - dy_jaw_front_mm[0]) * cfg_jaw["gain_y"]
    opening_raw_mm = -dy_jaw_shifted
    opening_mm = np.clip(opening_raw_mm, 0.0, max_open)
    clamped = (opening_raw_mm < 0.0) | (opening_raw_mm > max_open)

    sin_arg = np.clip(opening_mm / radius, 0.0, 1.0)
    dtheta_jaw_deg = np.clip(np.degrees(np.arcsin(sin_arg)), 0.0, max_deg)

    jaw_left_id1_deg  = home_deg + dtheta_jaw_deg
    jaw_right_id2_deg = home_deg - dtheta_jaw_deg
    dy_jaw_achieved_mm = -opening_mm

    return opening_mm, dy_jaw_achieved_mm, dtheta_jaw_deg, jaw_left_id1_deg, jaw_right_id2_deg, clamped


def solve_rack_pinion_ik(dy_lip_front_mm: np.ndarray, dy_jaw_achieved_mm: np.ndarray, cfg_rack: dict):
    circumference = np.pi * cfg_rack["pinion_pitch_diam_mm"]
    deg_per_mm = 360.0 / circumference
    mm_per_deg = circumference / 360.0

    min_deg  = cfg_rack["servo_min_down_deg"]
    max_deg  = cfg_rack["servo_max_up_deg"]
    home_deg = cfg_rack["servo_home_deg"]

    min_disp_mm = (min_deg - home_deg) * mm_per_deg
    max_disp_mm = (max_deg - home_deg) * mm_per_deg
    tilt_rad = np.radians(cfg_rack["forward_tilt_deg"])

    dy_lip_shifted = dy_lip_front_mm - dy_lip_front_mm[0]
    dy_rel_mm = (dy_lip_shifted - cfg_rack["jaw_compensation_factor"] * dy_jaw_achieved_mm) * cfg_rack["gain_y"]

    s_rack_raw_mm = dy_rel_mm / np.cos(tilt_rad)
    s_rack_mm = np.clip(s_rack_raw_mm, min_disp_mm, max_disp_mm)
    clamped = (s_rack_raw_mm < min_disp_mm) | (s_rack_raw_mm > max_disp_mm)

    dz_forward_mm = s_rack_mm * np.sin(tilt_rad)
    dtheta_rack_deg = s_rack_mm * deg_per_mm
    servo_target_deg = np.clip(home_deg + dtheta_rack_deg, min_deg, max_deg)
    dtheta_rack_deg = servo_target_deg - home_deg

    # Total vertical lower-lip position achieved in frontal frame (jaw + vertical projection of rack)
    dy_low_lip_achieved_mm = cfg_rack["jaw_compensation_factor"] * dy_jaw_achieved_mm + (s_rack_mm * np.cos(tilt_rad)) / max(cfg_rack["gain_y"], 1e-6)

    return s_rack_mm, dz_forward_mm, dtheta_rack_deg, servo_target_deg, dy_rel_mm, dy_low_lip_achieved_mm, clamped


def solve_upper_piston_ik(dy_up_front_mm: np.ndarray, cfg_up: dict):
    L1 = cfg_up["L1_crank_mm"]
    L2 = cfg_up["L2_coupler_mm"]
    L3 = cfg_up["L3_piston_tip_mm"]
    th0_deg = cfg_up["theta0_crank_deg"]
    max_dtheta = abs(cfg_up["servo_down_limit_deg"] - cfg_up["servo_up_limit_deg"])
    offset_x = cfg_up["slider_offset_x_mm"]
    rail_tilt = np.radians(cfg_up["rail_tilt_deg"])

    th_min = np.radians(th0_deg)
    th_max = np.radians(th0_deg + max_dtheta)

    x_A0, y_A0 = L1 * np.cos(th_min), L1 * np.sin(th_min)
    y_B_min = y_A0 - np.sqrt(max(L2**2 - (x_A0 - offset_x)**2, 0.0))

    x_A1, y_A1 = L1 * np.cos(th_max), L1 * np.sin(th_max)
    y_B_max = y_A1 - np.sqrt(max(L2**2 - (x_A1 - offset_x)**2, 0.0))
    max_stroke_mm = y_B_max - y_B_min

    baseline = np.min(dy_up_front_mm) if cfg_up.get("shift_min_to_zero", True) else dy_up_front_mm[0]
    dy_shifted_mm = (dy_up_front_mm - baseline) * cfg_up["gain_y"]
    ds_raw_mm = dy_shifted_mm / np.cos(rail_tilt)

    ds_piston_mm = np.clip(ds_raw_mm, 0.0, max_stroke_mm)
    clamped = (ds_raw_mm < 0.0) | (ds_raw_mm > max_stroke_mm)

    y_B_arr = y_B_min + ds_piston_mm
    y_tip_arr = y_B_arr - L3
    theta_up_deg = np.zeros_like(ds_piston_mm)

    for i, y_B_target in enumerate(y_B_arr):
        d_B = np.hypot(offset_x, y_B_target)
        phi_B = np.arctan2(y_B_target, offset_x)
        cos_alpha = np.clip((L1**2 + d_B**2 - L2**2) / (2.0 * L1 * d_B), -1.0, 1.0)
        theta_up_deg[i] = np.degrees(phi_B + np.arccos(cos_alpha))

    dtheta_up_deg = np.clip(theta_up_deg - th0_deg, 0.0, max_dtheta)
    servo_target_deg = cfg_up["servo_down_limit_deg"] - dtheta_up_deg
    dy_up_achieved_mm = (ds_piston_mm * np.cos(rail_tilt)) / max(cfg_up["gain_y"], 1e-6) + baseline

    return ds_piston_mm, y_B_arr, y_tip_arr, theta_up_deg, dtheta_up_deg, servo_target_deg, dy_up_achieved_mm, clamped


# ==============================================================================
# 5. UNIFIED SYLLABLES PROCESSOR
# ==============================================================================
def get_syllable_duration_ms(results_root: Path, syllable: str, fallback_ms: float) -> float:
    dur_csv = results_root / "quality_control" / syllable / "participant_durations.csv"
    if dur_csv.is_file():
        df_dur = pd.read_csv(dur_csv)
        if "mean_duration_ms" in df_dur.columns and df_dur["mean_duration_ms"].notna().any():
            return float(df_dur["mean_duration_ms"].mean())
    return fallback_ms


def process_syllable(
    csv_path: Path,
    results_root: Path,
    out_dir: Path,
    params: dict,
    safe_cloud: np.ndarray,
    P_home_5bar: np.ndarray,
    duration_override_ms: float | None = None,
):
    gen_cfg  = params["general"]
    cfg_5bar = params["corner_5bar"]
    cfg_jaw  = params["jaw"]
    cfg_up   = params["upper_piston"]
    cfg_rack = params["lower_rack"]

    syllable = csv_path.parent.name.upper()
    phases, mean_dict, sd_dict, n_valid = load_validated_cohort_stats(
        csv_path, gen_cfg["min_expected_participants"]
    )

    duration_ms = duration_override_ms or get_syllable_duration_ms(
        results_root, syllable, gen_cfg["default_duration_ms"]
    )
    time_ms = (phases / 100.0) * duration_ms
    time_s  = time_ms / 1000.0
    scale_mm = gen_cfg["eye_corner_scale_mm"]
    sigma = gen_cfg["smooth_sigma_steps"]

    traj_data = {
        "syllable": [syllable] * len(phases),
        "n_participants": [n_valid] * len(phases),
        "phase_pct": phases,
        "time_ms": np.round(time_ms, 3),
        "time_s": np.round(time_s, 5),
    }

    # Save the validated 50-participant human cohort mean and SD directly in the CSV
    for pt in LANDMARKS[:7]:
        for ax in ("X", "Y"):
            col = f"{pt}_Delta_{ax}"
            traj_data[f"HUMAN_{col}_mean"] = mean_dict[col]
            traj_data[f"HUMAN_{col}_sd"]   = sd_dict[col]

    robot_val_data = {"phase_pct": phases}

    # --- 1. Corner 5-Bar Mechanisms (DER: IDs 5 & 6, IZQ: IDs 7 & 8) ---
    th1_neutral = cfg_5bar["theta1_neutral_deg"]
    th2_neutral = cfg_5bar["theta2_neutral_deg"]
    blend_w = cfg_5bar["lower_lip_vertical_blend"]

    for side in ("DER", "IZQ"):
        dx_csv = smooth_curve(mean_dict[f"BOCA_{side}_Delta_X"], sigma) * cfg_5bar["gain_x"]
        dy_corner = smooth_curve(mean_dict[f"BOCA_{side}_Delta_Y"], sigma)
        dy_inf = smooth_curve(mean_dict["BOCA_INF_EXT_Delta_Y"], sigma)
        dy_csv = ((1.0 - blend_w) * dy_corner + blend_w * dy_inf) * cfg_5bar["gain_y"]

        dX_front_mm =  dx_csv * scale_mm
        dY_front_mm = -dy_csv * scale_mm

        u_arr, v_arr = np.zeros_like(phases), np.zeros_like(phases)
        t1_arr, t2_arr = np.zeros_like(phases), np.zeros_like(phases)
        b1_arr, b2_arr, gam_arr = np.zeros_like(phases), np.zeros_like(phases), np.zeros_like(phases)
        clamped_arr = np.zeros(len(phases), dtype=bool)
        rob_dx_csv, rob_dy_csv = np.zeros_like(phases), np.zeros_like(phases)

        for i, (dx_m, dy_m) in enumerate(zip(dX_front_mm, dY_front_mm)):
            u_raw, v_raw = frontal_to_local_uv(dx_m, dy_m, side, cfg_5bar, P_home_5bar)
            sol = solve_5bar_ik_local(u_raw, v_raw, cfg_5bar, enforce_strain=True)

            if sol is None:
                clamped_arr[i] = True
                dists = np.linalg.norm(safe_cloud - np.array([u_raw, v_raw]), axis=1)
                u_safe, v_safe = safe_cloud[np.argmin(dists)]
                sol = solve_5bar_ik_local(u_safe, v_safe, cfg_5bar, enforce_strain=False)

            u_arr[i], v_arr[i] = sol["u"], sol["v"]
            t1_arr[i], t2_arr[i] = sol["theta1"], sol["theta2"]
            b1_arr[i], b2_arr[i], gam_arr[i] = sol["beta1"], sol["beta2"], sol["gamma"]

            ach_dx_mm, ach_dy_mm = local_uv_to_frontal(sol["u"], sol["v"], side, cfg_5bar, P_home_5bar)
            rob_dx_csv[i] =  ach_dx_mm / scale_mm
            rob_dy_csv[i] = -ach_dy_mm / scale_mm

        vu_mms = np.gradient(u_arr, time_s)
        vv_mms = np.gradient(v_arr, time_s)
        lin_speed_mms = np.hypot(vu_mms, vv_mms)
        au_mms2 = np.gradient(vu_mms, time_s)
        av_mms2 = np.gradient(vv_mms, time_s)
        lin_accel_mms2 = np.hypot(au_mms2, av_mms2)

        omega1_degs = np.gradient(t1_arr, time_s)
        omega2_degs = np.gradient(t2_arr, time_s)
        alpha1_degs2 = np.gradient(omega1_degs, time_s)
        alpha2_degs2 = np.gradient(omega2_degs, time_s)

        traj_data[f"{side}_u_mm"] = u_arr
        traj_data[f"{side}_v_mm"] = v_arr
        traj_data[f"{side}_lin_speed_mms"] = lin_speed_mms
        traj_data[f"{side}_lin_accel_mms2"] = lin_accel_mms2

        traj_data[f"{side}_theta1_deg"] = t1_arr
        traj_data[f"{side}_theta2_deg"] = t2_arr
        traj_data[f"{side}_dtheta1_from_90_deg"] = t1_arr - th1_neutral
        traj_data[f"{side}_dtheta2_from_neg90_deg"] = t2_arr - th2_neutral

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
        traj_data[f"ROBOT_TARGET_BOCA_{side}_Delta_X"] = rob_dx_csv
        traj_data[f"ROBOT_TARGET_BOCA_{side}_Delta_Y"] = rob_dy_csv

    # --- 2. Chin / Jaw (IDs 1 & 2) ---
    dy_jaw_mm = smooth_curve(-mean_dict["BARBILLA_Delta_Y"] * scale_mm, sigma)
    jaw_open_mm, dy_jaw_ach_mm, dtheta_jaw_deg, jaw_id1_deg, jaw_id2_deg, jaw_clamped = solve_jaw_ik(
        dy_jaw_mm, cfg_jaw
    )
    jaw_lin_speed_mms  = np.gradient(jaw_open_mm, time_s)
    jaw_lin_accel_mms2 = np.gradient(jaw_lin_speed_mms, time_s)
    jaw_omega_degs     = np.gradient(dtheta_jaw_deg, time_s)
    jaw_alpha_degs2    = np.gradient(jaw_omega_degs, time_s)

    traj_data["JAW_opening_mm"] = jaw_open_mm
    traj_data["JAW_dy_achieved_mm"] = dy_jaw_ach_mm
    traj_data["JAW_lin_speed_mms"] = jaw_lin_speed_mms
    traj_data["JAW_lin_accel_mms2"] = jaw_lin_accel_mms2
    traj_data["JAW_dtheta_deg"] = dtheta_jaw_deg
    traj_data["JAW_LEFT_ID1_servo_deg"] = jaw_id1_deg
    traj_data["JAW_RIGHT_ID2_servo_deg"] = jaw_id2_deg
    traj_data["JAW_omega_speed_degs"] = jaw_omega_degs
    traj_data["JAW_alpha_accel_degs2"] = jaw_alpha_degs2
    traj_data["JAW_clamped"] = jaw_clamped

    rob_barbilla_dx = np.zeros_like(phases)
    rob_barbilla_dy = -dy_jaw_ach_mm / scale_mm
    robot_val_data["BARBILLA_Delta_X"] = rob_barbilla_dx
    robot_val_data["BARBILLA_Delta_Y"] = rob_barbilla_dy
    traj_data["ROBOT_TARGET_BARBILLA_Delta_X"] = rob_barbilla_dx
    traj_data["ROBOT_TARGET_BARBILLA_Delta_Y"] = rob_barbilla_dy

    # --- 3. Lower Center Lip Rack & Pinion (ID 10) ---
    dy_low_lip_mm = smooth_curve(-mean_dict["BOCA_INF_EXT_Delta_Y"] * scale_mm, sigma)
    (
        s_rack_mm,
        dz_low_mm,
        dtheta_rack_deg,
        low_servo_deg,
        dy_rel_low_mm,
        dy_low_ach_mm,
        rack_clamped,
    ) = solve_rack_pinion_ik(dy_low_lip_mm, dy_jaw_ach_mm, cfg_rack)

    rack_lin_speed_mms  = np.gradient(s_rack_mm, time_s)
    rack_lin_accel_mms2 = np.gradient(rack_lin_speed_mms, time_s)
    rack_omega_degs     = np.gradient(dtheta_rack_deg, time_s)
    rack_alpha_degs2    = np.gradient(rack_omega_degs, time_s)

    traj_data["LOW_dy_lip_global_mm"] = dy_low_lip_mm
    traj_data["LOW_dy_rel_from_jaw_mm"] = dy_rel_low_mm
    traj_data["LOW_rack_pos_mm"] = s_rack_mm
    traj_data["LOW_dz_forward_mm"] = dz_low_mm
    traj_data["LOW_rack_speed_mms"] = rack_lin_speed_mms
    traj_data["LOW_rack_accel_mms2"] = rack_lin_accel_mms2
    traj_data["LOW_dtheta_deg"] = dtheta_rack_deg
    traj_data["LOW_ID10_servo_deg"] = low_servo_deg
    traj_data["LOW_omega_speed_degs"] = rack_omega_degs
    traj_data["LOW_alpha_accel_degs2"] = rack_alpha_degs2
    traj_data["LOW_clamped"] = rack_clamped

    rob_boca_inf_dx = np.zeros_like(phases)
    rob_boca_inf_dy = -dy_low_ach_mm / scale_mm
    robot_val_data["BOCA_INF_EXT_Delta_X"] = rob_boca_inf_dx
    robot_val_data["BOCA_INF_EXT_Delta_Y"] = rob_boca_inf_dy
    traj_data["ROBOT_TARGET_BOCA_INF_EXT_Delta_X"] = rob_boca_inf_dx
    traj_data["ROBOT_TARGET_BOCA_INF_EXT_Delta_Y"] = rob_boca_inf_dy

    # --- 4. Upper Center Lip 3-Link Piston (ID 9) ---
    dy_up_lip_mm = smooth_curve(-mean_dict["BOCA_SUP_EXT_Delta_Y"] * scale_mm, sigma)
    (
        ds_up_mm,
        y_B_mm,
        y_tip_mm,
        theta_up_deg,
        dtheta_up_deg,
        up_servo_deg,
        dy_up_ach_mm,
        up_clamped,
    ) = solve_upper_piston_ik(dy_up_lip_mm, cfg_up)

    up_lin_speed_mms  = np.gradient(ds_up_mm, time_s)
    up_lin_accel_mms2 = np.gradient(up_lin_speed_mms, time_s)
    up_omega_degs     = np.gradient(dtheta_up_deg, time_s)
    up_alpha_degs2    = np.gradient(up_omega_degs, time_s)

    traj_data["UP_dy_lip_global_mm"] = dy_up_lip_mm
    traj_data["UP_piston_disp_mm"] = ds_up_mm
    traj_data["UP_pinB_y_mm"] = y_B_mm
    traj_data["UP_tip_y_mm"] = y_tip_mm
    traj_data["UP_piston_speed_mms"] = up_lin_speed_mms
    traj_data["UP_piston_accel_mms2"] = up_lin_accel_mms2
    traj_data["UP_theta_crank_deg"] = theta_up_deg
    traj_data["UP_dtheta_deg"] = dtheta_up_deg
    traj_data["UP_ID9_servo_deg"] = up_servo_deg
    traj_data["UP_omega_speed_degs"] = up_omega_degs
    traj_data["UP_alpha_accel_degs2"] = up_alpha_degs2
    traj_data["UP_clamped"] = up_clamped

    rob_boca_sup_dx = np.zeros_like(phases)
    rob_boca_sup_dy = -dy_up_ach_mm / scale_mm
    robot_val_data["BOCA_SUP_EXT_Delta_X"] = rob_boca_sup_dx
    robot_val_data["BOCA_SUP_EXT_Delta_Y"] = rob_boca_sup_dy
    traj_data["ROBOT_TARGET_BOCA_SUP_EXT_Delta_X"] = rob_boca_sup_dx
    traj_data["ROBOT_TARGET_BOCA_SUP_EXT_Delta_Y"] = rob_boca_sup_dy

    out_dir.mkdir(parents=True, exist_ok=True)
    traj_df = pd.DataFrame(traj_data)
    robot_df = pd.DataFrame(robot_val_data)

    traj_csv = out_dir / f"mouth_trajectory_{syllable}.csv"
    robot_csv = out_dir / f"robot_target_{syllable}.csv"
    traj_df.to_csv(traj_csv, index=False)
    robot_df.to_csv(robot_csv, index=False)

    plot_unified_summary(traj_df, syllable, n_valid, duration_ms, out_dir / f"mouth_profile_{syllable}.png")
    print(
        f"[{syllable}] n={n_valid} participants | T={duration_ms:.0f} ms | "
        f"Jaw: {jaw_open_mm.max():.1f}mm | Rack(ID10): {low_servo_deg.min():.1f}°..{low_servo_deg.max():.1f}° | "
        f"Upper(ID9): {up_servo_deg.max():.1f}°..{up_servo_deg.min():.1f}° -> {traj_csv.name}"
    )


def plot_unified_summary(df: pd.DataFrame, syllable: str, n_valid: int, duration_ms: float, out_png: Path):
    t_ms = df["time_ms"].to_numpy()
    fig, axs = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

    # 1. Corner 5-Bar Angles (IDs 5, 6, 7, 8)
    axs[0].plot(t_ms, 180.0 - df["DER_dtheta1_from_90_deg"], label="DER_TOP (ID 5)", lw=1.8)
    axs[0].plot(t_ms, 180.0 - df["DER_dtheta2_from_neg90_deg"], label="DER_BOTTOM (ID 6)", lw=1.8)
    axs[0].plot(t_ms, 180.0 + df["IZQ_dtheta1_from_90_deg"], label="IZQ_TOP (ID 7)", lw=1.8, ls="--")
    axs[0].plot(t_ms, 180.0 + df["IZQ_dtheta2_from_neg90_deg"], label="IZQ_BOTTOM (ID 8)", lw=1.8, ls="--")
    axs[0].axhline(180.0, color="k", lw=0.7, alpha=0.4)
    axs[0].set_ylabel("Corner Servos (deg)")
    axs[0].set_title(f"{syllable} (n={n_valid} participants, T={duration_ms:.0f} ms): Unified 8-Servo Trajectories")
    axs[0].grid(True, alpha=0.25)
    axs[0].legend(loc="best", ncol=2, fontsize=8)

    # 2. Jaw & Center Lip Angles (IDs 1, 2, 9, 10)
    axs[1].plot(t_ms, df["JAW_LEFT_ID1_servo_deg"], color="tab:green", lw=2, label="JAW_LEFT (ID 1: 180°->195°)")
    axs[1].plot(t_ms, df["JAW_RIGHT_ID2_servo_deg"], color="darkgreen", lw=2, ls="--", label="JAW_RIGHT (ID 2: 180°->165°)")
    axs[1].plot(t_ms, df["UP_ID9_servo_deg"], color="tab:orange", lw=2, label="UP_PISTON (ID 9: 180°->140°)")
    axs[1].plot(t_ms, df["LOW_ID10_servo_deg"], color="tab:blue", lw=2, label="LOW_RACK (ID 10: 81°..150°)")
    axs[1].set_ylabel("Center/Jaw Servos (deg)")
    axs[1].grid(True, alpha=0.25)
    axs[1].legend(loc="best", ncol=2, fontsize=8)

    # 3. Angular Speeds (deg/s)
    axs[2].plot(t_ms, df["DER_omega1_speed_degs"], label="DER_TOP ω", alpha=0.8)
    axs[2].plot(t_ms, df["DER_omega2_speed_degs"], label="DER_BOTTOM ω", alpha=0.8)
    axs[2].plot(t_ms, df["JAW_omega_speed_degs"], label="JAW ω (ID 1,2)", lw=1.8, color="tab:green")
    axs[2].plot(t_ms, df["UP_omega_speed_degs"], label="UP_PISTON ω (ID 9)", lw=1.8, color="tab:orange")
    axs[2].plot(t_ms, df["LOW_omega_speed_degs"], label="LOW_RACK ω (ID 10)", lw=1.8, color="tab:blue")
    axs[2].axhline(0.0, color="k", lw=0.7, alpha=0.4)
    axs[2].set_ylabel("Angular Speed (deg/s)")
    axs[2].set_xlabel("Time (ms)")
    axs[2].grid(True, alpha=0.25)
    axs[2].legend(loc="best", ncol=3, fontsize=8)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Unified 8-Servo Orofacial Trajectory Generator.")
    parser.add_argument("--results-root", type=Path, default=Path("orofacial_results"),
                        help="Path to orofacial_results directory")
    parser.add_argument("--syllable", type=str, default="ALL",
                        help="Syllable name (e.g. SA, SE) or ALL")
    parser.add_argument("--duration-ms", type=float, default=None,
                        help="Optional fixed duration in ms (overrides participant_durations.csv)")
    parser.add_argument("--config", type=Path, default=None,
                        help="Optional JSON file overriding MECHANISM_PARAMS")
    parser.add_argument("--save-default-config", type=Path, default=None,
                        help="Save MECHANISM_PARAMS to a JSON file for easy editing and exit")
    args = parser.parse_args()

    params = json.loads(json.dumps(MECHANISM_PARAMS))
    if args.save_default_config is not None:
        args.save_default_config.write_text(json.dumps(params, indent=4), encoding="utf-8")
        print(f"Saved editable configuration file -> {args.save_default_config}")
        return

    if args.config is not None and args.config.is_file():
        user_cfg = json.loads(args.config.read_text(encoding="utf-8"))
        for section, values in user_cfg.items():
            if section in params and isinstance(values, dict):
                params[section].update(values)
            else:
                params[section] = values
        print(f"Loaded custom mechanism parameters from {args.config}")

    results_root = args.results_root.expanduser().resolve()
    comp_root = results_root / "comparison"
    out_dir = results_root / "mouth_trajectories"

    # Save active parameters alongside generated trajectories for reproducibility
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "active_mechanism_params.json").write_text(json.dumps(params, indent=4), encoding="utf-8")

    P_home_5bar = compute_5bar_home(params["corner_5bar"])
    print(f"Computed 5-bar neutral home P_HOME = ({P_home_5bar[0]:.3f}, {P_home_5bar[1]:.3f}) mm")
    print("Pre-computing strain-free 5-bar workspace cloud...")
    safe_cloud = build_safe_workspace_cloud(params["corner_5bar"])

    syllables = SYLLABLES if args.syllable.upper() == "ALL" else [args.syllable.upper()]
    for syl in syllables:
        csv_path = comp_root / syl / "participant_curves.csv"
        if not csv_path.is_file():
            print(f"[{syl}] Skipped (not found: {csv_path})")
            continue
        process_syllable(csv_path, results_root, out_dir, params, safe_cloud, P_home_5bar, args.duration_ms)


if __name__ == "__main__":
    main()