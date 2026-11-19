# -*- coding: utf-8 -*-
"""
Chess blunder prediction - pre-registered modelling pipeline.

Implements the protocol stated in the team proposal:

1. Locked final test set: games dated 24-30 September 2026.
2. Three expanding validation windows inside 1-23 September
   (train 1-8 / validate 9-13, train 1-13 / validate 14-18,
   train 1-18 / validate 19-23). Whole games stay in one set.
3. Imputation, scaling and spline fitting happen inside each training window.
4. Configuration chosen by mean validation log loss (at most 12 per model).
5. Refit the frozen configuration on days 1-23, evaluate on the final week once.
6. Natural class distribution (no class weights); boosting's random internal
   early stopping disabled.

Outputs (written to results/):
- metrics.json            every number quoted in the report
- selection.json          per-window validation log loss for each configuration
- calibration.pdf/.png    calibration plot on the locked test week
- reliability_bins.csv    calibration bins behind the plot
- feature_importance.csv  permutation importance (selected boosting model)
- eda_rates.csv/.pdf/.png blunder rate and counts by clock, rating and phase
- daily_counts.csv        games, moves and prevalence per UTC day
- final_models.joblib     fitted feature pipeline + models + thresholds

Not applicable to the curated move table (recorded in metrics.json):
- player-disjoint check: no player identifiers, whole-game grouping only.
- mate-inclusive sensitivity: the annotated sample holds finite engine
  evaluations only (no mate markers), so forced win/loss endpoints cannot
  be reconstructed.

Usage:
    python train_model.py            # full run
    python train_model.py --quick    # small smoke run on a game subset
"""
import json
import os
import sys
import time
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score,
                             brier_score_loss, f1_score, log_loss,
                             precision_recall_curve, precision_score,
                             recall_score, roc_auc_score)
from sklearn.preprocessing import SplineTransformer, StandardScaler

RANDOM_STATE = 42

# ---- protocol constants -------------------------------------------------
WINDOWS = ((1, 8, 9, 13), (1, 13, 14, 18), (1, 18, 19, 23))
FIT_DAYS = (1, 23)
TEST_DAYS = (24, 30)
LABEL_PP = 10.0
LABEL_PP_VARIANTS = (5.0, 15.0)
LABEL_CP_VARIANT = 150.0
W_CHESS = 0.00368208          # Lichess winning-chance mapping
N_BOOTSTRAP = 1000
PERM_SAMPLE = 50_000
PERM_REPEATS = 5
N_KNOTS = 4
SPLINE_DEGREE = 3
HGB_MAX_ITER = 250

BASE_DIR = Path(__file__).resolve().parent
DATA_NAME = "moves.csv.gz"
PHASES = ("opening", "middlegame", "endgame")

USE_COLS = [
    "game_id", "date", "fullmove", "ply", "mover_is_white",
    "clk_mover", "clk_opponent", "mover_rating", "opp_rating",
    "rating_diff", "prev_think_time", "think_time_mean3",
    "material_adv_cp", "nonpawn_material", "legal_moves", "in_check",
    "phase", "pre_move_eval_cp", "y",
]

SPLINE_BASE = ["log_clk_mover", "log_clk_opp", "mover_rating", "move_no"]
LINEAR_BASE = [
    "clk_ratio", "rating_diff", "opp_rating", "prev_think_time",
    "think_time_mean3", "think_missing", "material_adv_cp",
    "nonpawn_material", "legal_moves", "in_check", "mover_is_white",
    "pre_move_eval_cp",
]
CLOCK_SPLINE = ["log_clk_mover", "log_clk_opp"]
CLOCK_LINEAR = ["clk_ratio", "prev_think_time", "think_time_mean3",
                "think_missing"]
EVAL_LINEAR = ["pre_move_eval_cp"]

LR_CONFIGS = [
    {"name": "lr_C0.03", "C": 0.03},
    {"name": "lr_C0.1", "C": 0.1},
    {"name": "lr_C0.3", "C": 0.3},
    {"name": "lr_C1", "C": 1.0},
]

