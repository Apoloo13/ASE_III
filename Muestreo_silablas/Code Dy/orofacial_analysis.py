# """Orofacial landmark trajectory analysis for one participant or a cohort.

# Compatible with the 9-landmark CSV files from orofacial_tracker.py:
#     BOCA_SUP_EXT, BOCA_INF_EXT, BOCA_SUP_INT, BOCA_INF_INT,
#     BOCA_IZQ, BOCA_DER, BARBILLA, MANDIBULA_IZQ, MANDIBULA_DER

# Install:
#     pip install numpy pandas matplotlib

# Folder structure:
#     my_study/
#         orofacial_analysis.py
#         orofacial_tracker.py
#         Joseph/SE_R01.csv
#         Joseph/SE_R02.csv
#         Bro/SE_R01.csv
#         segments.csv                  # OPTIONAL

# Examples:
#     python orofacial_analysis.py --mode individual --participant Joseph --syllable SE
#     python orofacial_analysis.py --mode compare --syllable SE
#     python orofacial_analysis.py --mode compare --syllable SE --participants Joseph Bro
#     python orofacial_analysis.py --mode reference --syllable SE
#     python orofacial_analysis.py --mode all --syllable SE --participant Joseph
#     python orofacial_analysis.py --mode reference --syllable ALL
#     python orofacial_analysis.py --mode reference --syllable SE --robot robot_SE.csv

# Optional segments.csv:
#     participant,filename,start_ms,end_ms
#     Joseph,SE_R01.csv,145,685
#     Bro,SE_R01.csv,170,720

# IMPORTANT: In the absence of an entry in segments.csv, the entire recording
# is time-normalized. That is *recording progress*, NOT a verified 0-100%
# articulatory gesture. For research comparisons, annotate consistent boundaries
# and use --require-segments. The time normalization is a linear resampling;
# it does NOT apply dynamic time warping.

# Units: ALL positions/displacements are dimensionless fractions of the eye-corner
# distance used by the capture program (landmarks 133 and 362), NOT millimeters
# and NOT physical interpupillary distance. Image Y increases downward.

# Each participant contributes ONE trajectory to cohort statistics, obtained by
# averaging their accepted repetitions after resampling. The group mean is an
# empirical reference, not a clinical norm or validated robotic target.

# Optional robot input: CSV with 'phase_pct' (0-100) and paired columns such as
# 'BOCA_INF_INT_Delta_X', 'BOCA_INF_INT_Delta_Y'. Values MUST already be in the
# SAME dimensionless coordinate convention as the human data, including spatial
# orientation, baseline definition, and head/robot reference frame. Only points
# with both components are compared. Robot and human events must also be aligned
# in time for the comparison to be meaningful.
# """
# from __future__ import annotations

# import argparse
# from collections import defaultdict
# from pathlib import Path
# import re
# import sys
# import warnings

# import matplotlib
# import matplotlib.pyplot as plt
# import numpy as np
# import pandas as pd


# SYLLABLES = ["TA", "TE", "TI", "TO", "TU", "SA", "SE", "SI", "SO", "SU", "RA", "RE", "RI", "RO", "RU"]
# LANDMARKS = [
#     "BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_SUP_INT", "BOCA_INF_INT",
#     "BOCA_IZQ", "BOCA_DER", "BARBILLA", "MANDIBULA_IZQ", "MANDIBULA_DER",
# ]
# MAIN_LANDMARKS = LANDMARKS[:7]  # Six lip points + chin
# LABELS = {
#     "BOCA_SUP_EXT": "Upper outer lip (0)",
#     "BOCA_INF_EXT": "Lower outer lip (17)",
#     "BOCA_SUP_INT": "Upper inner lip (13)",
#     "BOCA_INF_INT": "Lower inner lip (14)",
#     "BOCA_IZQ": "Left mouth corner (61)",
#     "BOCA_DER": "Right mouth corner (291)",
#     "BARBILLA": "Chin (152)",
#     "MANDIBULA_IZQ": "Left jaw-region point (148)",
#     "MANDIBULA_DER": "Right jaw-region point (377)",
# }
# COLORS = plt.get_cmap("tab10").colors
# MEASURES = {
#     "Inner_lip_opening_change": "Inner lip opening: change from neutral",
#     "Outer_lip_separation_change": "Outer lip separation: change from neutral",
#     "Mouth_width_change": "Mouth width: change from neutral",
#     "BARBILLA_Delta_Y": "Chin: vertical displacement",
# }
# RAW_COLS = ["Tiempo_ms"] + [
#     f"{pt}_{basis}_{axis}"
#     for pt in LANDMARKS for basis in ("Norm", "Delta") for axis in ("X", "Y")
# ]
# FEATURES = [col for col in RAW_COLS if col != "Tiempo_ms"] + list(MEASURES)[:3]

# # Quality control defaults. Tune transparently and keep settings consistent.
# N_PHASE = 101
# MIN_FRAMES = 6
# MIN_DURATION_MS = 120.0
# MAX_MISSING_FRACTION = 0.20
# MAX_GAP_MS = 250.0
# MAX_EDGE_GAP_MS = 120.0
# DPI = 150


# def normalize_syllables(request: str) -> list[str]:
#     if request.upper() == "ALL":
#         return SYLLABLES.copy()
#     syllables = [s.strip().upper() for s in request.split(",") if s.strip()]
#     unknown = set(syllables) - set(SYLLABLES)
#     if not syllables or unknown:
#         raise ValueError(f"Unsupported syllable(s): {sorted(unknown)}. Use TA, SE, ... or ALL.")
#     return list(dict.fromkeys(syllables))


# def read_segments(path: Path) -> dict[tuple[str, str], tuple[float, float]]:
#     if not path.is_file():
#         return {}
#     df = pd.read_csv(path)
#     required = {"participant", "filename", "start_ms", "end_ms"}
#     if not required.issubset(df.columns):
#         raise ValueError(f"{path} must have columns {sorted(required)}")
#     boundaries = {}
#     for row in df.itertuples(index=False):
#         key = (str(row.participant).strip(), str(row.filename).strip())
#         start, end = float(row.start_ms), float(row.end_ms)
#         if not np.isfinite([start, end]).all() or end <= start:
#             raise ValueError(f"Invalid interval for {key} in {path}")
#         if key in boundaries:
#             raise ValueError(f"Duplicate segment for {key} in {path}")
#         boundaries[key] = (start, end)
#     return boundaries


# def discover_trials(root: Path, syllable: str, participants: list[str] | None):
#     pattern = re.compile(rf"{re.escape(syllable)}(?:_R\d+)?\.csv", re.IGNORECASE)
#     selected = set(participants) if participants is not None else None
#     if not root.is_dir():
#         raise FileNotFoundError(f"Data root does not exist: {root}")
#     for folder in sorted(root.iterdir()):
#         if not folder.is_dir() or folder.name == "orofacial_results":
#             continue
#         if selected is not None and folder.name not in selected:
#             continue
#         for path in sorted(folder.iterdir()):
#             if path.is_file() and pattern.fullmatch(path.name):
#                 yield folder.name, path


# def append_measures(df: pd.DataFrame) -> pd.DataFrame:
#     df = df.copy()
#     # Differences of the rest-relative displacements preserve each person's
#     # individual neutral-face calibration (rather than zeroing first CSV frame).
#     df["Inner_lip_opening_change"] = (
#         df["BOCA_INF_INT_Delta_Y"] - df["BOCA_SUP_INT_Delta_Y"]
#     )
#     df["Outer_lip_separation_change"] = (
#         df["BOCA_INF_EXT_Delta_Y"] - df["BOCA_SUP_EXT_Delta_Y"]
#     )
#     left = df["BOCA_IZQ_Norm_X"]
#     right = df["BOCA_DER_Norm_X"]
#     neutral_left = left - df["BOCA_IZQ_Delta_X"]
#     neutral_right = right - df["BOCA_DER_Delta_X"]
#     df["Mouth_width_change"] = (right-left).abs() - (neutral_right-neutral_left).abs()
#     return df


