"""Refresh the report's numeric TeX tables from the verified comparison results."""

import csv
import json
import math
from pathlib import Path


REPORT = Path(__file__).resolve().parent
RESULTS = REPORT.parents[1] / "results" / "model_comparison" / "verified_180_0"
FAMILIES = {"hgb": "Histogram boosting", "xgb": "XGBoost", "logistic": "L2 logistic regression"}
FULL = "clocks_and_history"


def read_csv(name):
    with (RESULTS / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def indexed_metrics(name):
    rows = read_csv(name)
    return {
        (r["family"], r["inputs"], r["gate"].lower() == "true"): r for r in rows
    }


def number(row, field, digits):
    return f"{float(row[field]):.{digits}f}"


def interval(row):
    values = [number(row, key, 5) for key in ("delta_log_loss", "lower_95", "upper_95")]
    point, low, high = values
    return rf"\({point}\;[{low},\,{high}]\)"


def metric_or_dash(row, field, digits):
    value = row.get(field)
    if not value or not math.isfinite(float(value)):
        return "---"
    return number(row, field, digits)


def texrow(cells):
    return " & ".join(cells) + r" \\"


def main():
    selection = json.loads((RESULTS / "selection.json").read_text(encoding="utf-8"))
    family, rule = selection["family"], selection["gate"]
    development = indexed_metrics("validation_means.csv")
    final_week = indexed_metrics("published_test_metrics.csv")
    paired = {(r["split"], r["contrast"]): r for r in read_csv("paired_log_loss.csv")}
    selected = final_week[family, FULL, rule]
    cohort = selection["data"]

    configs = [("prevalence", "constant", False, "Training prevalence")]
    for model in ("logistic", "hgb", "xgb"):
        for constrained in (False, True):
            label = FAMILIES[model] + (" + zero-risk rule" if constrained else "")
            configs.append((model, FULL, constrained, label))
    performance = []
    for model, features, gate, label in configs:
        key = (model, features, gate)
        cv, test = development[key], final_week[key]
        values = [label, number(cv, "log_loss", 6), number(test, "log_loss", 6),
                  number(test, "brier", 5), number(test, "roc_auc", 4),
                  number(test, "average_precision", 4)]
        if key == (family, FULL, rule):
            values = [rf"\textbf{{{value}}}" for value in values]
        performance.append(texrow(values))

    increments = []
    for group, label, contrast in [
        ("no_time", "Position and ratings", None),
        ("clocks", "Add pre-move clocks", "clocks_minus_no_time"),
        (FULL, "Add recent time use", "history_minus_clocks"),
    ]:
        key = family, group, rule
        ci = interval(paired["published_test", contrast]) if contrast else "---"
        increments.append(texrow([label, number(development[key], "log_loss", 6),
                                  number(final_week[key], "log_loss", 6), ci]))

    robustness = []
    with (RESULTS.parent / "robustness.csv").open(encoding="utf-8-sig", newline="") as source:
        checks = {row["check"]: row for row in csv.DictReader(source)}
    for key, label in [
        ("primary_10pp", "Finite scores, 10 points"),
        ("identified_players_reference", "Identified-player reference"),
        ("player_disjoint_10pp", "Player-disjoint training, 10 points"),
        ("finite_5pp", "Finite scores, 5 points"),
        ("finite_15pp", "Finite scores, 15 points"),
        ("finite_150cp", "Finite scores, 150 centipawns"),
        ("finite_10pp_win_feature", r"Finite scores, \(W\) predictor"),
        ("mate_inclusive_10pp_win_feature", r"Mate scores included, \(W\) predictor"),
    ]:
        if key == "identified_players_reference" and key not in checks:
            continue
        row = checks[key]
        robustness.append(texrow([label, f"{int(row['train_moves']):,}",
                                  f"{int(row['test_moves']):,}",
                                  f"{100 * float(row['observed_test_rate']):.2f}",
                                  metric_or_dash(row, "log_loss", 5),
                                  metric_or_dash(row, "average_precision", 4)]))

    audit_file = REPORT.parents[1] / "data" / "processed" / "recovery_counts.json"
    audit = json.loads(audit_file.read_text(encoding="utf-8"))
    standard_starts = audit["unique_source_games"] - audit["excluded_not_rated_standard"]
    verified_control = standard_starts - audit["excluded_time_control_other_or_missing"]
    macros = {
        "RecoveredGames": f"{audit['unique_source_games']:,}",
        "StandardStartGames": f"{standard_starts:,}",
        "TimeControlGames": f"{verified_control:,}",
        "RebuiltMoves": f"{audit['rows']:,}",
        "VerifiedMoves": f"{cohort['moves']:,}",
        "VerifiedGames": f"{cohort['games']:,}",
        "VerifiedPrevalence": f"{100 * cohort['prevalence']:.2f}",
        "VerifiedTestMoves": f"{int(selected['valid_moves']):,}",
        "VerifiedTestGames": f"{int(selected['valid_games']):,}",
        "VerifiedTestRate": f"{100 * int(selected['positives']) / int(selected['valid_moves']):.2f}",
        "SelectedFamily": FAMILIES[family],
        "SelectedValidation": number(development[family, FULL, rule], "log_loss", 6),
        "SelectedTest": number(selected, "log_loss", 6),
        "BoardOnlyTest": number(final_week[family, "no_time", rule], "log_loss", 6),
        "ClocksOnlyTest": number(final_week[family, "clocks", rule], "log_loss", 6),
        "EligibleTest": f"{int(selected['rule_applicable']):,}",
        "GateDelta": number(paired["published_test", "selected_family_rule_minus_raw"], "delta_log_loss", 7),
        "BestAP": number(selected, "average_precision", 4),
        "BestAUC": number(selected, "roc_auc", 4),
        "PerformanceRows": "\n" + "\n".join(performance) + "\n",
        "IncrementRows": "\n" + "\n".join(increments) + "\n",
        "RobustRows": "\n" + "\n".join(robustness) + "\n",
    }
    result = "% Generated by refresh_tables.py from results/model_comparison/verified_180_0.\n"
    for name, value in macros.items():
        result += rf"\newcommand{{\{name}}}{{{value}}}" + "\n"
    (REPORT / "model_tables.tex").write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
