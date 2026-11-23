"""Estimate model-standardised time profiles for the source-verified cohort."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

import train_model as original
from compare_models import FULL, candidate, read_data
from comparison_features import apply_rule, feature_spec, rule_mask
from reproduce_baselines import TEST, archived_configs, split_rows


RATINGS = ["<1600", "1600–2199", "2200+"]
PHASES = ["opening", "middlegame", "endgame"]


def profiles(path):
    data, _ = read_data(path, "provided")
    train, test = split_rows(data, TEST)
    raw = original.engineer_features(data.loc[train])
    design = feature_spec(raw, FULL)
    model = candidate("logistic", archived_configs()).fit(design.transform(raw), data.loc[train, "y"])
    frame = data.loc[test].copy()
    frame["rating_band"] = pd.cut(frame.mover_rating, [-np.inf, 1600, 2200, np.inf],
                                  right=False, labels=RATINGS)
    rows = []
    for (phase, rating), stratum in frame.groupby(["phase", "rating_band"], observed=True):
        mask = rule_mask(stratum.pre_move_eval_cp)
        for quantile in [0.10, 0.25, 0.50, 0.75, 0.90]:
            clock = float(stratum.clk_mover.quantile(quantile))
            adjusted = original.engineer_features(stratum.assign(clk_mover=clock))
            probabilities = model.predict_proba(design.transform(adjusted))[:, 1]
            rows.append(dict(phase=phase, rating_band=rating, clock_quantile=quantile,
                             seconds=clock, predicted_risk=apply_rule(probabilities, mask, True).mean(),
                             moves=len(stratum), games=stratum.game_id.nunique(),
                             observed_risk=stratum.y.mean()))
    return pd.DataFrame(rows)


def draw(table, path):
    fig, axes = plt.subplots(1, 3, sharex=True, sharey=True, figsize=(8.5, 2.8),
                             layout="constrained")
    series_styles = [
        ("#555D61", "o", ":"),
        ("#1D1D1F", "s", "--"),
        ("#BF165E", "^", "-"),
    ]
    for ax, phase in zip(axes, PHASES):
        for rating, (color, marker, line_style) in zip(RATINGS, series_styles):
            data = table[(table.phase == phase) & (table.rating_band == rating)]
            ax.plot(data.seconds, 100 * data.predicted_risk, color=color, marker=marker,
                    ms=3.5, linewidth=1.4, linestyle=line_style, label=rating)
        ax.set(title=phase.capitalize(), xlabel="Mover clock (seconds)", xlim=(-4, 185))
        ax.set_xticks([0, 60, 120, 180])
        ax.grid(axis="y", alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Predicted serious-error risk (%)")
    axes[0].set_ylim(bottom=0)
    axes[-1].legend(title="Mover rating", fontsize=7, title_fontsize=8)
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verified_moves", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=4):
        table = profiles(args.verified_moves)
    table.to_csv(args.output_directory / "adjusted_clock_curves.csv", index=False)
    draw(table, args.output_directory / "adjusted_clock_curves.pdf")