# def read_trial(
#     csv: Path, person: str, syllable: str, segments: dict,
#     require_segments: bool, phase: np.ndarray,
# ) -> tuple[dict[str, np.ndarray], dict]:
#     df = pd.read_csv(csv)
#     missing = [name for name in RAW_COLS if name not in df.columns]
#     if missing:
#         raise ValueError("missing expected CSV columns: " + ", ".join(missing[:5]))
#     if "Silaba" in df and df["Silaba"].notna().any():
#         actual = set(df["Silaba"].dropna().astype(str).str.strip().str.upper())
#         if actual != {syllable}:
#             raise ValueError(f"syllable label mismatch: {actual}")

#     df = df[RAW_COLS].copy()
#     for name in RAW_COLS:
#         df[name] = pd.to_numeric(df[name], errors="coerce")
#     df = df[np.isfinite(df["Tiempo_ms"])].sort_values("Tiempo_ms")
#     if df.empty:
#         raise ValueError("no valid recording times")
#     key = (person, csv.name)
#     annotated = key in segments
#     if require_segments and not annotated:
#         raise ValueError("missing gesture boundaries in segments.csv")
#     start, end = segments[key] if annotated else (
#         float(df["Tiempo_ms"].iloc[0]), float(df["Tiempo_ms"].iloc[-1])
#     )
#     df = df[df["Tiempo_ms"].between(start, end)].copy()
#     if df.empty:
#         raise ValueError("selected segment contains no frames")
#     # Recorder timestamps are integer milliseconds; duplicates can occur.
#     df = df.groupby("Tiempo_ms", as_index=False).mean(numeric_only=True)
#     if len(df) < MIN_FRAMES:
#         raise ValueError(f"fewer than {MIN_FRAMES} distinct frames")
#     duration = end - start
#     if duration < MIN_DURATION_MS:
#         raise ValueError(f"selected interval shorter than {MIN_DURATION_MS:.0f} ms")

#     df = append_measures(df)
#     finite = np.isfinite(df[FEATURES].to_numpy(dtype=float)).all(axis=1)
#     missing_fraction = float(1 - finite.mean())
#     if missing_fraction > MAX_MISSING_FRACTION:
#         raise ValueError(f"missing landmark tracking: {missing_fraction:.1%} of frames")
#     valid = df.loc[finite]
#     if len(valid) < MIN_FRAMES:
#         raise ValueError("too few fully tracked frames")

#     t = valid["Tiempo_ms"].to_numpy(dtype=float)
#     max_gap = float(np.diff(t).max())
#     if max_gap > MAX_GAP_MS:
#         raise ValueError(f"tracking gap of {max_gap:.0f} ms exceeds limit")
#     if t[0] - start > MAX_EDGE_GAP_MS or end - t[-1] > MAX_EDGE_GAP_MS:
#         raise ValueError("missing tracking at selected-interval boundary")

#     # Linear resampling: avoids spurious cubic-spline overshoot.
#     sample_times = start + (phase / 100) * duration
#     curves = {
#         feat: np.interp(sample_times, t, valid[feat].to_numpy(dtype=float))
#         for feat in FEATURES
#     }
#     metadata = {
#         "participant": person, "filename": csv.name, "status": "accepted",
#         "reason": "", "annotated": annotated, "start_ms": start, "end_ms": end,
#         "duration_ms": duration, "total_frames": len(df),
#         "valid_frames": len(valid), "missing_fraction": missing_fraction,
#         "max_tracking_gap_ms": max_gap,
#     }
#     return curves, metadata


# def prepare_cohort(
#     root: Path, syllable: str, participants: list[str] | None,
#     segments: dict, require_segments: bool, phase: np.ndarray,
# ):
#     repetitions: dict[str, list[dict]] = defaultdict(list)
#     qc = []
#     paths = list(discover_trials(root, syllable, participants))
#     for person, path in paths:
#         try:
#             curves, metadata = read_trial(path, person, syllable, segments, require_segments, phase)
#         except (ValueError, OSError, pd.errors.ParserError) as exc:
#             qc.append({"participant": person, "filename": path.name,
#                        "status": "rejected", "reason": str(exc)})
#             print(f"  Rejected {person}/{path.name}: {exc}")
#             continue
#         repetitions[person].append(curves)
#         qc.append(metadata)
#     people = {
#         person: {
#             feature: np.mean(np.stack([rep[feature] for rep in trials]), axis=0)
#             for feature in FEATURES
#         }
#         for person, trials in repetitions.items()
#     }
#     if not people:
#         print(f"  No accepted recordings for {syllable}.")
#     elif any(x.get("annotated") is False for x in qc if x["status"] == "accepted"):
#         print("  NOTE: Some recordings use their full duration (not annotated syllable boundaries).")
#     return people, repetitions, qc, len(paths)


# def stats(people: dict[str, dict[str, np.ndarray]], phase: np.ndarray):
#     if not people:
#         return {}, {}
#     means = {}
#     sd = {}
#     for feat in FEATURES:
#         stack = np.stack([person[feat] for person in people.values()])
#         means[feat] = stack.mean(axis=0)
#         sd[feat] = stack.std(axis=0, ddof=1) if len(stack) > 1 else np.full(len(phase), np.nan)
#     return means, sd


# def plot_save(fig, filename: Path, show: bool):
#     filename.parent.mkdir(parents=True, exist_ok=True)
#     fig.savefig(filename, dpi=DPI, bbox_inches="tight")
#     if show:
#         plt.show()
#     plt.close(fig)


# def plot_xy_absolute(
#     data: dict[str, np.ndarray], syllable: str, name: str, target: Path,
#     show: bool, repeats: list[dict] | None = None,
# ):
#     fig, ax = plt.subplots(figsize=(8.5, 8.5))
#     for idx, point in enumerate(LANDMARKS):
#         x, y = f"{point}_Norm_X", f"{point}_Norm_Y"
#         color = COLORS[idx]
#         if repeats:
#             for rep in repeats:
#                 ax.plot(rep[x], rep[y], color=color, linewidth=.8, alpha=.19)
#         ax.plot(data[x], data[y], color=color, linewidth=2.1, label=LABELS[point])
#         ax.scatter([data[x][0]], [data[y][0]], s=18, color=color)
#         ax.scatter([data[x][-1]], [data[y][-1]], s=28, marker="x", color=color)
#     ax.set_title(f"{name} | {syllable} | normalized anatomical XY\n"
#                  "Dot = first frame; X = last frame")
#     ax.set_xlabel("X relative to nose (eye-distance units)")
#     ax.set_ylabel("Y relative to nose (eye-distance units; positive downward)")
#     ax.invert_yaxis()
#     ax.set_aspect("equal", adjustable="datalim")
#     ax.grid(alpha=.20)
#     ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
#     fig.tight_layout()
#     plot_save(fig, target, show)


