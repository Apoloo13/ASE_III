# -*- coding: utf-8 -*-
"""Script Maestro v2: 15 Sílabas (FK vs MediaPipe vs Cohorte Humana n=50).

Incluye:
  1) Equivalencia física exacta en milímetros (mm) de las bandas ±1σ y ±0.5σ por punto anatómico.
  2) Corrección del radio mandibular R_jaw = 135.23 mm (35/sin(15°), Ec. 1 del artículo) y offset en p=0%.
  3) Permanencia en banda estricta ±0.5σ (FK sin offset vs MP).
  4) Fidelidad de forma con desfase temporal: Correlación Cruzada Máxima (r_max) para |Δp| <= 15%.
  5) Análisis con 1.ª Derivada (dY/dp): Índice de Rugosidad Cinemática (κ_v = RMS(dY_med)/RMS(dY_hum))
     y conteo de inversiones de dirección (picos espurios) para demostrar suavidad en FK vs ruido/picos en MP.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from evaluate_robot import (
    read_segments,
    find_patricio_folder,
    load_patricio_syllable,
    load_human_cohort_reference,
    auto_align_robot_phase,
)
from play_sts3215_8servos_gui import (
    DEFAULT_FK_PARAMS,
    reconstruct_measured_landmarks,
)

SYLLABLES_TABLE_ORDER = [
    "SA", "SE", "SI", "SO", "SU",
    "TA", "TE", "TI", "TO", "TU",
    "RA", "RE", "RI", "RO", "RU",
]

MAIN_5_POINTS = [
    ("BOCA_SUP_EXT", "Labio Sup (0)"),
    ("BOCA_INF_EXT", "Labio Inf (17)"),
    ("BOCA_IZQ",     "Com. Izq (61)"),
    ("BOCA_DER",     "Com. Der (291)"),
    ("BARBILLA",     "Mentón (152)"),
]


# ==============================================================================
# 1. FUNCIONES MATEMÁTICAS DE FORMA (DESFASE) Y 1.ª DERIVADA (RUGOSIDAD / PICOS)
# ==============================================================================
def max_lagged_correlation(sig: np.ndarray, ref: np.ndarray, max_shift: int = 15) -> tuple[float, int]:
    """Calcula la correlación de Pearson máxima permitiendo un desfase temporal de ±max_shift fases (%)."""
    sig = np.asarray(sig, dtype=float)
    ref = np.asarray(ref, dtype=float)
    if np.nanstd(sig) < 1e-8 or np.nanstd(ref) < 1e-8:
        return 0.0, 0

    best_r = -1.0
    best_lag = 0
    n = len(ref)

    for lag in range(-max_shift, max_shift + 1):
        if lag < 0:
            s_sub = sig[-lag:]
            r_sub = ref[: n + lag]
        elif lag > 0:
            s_sub = sig[: n - lag]
            r_sub = ref[lag:]
        else:
            s_sub = sig
            r_sub = ref

        if len(s_sub) > 10 and np.nanstd(s_sub) > 1e-8 and np.nanstd(r_sub) > 1e-8:
            r = float(np.corrcoef(s_sub, r_sub)[0, 1])
            if np.isfinite(r) and r > best_r:
                best_r = r
                best_lag = lag

    return (best_r if best_r > -1.0 else 0.0), best_lag


def derivative_roughness_and_peaks(sig: np.ndarray, ref: np.ndarray) -> tuple[float, int, int]:
    """
    Analiza la 1.ª derivada respecto a la fase (dY/dp):
      - roughness_ratio (κ_v): RMS(dY_sig/dp) / RMS(dY_ref/dp).
        κ_v ≈ 1.0 indica movimiento suave igual al humano; κ_v >> 1 indica oscilaciones/picos de alta frecuencia.
      - sign_changes_sig: número de cambios de signo de la 1.ª derivada (inversiones de dirección / picos).
      - sign_changes_ref: número de cambios de signo en la curva humana de referencia.
    """
    d_sig = np.diff(sig)
    d_ref = np.diff(ref)

    rms_sig = float(np.sqrt(np.nanmean(d_sig**2)))
    rms_ref = float(np.sqrt(np.nanmean(d_ref**2)))
    roughness_ratio = rms_sig / max(rms_ref, 1e-6)

    # Ignorar fluctuaciones menores a 1e-4 u. por paso de cuantización de 1 tick en encoders
    thr = 1e-4
    s_sig = np.sign(np.where(np.abs(d_sig) > thr, d_sig, 0.0))
    s_ref = np.sign(np.where(np.abs(d_ref) > thr, d_ref, 0.0))

    # Filtrar ceros para contar inversiones reales de dirección
    nz_sig = s_sig[s_sig != 0]
    nz_ref = s_ref[s_ref != 0]
    peaks_sig = int(np.sum(nz_sig[1:] != nz_sig[:-1])) if len(nz_sig) > 1 else 0
    peaks_ref = int(np.sum(nz_ref[1:] != nz_ref[:-1])) if len(nz_ref) > 1 else 0

    return roughness_ratio, peaks_sig, peaks_ref


# ==============================================================================
# 2. CARGA DE DATOS FK Y MP
# ==============================================================================
def find_trajectory_dir(root: Path, results_root: Path) -> Path:
    for c in (
        results_root / "mouth_trajectories",
        root / "orofacial_results" / "mouth_trajectories",
        root / "mouth_trajectories",
        root,
    ):
        if c.is_dir() and list(c.glob("mouth_trajectory_*.csv")):
            return c.resolve()
    return (results_root / "mouth_trajectories").resolve()


def load_or_reconstruct_fk(syl: str, traj_dir: Path, use_paper_jaw_radius: bool = True):
    traj_csv = traj_dir / f"mouth_trajectory_{syl}.csv"
    if not traj_csv.is_file():
        return None, None

    df_traj = pd.read_csv(traj_csv)
    fb_csv = traj_dir / f"mouth_feedback_{syl}.csv"
    rob_csv = traj_dir / f"robot_measured_{syl}.csv"

    fk_params = dict(DEFAULT_FK_PARAMS)
    if use_paper_jaw_radius:
        # Radio documentado en Metodología (Ec. 1): R_jaw = 35.0 / sin(15°) = 135.23 mm
        fk_params["jaw_radius_mm"] = 35.0 / np.sin(np.radians(15.0))

    if fb_csv.is_file():
        df_fb = pd.read_csv(fb_csv)
        df_meas = reconstruct_measured_landmarks(df_traj, df_fb, fk_params)
        df_meas.to_csv(rob_csv, index=False)
        return df_traj, df_meas
    elif rob_csv.is_file():
        return df_traj, pd.read_csv(rob_csv)
    return df_traj, None


# ==============================================================================
# 3. EVALUACIÓN INTEGRAL POR SÍLABA
# ==============================================================================
def evaluate_syllable(
    syl: str,
    df_traj: pd.DataFrame | None,
    df_fk: pd.DataFrame | None,
    human_mean: dict[str, np.ndarray] | None,
    human_sd: dict[str, np.ndarray] | None,
    mp_mean: dict[str, np.ndarray] | None,
) -> dict:
    res = {"syllable": syl}

    fk_rmses, fk_rmses_no_off, fk_in1sd, fk_in05sd = [], [], [], []
    fk_rmax, fk_roughness, fk_peaks = [], [], []

    mp_rmses, mp_in1sd_all6, mp_in05sd_all6 = [], [], []
    mp_rmax, mp_roughness, mp_peaks = [], [], []

    for pt, _ in MAIN_5_POINTS:
        # Desviación estándar humana promedio en este punto (en unidades u.)
        if df_traj is not None and f"HUMAN_{pt}_Delta_Y_sd" in df_traj.columns:
            hsd_arr = df_traj[f"HUMAN_{pt}_Delta_Y_sd"].to_numpy(dtype=float)
            res[f"{pt}_human_sd_mean_u"] = float(np.nanmean(hsd_arr))
            res[f"{pt}_human_sd_max_u"] = float(np.nanmax(hsd_arr))
        elif human_sd is not None and f"{pt}_Delta_Y" in human_sd:
            res[f"{pt}_human_sd_mean_u"] = float(np.nanmean(human_sd[f"{pt}_Delta_Y"]))
            res[f"{pt}_human_sd_max_u"] = float(np.nanmax(human_sd[f"{pt}_Delta_Y"]))
        else:
            res[f"{pt}_human_sd_mean_u"] = np.nan
            res[f"{pt}_human_sd_max_u"] = np.nan

        # --- 1) Evaluación Cinemática Directa (FK) ---
        if df_traj is not None and df_fk is not None and f"{pt}_Delta_Y" in df_fk.columns:
            hy = df_traj[f"HUMAN_{pt}_Delta_Y_mean"].to_numpy(dtype=float)
            hsd = df_traj[f"HUMAN_{pt}_Delta_Y_sd"].to_numpy(dtype=float)
            iky = df_traj[f"ROBOT_TARGET_{pt}_Delta_Y"].to_numpy(dtype=float)
            fky = df_fk[f"{pt}_Delta_Y"].to_numpy(dtype=float)

            # Corrección de offset inicial en p=0% respecto a la referencia
            offset_hum0 = float(fky[0] - hy[0]) if np.isfinite(fky[0]) else 0.0
            fky_aligned0 = fky - offset_hum0

            err_fk_raw = fky - hy
            err_fk_no_off = fky_aligned0 - hy

            rmse_fk = float(np.sqrt(np.nanmean(err_fk_raw**2)))
            rmse_fk_no_off = float(np.sqrt(np.nanmean(err_fk_no_off**2)))

            # Permanencia en ±1σ y en ±0.5σ (sin offset mecánico de home)
            in1sd_fk = float(np.mean(np.abs(err_fk_no_off) <= np.maximum(hsd, 1e-6)) * 100.0)
            in05sd_fk = float(np.mean(np.abs(err_fk_no_off) <= np.maximum(0.5 * hsd, 1e-6)) * 100.0)

            # Correlación de forma permitiendo desfase (FK vs IK / Humano)
            rmax_fk, lag_fk = max_lagged_correlation(fky, hy, max_shift=15)

            # Análisis por 1.ª derivada (suavidad vs picos)
            rough_fk, pks_fk, pks_hum = derivative_roughness_and_peaks(fky, hy)

            res[f"{pt}_rmse_fk"] = rmse_fk
            res[f"{pt}_rmse_fk_no_off"] = rmse_fk_no_off
            res[f"{pt}_in1sd_fk"] = in1sd_fk
            res[f"{pt}_in05sd_fk"] = in05sd_fk
            res[f"{pt}_rmax_fk"] = rmax_fk
            res[f"{pt}_lag_fk"] = lag_fk
            res[f"{pt}_roughness_fk"] = rough_fk
            res[f"{pt}_peaks_fk"] = pks_fk
            res[f"{pt}_peaks_hum"] = pks_hum

            fk_rmses.append(rmse_fk)
            fk_rmses_no_off.append(rmse_fk_no_off)
            fk_in1sd.append(in1sd_fk)
            fk_in05sd.append(in05sd_fk)
            fk_rmax.append(rmax_fk)
            fk_roughness.append(rough_fk)
            fk_peaks.append(pks_fk)
        else:
            for k in ("rmse_fk", "rmse_fk_no_off", "in1sd_fk", "in05sd_fk", "rmax_fk", "lag_fk", "roughness_fk", "peaks_fk", "peaks_hum"):
                res[f"{pt}_{k}"] = np.nan

        # --- 2) Evaluación Óptica Externa MediaPipe (MP) ---
        feat_y = f"{pt}_Delta_Y"
        if human_mean is not None and human_sd is not None and mp_mean is not None and feat_y in mp_mean:
            hm_y = human_mean[feat_y]
            hs_y = human_sd[feat_y]
            mp_y = mp_mean[feat_y]

            err_mp = mp_y - hm_y
            rmse_mp = float(np.sqrt(np.mean(err_mp**2)))
            in1sd_mp = float(np.mean(np.abs(err_mp) <= np.maximum(hs_y, 1e-6)) * 100.0)
            in05sd_mp = float(np.mean(np.abs(err_mp) <= np.maximum(0.5 * hs_y, 1e-6)) * 100.0)

            rmax_mp, lag_mp = max_lagged_correlation(mp_y, hm_y, max_shift=15)
            rough_mp, pks_mp, _ = derivative_roughness_and_peaks(mp_y, hm_y)

            res[f"{pt}_rmse_mp"] = rmse_mp
            res[f"{pt}_in1sd_mp"] = in1sd_mp
            res[f"{pt}_in05sd_mp"] = in05sd_mp
            res[f"{pt}_rmax_mp"] = rmax_mp
            res[f"{pt}_lag_mp"] = lag_mp
            res[f"{pt}_roughness_mp"] = rough_mp
            res[f"{pt}_peaks_mp"] = pks_mp

            mp_rmses.append(rmse_mp)
            mp_in1sd_all6.append(in1sd_mp)
            mp_in05sd_all6.append(in05sd_mp)
            mp_rmax.append(rmax_mp)
            mp_roughness.append(rough_mp)
            mp_peaks.append(pks_mp)
        else:
            for k in ("rmse_mp", "in1sd_mp", "in05sd_mp", "rmax_mp", "lag_mp", "roughness_mp", "peaks_mp"):
                res[f"{pt}_{k}"] = np.nan

    # Ancho intercomisural (61 <-> 291) en MediaPipe
    if human_mean is not None and human_sd is not None and mp_mean is not None and "Mouth_width_change" in mp_mean:
        err_w = mp_mean["Mouth_width_change"] - human_mean["Mouth_width_change"]
        hs_w = human_sd["Mouth_width_change"]
        in1sd_w = float(np.mean(np.abs(err_w) <= np.maximum(hs_w, 1e-6)) * 100.0)
        in05sd_w = float(np.mean(np.abs(err_w) <= np.maximum(0.5 * hs_w, 1e-6)) * 100.0)
        res["WIDTH_in1sd_mp"] = in1sd_w
        res["WIDTH_in05sd_mp"] = in05sd_w
        mp_in1sd_all6.append(in1sd_w)
        mp_in05sd_all6.append(in05sd_w)
    else:
        res["WIDTH_in1sd_mp"] = np.nan
        res["WIDTH_in05sd_mp"] = np.nan

    res["global_rmse_fk"] = float(np.mean(fk_rmses)) if fk_rmses else np.nan
    res["global_rmse_fk_no_off"] = float(np.mean(fk_rmses_no_off)) if fk_rmses_no_off else np.nan
    res["global_in1sd_fk"] = float(np.mean(fk_in1sd)) if fk_in1sd else np.nan
    res["global_in05sd_fk"] = float(np.mean(fk_in05sd)) if fk_in05sd else np.nan
    res["global_rmax_fk"] = float(np.mean(fk_rmax)) if fk_rmax else np.nan
    res["global_roughness_fk"] = float(np.mean(fk_roughness)) if fk_roughness else np.nan
    res["global_peaks_fk"] = float(np.mean(fk_peaks)) if fk_peaks else np.nan

    res["global_rmse_mp"] = float(np.mean(mp_rmses)) if mp_rmses else np.nan
    res["global_in1sd_mp"] = float(np.mean(mp_in1sd_all6)) if mp_in1sd_all6 else np.nan
    res["global_in05sd_mp"] = float(np.mean(mp_in05sd_all6)) if mp_in05sd_all6 else np.nan
    res["global_rmax_mp"] = float(np.mean(mp_rmax)) if mp_rmax else np.nan
    res["global_roughness_mp"] = float(np.mean(mp_roughness)) if mp_roughness else np.nan
    res["global_peaks_mp"] = float(np.mean(mp_peaks)) if mp_peaks else np.nan

    return res


# ==============================================================================
# 4. CONSTRUCCIÓN DE LA TABLA 1 MEJORADA (COMPACTA CON ±0.5σ, DESFASE Y DERIVADAS)
# ==============================================================================
def fmt_pair(v_fk: float, v_mp: float, dec: int = 3) -> str:
    s1 = f"{v_fk:.{dec}f}" if np.isfinite(v_fk) else "[--]"
    s2 = f"{v_mp:.{dec}f}" if np.isfinite(v_mp) else "[--]"
    return f"{s1} | {s2}"


def fmt_global_mm(v_fk: float, v_mp: float, scale_mm: float = 35.0) -> str:
    s1 = f"{v_fk:.3f} ({v_fk * scale_mm:.1f})" if np.isfinite(v_fk) else "[--]"
    s2 = f"{v_mp:.3f} ({v_mp * scale_mm:.1f})" if np.isfinite(v_mp) else "[--]"
    return f"{s1} | {s2}"


def build_enhanced_table_1(df_m: pd.DataFrame, scale_mm: float = 35.0, use_no_offset_fk: bool = True) -> pd.DataFrame:
    fk_col_suffix = "rmse_fk_no_off" if use_no_offset_fk else "rmse_fk"
    glob_fk_col = "global_rmse_fk_no_off" if use_no_offset_fk else "global_rmse_fk"

    rows = []
    for _, row in df_m.iterrows():
        syl = str(row["syllable"])
        syl_lbl = "RA (Fig. 1–2)" if syl == "RA" else syl
        item = {"Sílaba / Punto": syl_lbl}

        for pt, col_title in MAIN_5_POINTS:
            cname = f"{col_title}\nRMSE FK | MP"
            item[cname] = fmt_pair(row[f"{pt}_{fk_col_suffix}"], row[f"{pt}_rmse_mp"], 3)

        item["RMSE Global FK | MP (mm)"] = fmt_global_mm(row[glob_fk_col], row["global_rmse_mp"], scale_mm)
        item["En ±1σ | ±0.5σ MP (%)"] = (
            f"{row['global_in1sd_mp']:.1f}% | {row['global_in05sd_mp']:.1f}%"
            if np.isfinite(row["global_in1sd_mp"]) else "[--]"
        )
        rows.append(item)

    # --- Fila Resumen 1: Prom. Global (RMSE) ---
    r_prom = {"Sílaba / Punto": "Prom. Global (RMSE)"}
    for pt, col_title in MAIN_5_POINTS:
        cname = f"{col_title}\nRMSE FK | MP"
        r_prom[cname] = fmt_pair(df_m[f"{pt}_{fk_col_suffix}"].mean(), df_m[f"{pt}_rmse_mp"].mean(), 3)
    r_prom["RMSE Global FK | MP (mm)"] = fmt_global_mm(df_m[glob_fk_col].mean(), df_m["global_rmse_mp"].mean(), scale_mm)
    r_prom["En ±1σ | ±0.5σ MP (%)"] = f"{df_m['global_in1sd_mp'].mean():.1f}% | {df_m['global_in05sd_mp'].mean():.1f}%"
    rows.append(r_prom)

    # --- Fila Resumen 2: % en ±0.5σ Estricta (FK | MP) ---
    r_05 = {"Sílaba / Punto": "% en ±0.5σ (FK | MP)"}
    for pt, col_title in MAIN_5_POINTS:
        cname = f"{col_title}\nRMSE FK | MP"
        r_05[cname] = f"{df_m[f'{pt}_in05sd_fk'].mean():.1f}% | {df_m[f'{pt}_in05sd_mp'].mean():.1f}%"
    r_05["RMSE Global FK | MP (mm)"] = f"{df_m['global_in05sd_fk'].mean():.1f}% | {df_m['global_in05sd_mp'].mean():.1f}%"
    r_05["En ±1σ | ±0.5σ MP (%)"] = f"Ancho: {df_m['WIDTH_in05sd_mp'].mean():.1f}%"
    rows.append(r_05)

    # --- Fila Resumen 3: Correlación de Forma con Desfase r_max (FK | MP) ---
    r_corr = {"Sílaba / Punto": "Corr. Forma r_max (FK|MP)"}
    for pt, col_title in MAIN_5_POINTS:
        cname = f"{col_title}\nRMSE FK | MP"
        r_corr[cname] = fmt_pair(df_m[f"{pt}_rmax_fk"].mean(), df_m[f"{pt}_rmax_mp"].mean(), 2)
    r_corr["RMSE Global FK | MP (mm)"] = fmt_pair(df_m["global_rmax_fk"].mean(), df_m["global_rmax_mp"].mean(), 2)
    r_corr["En ±1σ | ±0.5σ MP (%)"] = "Desfase ≤15%"
    rows.append(r_corr)

    # --- Fila Resumen 4: Rugosidad 1.ª Derivada κ_v (FK | MP) ---
    r_deriv = {"Sílaba / Punto": "Rugosidad Deriv. κ_v (FK|MP)"}
    for pt, col_title in MAIN_5_POINTS:
        cname = f"{col_title}\nRMSE FK | MP"
        r_deriv[cname] = f"{df_m[f'{pt}_roughness_fk'].mean():.1f}x | {df_m[f'{pt}_roughness_mp'].mean():.1f}x"
    r_deriv["RMSE Global FK | MP (mm)"] = (
        f"{df_m['global_roughness_fk'].mean():.1f}x | {df_m['global_roughness_mp'].mean():.1f}x"
    )
    r_deriv["En ±1σ | ±0.5σ MP (%)"] = (
        f"Picos: {df_m['global_peaks_fk'].mean():.0f} | {df_m['global_peaks_mp'].mean():.0f}"
    )
    rows.append(r_deriv)

    return pd.DataFrame(rows)


def render_table_png(df_tbl: pd.DataFrame, out_png: Path):
    fig, ax = plt.subplots(figsize=(17.0, 9.6))
    ax.axis("off")

    col_labels = list(df_tbl.columns)
    cell_text = df_tbl.values.tolist()
    col_widths = [0.14, 0.115, 0.115, 0.115, 0.115, 0.115, 0.155, 0.13]

    tbl = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.6)
    tbl.scale(1.0, 1.82)

    n_rows = len(cell_text)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#d0d7de")
        cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor("#efefef")
            cell.get_text().set_weight("bold")
        elif r > n_rows - 4:
            cell.set_facecolor("#f0f4f9")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("#ffffff" if r % 2 == 1 else "#fafbfc")
        if c == 0 and r > 0:
            cell.get_text().set_weight("bold")
            cell.get_text().set_ha("left")
            cell.PAD = 0.04

    title_str = (
        "Tabla 1: Desempeño cinemático en las 15 sílabas (FK Servomotores vs. MediaPipe Piel de Silicona, 1 u. = 35.0 mm):\n"
        "error RMSE, permanencia en bandas ±1σ y ±0.5σ, correlación morfológica con desfase (r_max) y rugosidad por 1.ª derivada (κ_v)."
    )
    ax.set_title(title_str, fontsize=10.5, fontweight="bold", loc="left", pad=14)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--patricio-name", type=str, default="Patricio")
    parser.add_argument("--scale-mm", type=float, default=35.0)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    results_root = root / "orofacial_results"
    comp_root = results_root / "comparison"
    traj_dir = find_trajectory_dir(root, results_root)
    patricio_dir = find_patricio_folder(root, results_root, args.patricio_name)
    out_dir = results_root / "tabla_comparativa_final"
    out_dir.mkdir(parents=True, exist_ok=True)

    segments = read_segments(root / "segments.csv")
    phase = np.linspace(0.0, 100.0, 101)

    all_metrics = []
    for syl in SYLLABLES_TABLE_ORDER:
        df_traj, df_fk = load_or_reconstruct_fk(syl, traj_dir, use_paper_jaw_radius=True)
        comp_csv = comp_root / syl / "participant_curves.csv"
        human_mean, human_sd, mp_mean = None, None, None
        if comp_csv.is_file():
            _, human_mean, human_sd, _ = load_human_cohort_reference(comp_csv, args.patricio_name, phase)
            mp_mean, _ = load_patricio_syllable(patricio_dir, comp_csv, args.patricio_name, syl, segments, phase)

        all_metrics.append(evaluate_syllable(syl, df_traj, df_fk, human_mean, human_sd, mp_mean))

    df_m = pd.DataFrame(all_metrics)
    df_m.to_csv(out_dir / "METRICAS_AVANZADAS_DERIVADAS_Y_SIGMA.csv", index=False)

    # 1. Tabla de equivalencia en milímetros de ±1σ y ±0.5σ
    sigma_rows = []
    for pt, label_es in MAIN_5_POINTS:
        sd_mean_u = df_m[f"{pt}_human_sd_mean_u"].mean()
        sd_max_u = df_m[f"{pt}_human_sd_max_u"].mean()
        sigma_rows.append({
            "Punto Anatómico": label_es,
            "±1σ Promedio (u.)": f"±{sd_mean_u:.4f} u.",
            "±1σ Promedio (mm)": f"±{sd_mean_u * args.scale_mm:.2f} mm (banda total {2 * sd_mean_u * args.scale_mm:.2f} mm)",
            "±1σ Pico Vocal (mm)": f"±{sd_max_u * args.scale_mm:.2f} mm",
            "±0.5σ Estricta (mm)": f"±{0.5 * sd_mean_u * args.scale_mm:.2f} mm (banda total {sd_mean_u * args.scale_mm:.2f} mm)",
            "% en ±1σ (FK | MP)": f"{df_m[f'{pt}_in1sd_fk'].mean():.1f}% | {df_m[f'{pt}_in1sd_mp'].mean():.1f}%",
            "% en ±0.5σ (FK | MP)": f"{df_m[f'{pt}_in05sd_fk'].mean():.1f}% | {df_m[f'{pt}_in05sd_mp'].mean():.1f}%",
            "Corr. c/desfase r_max (FK | MP)": f"{df_m[f'{pt}_rmax_fk'].mean():.2f} | {df_m[f'{pt}_rmax_mp'].mean():.2f}",
            "Rugosidad 1.ª Deriv κ_v (FK | MP)": f"{df_m[f'{pt}_roughness_fk'].mean():.2f}x | {df_m[f'{pt}_roughness_mp'].mean():.2f}x",
            "Cambios Signo Deriv / Picos (Hum | FK | MP)": (
                f"{df_m[f'{pt}_peaks_hum'].mean():.1f} | {df_m[f'{pt}_peaks_fk'].mean():.1f} | {df_m[f'{pt}_peaks_mp'].mean():.1f}"
            ),
        })
    df_sigma = pd.DataFrame(sigma_rows)
    df_sigma.to_csv(out_dir / "EQUIVALENCIA_MM_SIGMA_Y_DERIVADAS.csv", index=False)

    # 2. Tabla 1 Mejorada lista para insertar en el documento Word
    df_t1_new = build_enhanced_table_1(df_m, scale_mm=args.scale_mm, use_no_offset_fk=True)
    df_t1_new.to_csv(out_dir / "TABLA_1_MEJORADA_CON_05SIGMA_Y_DERIVADAS.csv", index=False)
    render_table_png(df_t1_new, out_dir / "TABLA_1_MEJORADA_CON_05SIGMA_Y_DERIVADAS.png")

    print("\n=== 1. EQUIVALENCIA EN MILÍMETROS DE ±1σ Y ±0.5σ + ANÁLISIS DE DERIVADAS ===")
    print(df_sigma.to_string(index=False))
    print("\n=== 2. NUEVA TABLA 1 COMPACTA PARA EL RESUMEN EJECUTIVO ===")
    print(df_t1_new.to_string(index=False))


if __name__ == "__main__":
    main()