HGB_CONFIGS = [
    {"name": "leaves15_lr0.10_leaf100_l2_1", "max_leaf_nodes": 15,
     "learning_rate": 0.10, "min_samples_leaf": 100, "l2_regularization": 1.0},
    {"name": "leaves31_lr0.10_leaf50_l2_1", "max_leaf_nodes": 31,
     "learning_rate": 0.10, "min_samples_leaf": 50, "l2_regularization": 1.0},
    {"name": "leaves31_lr0.05_leaf50_l2_1", "max_leaf_nodes": 31,
     "learning_rate": 0.05, "min_samples_leaf": 50, "l2_regularization": 1.0},
    {"name": "leaves63_lr0.05_leaf50_l2_1", "max_leaf_nodes": 63,
     "learning_rate": 0.05, "min_samples_leaf": 50, "l2_regularization": 1.0},
    {"name": "leaves31_lr0.05_leaf100_l2_10", "max_leaf_nodes": 31,
     "learning_rate": 0.05, "min_samples_leaf": 100,
     "l2_regularization": 10.0},
]


# ==============================================================
# 1. Data
# ==============================================================
def resolve_data_path():
    """Locate moves.csv.gz: env override, script dir, data/, project root."""
    candidates = []
    env_path = os.environ.get("MOVES_CSV", "").strip()
    if env_path:
        candidates.append(Path(env_path))
    for base in (BASE_DIR, BASE_DIR / "data", BASE_DIR.parent,
                 BASE_DIR.parent / "data", BASE_DIR.parent.parent,
                 BASE_DIR.parent.parent / "data"):
        candidates.append(base / DATA_NAME)
    for path in candidates:
        if path.exists():
            return path
    tried = "\n  ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"moves.csv.gz not found, tried:\n  {tried}")


def winning_chance(cp):
    """Lichess winning-chance proxy in percentage points."""
    return 100.0 / (1.0 + np.exp(-W_CHESS * np.asarray(cp, dtype=np.float64)))


def load_data(quick=False):
    """Read the curated move table, drop duplicated rows, rebuild the label."""
    path = resolve_data_path()
    df = pd.read_csv(path, compression="gzip", usecols=USE_COLS)

    n_raw = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    n_duplicates = n_raw - len(df)

    # Sorted by game and ply so that adjacent evaluations pair up.
    df = df.sort_values(["game_id", "ply"], kind="stable").reset_index(drop=True)
    df["eval_after"] = -df.groupby("game_id")["pre_move_eval_cp"].shift(-1)
    df["drop_pp"] = (winning_chance(df["pre_move_eval_cp"])
                     - winning_chance(df["eval_after"]))

    checked = df["y"].notna() & df["drop_pp"].notna() & (df["ply"] > 0)
    rebuilt = (df.loc[checked, "drop_pp"] >= LABEL_PP).astype(int)
    agreement = float((rebuilt == df.loc[checked, "y"].astype(int)).mean())
    n_checked = int(checked.sum())

    df = df[df["y"].notna()].reset_index(drop=True)
    df["y"] = df["y"].astype(np.int8)
    df = df[(df["ply"] > 0)].reset_index(drop=True)

    if quick:
        rng = np.random.default_rng(RANDOM_STATE)
        keep = rng.choice(df["game_id"].unique(), size=1500, replace=False)
        df = df[df["game_id"].isin(keep)].reset_index(drop=True)

    info = {
        # file name and size only: keep personal absolute paths out of the repo
        "source_file": path.name,
        "source_bytes": int(path.stat().st_size),
        "rows_in_file": int(n_raw),
        "duplicate_rows_removed": int(n_duplicates),
        "rows_used": int(len(df)),
        "games_used": int(df["game_id"].nunique()),
        "positive_rate": float(df["y"].mean()),
        "date_min": str(df["date"].min()),
        "date_max": str(df["date"].max()),
        "label_rule": f"winning chance drops by >= {LABEL_PP:.0f} pp",
        "label_check_rows": n_checked,
        "label_check_agreement": agreement,
        "evaluation_handling": "finite engine evaluations only, no centipawn cap",
    }
    assert agreement >= 0.999, f"label reconstruction mismatch: {agreement:.4f}"
    return df, info