# def plot_grid(
#     phase: np.ndarray, curves: dict[str, dict], syllable: str, axis: str,
#     target: Path, show: bool, mean: dict | None = None,
#     sd: dict | None = None, mode: str = "individual",
#     points: list[str] | None = None, robot: dict | None = None,
#     count_label: str | None = None,
# ):
#     points = points or LANDMARKS
#     ncols = 3
#     nrows = int(np.ceil(len(points) / ncols))
#     fig, axs = plt.subplots(nrows, ncols, figsize=(15, 3.35 * nrows), sharex=True)
#     for i, point in enumerate(points):
#         ax = axs.flat[i]
#         feature = f"{point}_Delta_{axis}"
#         color = COLORS[LANDMARKS.index(point)]
#         for person in curves.values():
#             ax.plot(phase, person[feature], color="0.55" if mode != "individual" else color,
#                     alpha=.24 if len(curves) >= 8 else .47,
#                     linewidth=.9 if len(curves) > 1 else 1.2)
#         if mean is not None:
#             if sd is not None and np.isfinite(sd[feature]).any():
#                 ax.fill_between(phase, mean[feature]-sd[feature], mean[feature]+sd[feature],
#                                 color=color, alpha=.19)
#             ax.plot(phase, mean[feature], color=color, linewidth=2.4, label="Group mean")
#         if robot is not None and feature in robot:
#             ax.plot(phase, robot[feature], color="black", ls="--", linewidth=2, label="Robot")
#         ax.axhline(0, linewidth=.7, color="black", alpha=.4)
#         ax.set_title(LABELS[point], fontsize=10)
#         ax.set_ylabel(f"Delta {axis} (eye-distance units)", fontsize=8)
#         ax.set_xlim(0, 100)
#         ax.grid(alpha=.18)
#         if robot is not None and feature in robot:
#             ax.legend(fontsize=8, loc="best")
#     for ax in axs.flat[len(points):]:
#         ax.set_visible(False)
#     for ax in axs.flat:
#         if ax.get_visible():
#             ax.set_xlabel("Selected interval (%)")
#     meaning = {"individual": "Individual repetitions and participant mean",
#                "compare": "Participants (grey) and cohort mean",
#                "reference": "Cohort mean, ±1 participant SD and optional robot"}[mode]
#     fig.suptitle(f"{syllable}: {axis} displacement | {meaning} | {count_label or f'n={len(curves)}'}", fontsize=13)
#     fig.tight_layout(rect=(0, 0, 1, .96))
#     plot_save(fig, target, show)


# def plot_measures(
#     phase: np.ndarray, curves: dict[str, dict], syllable: str,
#     target: Path, show: bool, mean: dict | None = None,
#     sd: dict | None = None, mode: str = "compare", count_label: str | None = None,
# ):
#     fig, axs = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
#     for ax, (feature, label) in zip(axs.flat, MEASURES.items()):
#         for values in curves.values():
#             ax.plot(phase, values[feature], color="0.56", alpha=.26 if len(curves) >= 8 else .55,
#                     linewidth=1.0)
#         if mean is not None:
#             if sd is not None and np.isfinite(sd[feature]).any():
#                 ax.fill_between(phase, mean[feature]-sd[feature], mean[feature]+sd[feature],
#                                 color="#7c47a9", alpha=.18)
#             ax.plot(phase, mean[feature], color="#7c47a9", linewidth=2.4)
#         ax.axhline(0, color="black", alpha=.45, linewidth=.7)
#         ax.set_title(label, fontsize=11)
#         ax.set_xlabel("Selected interval (%)")
#         ax.set_ylabel("Change from neutral (eye-distance units)")
#         ax.set_xlim(0, 100)
#         ax.grid(alpha=.20)
#     fig.suptitle(f"{syllable}: mouth measurements | {mode} | {count_label or f'n={len(curves)}'}", fontsize=13)
#     fig.tight_layout(rect=(0, 0, 1, .96))
#     plot_save(fig, target, show)


# def plot_delta_xy(
#     curves: dict[str, dict], syllable: str, target: Path, show: bool,
#     mean: dict | None = None, mode: str = "reference", robot: dict | None = None,
#     points: list[str] | None = None,
# ):
#     points = points or LANDMARKS
#     rows = int(np.ceil(len(points) / 3))
#     fig, axs = plt.subplots(rows, 3, figsize=(13.8, rows * 3.5))
#     for idx, point in enumerate(points):
#         ax = axs.flat[idx]
#         xf, yf = f"{point}_Delta_X", f"{point}_Delta_Y"
#         color = COLORS[LANDMARKS.index(point)]
#         for person in curves.values():
#             ax.plot(person[xf], person[yf], linewidth=.85,
#                     color="0.6" if len(curves) > 1 else color,
#                     alpha=.22 if len(curves) > 7 else .5)
#         if mean is not None:
#             ax.plot(mean[xf], mean[yf], linewidth=2.6, color=color, label="Human mean")
#             ax.scatter([mean[xf][0]], [mean[yf][0]], color=color, s=20, zorder=5)
#             ax.scatter([mean[xf][-1]], [mean[yf][-1]], color=color, marker="x", s=32, zorder=5)
#         if robot is not None and xf in robot and yf in robot:
#             ax.plot(robot[xf], robot[yf], "--", color="black", linewidth=2, label="Robot")
#             ax.legend(fontsize=7)
#         ax.axhline(0, color="black", alpha=.25, linewidth=.6)
#         ax.axvline(0, color="black", alpha=.25, linewidth=.6)
#         ax.set_title(LABELS[point], fontsize=10)
#         ax.set_xlabel("Delta X (eye-distance units)", fontsize=8)
#         ax.set_ylabel("Delta Y (positive downward)", fontsize=8)
#         ax.invert_yaxis()
#         ax.set_aspect("equal", adjustable="datalim")
#         ax.grid(alpha=.12)
#     for ax in axs.flat[len(points):]:
#         ax.set_visible(False)
#     fig.suptitle(f"{syllable}: XY trajectories relative to neutral | {mode}", fontsize=13)
#     fig.tight_layout(rect=(0, 0, 1, .96))
#     plot_save(fig, target, show)


# def export_qc(path: Path, qc: list[dict]):
#     path.parent.mkdir(parents=True, exist_ok=True)
#     pd.DataFrame(qc).to_csv(path, index=False)


# def export_participant_curves(path: Path, phase: np.ndarray, syllable: str, people: dict):
#     rows = []
#     for person, data in people.items():
#         for i, pct in enumerate(phase):
#             row = {"participant": person, "syllable": syllable, "phase_pct": pct}
#             row.update({feat: float(data[feat][i]) for feat in FEATURES})
#             rows.append(row)
#     path.parent.mkdir(parents=True, exist_ok=True)
#     pd.DataFrame(rows).to_csv(path, index=False)


# def export_reference(path: Path, phase: np.ndarray, syllable: str,
#                      people: dict, mean: dict, sd: dict):
#     rows = []
#     for i, pct in enumerate(phase):
#         row = {"syllable": syllable, "phase_pct": pct, "n_participants": len(people)}
#         for feat in FEATURES:
#             row[f"{feat}_mean"] = float(mean[feat][i])
#             row[f"{feat}_sd"] = float(sd[feat][i])
#         rows.append(row)
#     path.parent.mkdir(parents=True, exist_ok=True)
#     pd.DataFrame(rows).to_csv(path, index=False)


# def export_durations(path: Path, syllable: str, qc: list[dict]):
#     accepted = [r for r in qc if r["status"] == "accepted"]
#     rows = []
#     for person in sorted({r["participant"] for r in accepted}):
#         durations = [r["duration_ms"] for r in accepted if r["participant"] == person]
#         rows.append({"participant": person, "syllable": syllable,
#                      "n_repetitions": len(durations),
#                      "mean_duration_ms": float(np.mean(durations)),
#                      "sd_duration_ms": float(np.std(durations, ddof=1))
#                      if len(durations) > 1 else np.nan})
#     path.parent.mkdir(parents=True, exist_ok=True)
#     pd.DataFrame(rows).to_csv(path, index=False)


# def load_robot(path: Path, phase: np.ndarray) -> dict[str, np.ndarray]:
#     df = pd.read_csv(path)
#     if "phase_pct" not in df.columns:
#         raise ValueError("Robot CSV requires 'phase_pct' from 0 to 100.")
#     df["phase_pct"] = pd.to_numeric(df["phase_pct"], errors="coerce")
#     cols = [f"{pt}_Delta_{axis}" for pt in LANDMARKS for axis in ("X", "Y")]
#     matched = [c for c in cols if c in df.columns]
#     if not matched:
#         raise ValueError("Robot CSV has no matching landmark Delta_X / Delta_Y columns.")
#     for col in matched:
#         df[col] = pd.to_numeric(df[col], errors="coerce")
#     df = df.dropna(subset=["phase_pct"] + matched).sort_values("phase_pct")
#     if len(df) < 3:
#         raise ValueError("Robot CSV needs >=3 complete time samples.")
#     df = df.groupby("phase_pct", as_index=False).mean(numeric_only=True)
#     t = df["phase_pct"].to_numpy(dtype=float)
#     if t[0] > 0 or t[-1] < 100 or t[0] < 0 or t[-1] > 100:
#         raise ValueError("Robot phase_pct must span exactly 0..100 (endpoints present).")
#     values = {c: np.interp(phase, t, df[c].to_numpy(dtype=float)) for c in matched}
#     return values


