"""Run the proposal's label and player-overlap checks on source-verified moves."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

import train_model as original
from compare_models import FULL, archived_configs, candidate
from comparison_features import apply_rule, feature_spec
from reproduce_baselines import TEST, split_rows


def memberships(frame):
    columns = ["white_player_id", "black_player_id"]
    if frame[columns].isna().any().any():
        raise ValueError("Player-disjoint check requires both player IDs for every eligible game")
    return set(frame[columns].to_numpy().ravel())


def run(source, decision):
    df = pd.read_csv(source).sort_values(["game_id", "ply"]).reset_index(drop=True)
    if df.duplicated(["game_id", "ply"]).any():
        raise ValueError("Source-verified input contains duplicate moves")
    with decision.open(encoding="utf-8") as f:
        choice = json.load(f)
    family, gate = choice["family"], choice["gate"]
    configs = archived_configs()
    train_days, test_days = split_rows(df, TEST)
    finite = df.y.isin([0, 1]) & df.ply.gt(0)
    available = df.y_mate_inclusive.isin([0, 1]) & df.ply.gt(0)
    known_players = df[["white_player_id", "black_player_id"]].notna().all(axis=1)
    test_players = memberships(df.loc[test_days & finite & known_players])
    has_test_player = df.white_player_id.isin(test_players) | df.black_player_id.isin(test_players)
    delta = df.pre_move_win_pct - df.post_move_win_pct
    rows = []
    specifications = [
        ("primary_10pp", finite, df.y, 10, False, False),
        ("player_disjoint_10pp", finite, df.y, 10, False, True),
        ("finite_5pp", finite, delta.ge(5), 5, False, False),
        ("finite_15pp", finite, delta.ge(15), 15, False, False),
        ("finite_150cp", finite, (df.pre_move_eval_cp-df.post_move_eval_cp).ge(150), None, False, False),
        ("finite_10pp_win_feature", finite, df.y, 10, True, False),
        ("mate_inclusive_10pp_win_feature", available, df.y_mate_inclusive, 10, True, False),
    ]
    if (finite & ~known_players).any():
        specifications.insert(1, ("identified_players_reference", finite & known_players,
                                  df.y, 10, False, False))
    for name, usable, labels, bound, use_win_pct, disjoint in specifications:
        train = train_days & usable
        test = test_days & usable
        if disjoint:
            train &= known_players & ~has_test_player
            test &= known_players
        y_train = labels.loc[train].astype(int)
        y_test = labels.loc[test].astype(int)
        overlap = memberships(df.loc[train & known_players]) & memberships(df.loc[test & known_players])
        row = dict(check=name, family=family, rule=bool(gate and bound is not None),
                   train_games=df.loc[train, "game_id"].nunique(), train_moves=int(train.sum()),
                   test_games=df.loc[test, "game_id"].nunique(), test_moves=int(test.sum()),
                   train_events=int(y_train.sum()), test_events=int(y_test.sum()),
                   observed_test_rate=y_test.mean(), shared_players=len(overlap),
                   unknown_id_train_moves=int((train & ~known_players).sum()),
                   unknown_id_test_moves=int((test & ~known_players).sum()))
        if disjoint and overlap:
            raise AssertionError("Player separation failed")
        if y_train.nunique() < 2 or y_test.nunique() < 2:
            row["status"] = "Fewer than two classes after eligibility filters"
        else:
            a = original.engineer_features(df.loc[train])
            b = original.engineer_features(df.loc[test])
            if use_win_pct:
                # Reuse the same input column position and transformation on both cohorts.
                a["pre_move_eval_cp"] = df.loc[train, "pre_move_win_pct"]
                b["pre_move_eval_cp"] = df.loc[test, "pre_move_win_pct"]
            transformer = feature_spec(a, FULL)
            model = candidate(family, configs).fit(transformer.transform(a), y_train)
            probs = model.predict_proba(transformer.transform(b))[:, 1]
            if row["rule"]:
                impossible = df.loc[test, "pre_move_win_pct"].to_numpy() < bound
                if y_test.to_numpy()[impossible].any():
                    raise ValueError(f"Label violates its theoretical bound in {name}")
                probs = apply_rule(probs, impossible, True)
            row.update(original.probability_metrics(y_test, probs))
            row["status"] = "scored"
        rows.append(row)
        print(name, row["train_games"], row.get("log_loss"), flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verified_moves", type=Path)
    parser.add_argument("selected_config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        result = run(args.verified_moves, args.selected_config)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    result.to_csv(args.output, index=False)
