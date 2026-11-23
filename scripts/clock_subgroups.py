"""Estimate paired changes in log loss by phase and mover rating."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def log_loss_per_move(y, probability):
    p = probability.to_numpy(dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid predicted probability")
    eps = np.finfo(float).eps
    p = np.clip(p, eps, 1 - eps)
    return np.where(y == 1, -np.log(p), -np.log1p(-p))


def summarize(group, rng, replicates):
    per_game = group.groupby("game_id", sort=True).agg(
        moves=("y", "size"), clock=("clock_change", "sum"),
        history=("history_change", "sum")
    )
    totals = per_game.to_numpy(dtype=float)
    observed = totals[:, 1:].sum(axis=0) / totals[:, 0].sum()
    draws = []
    for start in range(0, replicates, 64):
        indices = rng.integers(len(totals), size=(min(64, replicates - start), len(totals)))
        resampled = totals[indices].sum(axis=1)
        draws.extend(resampled[:, 1:] / resampled[:, [0]])
    low, high = np.quantile(draws, [0.025, 0.975], axis=0)
    return {
        "moves": len(group), "games": len(per_game), "events": int(group.y.sum()),
        "prevalence": group.y.mean(),
        "clock_delta": observed[0], "clock_lower": low[0], "clock_upper": high[0],
        "history_delta": observed[1], "history_lower": low[1], "history_upper": high[1],
    }


def compare(frame, replicates=1000, seed=42):
    required = ["game_id", "phase", "mover_rating", "y", "no_clock", "clocks", "full"]
    if frame.empty or frame[required].isna().any().any() or not frame.y.isin([0, 1]).all():
        raise ValueError("Expected complete paired predictions with binary labels")
    phases = ["opening", "middlegame", "endgame"]
    if not frame.phase.isin(phases).all():
        raise ValueError("Unknown phase in paired predictions")
    data = frame[required].copy()
    losses = [log_loss_per_move(data.y, data[c]) for c in ("no_clock", "clocks", "full")]
    data["clock_change"] = losses[1] - losses[0]
    data["history_change"] = losses[2] - losses[1]
    rating_groups = ["<1600", "1600-2199", "2200+"]
    data["rating"] = pd.cut(data.mover_rating, [-np.inf, 1600, 2200, np.inf],
                            right=False, labels=rating_groups)
    rng = np.random.default_rng(seed)
    rows = [{"dimension": "all", "group": "all", **summarize(data, rng, replicates)}]
    for field, groups in [("phase", phases), ("rating", rating_groups)]:
        for value in groups:
            subset = data[data[field] == value]
            if len(subset):
                rows.append({"dimension": field, "group": value,
                             **summarize(subset, rng, replicates)})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    results = compare(pd.read_csv(args.predictions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