# def export_robot_error(path: Path, phase: np.ndarray, mean: dict, robot: dict):
#     records = []
#     for point in LANDMARKS:
#         for axis in ("X", "Y"):
#             feat = f"{point}_Delta_{axis}"
#             if feat not in robot:
#                 continue
#             err = robot[feat] - mean[feat]
#             records.append({"point": point, "axis": axis,
#                             "rmse": float(np.sqrt(np.mean(err**2))),
#                             "mae": float(np.mean(np.abs(err))),
#                             "peak_absolute_error": float(np.max(np.abs(err))),
#                             "units": "fraction_of_eye_corner_distance"})
#     pd.DataFrame(records).to_csv(path, index=False)


# def analyze_individual(person: str, syllable: str, repeats: list[dict],
#                        phase: np.ndarray, result_root: Path, show: bool):
#     """Plot one person's repetitions AND their within-person mean."""
#     if not repeats:
#         return
#     avg = {feat: np.mean(np.stack([r[feat] for r in repeats]), axis=0) for feat in FEATURES}
#     folder = result_root / "individual" / person / syllable
#     folder.mkdir(parents=True, exist_ok=True)
#     plot_xy_absolute(avg, syllable, person, folder / "01_anatomical_XY.png", show, repeats)
#     plot_delta_xy({f"repetition_{i+1}": r for i, r in enumerate(repeats)},
#                   syllable, folder / "02_delta_XY.png", show, mean=avg, mode="individual")
#     rep_dict = {f"repetition_{i+1}": r for i, r in enumerate(repeats)}
#     plot_grid(phase, rep_dict, syllable, "X", folder / "03_horizontal_X.png",
#               show, mean=avg, mode="individual", count_label=f"{len(repeats)} repetition(s)")
#     plot_grid(phase, rep_dict, syllable, "Y", folder / "04_vertical_Y.png",
#               show, mean=avg, mode="individual", count_label=f"{len(repeats)} repetition(s)")
#     plot_measures(phase, rep_dict, syllable, folder / "05_mouth_measurements.png",
#                   show, mean=avg, mode="individual", count_label=f"{len(repeats)} repetition(s)")
#     export_participant_curves(folder / "individual_mean.csv", phase, syllable, {person: avg})
#     print(f"  INDIVIDUAL {person}: {len(repeats)} accepted recording(s); 5 graphs -> {folder}")


# def compare_participants(syllable: str, people: dict, phase: np.ndarray,
#                          folder_root: Path, show: bool):
#     """Show each participant's time-normalized X and Y curves (one/person)."""
#     if not people:
#         return
#     folder = folder_root / "comparison" / syllable
#     folder.mkdir(parents=True, exist_ok=True)
#     mean, sd = stats(people, phase)
#     plot_grid(phase, people, syllable, "X", folder / "01_horizontal_X.png",
#               show, mean=mean, sd=sd, mode="compare")
#     plot_grid(phase, people, syllable, "Y", folder / "02_vertical_Y.png",
#               show, mean=mean, sd=sd, mode="compare")
#     plot_measures(phase, people, syllable, folder / "03_mouth_measurements.png",
#                   show, mean=mean, sd=sd, mode="compare")
#     plot_delta_xy(people, syllable, folder / "04_lips_chin_delta_XY.png",
#                   show, mean=mean, mode="compare", points=MAIN_LANDMARKS)
#     export_participant_curves(folder / "participant_curves.csv", phase, syllable, people)
#     print(f"  COMPARISON: {len(people)} participant(s); 4 graphs -> {folder}")


# def generate_reference(syllable: str, people: dict, phase: np.ndarray,
#                        folder_root: Path, show: bool, robot_csv: Path | None):
#     """Export population reference for future robot evaluation."""
#     if not people:
#         return
#     folder = folder_root / "reference" / syllable
#     folder.mkdir(parents=True, exist_ok=True)
#     mean, sd = stats(people, phase)
#     robot = load_robot(robot_csv, phase) if robot_csv else None
#     export_reference(folder / "group_reference.csv", phase, syllable, people, mean, sd)
#     plot_grid(phase, {}, syllable, "X", folder / "01_mean_horizontal_X.png",
#               show, mean=mean, sd=sd, mode="reference", robot=robot,
#               count_label=f"n={len(people)} participants")
#     plot_grid(phase, {}, syllable, "Y", folder / "02_mean_vertical_Y.png",
#               show, mean=mean, sd=sd, mode="reference", robot=robot,
#               count_label=f"n={len(people)} participants")
#     plot_measures(phase, {}, syllable, folder / "03_mean_mouth_measurements.png",
#                   show, mean=mean, sd=sd, mode="reference",
#                   count_label=f"n={len(people)} participants")
#     plot_delta_xy({}, syllable, folder / "04_mean_delta_XY.png", show,
#                   mean=mean, robot=robot, mode="reference")
#     if robot is not None:
#         export_robot_error(folder / "robot_vs_group_error.csv", phase, mean, robot)
#     if len(people) == 1:
#         print("  NOTE: SD requires >=2 participants; current reference uses one participant only.")
#     print(f"  REFERENCE: {len(people)} participant(s); 4 graphs and mean/SD CSV -> {folder}")


# def parse_args(argv=None):
#     parser = argparse.ArgumentParser(
#         description="Single-program orofacial analysis: individual, compare, reference, all.",
#         formatter_class=argparse.ArgumentDefaultsHelpFormatter,
#     )
#     parser.add_argument("--mode", choices=["individual", "compare", "reference", "all"],
#                         default="all", help="Which analysis to run")
#     parser.add_argument("--syllable", default="SE", help="SE, TA, SE,TA, or ALL")
#     parser.add_argument("--participant", help="Participant for individual plots (folder name)")
#     parser.add_argument("--participants", nargs="+", help="Filter cohort to selected participants")
#     parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
#                         help="Directory containing participant folders")
#     parser.add_argument("--output", type=Path, help="Output directory; default root/orofacial_results")
#     parser.add_argument("--segments", type=Path, help="CSV for manually annotated time intervals")
#     parser.add_argument("--require-segments", action="store_true",
#                         help="Reject trials without manually annotated intervals")
#     parser.add_argument("--robot", type=Path,
#                         help="Optional robot CSV (reference mode only; one syllable)")
#     parser.add_argument("--show", action="store_true", help="Also open generated plots in windows")
#     return parser.parse_args(argv)


# def main(argv=None):
#     args = parse_args(argv)
#     syllables = normalize_syllables(args.syllable)
#     if args.mode == "individual" and not args.participant:
#         raise SystemExit("--mode individual requires --participant <folder name>.")
#     if args.robot and (args.mode not in ("reference", "all") or len(syllables) != 1):
#         raise SystemExit("--robot requires --mode reference/all and exactly one syllable.")
#     if args.mode == "all" and args.participant and args.participants and args.participant not in args.participants:
#         raise SystemExit("Selected --participant is excluded by --participants filter.")

#     root = args.root.expanduser().resolve()
#     output = (args.output or root / "orofacial_results").expanduser().resolve()
#     segment_file = (args.segments or root / "segments.csv").expanduser().resolve()
#     segments = read_segments(segment_file)
#     phase = np.linspace(0.0, 100.0, N_PHASE)
#     modes = (["individual", "compare", "reference"] if args.mode == "all" else [args.mode])

