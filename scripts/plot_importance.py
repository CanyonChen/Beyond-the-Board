# -*- coding: utf-8 -*-
"""
Permutation-importance figure for the blunder model.

Reads results/feature_importance.csv written by train_model.py and exports
results/feature_importance.pdf and .png. Paths are resolved from this file,
so the script can be run from any working directory.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR.parent / "results"
SOURCE = OUT_DIR / "feature_importance.csv"

LABELS = {
    "pre_move_eval_cp": "Pre-move evaluation",
    "log_clk_mover": "Own remaining time (log)",
    "log_clk_opp": "Opponent time (log)",
    "clk_ratio": "Clock share",
    "think_time_mean3": "Think time (mean of 3)",
    "prev_think_time": "Previous think time",
    "mover_rating": "Mover rating",
    "opp_rating": "Opponent rating",
    "rating_diff": "Rating difference",
    "move_no": "Move number",
    "material_adv_cp": "Material advantage",
    "nonpawn_material": "Non-pawn material",
    "legal_moves": "Legal moves",
    "in_check": "In check",
    "mover_is_white": "Mover is White",
    "phase": "Game phase",
    "think_missing": "History missing",
}


def main():
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found - run train_model.py first")

    frame = pd.read_csv(SOURCE)
    frame["Feature"] = frame["Feature"].map(lambda s: LABELS.get(s, s))
    frame = frame.sort_values("Importance", ascending=True)

    fig, ax = plt.subplots(figsize=(8, 0.36 * len(frame) + 1.2), dpi=300)
    ax.barh(frame["Feature"], frame["Importance"], color="#4c72b0",
            alpha=0.9, height=0.62)

    span = max(float(frame["Importance"].max()), 1e-9)
    for bar, value in zip(ax.patches, frame["Importance"]):
        ax.text(bar.get_width() + span * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.4f}", va="center", fontsize=8, color="#333333")

    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#cccccc")
    ax.yaxis.grid(False)
    ax.set_xlim(0, span * 1.18)
    ax.set_title("Permutation importance for blunder prediction", fontsize=11,
                 fontweight="bold", pad=12)
    ax.set_xlabel("Mean ROC-AUC drop on the locked test week", fontsize=9)
    ax.tick_params(axis="both", which="major", labelsize=9)

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "feature_importance.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "feature_importance.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'feature_importance.pdf'} and .png")


if __name__ == "__main__":
    main()