def engineer_features(df):
    """Model inputs; the engine evaluation is kept raw (no cap, no sentinel)."""
    out = pd.DataFrame(index=df.index)
    out["log_clk_mover"] = np.log1p(df["clk_mover"].clip(lower=0.0))
    out["log_clk_opp"] = np.log1p(df["clk_opponent"].clip(lower=0.0))
    out["mover_rating"] = df["mover_rating"].astype(np.float64)
    out["move_no"] = df["fullmove"].astype(np.float64)
    total_clock = df["clk_mover"] + df["clk_opponent"]
    out["clk_ratio"] = np.where(total_clock > 0,
                                df["clk_mover"] / total_clock, 0.5)
    out["rating_diff"] = df["rating_diff"].astype(np.float64)
    out["opp_rating"] = df["opp_rating"].astype(np.float64)
    out["think_missing"] = df["think_time_mean3"].isna().astype(np.float64)
    out["prev_think_time"] = df["prev_think_time"].fillna(0.0)
    out["think_time_mean3"] = df["think_time_mean3"].fillna(0.0)
    out["material_adv_cp"] = df["material_adv_cp"].astype(np.float64)
    out["nonpawn_material"] = df["nonpawn_material"].astype(np.float64)
    out["legal_moves"] = df["legal_moves"].astype(np.float64)
    out["in_check"] = df["in_check"].astype(np.float64)
    out["mover_is_white"] = df["mover_is_white"].astype(np.float64)
    out["pre_move_eval_cp"] = df["pre_move_eval_cp"].astype(np.float64)
    out["phase"] = df["phase"].fillna("unknown")
    return out


def drop_constant_columns(X, info):
    """Remove indicators with no variation in this sample."""
    dropped = [c for c in X.columns
               if c != "phase" and X[c].nunique(dropna=False) <= 1]
    if dropped:
        X = X.drop(columns=dropped)
    info["constant_columns_dropped"] = dropped
    return X


# ==============================================================
# 2. Feature pipeline (fitted inside each training window)
# ==============================================================
class BlunderFeatures(BaseEstimator, TransformerMixin):
    """Spline bases, standardised linear block, phase dummies, interactions.

    Every learned quantity (spline knots, means, standard deviations) is
    fitted on the training window only.
    """

    def __init__(self, spline_columns=None, linear_columns=None,
                 n_knots=N_KNOTS, degree=SPLINE_DEGREE,
                 use_interactions=True, clip=10.0):
        self.spline_columns = spline_columns
        self.linear_columns = linear_columns
        self.n_knots = n_knots
        self.degree = degree
        self.use_interactions = use_interactions
        self.clip = clip

    # -- helpers ---------------------------------------------------
    @staticmethod
    def _phase_matrix(X):
        values = X["phase"].to_numpy()
        return np.column_stack(
            [(values == p).astype(np.float64) for p in PHASES])

    def _linear_block(self, X):
        block = X[self.linear_columns_].to_numpy(np.float64)
        if not self.use_interactions:
            return block
        clock = X["log_clk_mover"].to_numpy(np.float64)
        rating = X["mover_rating"].to_numpy(np.float64)
        phase = self._phase_matrix(X)
        inter = np.column_stack(
            [clock * rating]
            + [clock * phase[:, i] for i in range(phase.shape[1])])
        return np.hstack([block, inter])

    # -- sklearn API -----------------------------------------------
    def fit(self, X, y=None):
        self.spline_columns_ = (
            list(self.spline_columns) if self.spline_columns is not None
            else [c for c in SPLINE_BASE if c in X.columns])
        self.linear_columns_ = (
            list(self.linear_columns) if self.linear_columns is not None
            else [c for c in LINEAR_BASE if c in X.columns])

        self.spline_transformers_ = []
        for column in self.spline_columns_:
            transformer = SplineTransformer(
                n_knots=self.n_knots, degree=self.degree, include_bias=False)
            transformer.fit(X[[column]].to_numpy(np.float64))
            self.spline_transformers_.append(transformer)
        self.scaler_ = StandardScaler().fit(self._linear_block(X))
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        parts = [transformer.transform(X[[column]].to_numpy(np.float64))
                 for transformer, column in
                 zip(self.spline_transformers_, self.spline_columns_)]
        parts.append(np.clip(self.scaler_.transform(self._linear_block(X)),
                             -self.clip, self.clip))
        parts.append(self._phase_matrix(X))
        return np.hstack(parts)


class FittedModel(BaseEstimator):
    """Inference wrapper (fitted feature pipeline + model) for permutation."""

    _estimator_type = "classifier"

    def __init__(self, features=None, model=None):
        self.features = features
        self.model = model
        self.classes_ = np.array([0, 1])

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(self.features.transform(X))

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def auc_scorer(estimator, X, y):
    """Explicit ROC-AUC scorer: the wrapper is not a native sklearn estimator."""
    return roc_auc_score(y, estimator.predict_proba(X)[:, 1])


# ==============================================================
# 3. Models
# ==============================================================
def make_logistic(config):
    """L2-regularised logistic regression on the natural class distribution."""
    # L2 is the default penalty; passing it explicitly is deprecated in sklearn 1.8+
    return LogisticRegression(C=config["C"], solver="lbfgs", max_iter=1000,
                              random_state=RANDOM_STATE)