#     for syllable in syllables:
#         print(f"\n[{syllable}] Loading recordings...")
#         filter_people = args.participants
#         if args.mode == "individual":
#             filter_people = [args.participant]
#         # For --mode all, compare/reference can include the whole cohort while
#         # individual analysis runs only for the --participant provided.
#         people, reps, qc, total = prepare_cohort(
#             root, syllable, filter_people, segments, args.require_segments, phase
#         )
#         accepted = sum(row["status"] == "accepted" for row in qc)
#         print(f"  Accepted: {accepted}/{total} recordings from {len(people)} participant(s)")
#         if total == 0:
#             continue
#         qc_folder = output / "quality_control" / syllable
#         export_qc(qc_folder / "recordings.csv", qc)
#         export_durations(qc_folder / "participant_durations.csv", syllable, qc)
#         if not people:
#             continue
#         if "individual" in modes:
#             if args.participant:
#                 if args.participant in reps:
#                     analyze_individual(args.participant, syllable, reps[args.participant], phase, output, args.show)
#                 else:
#                     print(f"  No valid recordings for requested participant: {args.participant}")
#             else:
#                 print("  Individual graphs skipped: specify --participant NAME to include them.")
#         if "compare" in modes:
#             compare_participants(syllable, people, phase, output, args.show)
#         if "reference" in modes:
#             generate_reference(syllable, people, phase, output, args.show,
#                                args.robot.expanduser().resolve() if args.robot else None)


