# -*- coding: utf-8 -*-
"""Complete Robot Validation & Thesis Table Generator for "Patricio" (Orofacial Simulator).

Compares the physical robot's MediaPipe recordings (folder: `Patricio`) against
the 50-participant human cohort (`orofacial_results/comparison/<SYL>/participant_curves.csv`).

Outputs (in `orofacial_results/patricio_evaluation/`):
    1) Per-syllable folders (`<SYL>/`):
       - `01_vertical_opening.png`       (Human mean ±1 SD vs Patricio)
       - `02_horizontal_widening.png`    (Human mean ±1 SD vs Patricio)
       - `03_jaw_contribution.png`       (Human mean ±1 SD vs Patricio)
       - `04_mouth_translation.png`      (Human mean ±1 SD vs Patricio)
       - `05_delta_XY_trajectories.png`  (2D XY trajectories: Human mean vs Patricio)
       - `06_subsystems_time_series.png` (5 Actuated Landmarks: 61, 291, 152, 17, 0 vs Time)
       - `error_metrics_<SYL>.csv`       (Per-landmark RMSE, MAE, Peak Error)

    2) Global Thesis Summary (`summary/`):
       - `TABLA_VALIDACION_PATRICIO_UNITS.png` & `.csv` (Exact table from thesis in eye-corner units)
       - `TABLA_VALIDACION_PATRICIO_MM.png`    & `.csv` (Exact table from thesis in physical mm)
       - `TABLA_VALIDACION_PATRICIO.md`                 (Ready-to-paste Markdown & LaTeX tables)
       - `DASHBOARD_DESEMPENO_GLOBAL.png`               (Executive visual chart of robot accuracy)
       - `DESGLOSE_POR_SILABA.csv`                      (Full table broken down by SA-SU, TA-TU, RA-RU)

Usage:
    python evaluate_patricio_robot.py
    python evaluate_patricio_robot.py --patricio-name Patricio --scale-mm 35.0 --auto-align
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ==============================================================================
# 1. CONSTANTS, LANDMARKS & SUBSYSTEM DEFINITIONS
# ==============================================================================
SYLLABLES = ["TA", "TE", "TI", "TO", "TU", "SA", "SE", "SI", "SO", "SU", "RA", "RE", "RI", "RO", "RU"]
SYLLABLE_GROUPS = {
    "SA–SU": ["SA", "SE", "SI", "SO", "SU"],
    "TA–TU": ["TA", "TE", "TI", "TO", "TU"],
    "RA–RU": ["RA", "RE", "RI", "RO", "RU"],
}

LANDMARKS = [
    "BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_SUP_INT", "BOCA_INF_INT",
    "BOCA_IZQ", "BOCA_DER", "BARBILLA", "MANDIBULA_IZQ", "MANDIBULA_DER",
]
MAIN_LANDMARKS = LANDMARKS[:7]
ACTUATED_LANDMARKS = ["BOCA_IZQ", "BOCA_DER", "BARBILLA", "BOCA_INF_EXT", "BOCA_SUP_EXT"]

LABELS = {
    "BOCA_SUP_EXT": "Upper outer lip (0)",
    "BOCA_INF_EXT": "Lower outer lip (17)",
    "BOCA_SUP_INT": "Upper inner lip (13)",
    "BOCA_INF_INT": "Lower inner lip (14)",
    "BOCA_IZQ": "Left mouth corner (61)",
    "BOCA_DER": "Right mouth corner (291)",
    "BARBILLA": "Chin (152)",
    "MANDIBULA_IZQ": "Left jaw-region point (148)",
    "MANDIBULA_DER": "Right jaw-region point (377)",
}

MEASURE_GROUPS = {
    "vertical_opening": [
        ("Inner_lip_opening_change", "Inner lip opening"),
        ("Outer_lip_separation_change", "Outer lip opening"),
    ],
    "horizontal_widening": [
        ("Mouth_width_change", "Mouth width change"),
        ("Mouth_center_shift_X", "Mouth center shift (X)"),
    ],
    "jaw_contribution": [
        ("Chin_drop", "Chin drop"),
        ("Chin_to_lower_lip_change", "Chin relative to lower lip"),
    ],
    "mouth_translation": [
        ("Mouth_center_shift_Y", "Mouth center shift (Y)"),
        ("Lip_height_change", "Mean lip height shift"),
    ],
}
MEASURE_LABELS = {feat: label for pairs in MEASURE_GROUPS.values() for feat, label in pairs}

RAW_COLS = ["Tiempo_ms"] + [
    f"{pt}_{basis}_{axis}"
    for pt in LANDMARKS for basis in ("Norm", "Delta") for axis in ("X", "Y")
]
FEATURES = [col for col in RAW_COLS if col != "Tiempo_ms"] + list(MEASURE_LABELS)

COLORS = plt.get_cmap("tab10").colors
N_PHASE = 101
DPI = 160


# ==============================================================================
# 2. DATA LOADING & PREPROCESSING (PATRICIO + 50 HUMAN PARTICIPANTS)
# ==============================================================================
def append_measures(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Inner_lip_opening_change"] = df["BOCA_INF_INT_Delta_Y"] - df["BOCA_SUP_INT_Delta_Y"]
    df["Outer_lip_separation_change"] = df["BOCA_INF_EXT_Delta_Y"] - df["BOCA_SUP_EXT_Delta_Y"]

    if "BOCA_IZQ_Norm_X" in df.columns and "BOCA_DER_Norm_X" in df.columns:
        left = df["BOCA_IZQ_Norm_X"]
        right = df["BOCA_DER_Norm_X"]
        neutral_left = left - df["BOCA_IZQ_Delta_X"]
        neutral_right = right - df["BOCA_DER_Delta_X"]
        df["Mouth_width_change"] = (right - left).abs() - (neutral_right - neutral_left).abs()
    else:
        df["Mouth_width_change"] = df["BOCA_DER_Delta_X"] - df["BOCA_IZQ_Delta_X"]

    df["Chin_drop"] = df["BARBILLA_Delta_Y"]
    df["Chin_to_lower_lip_change"] = df["BARBILLA_Delta_Y"] - df["BOCA_INF_EXT_Delta_Y"]
    df["Mouth_center_shift_X"] = 0.5 * (df["BOCA_IZQ_Delta_X"] + df["BOCA_DER_Delta_X"])
    df["Mouth_center_shift_Y"] = 0.5 * (df["BOCA_IZQ_Delta_Y"] + df["BOCA_DER_Delta_Y"])
    df["Lip_height_change"] = 0.25 * (
        df["BOCA_SUP_EXT_Delta_Y"] + df["BOCA_INF_EXT_Delta_Y"] +
        df["BOCA_SUP_INT_Delta_Y"] + df["BOCA_INF_INT_Delta_Y"]
    )
    return df


def read_segments(path: Path) -> dict[tuple[str, str], tuple[float, float]]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    required = {"participant", "filename", "start_ms", "end_ms"}
    if not required.issubset(df.columns):
        return {}
    boundaries = {}
    for row in df.itertuples(index=False):
        key = (str(row.participant).strip(), str(row.filename).strip())
        start, end = float(row.start_ms), float(row.end_ms)
        if np.isfinite([start, end]).all() and end > start:
            boundaries[key] = (start, end)
    return boundaries


def find_patricio_folder(root: Path, results_root: Path, patricio_name: str) -> Path | None:
    """Searches common locations for the `Patricio` folder."""
    candidates = [
        root / patricio_name,
        results_root / patricio_name,
        results_root / "individual" / patricio_name,
        root.parent / patricio_name,
        Path.cwd() / patricio_name,
        Path.cwd() / "orofacial_results" / patricio_name,
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand.resolve()
    for base in (root, results_root, Path.cwd()):
        if base.is_dir():
            for child in base.iterdir():
                if child.is_dir() and child.name.lower() == patricio_name.lower():
                    return child.resolve()
    return None


def load_patricio_syllable(
    patricio_dir: Path | None,
    comp_csv: Path,
    patricio_name: str,
    syllable: str,
    segments: dict,
    phase: np.ndarray,
) -> tuple[dict[str, np.ndarray] | None, list[dict[str, np.ndarray]]]:
    """
    Loads all accepted repetitions of `syllable` for Patricio and returns:
      (patricio_mean_dict, list_of_repetition_dicts)
    Supports:
      1) Raw tracker CSVs inside `Patricio/<SYL>_R01.csv`
      2) Pre-exported `individual_mean.csv` inside `Patricio/<SYL>/individual_mean.csv`
      3) Pre-merged rows for `Patricio` inside `comparison/<SYL>/participant_curves.csv`
    """
    reps = []

    if patricio_dir is not None and patricio_dir.is_dir():
        pattern = re.compile(rf"{re.escape(syllable)}(?:_R\d+)?\.csv$", re.IGNORECASE)
        raw_files = [p for p in sorted(patricio_dir.iterdir()) if p.is_file() and pattern.fullmatch(p.name)]

        for csv_file in raw_files:
            try:
                df = pd.read_csv(csv_file)
                if "Tiempo_ms" in df.columns:
                    for col in RAW_COLS:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    df = df[np.isfinite(df["Tiempo_ms"])].sort_values("Tiempo_ms")
                    key = (patricio_name, csv_file.name)
                    start, end = segments.get(
                        key, (float(df["Tiempo_ms"].iloc[0]), float(df["Tiempo_ms"].iloc[-1]))
                    )
                    df = df[df["Tiempo_ms"].between(start, end)].copy()
                    df = df.groupby("Tiempo_ms", as_index=False).mean(numeric_only=True)
                    df = append_measures(df)
                    avail_feats = [f for f in FEATURES if f in df.columns]
                    valid = df.dropna(subset=avail_feats)
                    if len(valid) >= 4:
                        t = valid["Tiempo_ms"].to_numpy(dtype=float)
                        dur = float(t[-1] - t[0])
                        if dur > 0:
                            sample_times = t[0] + (phase / 100.0) * dur
                            curves = {
                                f: np.interp(sample_times, t, valid[f].to_numpy(dtype=float))
                                for f in avail_feats
                            }
                            reps.append(curves)
                elif "phase_pct" in df.columns:
                    df = append_measures(df)
                    avail_feats = [f for f in FEATURES if f in df.columns]
                    t = df["phase_pct"].to_numpy(dtype=float)
                    curves = {f: np.interp(phase, t, df[f].to_numpy(dtype=float)) for f in avail_feats}
                    reps.append(curves)
            except Exception as exc:
                print(f"  [WARN] Could not parse {csv_file.name}: {exc}")

        sub_csv = patricio_dir / syllable / "individual_mean.csv"
        if not reps and sub_csv.is_file():
            df = pd.read_csv(sub_csv)
            df = append_measures(df)
            avail_feats = [f for f in FEATURES if f in df.columns]
            t = df["phase_pct"].to_numpy(dtype=float)
            reps.append({f: np.interp(phase, t, df[f].to_numpy(dtype=float)) for f in avail_feats})

    if not reps and comp_csv.is_file():
        df_comp = pd.read_csv(comp_csv)
        if "participant" in df_comp.columns:
            mask = df_comp["participant"].astype(str).str.strip().str.lower() == patricio_name.lower()
            if mask.any():
                df_p = df_comp[mask].sort_values("phase_pct")
                df_p = append_measures(df_p)
                avail_feats = [f for f in FEATURES if f in df_p.columns]
                t = df_p["phase_pct"].to_numpy(dtype=float)
                reps.append({f: np.interp(phase, t, df_p[f].to_numpy(dtype=float)) for f in avail_feats})

    if not reps:
        return None, []

    common_feats = set(reps[0].keys())
    for r in reps[1:]:
        common_feats &= set(r.keys())

    mean_patricio = {
        feat: np.mean(np.vstack([r[feat] for r in reps]), axis=0)
        for feat in common_feats
    }
    return mean_patricio, reps


def load_human_cohort_reference(comp_csv: Path, patricio_name: str, phase: np.ndarray):
    """
    Loads `comparison/<SYL>/participant_curves.csv`, excludes `Patricio` if present
    so the human reference is strictly the 50 human participants, and returns:
      (people_dict, mean_dict, sd_dict, n_humans)
    """
    df = pd.read_csv(comp_csv)
    df = df[df["participant"].astype(str).str.strip().str.lower() != patricio_name.lower()].copy()
    df = append_measures(df)

    avail_feats = [f for f in FEATURES if f in df.columns]
    for c in ["phase_pct"] + avail_feats:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    people = {}
    for person, g in df.groupby("participant"):
        g = g.sort_values("phase_pct")
        if len(g) == len(phase) and not g[avail_feats].isna().any().any():
            people[person] = {f: g[f].to_numpy(dtype=float) for f in avail_feats}

    if not people:
        raise ValueError(f"No valid human participants found in {comp_csv}")

    mean_dict, sd_dict = {}, {}
    for f in avail_feats:
        stack = np.vstack([p[f] for p in people.values()])
        mean_dict[f] = np.mean(stack, axis=0)
        sd_dict[f]   = np.std(stack, axis=0, ddof=1) if len(people) > 1 else np.zeros_like(phase)

    return people, mean_dict, sd_dict, len(people)


def auto_align_robot_phase(robot_dict: dict[str, np.ndarray], human_mean: dict[str, np.ndarray], max_shift: int = 18):
    ref_col = "Outer_lip_separation_change" if "Outer_lip_separation_change" in robot_dict else "BARBILLA_Delta_Y"
    if ref_col not in robot_dict or ref_col not in human_mean:
        return robot_dict, 0

    h_curve = human_mean[ref_col]
    r_curve = robot_dict[ref_col]
    best_shift = 0
    best_mse = float("inf")

    for shift in range(-max_shift, max_shift + 1):
        if shift < 0:
            shifted = np.pad(r_curve[-shift:], (0, -shift), mode="edge")
        elif shift > 0:
            shifted = np.pad(r_curve[:-shift], (shift, 0), mode="edge")
        else:
            shifted = r_curve
        mse = float(np.mean((shifted - h_curve) ** 2))
        if mse < best_mse:
            best_mse = mse
            best_shift = shift

    if best_shift == 0:
        return robot_dict, 0

    aligned = {}
    for k, arr in robot_dict.items():
        if best_shift < 0:
            aligned[k] = np.pad(arr[-best_shift:], (0, -best_shift), mode="edge")
        else:
            aligned[k] = np.pad(arr[:-best_shift], (best_shift, 0), mode="edge")
    return aligned, best_shift


# ==============================================================================
# 3. PER-SYLLABLE GRAPH GENERATORS (MATCHING orofacial_analysis.py)
# ==============================================================================
def plot_measure_group_vs_patricio(
    phase: np.ndarray, syllable: str, group_key: str,
    human_mean: dict, human_sd: dict, patricio: dict,
    n_humans: int, n_reps: int, out_path: Path,
):
    pairs = MEASURE_GROUPS[group_key]
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    palette = ["#7c47a9", "#0c8a8a", "#d97904", "#c23b3b"]

    for idx, (feat, label) in enumerate(pairs):
        if feat not in human_mean or feat not in patricio:
            continue
        color = palette[idx % len(palette)]
        hm = human_mean[feat]
        hs = human_sd[feat]
        pr = patricio[feat]

        err = pr - hm
        rmse = float(np.sqrt(np.mean(err**2)))
        mae  = float(np.mean(np.abs(err)))

        ax.fill_between(phase, hm - hs, hm + hs, color=color, alpha=0.15, label=f"{label} Human ±1 SD")
        ax.plot(phase, hm, color=color, lw=2.3, label=f"{label} (Human mean, n={n_humans})")
        ax.plot(
            phase, pr, color=color, ls="--", lw=2.4,
            label=f"{label} (Patricio Robot, RMSE={rmse:.3f}, MAE={mae:.3f})",
        )

    title_map = {
        "vertical_opening": "Vertical mouth opening",
        "horizontal_widening": "Horizontal mouth widening",
        "jaw_contribution": "Jaw / chin contribution",
        "mouth_translation": "Overall mouth translation",
    }
    ax.axhline(0, color="black", alpha=0.45, lw=0.7)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Selected interval (%)")
    ax.set_ylabel("Change from neutral (eye-distance units)")
    ax.set_title(f"{syllable}: {title_map[group_key]} | Human Cohort (n={n_humans}) vs Patricio ({n_reps} rep)")
    ax.grid(alpha=0.20)
    ax.legend(loc="best", fontsize=8.5)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def plot_delta_xy_vs_patricio(
    syllable: str, human_people: dict, human_mean: dict, patricio: dict,
    out_path: Path, points: list[str] | None = None,
):
    points = points or MAIN_LANDMARKS
    rows = int(np.ceil(len(points) / 3))
    fig, axs = plt.subplots(rows, 3, figsize=(13.8, rows * 3.6))

    for idx, pt in enumerate(points):
        ax = axs.flat[idx]
        xf, yf = f"{pt}_Delta_X", f"{pt}_Delta_Y"
        color = COLORS[LANDMARKS.index(pt)]

        for person in human_people.values():
            ax.plot(person[xf], person[yf], lw=0.75, color="0.65", alpha=0.20)

        ax.plot(human_mean[xf], human_mean[yf], lw=2.5, color=color, label="Human mean")
        ax.scatter([human_mean[xf][0]], [human_mean[yf][0]], color=color, s=20, zorder=5)
        ax.scatter([human_mean[xf][-1]], [human_mean[yf][-1]], color=color, marker="x", s=32, zorder=5)

        if xf in patricio and yf in patricio:
            ax.plot(patricio[xf], patricio[yf], "--", color="black", lw=2.1, label="Patricio (Robot)")
            ax.scatter([patricio[xf][0]], [patricio[yf][0]], color="black", s=18, zorder=6)
            ax.scatter([patricio[xf][-1]], [patricio[yf][-1]], color="black", marker="x", s=30, zorder=6)
            err_2d = np.hypot(patricio[xf] - human_mean[xf], patricio[yf] - human_mean[yf])
            rmse_2d = float(np.sqrt(np.mean(err_2d**2)))
            ax.set_title(f"{LABELS[pt]}\n2D RMSE = {rmse_2d:.3f} units", fontsize=9.5)
        else:
            ax.set_title(LABELS[pt], fontsize=10)

        ax.axhline(0, color="black", alpha=0.25, lw=0.6)
        ax.axvline(0, color="black", alpha=0.25, lw=0.6)
        ax.set_xlabel("Delta X (eye-distance units)", fontsize=8)
        ax.set_ylabel("Delta Y (positive downward)", fontsize=8)
        ax.invert_yaxis()
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=0.15)
        ax.legend(fontsize=7.5, loc="best")

    for ax in axs.flat[len(points):]:
        ax.set_visible(False)

    fig.suptitle(f"{syllable}: 2D XY Trajectories Relative to Neutral | Human Cohort vs Patricio", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def plot_subsystems_time_panel(
    phase: np.ndarray, syllable: str, human_mean: dict, human_sd: dict,
    patricio: dict, patricio_reps: list[dict], n_humans: int, out_path: Path,
):
    """6-panel figure showing the actuated landmarks (61, 291, 152, 17, 0) across 0..100% time."""
    fig, axs = plt.subplots(2, 3, figsize=(15.5, 8.2), sharex=True)
    panel_spec = [
        ("BOCA_IZQ", "Y", "Comisura Izq. (61) · ΔY"),
        ("BOCA_DER", "Y", "Comisura Der. (291) · ΔY"),
        ("BARBILLA", "Y", "Mandíbula / Chin (152) · ΔY"),
        ("BOCA_INF_EXT", "Y", "Labio Inf. (17) · ΔY"),
        ("BOCA_SUP_EXT", "Y", "Labio Sup. (0) · ΔY"),
        ("Mouth_width_change", None, "Ancho de Boca (61↔291) · ΔX"),
    ]

    for idx, (pt_or_feat, axis, title) in enumerate(panel_spec):
        ax = axs.flat[idx]
        feat = f"{pt_or_feat}_Delta_{axis}" if axis else pt_or_feat
        color = COLORS[idx % len(COLORS)]

        hm = human_mean[feat]
        hs = human_sd[feat]
        pr = patricio[feat]

        ax.fill_between(phase, hm - hs, hm + hs, color=color, alpha=0.18, label=f"Humano ±1 DE (n={n_humans})")
        ax.plot(phase, hm, color=color, lw=2.3, label="Media Humana")

        for r in patricio_reps:
            if feat in r:
                ax.plot(phase, r[feat], color="black", alpha=0.22, lw=0.9)

        ax.plot(phase, pr, "--", color="black", lw=2.2, label="Robot")

        err = pr - hm
        rmse = float(np.sqrt(np.mean(err**2)))
        mae  = float(np.mean(np.abs(err)))
        in_band = float(np.mean(np.abs(err) <= np.maximum(hs, 1e-6)) * 100.0)

        ax.axhline(0, color="black", alpha=0.35, lw=0.7)
        ax.set_title(f"{title}\nRMSE={rmse:.3f} | MAE={mae:.3f} | En ±1σ: {in_band:.0f}%", fontsize=9.5, fontweight="bold")
        ax.set_ylabel("Unidades de distancia ocular", fontsize=8.5)
        ax.set_xlim(0, 100)
        ax.grid(alpha=0.18)
        
        # Se dibuja la leyenda para todos los paneles sin restricción de índice
        ax.legend(loc="best", fontsize=8)

    for ax in axs[-1, :]:
        ax.set_xlabel("Intervalo seleccionado (%)")

    # Cambio del nombre del sujeto en el título
    fig.suptitle(f"{syllable}: Validación por Subsistema Actuado | Cohorte Humana vs (Robot)", fontsize=13.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)

# ==============================================================================
# 4. THESIS TABLE & EXECUTIVE DASHBOARD GENERATOR (MATCHING image_0e78bb.png)
# ==============================================================================
def compute_subsystem_metrics_for_syllable(
    syllable: str, human_mean: dict, human_sd: dict, patricio: dict
) -> list[dict]:
    """
    Computes Ref. Humana (mu +/- sigma), Medicion Robot (Patricio), RMSE, MAE, and Peak Error
    for each mechanical subsystem in `image_0e78bb.png`.
    """
    subsystems = [
        {
            "key": "comisuras",
            "name": "Comisuras (5 barras 2 GDL, 61/291)",
            "actuators": "IDs 5–8 (FK Encoder)",
            "features": ["BOCA_IZQ_Delta_X", "BOCA_IZQ_Delta_Y", "BOCA_DER_Delta_X", "BOCA_DER_Delta_Y"],
            "peak_feat": "BOCA_DER_Delta_Y",
        },
        {
            "key": "mandibula",
            "name": "Mandíbula (Arco circular, 152)",
            "actuators": "IDs 1–2 (FK Encoder)",
            "features": ["BARBILLA_Delta_Y"],
            "peak_feat": "BARBILLA_Delta_Y",
        },
        {
            "key": "labio_inf",
            "name": "Labio Inf. (Piñón-cremallera, 17)",
            "actuators": "ID 10 (FK Encoder)",
            "features": ["BOCA_INF_EXT_Delta_Y"],
            "peak_feat": "BOCA_INF_EXT_Delta_Y",
        },
        {
            "key": "labio_sup",
            "name": "Labio Sup. (Manivela-pistón, 0)",
            "actuators": "ID 9 (FK Encoder)",
            "features": ["BOCA_SUP_EXT_Delta_Y"],
            "peak_feat": "BOCA_SUP_EXT_Delta_Y",
        },
    ]

    rows = []
    for sub in subsystems:
        feats = [f for f in sub["features"] if f in human_mean and f in patricio]
        if not feats:
            continue

        errs = np.concatenate([patricio[f] - human_mean[f] for f in feats])
        sds  = np.concatenate([human_sd[f] for f in feats])

        rmse = float(np.sqrt(np.mean(errs**2)))
        mae  = float(np.mean(np.abs(errs)))
        peak_err = float(np.max(np.abs(errs)))
        within_1sd_pct = float(np.mean(np.abs(errs) <= np.maximum(sds, 1e-6)) * 100.0)

        pf = sub["peak_feat"]
        idx_peak_h = int(np.argmax(np.abs(human_mean[pf])))
        h_peak_val = float(np.abs(human_mean[pf][idx_peak_h]))
        h_peak_sd  = float(human_sd[pf][idx_peak_h])

        r_peak_val = float(np.max(np.abs(patricio[pf])))
        r_traj_sd  = float(np.std(patricio[pf], ddof=1))

        rows.append({
            "syllable": syllable,
            "subsystem_key": sub["key"],
            "Subsistema / Mecanismo": sub["name"],
            "Actuadores / Método": sub["actuators"],
            "human_peak_mean": h_peak_val,
            "human_peak_sd": h_peak_sd,
            "robot_peak_mean": r_peak_val,
            "robot_traj_sd": r_traj_sd,
            "rmse": rmse,
            "mae": mae,
            "peak_error": peak_err,
            "within_1sd_pct": within_1sd_pct,
        })
    return rows


def build_thesis_table_dataframe(all_sub_rows: list[dict], scale_mult: float = 1.0, unit_suffix: str = "") -> pd.DataFrame:
    df_all = pd.DataFrame(all_sub_rows)
    fmt = ".2f" if scale_mult > 1.5 else ".4f"
    u_lbl = f" {unit_suffix}".rstrip()

    table_rows = []
    subsystem_order = [
        ("comisuras", "Comisuras (5 barras 2 GDL, 61/291)", "IDs 5–8 (FK Encoder)"),
        ("mandibula", "Mandíbula (Arco circular, 152)", "IDs 1–2 (FK Encoder)"),
        ("labio_inf", "Labio Inf. (Piñón-cremallera, 17)", "ID 10 (FK Encoder)"),
        ("labio_sup", "Labio Sup. (Manivela-pistón, 0)", "ID 9 (FK Encoder)"),
    ]

    for key, name, actuators in subsystem_order:
        sub_df = df_all[df_all["subsystem_key"] == key]
        if sub_df.empty:
            table_rows.append({
                "Subsistema / Mecanismo": name,
                "Actuadores / Método": actuators,
                "Ref. Humana / MATLAB (μ ± σ)": "[ Sin datos ]",
                "Medición FK / Sim. PySINDy": "[ Sin datos ]",
                "RMSE": "[ -- ]",
                "MAE": "[ -- ]",
                "Error Máx.": "[ -- ]",
            })
            continue

        h_mu = sub_df["human_peak_mean"].mean() * scale_mult
        h_sd = sub_df["human_peak_sd"].mean() * scale_mult
        r_mu = sub_df["robot_peak_mean"].mean() * scale_mult
        r_sd = sub_df["robot_peak_mean"].std(ddof=1) * scale_mult if len(sub_df) > 1 else sub_df["robot_traj_sd"].mean() * scale_mult

        rmse_val = sub_df["rmse"].mean() * scale_mult
        mae_val  = sub_df["mae"].mean() * scale_mult
        max_val  = sub_df["peak_error"].mean() * scale_mult

        table_rows.append({
            "Subsistema / Mecanismo": name,
            "Actuadores / Método": actuators,
            "Ref. Humana / MATLAB (μ ± σ)": f"{h_mu:{fmt}} ± {h_sd:{fmt}}{u_lbl}",
            "Medición FK / Sim. PySINDy": f"{r_mu:{fmt}} ± {r_sd:{fmt}}{u_lbl}",
            "RMSE": f"{rmse_val:{fmt}}{u_lbl}",
            "MAE": f"{mae_val:{fmt}}{u_lbl}",
            "Error Máx.": f"{max_val:{fmt}}{u_lbl}",
        })

    table_rows.append({
        "Subsistema / Mecanismo": "Lengua (Costillas pull-pull, /r,s,t/)",
        "Actuadores / Método": "2 Servos (Sim. PySINDy)",
        "Ref. Humana / MATLAB (μ ± σ)": "[ Polígono MATLAB ]",
        "Medición FK / Sim. PySINDy": "[ Espacio Estados ]",
        "RMSE": "[ -- ]",
        "MAE": "[ -- ]",
        "Error Máx.": "[ -- ]",
    })

    if not df_all.empty:
        g_h_mu = df_all["human_peak_mean"].mean() * scale_mult
        g_h_sd = df_all["human_peak_sd"].mean() * scale_mult
        g_r_mu = df_all["robot_peak_mean"].mean() * scale_mult
        g_r_sd = df_all["robot_peak_mean"].std(ddof=1) * scale_mult if len(df_all) > 1 else 0.0

        grp_rmses, grp_maes, grp_maxs = [], [], []
        for g_name, syl_list in SYLLABLE_GROUPS.items():
            gdf = df_all[df_all["syllable"].isin(syl_list)]
            if not gdf.empty:
                grp_rmses.append(f"{gdf['rmse'].mean() * scale_mult:{fmt}}")
                grp_maes.append(f"{gdf['mae'].mean() * scale_mult:{fmt}}")
                grp_maxs.append(f"{gdf['peak_error'].mean() * scale_mult:{fmt}}")

        rmse_global = df_all["rmse"].mean() * scale_mult
        mae_global  = df_all["mae"].mean() * scale_mult
        max_global  = df_all["peak_error"].mean() * scale_mult

        table_rows.append({
            "Subsistema / Mecanismo": "Desempeño Global por Sílabas",
            "Actuadores / Método": "SA–SU / TA–TU / RA–RU",
            "Ref. Humana / MATLAB (μ ± σ)": f"{g_h_mu:{fmt}} ± {g_h_sd:{fmt}}{u_lbl}",
            "Medición FK / Sim. PySINDy": f"{g_r_mu:{fmt}} ± {g_r_sd:{fmt}}{u_lbl}",
            "RMSE": f"{rmse_global:{fmt}}{u_lbl} ({' / '.join(grp_rmses)})",
            "MAE": f"{mae_global:{fmt}}{u_lbl} ({' / '.join(grp_maes)})",
            "Error Máx.": f"{max_global:{fmt}}{u_lbl} ({' / '.join(grp_maxs)})",
        })

    return pd.DataFrame(table_rows)


def render_thesis_table_image(table_df: pd.DataFrame, title: str, out_png: Path):
    """Renders a publication-quality table image matching `image_0e78bb.png`."""
    fig, ax = plt.subplots(figsize=(15.5, 4.8))
    ax.axis("off")

    col_labels = list(table_df.columns)
    cell_text = table_df.values.tolist()
    col_widths = [0.20, 0.14, 0.16, 0.16, 0.11, 0.11, 0.12]

    tbl = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9.5)
    tbl.scale(1.0, 2.15)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#222222")
        cell.set_linewidth(0.9)
        if row == 0:
            cell.set_facecolor("#e6e6e6")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(10)
        else:
            cell.set_facecolor("#ffffff" if row % 2 == 1 else "#f9fbfd")
            if col in (0, 1):
                cell.get_text().set_ha("left")
                cell.PAD = 0.04

    ax.set_title(title, fontsize=12.5, fontweight="bold", pad=14)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_global_executive_dashboard(all_sub_rows: list[dict], scale_mm: float, out_png: Path):
    df = pd.DataFrame(all_sub_rows)
    if df.empty:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.8))

    sub_order = ["comisuras", "mandibula", "labio_inf", "labio_sup"]
    sub_labels = ["Comisuras\n(61 / 291)", "Mandíbula\n(152)", "Labio Inf.\n(17)", "Labio Sup.\n(0)"]

    h_means, h_sds, r_means, rmses, maes = [], [], [], [], []
    for k in sub_order:
        sdf = df[df["subsystem_key"] == k]
        h_means.append(sdf["human_peak_mean"].mean() * scale_mm if not sdf.empty else 0)
        h_sds.append(sdf["human_peak_sd"].mean() * scale_mm if not sdf.empty else 0)
        r_means.append(sdf["robot_peak_mean"].mean() * scale_mm if not sdf.empty else 0)
        rmses.append(sdf["rmse"].mean() * scale_mm if not sdf.empty else 0)
        maes.append(sdf["mae"].mean() * scale_mm if not sdf.empty else 0)

    x = np.arange(len(sub_order))
    w = 0.26

    ax1.bar(x - w, h_means, width=w, yerr=h_sds, capsize=5, color="#4e79a7", alpha=0.88, label="Ref. Humana Pico (μ ± σ)")
    ax1.bar(x, r_means, width=w, color="#59a14f", alpha=0.90, label="Robot Patricio Pico (Medido)")
    ax1.bar(x + w, rmses, width=w, color="#e15759", alpha=0.88, label="Error Medio RMSE (mm)")

    for i, (rm, ma) in enumerate(zip(rmses, maes)):
        ax1.text(x[i] + w, rm + 0.25, f"RMSE: {rm:.2f}\nMAE: {ma:.2f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(sub_labels, fontsize=9.5, fontweight="bold")
    ax1.set_ylabel(f"Desplazamiento / Error (mm, escala={scale_mm:.0f} mm)", fontsize=10)
    ax1.set_title("A) Desempeño por Subsistema Mecánico (Amplitud vs Error)", fontsize=11.5, fontweight="bold")
    ax1.grid(axis="y", alpha=0.25)
    ax1.legend(loc="upper right", fontsize=8.5)

    grp_names = list(SYLLABLE_GROUPS.keys()) + ["GLOBAL (15 Sílabas)"]
    g_rmses, g_maes, g_maxs, g_inband = [], [], [], []

    for g_label in grp_names:
        if g_label.startswith("GLOBAL"):
            gdf = df
        else:
            gdf = df[df["syllable"].isin(SYLLABLE_GROUPS[g_label])]
        g_rmses.append(gdf["rmse"].mean() * scale_mm if not gdf.empty else 0)
        g_maes.append(gdf["mae"].mean() * scale_mm if not gdf.empty else 0)
        g_maxs.append(gdf["peak_error"].mean() * scale_mm if not gdf.empty else 0)
        g_inband.append(gdf["within_1sd_pct"].mean() if not gdf.empty else 0)

    x2 = np.arange(len(grp_names))
    w2 = 0.25
    ax2.bar(x2 - w2, g_rmses, width=w2, color="#76b7b2", label="RMSE (mm)")
    ax2.bar(x2, g_maes, width=w2, color="#f28e2b", label="MAE (mm)")
    ax2.bar(x2 + w2, g_maxs, width=w2, color="#edc948", label="Error Máx. Promedio (mm)")

    for i, (rm, ma, ib) in enumerate(zip(g_rmses, g_maes, g_inband)):
        ax2.text(x2[i], max(rm, ma, g_maxs[i]) + 0.25, f"{ib:.0f}% en ±1σ", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1b5e20")

    ax2.set_xticks(x2)
    ax2.set_xticklabels(grp_names, fontsize=9.5, fontweight="bold")
    ax2.set_ylabel("Error en Milímetros (mm)", fontsize=10)
    ax2.set_title("B) Error Global por Familia Fonética y % Dentro de ±1σ Humano", fontsize=11.5, fontweight="bold")
    ax2.grid(axis="y", alpha=0.25)
    ax2.legend(loc="upper right", fontsize=8.5)

    fig.suptitle("Resumen Ejecutivo de Validación Cinemática: Simulador Robótico 'Patricio' vs Cohorte Humana (n=50)", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ==============================================================================
# 5. MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Validate Patricio robot recordings against 50-participant human cohort.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="Project root directory containing Patricio folder and orofacial_results")
    parser.add_argument("--results-root", type=Path, default=None,
                        help="Path to orofacial_results (default: <root>/orofacial_results)")
    parser.add_argument("--patricio-dir", type=Path, default=None,
                        help="Explicit path to Patricio folder (auto-detected if omitted)")
    parser.add_argument("--patricio-name", type=str, default="Patricio",
                        help="Folder / participant name used for the robot recordings (default: Patricio)")
    parser.add_argument("--syllable", type=str, default="ALL",
                        help="Syllable to evaluate (e.g. SA, SE) or ALL")
    parser.add_argument("--scale-mm", type=float, default=35.0,
                        help="Eye-corner scale factor in mm for physical millimeter table (default: 35.0)")
    parser.add_argument("--auto-align", action="store_true",
                        help="Automatically align phase offset if recording has idle start/end frames")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    results_root = (args.results_root or (root / "orofacial_results")).expanduser().resolve()
    comp_root = results_root / "comparison"
    out_root = results_root / f"{args.patricio_name}_evaluation"

    patricio_dir = args.patricio_dir.expanduser().resolve() if args.patricio_dir else find_patricio_folder(
        root, results_root, args.patricio_name
    )
    print(f"=== VALIDACIÓN CINEMÁTICA DEL ROBOT ({args.patricio_name}) ===")
    print(f"Carpeta de resultados humanos: {comp_root}")
    print(f"Carpeta del robot detectada:   {patricio_dir if patricio_dir else 'Buscando en participant_curves.csv'}")

    segments = read_segments(root / "segments.csv")
    phase = np.linspace(0.0, 100.0, N_PHASE)
    syllables = SYLLABLES if args.syllable.upper() == "ALL" else [s.strip().upper() for s in args.syllable.split(",")]

    all_subsystem_rows = []
    all_landmark_rows = []

    for syl in syllables:
        comp_csv = comp_root / syl / "participant_curves.csv"
        if not comp_csv.is_file():
            print(f"[{syl}] Omitida: no existe {comp_csv}")
            continue

        patricio_mean, patricio_reps = load_patricio_syllable(
            patricio_dir, comp_csv, args.patricio_name, syl, segments, phase
        )
        if patricio_mean is None:
            print(f"[{syl}] Omitida: no se encontraron grabaciones de '{args.patricio_name}' para {syl}.")
            continue

        human_people, human_mean, human_sd, n_humans = load_human_cohort_reference(
            comp_csv, args.patricio_name, phase
        )

        shift_pct = 0
        if args.auto_align:
            patricio_mean, shift_pct = auto_align_robot_phase(patricio_mean, human_mean)

        syl_out = out_root / syl
        syl_out.mkdir(parents=True, exist_ok=True)

        # 1. Generate the 4 measure-group comparison plots
        for idx, g_key in enumerate(MEASURE_GROUPS, start=1):
            plot_measure_group_vs_patricio(
                phase, syl, g_key, human_mean, human_sd, patricio_mean,
                n_humans, len(patricio_reps), syl_out / f"0{idx}_{g_key}.png"
            )

        # 2. Generate 2D XY trajectories plot
        plot_delta_xy_vs_patricio(
            syl, human_people, human_mean, patricio_mean, syl_out / "05_delta_XY_trajectories.png"
        )

        # 3. Generate 6-panel subsystem time-series validation plot
        plot_subsystems_time_panel(
            phase, syl, human_mean, human_sd, patricio_mean, patricio_reps,
            n_humans, syl_out / "06_subsystems_time_series.png"
        )

        # 4. Compute per-landmark and per-subsystem errors
        syl_lm_rows = []
        for pt in MAIN_LANDMARKS:
            for ax in ("X", "Y"):
                feat = f"{pt}_Delta_{ax}"
                if feat not in patricio_mean or feat not in human_mean:
                    continue
                err = patricio_mean[feat] - human_mean[feat]
                row_lm = {
                    "syllable": syl,
                    "point": pt,
                    "label": LABELS[pt],
                    "axis": ax,
                    "rmse_units": float(np.sqrt(np.mean(err**2))),
                    "mae_units": float(np.mean(np.abs(err))),
                    "peak_error_units": float(np.max(np.abs(err))),
                    "rmse_mm": float(np.sqrt(np.mean(err**2)) * args.scale_mm),
                    "mae_mm": float(np.mean(np.abs(err)) * args.scale_mm),
                    "peak_error_mm": float(np.max(np.abs(err)) * args.scale_mm),
                }
                syl_lm_rows.append(row_lm)
                all_landmark_rows.append(row_lm)

        pd.DataFrame(syl_lm_rows).to_csv(syl_out / f"error_metrics_{syl}.csv", index=False)

        sub_rows = compute_subsystem_metrics_for_syllable(syl, human_mean, human_sd, patricio_mean)
        all_subsystem_rows.extend(sub_rows)

        mean_rmse_u = np.mean([r["rmse"] for r in sub_rows])
        print(
            f"  [OK] [{syl}] n_human={n_humans} | reps_robot={len(patricio_reps)} | "
            f"RMSE medio={mean_rmse_u:.4f} u ({mean_rmse_u * args.scale_mm:.2f} mm) -> {syl_out}"
        )

    if not all_subsystem_rows:
        raise SystemExit(
            f"\nNo se encontraron datos de '{args.patricio_name}' para comparar. "
            f"Verifica que la carpeta '{args.patricio_name}' contenga archivos como SA_R01.csv."
        )

    # --- 5. Export Global Thesis Tables & Executive Dashboard ---
    summary_dir = out_root / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    df_sub_all = pd.DataFrame(all_subsystem_rows)
    df_sub_all.to_csv(summary_dir / "DESGLOSE_POR_SILABA.csv", index=False)
    pd.DataFrame(all_landmark_rows).to_csv(summary_dir / "DESGLOSE_LANDMARKS_TODOS.csv", index=False)

    # Table in dimensionless eye-corner units
    tbl_units = build_thesis_table_dataframe(all_subsystem_rows, scale_mult=1.0, unit_suffix="u")
    tbl_units.to_csv(summary_dir / "TABLA_VALIDACION_PATRICIO_UNITS.csv", index=False)
    render_thesis_table_image(
        tbl_units,
        "Tabla de Validación Cinemática: Referencia Humana (n=50) vs Robot 'Patricio' (Unidades Oculares)",
        summary_dir / "TABLA_VALIDACION_PATRICIO_UNITS.png",
    )

    # Table in physical millimeters (mm)
    tbl_mm = build_thesis_table_dataframe(all_subsystem_rows, scale_mult=args.scale_mm, unit_suffix="mm")
    tbl_mm.to_csv(summary_dir / "TABLA_VALIDACION_PATRICIO_MM.csv", index=False)
    render_thesis_table_image(
        tbl_mm,
        f"Tabla de Validación Cinemática: Referencia Humana (n=50) vs Robot 'Patricio' (Milímetros, Escala={args.scale_mm:.0f} mm)",
        summary_dir / "TABLA_VALIDACION_PATRICIO_MM.png",
    )

    # Save Markdown summary (without requiring 'tabulate' package)
    def df_to_md(df_in: pd.DataFrame) -> str:
        cols = list(df_in.columns)
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for row in df_in.values.tolist():
            lines.append("| " + " | ".join(str(x) for x in row) + " |")
        return "\n".join(lines)

    md_text = (
        "# Resumen de Validación Cinemática: Simulador 'Patricio' vs Cohorte Humana (n=50)\n\n"
        "## 1. Tabla en Unidades Normalizadas de Distancia Inter-Ocular (u)\n\n"
        + df_to_md(tbl_units)
        + f"\n\n## 2. Tabla en Milímetros Físicos (Escala = {args.scale_mm:.1f} mm)\n\n"
        + df_to_md(tbl_mm)
        + "\n"
    )
    (summary_dir / "TABLA_VALIDACION_PATRICIO.md").write_text(md_text, encoding="utf-8")

    # Executive Dashboard Plot
    plot_global_executive_dashboard(all_subsystem_rows, args.scale_mm, summary_dir / "DASHBOARD_DESEMPENO_GLOBAL.png")

    print("\n" + "=" * 88)
    print("TABLA DE VALIDACIÓN LISTA PARA TU REPORTE (UNIDADES OCULARES):")
    print("=" * 88)
    print(tbl_units.to_string(index=False))
    print("\n" + "=" * 88)
    print(f"TABLA DE VALIDACIÓN LISTA PARA TU REPORTE (MILÍMETROS, ESCALA = {args.scale_mm:.0f} mm):")
    print("=" * 88)
    print(tbl_mm.to_string(index=False))
    print("=" * 88)
    print(f"\nTodos los gráficos por sílaba y las tablas finales se guardaron en:\n  -> {out_root}")


if __name__ == "__main__":
    main()