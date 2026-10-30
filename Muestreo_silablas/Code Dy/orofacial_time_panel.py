"""Plot 7 lips/chin landmarks across normalized time in one single figure.

Supports two usage styles:
1) Direct CSV:
   python orofacial_time_panel.py --csv path/to/participant_curves.csv

2) Folder-based discovery from your comparison results:
   python orofacial_time_panel.py --root .\orofacial_results\comparison --syllable SA
   python orofacial_time_panel.py --root .\orofacial_results\comparison --syllable ALL

Expected folder structure for discovery mode:
    orofacial_results/
        comparison/
            SA/participant_curves.csv
            SE/participant_curves.csv
            ...

Creates a 7-panel figure (3x3 layout with 2 empty slots) where each subplot
shows Delta X and Delta Y versus normalized time for one landmark.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

POINTS = [
    "BOCA_SUP_EXT",
    "BOCA_INF_EXT",
    "BOCA_SUP_INT",
    "BOCA_INF_INT",
    "BOCA_IZQ",
    "BOCA_DER",
    "BARBILLA",
]

LABELS = {
    "BOCA_SUP_EXT": "Upper outer lip (0)",
    "BOCA_INF_EXT": "Lower outer lip (17)",
    "BOCA_SUP_INT": "Upper inner lip (13)",
    "BOCA_INF_INT": "Lower inner lip (14)",
    "BOCA_IZQ": "Left mouth corner (61)",
    "BOCA_DER": "Right mouth corner (291)",
    "BARBILLA": "Chin (152)",
}

SYLLABLES = ["TA", "TE", "TI", "TO", "TU", "SA", "SE", "SI", "SO", "SU", "RA", "RE", "RI", "RO", "RU"]

X_COLOR = "#7c47a9"  # purple
Y_COLOR = "#0c8a8a"  # teal


def parse_args():
    p = argparse.ArgumentParser(
        description="Plot 7 landmark time-series panels from participant_curves CSV"
    )
    p.add_argument("--csv", type=Path, default=None,
                   help="Direct path to participant_curves.csv or participant_curves_<SYL>.csv")
    p.add_argument("--root", type=Path, default=None,
                   help="Root comparison folder containing syllable subfolders, e.g. .\\orofacial_results\\comparison")
    p.add_argument("--syllable", type=str, default=None,
                   help="Syllable to plot (e.g. SA) or ALL when using --root")
    p.add_argument("--filename", type=str, default="participant_curves.csv",
                   help="CSV filename expected inside each syllable folder when using --root")
    p.add_argument("--output", type=Path, default=None, help="Output PNG path (single-file mode only)")
    p.add_argument("--outdir", type=Path, default=None,
                   help="Output directory for --syllable ALL; default is each syllable folder")
    p.add_argument("--title", type=str, default=None, help="Main figure title (single-file mode only)")
    p.add_argument("--participant", type=str, default=None, help="Optional: only this participant")
    p.add_argument("--stat", choices=["mean", "median"], default="mean",
                   help="Highlighted central tendency")
    p.add_argument("--show-sd", action="store_true",
                   help="Show +/- 1 SD shaded band around highlighted curve")
    p.add_argument("--alpha-trials", type=float, default=0.18,
                   help="Transparency for individual participant traces")
    p.add_argument("--linewidth-trials", type=float, default=0.8,
                   help="Line width for individual participant traces")
    p.add_argument("--linewidth-main", type=float, default=2.2,
                   help="Line width for highlighted mean/median traces")
    args = p.parse_args()

    if args.csv is None and args.root is None:
        p.error("Provide either --csv PATH or --root PATH with --syllable.")
    if args.root is not None and not args.syllable:
        p.error("When using --root, you must also provide --syllable SA or --syllable ALL.")
    return args


def resolve_syllables(token: str) -> list[str]:
    token = token.upper()
    if token == "ALL":
        return SYLLABLES
    if token not in SYLLABLES:
        raise ValueError(f"Unsupported syllable '{token}'. Use one of {SYLLABLES} or ALL.")
    return [token]


def load_data(csv_path: Path, participant: str | None):
    df = pd.read_csv(csv_path)
    required = {"participant", "syllable", "phase_pct"}
    for pt in POINTS:
        required.update({f"{pt}_Delta_X", f"{pt}_Delta_Y"})
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if participant is not None:
        df = df[df["participant"] == participant].copy()
        if df.empty:
            raise ValueError(f"Participant '{participant}' not found in {csv_path.name}")

    syllables = df["syllable"].dropna().astype(str).str.upper().unique().tolist()
    syllable = syllables[0] if syllables else csv_path.parent.name.upper()

    cols = ["phase_pct"] + [f"{pt}_Delta_{axis}" for pt in POINTS for axis in ("X", "Y")]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    groups = {}
    for name, g in df.groupby("participant"):
        g = g.sort_values("phase_pct").copy()
        if g[cols].isna().any().any():
            continue
        groups[name] = g
    if not groups:
        raise ValueError("No valid participant trajectories found after filtering.")
    return groups, syllable


def central_and_sd(stack: np.ndarray, stat: str):
    if stat == "median":
        center = np.median(stack, axis=0)
    else:
        center = np.mean(stack, axis=0)
    sd = np.std(stack, axis=0, ddof=1) if stack.shape[0] > 1 else np.full(stack.shape[1], np.nan)
    return center, sd


def plot_panel(groups: dict[str, pd.DataFrame], syllable: str, csv_path: Path, output: Path | None,
               title: str | None, stat: str, show_sd: bool, alpha_trials: float,
               linewidth_trials: float, linewidth_main: float):
    n_people = len(groups)
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), sharex=True)
    axes = axes.flatten()

    all_vals = []
    for pt in POINTS:
        for g in groups.values():
            all_vals.append(g[f"{pt}_Delta_X"].to_numpy())
            all_vals.append(g[f"{pt}_Delta_Y"].to_numpy())
    ymin = min(float(np.min(v)) for v in all_vals)
    ymax = max(float(np.max(v)) for v in all_vals)
    pad = 0.08 * (ymax - ymin if ymax > ymin else 1.0)
    ymin -= pad
    ymax += pad

    for i, pt in enumerate(POINTS):
        ax = axes[i]
        x_stack = []
        y_stack = []
        phase_ref = None
        for g in groups.values():
            phase = g["phase_pct"].to_numpy()
            x = g[f"{pt}_Delta_X"].to_numpy()
            y = g[f"{pt}_Delta_Y"].to_numpy()
            phase_ref = phase
            x_stack.append(x)
            y_stack.append(y)
            ax.plot(phase, x, color=X_COLOR, alpha=alpha_trials, linewidth=linewidth_trials)
            ax.plot(phase, y, color=Y_COLOR, alpha=alpha_trials, linewidth=linewidth_trials)

        x_stack = np.vstack(x_stack)
        y_stack = np.vstack(y_stack)
        x_center, x_sd = central_and_sd(x_stack, stat)
        y_center, y_sd = central_and_sd(y_stack, stat)

        if show_sd and n_people > 1:
            ax.fill_between(phase_ref, x_center - x_sd, x_center + x_sd, color=X_COLOR, alpha=0.12)
            ax.fill_between(phase_ref, y_center - y_sd, y_center + y_sd, color=Y_COLOR, alpha=0.12)

        label_x = f"Delta X ({stat})"
        label_y = f"Delta Y ({stat})"
        ax.plot(phase_ref, x_center, color=X_COLOR, linewidth=linewidth_main, label=label_x)
        ax.plot(phase_ref, y_center, color=Y_COLOR, linewidth=linewidth_main, label=label_y)

        ax.axhline(0, color="black", linewidth=0.8, alpha=0.35)
        ax.set_title(LABELS[pt], fontsize=11)
        ax.set_xlim(0, 100)
        ax.set_ylim(ymin, ymax)
        ax.grid(True, alpha=0.18)
        ax.set_xlabel("Selected interval (%)")
        ax.set_ylabel("Change from neutral\n(eye-distance units)")
        if i == 0:
            ax.legend(loc="best", fontsize=8)

    for j in range(len(POINTS), 9):
        axes[j].set_visible(False)

    if title is None:
        descriptor = f"{syllable}: 7 lips/chin landmarks across time"
        extra = f" | n={n_people}" if n_people > 1 else f" | participant={next(iter(groups.keys()))}"
        title = descriptor + extra
    fig.suptitle(title, fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    if output is None:
        output = csv_path.with_name(csv_path.stem + "_7panel_time.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return output


def process_one(csv_path: Path, args, output_override: Path | None = None, title_override: str | None = None):
    groups, syllable = load_data(csv_path, args.participant)
    return plot_panel(
        groups=groups,
        syllable=syllable,
        csv_path=csv_path,
        output=output_override,
        title=title_override,
        stat=args.stat,
        show_sd=args.show_sd,
        alpha_trials=args.alpha_trials,
        linewidth_trials=args.linewidth_trials,
        linewidth_main=args.linewidth_main,
    )


def main():
    args = parse_args()

    if args.csv is not None:
        output = process_one(args.csv, args, args.output, args.title)
        print(f"Saved: {output}")
        return

    root = args.root
    syllables = resolve_syllables(args.syllable)
    saved = []
    missing = []

    for syl in syllables:
        csv_path = root / syl / args.filename
        if not csv_path.is_file():
            missing.append(str(csv_path))
            continue
        if args.outdir is None:
            out_path = csv_path.with_name("07_lips_chin_time_panel.png")
        else:
            out_path = args.outdir / syl / "07_lips_chin_time_panel.png"
        title = None
        out = process_one(csv_path, args, out_path, title)
        saved.append(out)
        print(f"Saved: {out}")

    if missing:
        print("\nMissing CSV files:")
        for m in missing:
            print(f"  - {m}")

    if not saved:
        raise SystemExit("No plots were generated. Check --root, --syllable, and --filename.")
    print(f"\nGenerated {len(saved)} plot(s).")


if __name__ == "__main__":
    main()