# if __name__ == "__main__":
#     main()
"""Orofacial landmark trajectory analysis for one participant or a cohort.

Compatible with the 9-landmark CSV files from orofacial_tracker.py:
    BOCA_SUP_EXT, BOCA_INF_EXT, BOCA_SUP_INT, BOCA_INF_INT,
    BOCA_IZQ, BOCA_DER, BARBILLA, MANDIBULA_IZQ, MANDIBULA_DER

Install:
    pip install numpy pandas matplotlib

Folder structure:
    my_study/
        orofacial_analysis.py
        orofacial_tracker.py
        Joseph/SE_R01.csv
        Joseph/SE_R02.csv
        Bro/SE_R01.csv
        segments.csv                  # OPTIONAL

Examples:
    python orofacial_analysis.py --mode individual --participant Joseph --syllable SE
    python orofacial_analysis.py --mode compare --syllable SE
    python orofacial_analysis.py --mode compare --syllable SE --participants Joseph Bro
    python orofacial_analysis.py --mode reference --syllable SE
    python orofacial_analysis.py --mode all --syllable SE --participant Joseph
    python orofacial_analysis.py --mode reference --syllable ALL
    python orofacial_analysis.py --mode reference --syllable SE --robot robot_SE.csv

Optional segments.csv:
    participant,filename,start_ms,end_ms
    Joseph,SE_R01.csv,145,685
    Bro,SE_R01.csv,170,720

IMPORTANT: In the absence of an entry in segments.csv, the entire recording
is time-normalized. That is *recording progress*, NOT a verified 0-100%
articulatory gesture. For research comparisons, annotate consistent boundaries
and use --require-segments. The time normalization is a linear resampling;
it does NOT apply dynamic time warping.

Units: ALL positions/displacements are dimensionless fractions of the eye-corner
distance used by the capture program (landmarks 133 and 362), NOT millimeters
and NOT physical interpupillary distance. Image Y increases downward.

Each participant contributes ONE trajectory to cohort statistics, obtained by
averaging their accepted repetitions after resampling. The group mean is an
empirical reference, not a clinical norm or validated robotic target.

Optional robot input: CSV with 'phase_pct' (0-100) and paired columns such as
'BOCA_INF_INT_Delta_X', 'BOCA_INF_INT_Delta_Y'. Values MUST already be in the
SAME dimensionless coordinate convention as the human data, including spatial
orientation, baseline definition, and head/robot reference frame. Only points
with both components are compared. Robot and human events must also be aligned
in time for the comparison to be meaningful.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import sys
import warnings

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SYLLABLES = ["TA", "TE", "TI", "TO", "TU", "SA", "SE", "SI", "SO", "SU", "RA", "RE", "RI", "RO", "RU"]
LANDMARKS = [
    "BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_SUP_INT", "BOCA_INF_INT",
    "BOCA_IZQ", "BOCA_DER", "BARBILLA", "MANDIBULA_IZQ", "MANDIBULA_DER",
]
MAIN_LANDMARKS = LANDMARKS[:7]  # Six lip points + chin
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
COLORS = plt.get_cmap("tab10").colors
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

# Quality control defaults. Tune transparently and keep settings consistent.
N_PHASE = 101
MIN_FRAMES = 6
MIN_DURATION_MS = 120.0
MAX_MISSING_FRACTION = 0.20
MAX_GAP_MS = 250.0
MAX_EDGE_GAP_MS = 120.0
DPI = 150


def normalize_syllables(request: str) -> list[str]:
    if request.upper() == "ALL":
        return SYLLABLES.copy()
    syllables = [s.strip().upper() for s in request.split(",") if s.strip()]
    unknown = set(syllables) - set(SYLLABLES)
    if not syllables or unknown:
        raise ValueError(f"Unsupported syllable(s): {sorted(unknown)}. Use TA, SE, ... or ALL.")
    return list(dict.fromkeys(syllables))


def read_segments(path: Path) -> dict[tuple[str, str], tuple[float, float]]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    required = {"participant", "filename", "start_ms", "end_ms"}
    if not required.issubset(df.columns):
        raise ValueError(f"{path} must have columns {sorted(required)}")
    boundaries = {}
    for row in df.itertuples(index=False):
        key = (str(row.participant).strip(), str(row.filename).strip())
        start, end = float(row.start_ms), float(row.end_ms)
        if not np.isfinite([start, end]).all() or end <= start:
            raise ValueError(f"Invalid interval for {key} in {path}")
        if key in boundaries:
            raise ValueError(f"Duplicate segment for {key} in {path}")
        boundaries[key] = (start, end)
    return boundaries


def discover_trials(root: Path, syllable: str, participants: list[str] | None):
    pattern = re.compile(rf"{re.escape(syllable)}(?:_R\d+)?\.csv", re.IGNORECASE)
    selected = set(participants) if participants is not None else None
    if not root.is_dir():
        raise FileNotFoundError(f"Data root does not exist: {root}")
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name == "orofacial_results":
            continue
        if selected is not None and folder.name not in selected:
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and pattern.fullmatch(path.name):
                yield folder.name, path


def append_measures(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Differences of the rest-relative displacements preserve each person's
    # individual neutral-face calibration (rather than zeroing first CSV frame).
    df["Inner_lip_opening_change"] = (
        df["BOCA_INF_INT_Delta_Y"] - df["BOCA_SUP_INT_Delta_Y"]
    )
    df["Outer_lip_separation_change"] = (
        df["BOCA_INF_EXT_Delta_Y"] - df["BOCA_SUP_EXT_Delta_Y"]
    )

    left = df["BOCA_IZQ_Norm_X"]
    right = df["BOCA_DER_Norm_X"]
    neutral_left = left - df["BOCA_IZQ_Delta_X"]
    neutral_right = right - df["BOCA_DER_Delta_X"]
    df["Mouth_width_change"] = (right-left).abs() - (neutral_right-neutral_left).abs()

    df["Chin_drop"] = df["BARBILLA_Delta_Y"]
    df["Chin_to_lower_lip_change"] = df["BARBILLA_Delta_Y"] - df["BOCA_INF_EXT_Delta_Y"]
    df["Mouth_center_shift_X"] = 0.5 * (df["BOCA_IZQ_Delta_X"] + df["BOCA_DER_Delta_X"])
    df["Mouth_center_shift_Y"] = 0.5 * (df["BOCA_IZQ_Delta_Y"] + df["BOCA_DER_Delta_Y"])
    df["Lip_height_change"] = 0.25 * (
        df["BOCA_SUP_EXT_Delta_Y"] + df["BOCA_INF_EXT_Delta_Y"] +
        df["BOCA_SUP_INT_Delta_Y"] + df["BOCA_INF_INT_Delta_Y"]
    )
    return df


def read_trial(
    csv: Path, person: str, syllable: str, segments: dict,
    require_segments: bool, phase: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict]:
    df = pd.read_csv(csv)
    missing = [name for name in RAW_COLS if name not in df.columns]
    if missing:
        raise ValueError("missing expected CSV columns: " + ", ".join(missing[:5]))
    if "Silaba" in df and df["Silaba"].notna().any():
        actual = set(df["Silaba"].dropna().astype(str).str.strip().str.upper())
        if actual != {syllable}:
            raise ValueError(f"syllable label mismatch: {actual}")

    df = df[RAW_COLS].copy()
    for name in RAW_COLS:
        df[name] = pd.to_numeric(df[name], errors="coerce")
    df = df[np.isfinite(df["Tiempo_ms"])].sort_values("Tiempo_ms")
    if df.empty:
        raise ValueError("no valid recording times")
    key = (person, csv.name)
    annotated = key in segments
    if require_segments and not annotated:
        raise ValueError("missing gesture boundaries in segments.csv")
    start, end = segments[key] if annotated else (
        float(df["Tiempo_ms"].iloc[0]), float(df["Tiempo_ms"].iloc[-1])
    )
    df = df[df["Tiempo_ms"].between(start, end)].copy()
    if df.empty:
        raise ValueError("selected segment contains no frames")
    # Recorder timestamps are integer milliseconds; duplicates can occur.
    df = df.groupby("Tiempo_ms", as_index=False).mean(numeric_only=True)
    if len(df) < MIN_FRAMES:
        raise ValueError(f"fewer than {MIN_FRAMES} distinct frames")
    duration = end - start
    if duration < MIN_DURATION_MS:
        raise ValueError(f"selected interval shorter than {MIN_DURATION_MS:.0f} ms")

    df = append_measures(df)
    finite = np.isfinite(df[FEATURES].to_numpy(dtype=float)).all(axis=1)
    missing_fraction = float(1 - finite.mean())
    if missing_fraction > MAX_MISSING_FRACTION:
        raise ValueError(f"missing landmark tracking: {missing_fraction:.1%} of frames")
    valid = df.loc[finite]
    if len(valid) < MIN_FRAMES:
        raise ValueError("too few fully tracked frames")

    t = valid["Tiempo_ms"].to_numpy(dtype=float)
    max_gap = float(np.diff(t).max())
    if max_gap > MAX_GAP_MS:
        raise ValueError(f"tracking gap of {max_gap:.0f} ms exceeds limit")
    if t[0] - start > MAX_EDGE_GAP_MS or end - t[-1] > MAX_EDGE_GAP_MS:
        raise ValueError("missing tracking at selected-interval boundary")

    # Linear resampling: avoids spurious cubic-spline overshoot.
    sample_times = start + (phase / 100) * duration
    curves = {
        feat: np.interp(sample_times, t, valid[feat].to_numpy(dtype=float))
        for feat in FEATURES
    }
    metadata = {
        "participant": person, "filename": csv.name, "status": "accepted",
        "reason": "", "annotated": annotated, "start_ms": start, "end_ms": end,
        "duration_ms": duration, "total_frames": len(df),
        "valid_frames": len(valid), "missing_fraction": missing_fraction,
        "max_tracking_gap_ms": max_gap,
    }
    return curves, metadata


def prepare_cohort(
    root: Path, syllable: str, participants: list[str] | None,
    segments: dict, require_segments: bool, phase: np.ndarray,
):
    repetitions: dict[str, list[dict]] = defaultdict(list)
    qc = []
    paths = list(discover_trials(root, syllable, participants))
    for person, path in paths:
        try:
            curves, metadata = read_trial(path, person, syllable, segments, require_segments, phase)
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            qc.append({"participant": person, "filename": path.name,
                       "status": "rejected", "reason": str(exc)})
            print(f"  Rejected {person}/{path.name}: {exc}")
            continue
        repetitions[person].append(curves)
        qc.append(metadata)
    people = {
        person: {
            feature: np.mean(np.stack([rep[feature] for rep in trials]), axis=0)
            for feature in FEATURES
        }
        for person, trials in repetitions.items()
    }
    if not people:
        print(f"  No accepted recordings for {syllable}.")
    elif any(x.get("annotated") is False for x in qc if x["status"] == "accepted"):
        print("  NOTE: Some recordings use their full duration (not annotated syllable boundaries).")
    return people, repetitions, qc, len(paths)


def stats(people: dict[str, dict[str, np.ndarray]], phase: np.ndarray):
    if not people:
        return {}, {}
    means = {}
    sd = {}
    for feat in FEATURES:
        stack = np.stack([person[feat] for person in people.values()])
        means[feat] = stack.mean(axis=0)
        sd[feat] = stack.std(axis=0, ddof=1) if len(stack) > 1 else np.full(len(phase), np.nan)
    return means, sd


def plot_save(fig, filename: Path, show: bool):
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=DPI, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def plot_xy_absolute(
    data: dict[str, np.ndarray], syllable: str, name: str, target: Path,
    show: bool, repeats: list[dict] | None = None,
):
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    for idx, point in enumerate(LANDMARKS):
        x, y = f"{point}_Norm_X", f"{point}_Norm_Y"
        color = COLORS[idx]
        if repeats:
            for rep in repeats:
                ax.plot(rep[x], rep[y], color=color, linewidth=.55, alpha=.14)
        ax.plot(data[x], data[y], color=color, linewidth=1.15, label=LABELS[point])
        ax.scatter([data[x][0]], [data[y][0]], s=18, color=color)
        ax.scatter([data[x][-1]], [data[y][-1]], s=28, marker="x", color=color)
    ax.set_title(f"{name} | {syllable} | normalized anatomical XY\n"
                 "Dot = first frame; X = last frame")
    ax.set_xlabel("X relative to nose (eye-distance units)")
    ax.set_ylabel("Y relative to nose (eye-distance units; positive downward)")
    ax.invert_yaxis()
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(alpha=.20)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    plot_save(fig, target, show)


def plot_grid(
    phase: np.ndarray, curves: dict[str, dict], syllable: str, axis: str,
    target: Path, show: bool, mean: dict | None = None,
    sd: dict | None = None, mode: str = "individual",
    points: list[str] | None = None, robot: dict | None = None,
    count_label: str | None = None,
):
    points = points or LANDMARKS
    ncols = 3
    nrows = int(np.ceil(len(points) / ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(15, 3.35 * nrows), sharex=True)
    for i, point in enumerate(points):
        ax = axs.flat[i]
        feature = f"{point}_Delta_{axis}"
        color = COLORS[LANDMARKS.index(point)]
        for person in curves.values():
            ax.plot(phase, person[feature], color="0.55" if mode != "individual" else color,
                    alpha=.24 if len(curves) >= 8 else .47,
                    linewidth=.9 if len(curves) > 1 else 1.2)
        if mean is not None:
            if sd is not None and np.isfinite(sd[feature]).any():
                ax.fill_between(phase, mean[feature]-sd[feature], mean[feature]+sd[feature],
                                color=color, alpha=.19)
            ax.plot(phase, mean[feature], color=color, linewidth=2.4, label="Group mean")
        if robot is not None and feature in robot:
            ax.plot(phase, robot[feature], color="black", ls="--", linewidth=2, label="Robot")
        ax.axhline(0, linewidth=.7, color="black", alpha=.4)
        ax.set_title(LABELS[point], fontsize=10)
        ax.set_ylabel(f"Delta {axis} (eye-distance units)", fontsize=8)
        ax.set_xlim(0, 100)
        ax.grid(alpha=.18)
        if robot is not None and feature in robot:
            ax.legend(fontsize=8, loc="best")
    for ax in axs.flat[len(points):]:
        ax.set_visible(False)
    for ax in axs.flat:
        if ax.get_visible():
            ax.set_xlabel("Selected interval (%)")
    meaning = {"individual": "Individual repetitions and participant mean",
               "compare": "Participants (grey) and cohort mean",
               "reference": "Cohort mean, ±1 participant SD and optional robot"}[mode]
    fig.suptitle(f"{syllable}: {axis} displacement | {meaning} | {count_label or f'n={len(curves)}'}", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .96))
    plot_save(fig, target, show)


def plot_measure_group(
    phase: np.ndarray, curves: dict[str, dict], syllable: str,
    target: Path, show: bool, group_key: str, mean: dict | None = None,
    sd: dict | None = None, mode: str = "compare", count_label: str | None = None,
):
    pairs = MEASURE_GROUPS[group_key]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    palette = ["#7c47a9", "#0c8a8a", "#d97904", "#c23b3b"]

    for line_idx, (feature, label) in enumerate(pairs):
        color = palette[line_idx % len(palette)]
        for values in curves.values():
            ax.plot(phase, values[feature], color=color, alpha=.10 if len(curves) >= 8 else .20,
                    linewidth=.85)
        if mean is not None:
            if sd is not None and np.isfinite(sd[feature]).any():
                ax.fill_between(phase, mean[feature]-sd[feature], mean[feature]+sd[feature],
                                color=color, alpha=.12)
            ax.plot(phase, mean[feature], color=color, linewidth=2.3, label=label)
        else:
            # Individual mode with one-participant mean only.
            sample = next(iter(curves.values()))
            ax.plot(phase, sample[feature], color=color, linewidth=2.0, label=label)

    ax.axhline(0, color="black", alpha=.45, linewidth=.7)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Selected interval (%)")
    ax.set_ylabel("Change from neutral (eye-distance units)")
    title_map = {
        "vertical_opening": "Vertical mouth opening",
        "horizontal_widening": "Horizontal mouth widening",
        "jaw_contribution": "Jaw / chin contribution",
        "mouth_translation": "Overall mouth translation",
    }
    ax.set_title(title_map[group_key])
    ax.grid(alpha=.20)
    ax.legend(loc="best")
    fig.suptitle(f"{syllable}: {title_map[group_key].lower()} | {mode} | {count_label or f'n={len(curves)}'}", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .95))
    plot_save(fig, target, show)


def plot_delta_xy(

    curves: dict[str, dict], syllable: str, target: Path, show: bool,
    mean: dict | None = None, mode: str = "reference", robot: dict | None = None,
    points: list[str] | None = None,
):
    points = points or LANDMARKS
    rows = int(np.ceil(len(points) / 3))
    fig, axs = plt.subplots(rows, 3, figsize=(13.8, rows * 3.5))
    for idx, point in enumerate(points):
        ax = axs.flat[idx]
        xf, yf = f"{point}_Delta_X", f"{point}_Delta_Y"
        color = COLORS[LANDMARKS.index(point)]
        for person in curves.values():
            ax.plot(person[xf], person[yf], linewidth=.85,
                    color="0.6" if len(curves) > 1 else color,
                    alpha=.22 if len(curves) > 7 else .5)
        if mean is not None:
            ax.plot(mean[xf], mean[yf], linewidth=2.6, color=color, label="Human mean")
            ax.scatter([mean[xf][0]], [mean[yf][0]], color=color, s=20, zorder=5)
            ax.scatter([mean[xf][-1]], [mean[yf][-1]], color=color, marker="x", s=32, zorder=5)
        if robot is not None and xf in robot and yf in robot:
            ax.plot(robot[xf], robot[yf], "--", color="black", linewidth=2, label="Robot")
            ax.legend(fontsize=7)
        ax.axhline(0, color="black", alpha=.25, linewidth=.6)
        ax.axvline(0, color="black", alpha=.25, linewidth=.6)
        ax.set_title(LABELS[point], fontsize=10)
        ax.set_xlabel("Delta X (eye-distance units)", fontsize=8)
        ax.set_ylabel("Delta Y (positive downward)", fontsize=8)
        ax.invert_yaxis()
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=.12)
    for ax in axs.flat[len(points):]:
        ax.set_visible(False)
    fig.suptitle(f"{syllable}: XY trajectories relative to neutral | {mode}", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .96))
    plot_save(fig, target, show)


def export_qc(path: Path, qc: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(qc).to_csv(path, index=False)


def export_participant_curves(path: Path, phase: np.ndarray, syllable: str, people: dict):
    rows = []
    for person, data in people.items():
        for i, pct in enumerate(phase):
            row = {"participant": person, "syllable": syllable, "phase_pct": pct}
            row.update({feat: float(data[feat][i]) for feat in FEATURES})
            rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def export_reference(path: Path, phase: np.ndarray, syllable: str,
                     people: dict, mean: dict, sd: dict):
    rows = []
    for i, pct in enumerate(phase):
        row = {"syllable": syllable, "phase_pct": pct, "n_participants": len(people)}
        for feat in FEATURES:
            row[f"{feat}_mean"] = float(mean[feat][i])
            row[f"{feat}_sd"] = float(sd[feat][i])
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def export_durations(path: Path, syllable: str, qc: list[dict]):
    accepted = [r for r in qc if r["status"] == "accepted"]
    rows = []
    for person in sorted({r["participant"] for r in accepted}):
        durations = [r["duration_ms"] for r in accepted if r["participant"] == person]
        rows.append({"participant": person, "syllable": syllable,
                     "n_repetitions": len(durations),
                     "mean_duration_ms": float(np.mean(durations)),
                     "sd_duration_ms": float(np.std(durations, ddof=1))
                     if len(durations) > 1 else np.nan})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def load_robot(path: Path, phase: np.ndarray) -> dict[str, np.ndarray]:
    df = pd.read_csv(path)
    if "phase_pct" not in df.columns:
        raise ValueError("Robot CSV requires 'phase_pct' from 0 to 100.")
    df["phase_pct"] = pd.to_numeric(df["phase_pct"], errors="coerce")
    cols = [f"{pt}_Delta_{axis}" for pt in LANDMARKS for axis in ("X", "Y")]
    matched = [c for c in cols if c in df.columns]
    if not matched:
        raise ValueError("Robot CSV has no matching landmark Delta_X / Delta_Y columns.")
    for col in matched:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["phase_pct"] + matched).sort_values("phase_pct")
    if len(df) < 3:
        raise ValueError("Robot CSV needs >=3 complete time samples.")
    df = df.groupby("phase_pct", as_index=False).mean(numeric_only=True)
    t = df["phase_pct"].to_numpy(dtype=float)
    if t[0] > 0 or t[-1] < 100 or t[0] < 0 or t[-1] > 100:
        raise ValueError("Robot phase_pct must span exactly 0..100 (endpoints present).")
    values = {c: np.interp(phase, t, df[c].to_numpy(dtype=float)) for c in matched}
    return values


def export_robot_error(path: Path, phase: np.ndarray, mean: dict, robot: dict):
    records = []
    for point in LANDMARKS:
        for axis in ("X", "Y"):
            feat = f"{point}_Delta_{axis}"
            if feat not in robot:
                continue
            err = robot[feat] - mean[feat]
            records.append({"point": point, "axis": axis,
                            "rmse": float(np.sqrt(np.mean(err**2))),
                            "mae": float(np.mean(np.abs(err))),
                            "peak_absolute_error": float(np.max(np.abs(err))),
                            "units": "fraction_of_eye_corner_distance"})
    pd.DataFrame(records).to_csv(path, index=False)


def analyze_individual(person: str, syllable: str, repeats: list[dict],
                       phase: np.ndarray, result_root: Path, show: bool):
    """Plot one person's repetitions AND their within-person mean."""
    if not repeats:
        return
    avg = {feat: np.mean(np.stack([r[feat] for r in repeats]), axis=0) for feat in FEATURES}
    folder = result_root / "individual" / person / syllable
    folder.mkdir(parents=True, exist_ok=True)
    plot_xy_absolute(avg, syllable, person, folder / "01_anatomical_XY.png", show, repeats)
    plot_delta_xy({f"repetition_{i+1}": r for i, r in enumerate(repeats)},
                  syllable, folder / "02_delta_XY.png", show, mean=avg, mode="individual")
    rep_dict = {f"repetition_{i+1}": r for i, r in enumerate(repeats)}
    plot_measure_group(phase, {person: avg}, syllable, folder / "03_vertical_opening.png",
                       show, group_key="vertical_opening", mode="individual",
                       count_label=f"{len(repeats)} repetition(s)")
    plot_measure_group(phase, {person: avg}, syllable, folder / "04_horizontal_widening.png",
                       show, group_key="horizontal_widening", mode="individual",
                       count_label=f"{len(repeats)} repetition(s)")
    plot_measure_group(phase, {person: avg}, syllable, folder / "05_jaw_contribution.png",
                       show, group_key="jaw_contribution", mode="individual",
                       count_label=f"{len(repeats)} repetition(s)")
    plot_measure_group(phase, {person: avg}, syllable, folder / "06_mouth_translation.png",
                       show, group_key="mouth_translation", mode="individual",
                       count_label=f"{len(repeats)} repetition(s)")
    export_participant_curves(folder / "individual_mean.csv", phase, syllable, {person: avg})
    print(f"  INDIVIDUAL {person}: {len(repeats)} accepted recording(s); 6 graphs -> {folder}")