def make_hgb(config, max_iter=HGB_MAX_ITER):
    """Histogram gradient boosting, internal early stopping disabled."""
    return HistGradientBoostingClassifier(
        max_iter=max_iter,
        max_leaf_nodes=config["max_leaf_nodes"],
        learning_rate=config["learning_rate"],
        min_samples_leaf=config["min_samples_leaf"],
        l2_regularization=config["l2_regularization"],
        early_stopping=False,
        random_state=RANDOM_STATE,
    )


def fit_family(family, config, Z, y, max_iter=HGB_MAX_ITER):
    model = (make_logistic(config) if family == "logistic"
             else make_hgb(config, max_iter=max_iter))
    model.fit(Z, y)
    return model


# ==============================================================
# 4. Metrics
# ==============================================================
def probability_metrics(y, probability):
    return {
        "log_loss": float(log_loss(y, probability, labels=[0, 1])),
        "brier": float(brier_score_loss(y, probability)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "mean_prediction": float(np.mean(probability)),
    }


def best_f1_threshold(y, probability):
    precision, recall, thresholds = precision_recall_curve(y, probability)
    f1 = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-12)
    return float(thresholds[int(np.argmax(np.nan_to_num(f1, nan=0.0)))])


def operating_point(y, probability, threshold):
    prediction = (probability >= threshold).astype(int)
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y, prediction)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "predicted_positive_rate": float(prediction.mean()),
    }


def fast_average_precision(y_true, score):
    """Same definition as average_precision_score, without sklearn overhead.

    Only used inside the bootstrap loop; reported point estimates still come
    from sklearn.metrics.average_precision_score.
    """
    order = np.argsort(-np.asarray(score), kind="stable")
    y_sorted = np.asarray(y_true)[order]
    cum_tp = np.cumsum(y_sorted)
    total_pos = cum_tp[-1]
    if total_pos == 0:
        return 0.0
    precision = cum_tp / np.arange(1, len(y_sorted) + 1)
    return float(np.sum(precision * y_sorted) / total_pos)


def paired_bootstrap(y, probability_ref, probability_alt, game_codes,
                     n_boot=N_BOOTSTRAP, seed=RANDOM_STATE):
    """Resample whole test games; 95% percentile CI for log loss and AP gaps."""
    rng = np.random.default_rng(seed)
    eps = 1e-12
    y = np.asarray(y, dtype=np.float64)

    # Rows grouped by game so a resample is a concatenation of game slices.
    order = np.argsort(game_codes, kind="stable")
    sorted_codes = np.asarray(game_codes)[order]
    n_games = int(sorted_codes.max()) + 1
    starts = np.searchsorted(sorted_codes, np.arange(n_games + 1))
    slices = [order[starts[g]:starts[g + 1]] for g in range(n_games)]

    # Log loss is an average of per-row losses, so game sums are enough.
    def row_losses(probability):
        p = np.clip(np.asarray(probability)[order], eps, 1.0 - eps)
        y_sorted = y[order]
        return -(y_sorted * np.log(p) + (1 - y_sorted) * np.log(1 - p))

    loss_ref = row_losses(probability_ref)
    loss_alt = row_losses(probability_alt)
    sum_ref = np.array([loss_ref[s].sum() for s in slices])
    sum_alt = np.array([loss_alt[s].sum() for s in slices])
    counts = np.array([len(s) for s in slices])

    delta_log_loss, delta_ap = [], []
    for _ in range(n_boot):
        pick = rng.integers(0, n_games, n_games)
        total = counts[pick].sum()
        delta_log_loss.append(float(sum_alt[pick].sum() / total
                                    - sum_ref[pick].sum() / total))
        idx = np.concatenate([slices[g] for g in pick])
        y_boot = y[idx]
        delta_ap.append(fast_average_precision(y_boot, np.asarray(probability_alt)[idx])
                        - fast_average_precision(y_boot, np.asarray(probability_ref)[idx]))

    delta_log_loss = np.asarray(delta_log_loss)
    delta_ap = np.asarray(delta_ap)
    return {
        "resampling": "whole test games, paired",
        "n_bootstrap": int(n_boot),
        "delta_log_loss": float(delta_log_loss.mean()),
        "delta_log_loss_ci95": [float(np.percentile(delta_log_loss, 2.5)),
                                float(np.percentile(delta_log_loss, 97.5))],
        "delta_average_precision": float(delta_ap.mean()),
        "delta_average_precision_ci95": [float(np.percentile(delta_ap, 2.5)),
                                         float(np.percentile(delta_ap, 97.5))],
    }