def compare_participants(syllable: str, people: dict, phase: np.ndarray,
                         folder_root: Path, show: bool):
    """Show each participant's time-normalized X and Y curves (one/person)."""
    if not people:
        return
    folder = folder_root / "comparison" / syllable
    folder.mkdir(parents=True, exist_ok=True)
    mean, sd = stats(people, phase)
    plot_measure_group(phase, people, syllable, folder / "01_vertical_opening.png",
                       show, group_key="vertical_opening", mean=mean, sd=sd, mode="compare")
    plot_measure_group(phase, people, syllable, folder / "02_horizontal_widening.png",
                       show, group_key="horizontal_widening", mean=mean, sd=sd, mode="compare")
    plot_measure_group(phase, people, syllable, folder / "03_jaw_contribution.png",
                       show, group_key="jaw_contribution", mean=mean, sd=sd, mode="compare")
    plot_measure_group(phase, people, syllable, folder / "04_mouth_translation.png",
                       show, group_key="mouth_translation", mean=mean, sd=sd, mode="compare")
    plot_delta_xy(people, syllable, folder / "05_lips_chin_delta_XY.png",
                  show, mean=mean, mode="compare", points=MAIN_LANDMARKS)
    export_participant_curves(folder / "participant_curves.csv", phase, syllable, people)
    print(f"  COMPARISON: {len(people)} participant(s); 5 graphs -> {folder}")


def generate_reference(syllable: str, people: dict, phase: np.ndarray,
                       folder_root: Path, show: bool, robot_csv: Path | None):
    """Export population reference for future robot evaluation."""
    if not people:
        return
    folder = folder_root / "reference" / syllable
    folder.mkdir(parents=True, exist_ok=True)
    mean, sd = stats(people, phase)
    robot = load_robot(robot_csv, phase) if robot_csv else None
    export_reference(folder / "group_reference.csv", phase, syllable, people, mean, sd)
    plot_measure_group(phase, {}, syllable, folder / "01_mean_vertical_opening.png",
                       show, group_key="vertical_opening", mean=mean, sd=sd, mode="reference",
                       count_label=f"n={len(people)} participants")
    plot_measure_group(phase, {}, syllable, folder / "02_mean_horizontal_widening.png",
                       show, group_key="horizontal_widening", mean=mean, sd=sd, mode="reference",
                       count_label=f"n={len(people)} participants")
    plot_measure_group(phase, {}, syllable, folder / "03_mean_jaw_contribution.png",
                       show, group_key="jaw_contribution", mean=mean, sd=sd, mode="reference",
                       count_label=f"n={len(people)} participants")
    plot_measure_group(phase, {}, syllable, folder / "04_mean_mouth_translation.png",
                       show, group_key="mouth_translation", mean=mean, sd=sd, mode="reference",
                       count_label=f"n={len(people)} participants")
    plot_delta_xy({}, syllable, folder / "05_mean_delta_XY.png", show,
                  mean=mean, robot=robot, mode="reference")
    if robot is not None:
        export_robot_error(folder / "robot_vs_group_error.csv", phase, mean, robot)
    if len(people) == 1:
        print("  NOTE: SD requires >=2 participants; current reference uses one participant only.")
    print(f"  REFERENCE: {len(people)} participant(s); 5 graphs and mean/SD CSV -> {folder}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Single-program orofacial analysis: individual, compare, reference, all.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mode", choices=["individual", "compare", "reference", "all"],
                        default="all", help="Which analysis to run")
    parser.add_argument("--syllable", default="SE", help="SE, TA, SE,TA, or ALL")
    parser.add_argument("--participant", help="Participant for individual plots (folder name)")
    parser.add_argument("--participants", nargs="+", help="Filter cohort to selected participants")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="Directory containing participant folders")
    parser.add_argument("--output", type=Path, help="Output directory; default root/orofacial_results")
    parser.add_argument("--segments", type=Path, help="CSV for manually annotated time intervals")
    parser.add_argument("--require-segments", action="store_true",
                        help="Reject trials without manually annotated intervals")
    parser.add_argument("--robot", type=Path,
                        help="Optional robot CSV (reference mode only; one syllable)")
    parser.add_argument("--show", action="store_true", help="Also open generated plots in windows")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    syllables = normalize_syllables(args.syllable)
    if args.mode == "individual" and not args.participant:
        raise SystemExit("--mode individual requires --participant <folder name>.")
    if args.robot and (args.mode not in ("reference", "all") or len(syllables) != 1):
        raise SystemExit("--robot requires --mode reference/all and exactly one syllable.")
    if args.mode == "all" and args.participant and args.participants and args.participant not in args.participants:
        raise SystemExit("Selected --participant is excluded by --participants filter.")

    root = args.root.expanduser().resolve()
    output = (args.output or root / "orofacial_results").expanduser().resolve()
    segment_file = (args.segments or root / "segments.csv").expanduser().resolve()
    segments = read_segments(segment_file)
    phase = np.linspace(0.0, 100.0, N_PHASE)
    modes = (["individual", "compare", "reference"] if args.mode == "all" else [args.mode])

    for syllable in syllables:
        print(f"\n[{syllable}] Loading recordings...")
        filter_people = args.participants
        if args.mode == "individual":
            filter_people = [args.participant]
        # For --mode all, compare/reference can include the whole cohort while
        # individual analysis runs only for the --participant provided.
        people, reps, qc, total = prepare_cohort(
            root, syllable, filter_people, segments, args.require_segments, phase
        )
        accepted = sum(row["status"] == "accepted" for row in qc)
        print(f"  Accepted: {accepted}/{total} recordings from {len(people)} participant(s)")
        if total == 0:
            continue
        qc_folder = output / "quality_control" / syllable
        export_qc(qc_folder / "recordings.csv", qc)
        export_durations(qc_folder / "participant_durations.csv", syllable, qc)
        if not people:
            continue
        if "individual" in modes:
            if args.participant:
                if args.participant in reps:
                    analyze_individual(args.participant, syllable, reps[args.participant], phase, output, args.show)
                else:
                    print(f"  No valid recordings for requested participant: {args.participant}")
            else:
                print("  Individual graphs skipped: specify --participant NAME to include them.")
        if "compare" in modes:
            compare_participants(syllable, people, phase, output, args.show)
        if "reference" in modes:
            generate_reference(syllable, people, phase, output, args.show,
                               args.robot.expanduser().resolve() if args.robot else None)


if __name__ == "__main__":
    main()
    