# ==============================================================
# 5. Protocol steps
# ==============================================================
def day_mask(dates, start, end):
    return (dates >= f"2026-09-{start:02d}") & (dates <= f"2026-09-{end:02d}")


def run_selection(raw, y, dates, configs_map, quick=False, max_iter=HGB_MAX_ITER):
    """Expanding-window selection; returns per-config validation results."""
    windows = WINDOWS[:1] if quick else WINDOWS
    results = {"logistic": [], "hgb": []}
    val_probabilities = {}

    for window_id, (tr_start, tr_end, va_start, va_end) in enumerate(windows,
                                                                     start=1):
        tr_mask = day_mask(dates, tr_start, tr_end)
        va_mask = day_mask(dates, va_start, va_end)
        X_tr, X_va = raw[tr_mask], raw[va_mask]
        y_tr, y_va = y[tr_mask], y[va_mask]

        started = time.perf_counter()
        features = BlunderFeatures().fit(X_tr)
        Z_tr = features.transform(X_tr)
        Z_va = features.transform(X_va)
        print(f"  window {window_id}: train {len(y_tr):,} / valid {len(y_va):,} "
              f"moves, {Z_tr.shape[1]} features "
              f"({time.perf_counter() - started:.1f}s prep)", flush=True)

        for family, configs in configs_map.items():
            for config in configs:
                started = time.perf_counter()
                model = fit_family(family, config, Z_tr, y_tr, max_iter=max_iter)
                probability = model.predict_proba(Z_va)[:, 1]
                val_probabilities[(window_id, family, config["name"])] = probability
                row = {
                    "window": window_id,
                    "family": family,
                    "name": config["name"],
                    "train_moves": int(len(y_tr)),
                    "valid_moves": int(len(y_va)),
                    "seconds": float(time.perf_counter() - started),
                }
                row.update(probability_metrics(y_va, probability))
                results[family].append(row)
                print(f"    {family:<8} {config['name']:<32} "
                      f"valid log loss={row['log_loss']:.5f}", flush=True)
    return results, val_probabilities


def select_configs(selection):
    """Pick the configuration with the lowest mean validation log loss."""
    chosen = {}
    for family, rows in selection.items():
        frame = pd.DataFrame(rows)
        mean_ll = frame.groupby("name")["log_loss"].mean().sort_values()
        best = mean_ll.index[0]
        best_rows = frame[frame["name"] == best]
        chosen[family] = {
            "name": str(best),
            "mean_valid_log_loss": float(mean_ll.iloc[0]),
            "per_window": [
                {"window": int(row.window),
                 "log_loss": float(row.log_loss),
                 "brier": float(row.brier),
                 "roc_auc": float(row.roc_auc),
                 "average_precision": float(row.average_precision)}
                for row in best_rows.itertuples()],
        }
    return chosen


def run_eda(df, out_dir):
    """Blunder rate and counts by clock band, rating band and phase."""
    frame = df.copy()
    frame["clock_band"] = pd.cut(
        frame["clk_mover"], bins=[-1, 10, 30, 60, 120, 181],
        labels=["0-10s", "10-30s", "30-60s", "60-120s", "120-180s"])
    frame["rating_band"] = pd.cut(
        frame["mover_rating"], bins=[0, 1200, 1500, 1800, 2100, 2400, 4000],
        labels=["<1200", "1200-1500", "1500-1800", "1800-2100",
                "2100-2400", "2400+"])

    rows = []
    for column in ("clock_band", "rating_band", "phase"):
        part = (frame.groupby(column, observed=True)["y"]
                .agg(moves="size", positive_rate="mean")
                .reset_index()
                .rename(columns={column: "band"}))
        part.insert(0, "dimension", column)
        rows.append(part)
    table = pd.concat(rows, ignore_index=True)
    table.to_csv(out_dir / "eda_rates.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), dpi=300)
    for ax, dimension in zip(axes, ("clock_band", "rating_band", "phase")):
        part = table[table["dimension"] == dimension]
        ax.bar(part["band"].astype(str), part["positive_rate"],
               color="#4c72b0", alpha=0.85)
        for x, (rate, moves) in enumerate(zip(part["positive_rate"],
                                              part["moves"])):
            ax.text(x, rate, f"{rate:.3f}\nn={moves:,}", ha="center",
                    va="bottom", fontsize=7)
        ax.set_title(dimension.replace("_", " ").title(), fontsize=10)
        ax.set_ylabel("Blunder rate")
        ax.tick_params(axis="x", labelsize=8, rotation=20)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "eda_rates.pdf", bbox_inches="tight")
    fig.savefig(out_dir / "eda_rates.png", bbox_inches="tight")
    plt.close(fig)


def plot_calibration(y, probabilities, out_dir):
    colors = {"logistic": "#dd8452", "hgb": "#4c72b0"}
    labels = {"logistic": "L2 logistic regression",
              "hgb": "Histogram gradient boosting"}
    fig, ax = plt.subplots(figsize=(5, 5), dpi=300)
    ax.plot([0, 1], [0, 1], linestyle="--", color="#999999", linewidth=1,
            label="Perfect calibration")

    rows = []
    for family, probability in probabilities.items():
        observed, predicted = calibration_curve(
            y, probability, n_bins=10, strategy="quantile")
        ax.plot(predicted, observed, marker="o", markersize=4,
                color=colors.get(family, "#55a868"), label=labels.get(family, family))
        rows += [{"model": family, "mean_predicted": float(p),
                  "observed_rate": float(o)} for p, o in zip(predicted, observed)]

    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed blunder rate")
    ax.set_title("Calibration on the locked test week", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "calibration.pdf", bbox_inches="tight")
    fig.savefig(out_dir / "calibration.png", bbox_inches="tight")
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out_dir / "reliability_bins.csv", index=False,
                              encoding="utf-8-sig")


# ==============================================================
# 6. Main
# ==============================================================
def main():
    quick = "--quick" in sys.argv
    out_dir = BASE_DIR.parent / ("results_quick" if quick else "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    max_iter = 60 if quick else HGB_MAX_ITER
    n_boot = 100 if quick else N_BOOTSTRAP
    configs_map = {
        "logistic": LR_CONFIGS[:2] if quick else LR_CONFIGS,
        "hgb": HGB_CONFIGS[:2] if quick else HGB_CONFIGS,
    }

    print("Loading data ...", flush=True)
    df, data_info = load_data(quick=quick)
    print(f"  {data_info['rows_used']:,} moves | "
          f"{data_info['games_used']:,} games | "
          f"positive rate={data_info['positive_rate']:.4f}", flush=True)
    print(f"  duplicate rows removed: {data_info['duplicate_rows_removed']:,} | "
          f"label check agreement: {data_info['label_check_agreement']:.4f}",
          flush=True)

    raw = engineer_features(df)
    raw = drop_constant_columns(raw, data_info)
    y = df["y"].to_numpy()
    dates = df["date"].to_numpy()

    (df.groupby("date")
     .agg(games=("game_id", "nunique"), moves=("y", "size"),
          positive_rate=("y", "mean"))
     .reset_index()
     .to_csv(out_dir / "daily_counts.csv", index=False, encoding="utf-8-sig"))

    if not quick:
        run_eda(df, out_dir)

    # ---- selection over the three expanding windows ----------------
    print("\nSelection over expanding validation windows ...", flush=True)
    selection, val_probabilities = run_selection(
        raw, y, dates, configs_map, quick=quick, max_iter=max_iter)
    chosen = select_configs(selection)
    for family, info in chosen.items():
        print(f"  selected {family}: {info['name']} "
              f"(mean valid log loss={info['mean_valid_log_loss']:.5f})",
              flush=True)
    with open(out_dir / "selection.json", "w", encoding="utf-8") as handle:
        json.dump({"rows": selection, "selected": chosen}, handle, indent=2)

    # ---- refit on days 1-23, evaluate once on the final week -------
    print("\nRefitting selected configurations on days 1-23 ...", flush=True)
    fit_mask = day_mask(dates, *FIT_DAYS)
    test_mask = day_mask(dates, *TEST_DAYS)
    X_fit, y_fit = raw[fit_mask], y[fit_mask]
    X_test, y_test = raw[test_mask], y[test_mask]
    print(f"  fit moves={len(y_fit):,} | test moves={len(y_test):,} | "
          f"test prevalence={y_test.mean():.4f}", flush=True)

    features_final = BlunderFeatures().fit(X_fit)
    Z_fit = features_final.transform(X_fit)
    Z_test = features_final.transform(X_test)

    config_by_family = {family: next(c for c in configs_map[family]
                                     if c["name"] == chosen[family]["name"])
                        for family in configs_map}
    models, test_probability = {}, {}
    for family, config in config_by_family.items():
        started = time.perf_counter()
        model = fit_family(family, config, Z_fit, y_fit, max_iter=max_iter)
        models[family] = model
        test_probability[family] = model.predict_proba(Z_test)[:, 1]
        print(f"  {family} refitted in {time.perf_counter() - started:.1f}s",
              flush=True)

    # Operating threshold from the last validation window.
    last_window = 1 if quick else len(WINDOWS)
    _, _, va_start, va_end = WINDOWS[last_window - 1]
    va_mask_sel = day_mask(dates, va_start, va_end)
    thresholds = {
        family: best_f1_threshold(
            y[va_mask_sel],
            val_probabilities[(last_window, family, config["name"])])
        for family, config in config_by_family.items()}

    # Prevalence benchmark = training-set error rate.
    prevalence = float(y_fit.mean())
    test_probability["prevalence_benchmark"] = np.full(len(y_test), prevalence)

    test_results = {}
    for name, probability in test_probability.items():
        entry = probability_metrics(y_test, probability)
        if name != "prevalence_benchmark":
            entry.update(operating_point(y_test, probability, thresholds[name]))
        entry["test_prevalence"] = float(y_test.mean())
        test_results[name] = entry

    print("\nTest week (24-30 Sep) performance", flush=True)
    for name, entry in test_results.items():
        print(f"  {name:<22} log loss={entry['log_loss']:.5f} "
              f"brier={entry['brier']:.5f} auc={entry['roc_auc']:.4f} "
              f"ap={entry['average_precision']:.4f}", flush=True)

    # ---- paired bootstrap over whole games ------------------------
    print("\nPaired bootstrap over whole test games ...", flush=True)
    codes = pd.factorize(df.loc[test_mask, "game_id"], sort=False)[0]
    bootstrap = {}
    if "logistic" in test_probability:
        bootstrap["hgb_minus_logistic"] = paired_bootstrap(
            y_test, test_probability["logistic"], test_probability["hgb"],
            codes, n_boot=n_boot)
    if not quick:
        bootstrap["hgb_minus_prevalence_benchmark"] = paired_bootstrap(
            y_test, test_probability["prevalence_benchmark"],
            test_probability["hgb"], codes, n_boot=n_boot)
    for name, entry in bootstrap.items():
        print(f"  {name:<38} dLogLoss={entry['delta_log_loss']:+.5f} "
              f"{entry['delta_log_loss_ci95']} | "
              f"dAP={entry['delta_average_precision']:+.4f}",
              flush=True)

    # ---- ablations ------------------------------------------------
    ablations = {}
    if not quick:
        print("\nAblations ...", flush=True)
        specs = {
            "without_clock_and_think_time": dict(
                spline_columns=[c for c in SPLINE_BASE
                                if c not in CLOCK_SPLINE],
                linear_columns=[c for c in LINEAR_BASE
                                if c in raw.columns and c not in CLOCK_LINEAR],
                use_interactions=False),
            "without_pre_move_evaluation": dict(
                spline_columns=[c for c in SPLINE_BASE if c in raw.columns],
                linear_columns=[c for c in LINEAR_BASE
                                if c in raw.columns and c not in EVAL_LINEAR],
                use_interactions=True),
        }
        for label, spec in specs.items():
            features_ab = BlunderFeatures(**spec).fit(X_fit)
            Z_ab_fit = features_ab.transform(X_fit)
            Z_ab_test = features_ab.transform(X_test)
            entry = {"features": int(Z_ab_fit.shape[1])}
            for family, config in config_by_family.items():
                model = fit_family(family, config, Z_ab_fit, y_fit,
                                   max_iter=max_iter)
                probability = model.predict_proba(Z_ab_test)[:, 1]
                entry[family] = probability_metrics(y_test, probability)
                entry[family]["delta_log_loss_vs_full"] = float(
                    entry[family]["log_loss"]
                    - test_results[family]["log_loss"])
                entry[family]["delta_average_precision_vs_full"] = float(
                    entry[family]["average_precision"]
                    - test_results[family]["average_precision"])
                print(f"  {label:<30} {family:<8} "
                      f"log loss={entry[family]['log_loss']:.5f}", flush=True)
            ablations[label] = entry

    # ---- label sensitivity ----------------------------------------
    sensitivity = {}
    if not quick:
        print("\nLabel sensitivity ...", flush=True)
        has_pair = df["drop_pp"].notna().to_numpy() & (df["ply"] > 0).to_numpy()
        variants = {f"{pp:.0f}pp": (df["drop_pp"] >= pp).to_numpy()
                    for pp in LABEL_PP_VARIANTS}
        variants[f"{LABEL_CP_VARIANT:.0f}cp"] = (
            (df["eval_after"] - df["pre_move_eval_cp"])
            <= -LABEL_CP_VARIANT).to_numpy()

        for label, target in variants.items():
            usable = has_pair & ~pd.isna(target)
            target = target.astype(np.int8)
            fit_m = fit_mask & usable
            test_m = test_mask & usable
            entry = {"moves": int(usable.sum()),
                     "positive_rate": float(target[usable].mean())}
            features_ls = BlunderFeatures().fit(raw[fit_m])
            Z_ls_fit = features_ls.transform(raw[fit_m])
            Z_ls_test = features_ls.transform(raw[test_m])
            for family, config in config_by_family.items():
                model = fit_family(family, config, Z_ls_fit, target[fit_m],
                                   max_iter=max_iter)
                probability = model.predict_proba(Z_ls_test)[:, 1]
                entry[family] = probability_metrics(
                    target[test_m], probability)
            sensitivity[label] = entry
            print(f"  label {label:<6} prevalence={entry['positive_rate']:.4f} "
                  f"| hgb log loss={entry['hgb']['log_loss']:.5f}", flush=True)

    # ---- figures and importance -----------------------------------
    plot_calibration(y_test, {k: v for k, v in test_probability.items()
                              if k != "prevalence_benchmark"}, out_dir)

    print("\nPermutation importance (selected boosting model) ...", flush=True)
    rng = np.random.default_rng(RANDOM_STATE)
    sample = rng.choice(len(X_test), size=min(PERM_SAMPLE, len(X_test)),
                        replace=False)
    wrapper = FittedModel(features=features_final, model=models["hgb"])
    perm = permutation_importance(
        wrapper, X_test.iloc[sample], y_test[sample], scoring=auc_scorer,
        n_repeats=PERM_REPEATS, random_state=RANDOM_STATE, n_jobs=-1)
    (pd.Series(perm.importances_mean, index=X_test.columns)
     .sort_values(ascending=False)
     .rename("Importance").rename_axis("Feature")
     .to_csv(out_dir / "feature_importance.csv", encoding="utf-8-sig"))

    # ---- save -----------------------------------------------------
    metrics = {
        "protocol": {
            "windows": [{"train_days": f"1-{tr_end}",
                         "valid_days": f"{va_start}-{va_end}"}
                        for _, tr_end, va_start, va_end in WINDOWS],
            "fit_days": f"{FIT_DAYS[0]}-{FIT_DAYS[1]}",
            "test_days": f"{TEST_DAYS[0]}-{TEST_DAYS[1]}",
            "selection_rule": "minimum mean validation log loss",
            "class_weights": "none (natural distribution)",
            "hgb_early_stopping": False,
            "hgb_max_iter": max_iter,
            "configs_per_model": {k: len(v) for k, v in configs_map.items()},
            "features": {"spline": SPLINE_BASE, "linear": LINEAR_BASE,
                         "interactions": ["clk_x_rating", "clk_x_phase_*"]},
        },
        "data": data_info,
        "selection": {"selected": chosen, "rows": selection},
        "test": test_results,
        "bootstrap": bootstrap,
        "ablations": ablations,
        "label_sensitivity": sensitivity,
        "not_applicable": {
            "player_disjoint_check": "no player identifiers in the move table",
            "mate_inclusive_sensitivity":
                "no mate evaluations in the annotated sample",
        },
    }
    with open(out_dir / "metrics.json", "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)

    # Pickle the custom classes under a stable module name so that predict.py
    # can unpickle the bundle. Running this file as a script gives __name__ ==
    # "__main__", so alias that module under its file stem first, otherwise
    # pickle cannot resolve the class.
    module_name = Path(__file__).stem
    sys.modules.setdefault(module_name, sys.modules[__name__])
    BlunderFeatures.__module__ = module_name
    FittedModel.__module__ = module_name

    bundle = {
        "feature_pipeline": features_final,
        "models": models,
        "configs": config_by_family,
        "thresholds": thresholds,
        "raw_columns": X_fit.columns.tolist(),
        "delivery_model": "hgb",
    }
    # Write to a temporary file first: a failed dump must not truncate the
    # previously good bundle.
    bundle_path = out_dir / "final_models.joblib"
    tmp_path = bundle_path.with_name(bundle_path.name + ".tmp")
    joblib.dump(bundle, tmp_path)
    tmp_path.replace(bundle_path)

    print(f"\nSaved results to {out_dir}", flush=True)


if __name__ == "__main__":
    main()
