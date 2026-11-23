"""Recheck the submitted evaluation from the verified data and saved model.

Run from the repository root with the environment recorded in selection.json.
Outputs go to a separate directory so the published experiment remains intact.
"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import scipy
import xgboost
from threadpoolctl import threadpool_limits

import train_model as original
from check_robustness import run as run_robustness
from clock_subgroups import compare as compare_subgroups
from compare_models import (FULL, average_validation, candidate, paired_interval,
                            read_data)
from comparison_features import apply_rule, feature_spec, rule_mask, score_frame
from reproduce_baselines import FOLDS, ROOT, SCORES, TEST, archived_configs, split_rows, write_json


PUBLISHED = ROOT / 'results/model_comparison/verified_180_0'


def compare_numbers(actual, expected, columns, tolerance=1e-10):
    difference = np.abs(actual[columns].to_numpy(dtype=float)
                        - expected[columns].to_numpy(dtype=float))
    maximum = float(difference.max())
    if not np.isfinite(difference).all() or maximum > tolerance:
        raise AssertionError(f'Review differs from published values by {maximum:g}')
    return maximum


def review(output):
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'data/processed/moves_verified.csv.gz'
    decision = json.loads((PUBLISHED / 'selection.json').read_text(encoding='utf-8'))
    df, counts = read_data(source, 'provided')
    if counts != decision['data']:
        raise AssertionError('The verified cohort or input hash changed')
    full_source = pd.read_csv(source)
    finite = full_source.y.isin([0, 1]) & full_source.ply.gt(0)
    expected_labels = (full_source.pre_move_win_pct - full_source.post_move_win_pct).ge(10)
    if not np.array_equal(full_source.loc[finite, 'y'], expected_labels.loc[finite]):
        raise AssertionError('Stored labels disagree with the ten-point definition')
    impossible = rule_mask(df.pre_move_eval_cp)
    if df.loc[impossible, 'y'].any():
        raise AssertionError('A primary label violates the zero-risk rule')
    for fold in [*FOLDS, TEST]:
        split_rows(df, fold)  # Also rejects games crossing the train/evaluation boundary.

    keys = ['family', 'inputs', 'gate']
    folds = pd.read_csv(PUBLISHED / 'fold_metrics.csv')
    means = average_validation(folds.to_dict('records')).set_index(keys).sort_index()
    recorded_means = pd.read_csv(PUBLISHED / 'validation_means.csv').set_index(keys).sort_index()
    validation_gap = compare_numbers(means, recorded_means, list(SCORES))
    eligible = means.reset_index().query("family in ['hgb', 'xgb'] and inputs == @FULL")
    winner = eligible.sort_values(['log_loss', 'family', 'gate']).iloc[0]
    if (winner.family, bool(winner.gate)) != (decision['family'], decision['gate']):
        raise AssertionError('The recorded model choice disagrees with validation')

    train, test = split_rows(df, TEST)
    test_rows = df.loc[test].reset_index(drop=True)
    y = test_rows.y.to_numpy()
    raw = original.engineer_features(df)
    bundle = joblib.load(PUBLISHED / 'selected_model.joblib')
    if bundle['data_sha256'] != counts['sha256']:
        raise AssertionError('Saved model uses a different dataset')
    full = score_frame(test_rows.drop(columns='y'), bundle)
    if not full.score_status.eq('scored').all():
        raise AssertionError('Eligible evaluation moves could not be scored')
    predictions = {'full': full.blunder_probability.to_numpy()}
    records = []
    configs = archived_configs()
    for level, column in [('no_time', 'no_clock'), ('clocks', 'clocks')]:
        transformer = feature_spec(raw.loc[train], level)
        model = candidate(decision['family'], configs).fit(
            transformer.transform(raw.loc[train]), df.loc[train, 'y'])
        values = model.predict_proba(transformer.transform(raw.loc[test]))[:, 1]
        predictions[column] = apply_rule(values, rule_mask(test_rows.pre_move_eval_cp), decision['gate'])
        print(f'Refitted {level}', flush=True)
    for level, column in [('no_time', 'no_clock'), ('clocks', 'clocks'), (FULL, 'full')]:
        records.append(dict(inputs=level, **original.probability_metrics(y, predictions[column])))
    metrics = pd.DataFrame(records).set_index('inputs').sort_index()
    published = pd.read_csv(PUBLISHED / 'published_test_metrics.csv')
    expected = published[(published.family == decision['family'])
                         & (published.gate == decision['gate'])].set_index('inputs').sort_index()
    metric_gap = compare_numbers(metrics, expected, list(SCORES))
    metrics.to_csv(output / 'recomputed_metrics.csv')

    paired = test_rows[['game_id', 'ply', 'mover_rating', 'phase', 'y']].copy()
    for column, values in predictions.items():
        paired[column] = values
    bins = pd.qcut(paired.full, q=10, duplicates='drop')
    calibration = paired.groupby(bins, observed=True).agg(
        moves=('y', 'size'), predicted_probability=('full', 'mean'),
        observed_rate=('y', 'mean'), min_probability=('full', 'min'),
        max_probability=('full', 'max')).reset_index(drop=True)
    expected_calibration = pd.read_csv(PUBLISHED / 'selected_calibration.csv')
    calibration_gap = compare_numbers(calibration, expected_calibration, list(calibration.columns))
    calibration.to_csv(output / 'recomputed_calibration.csv', index=False)
    intervals = []
    blocks = [(y, paired.game_id.to_numpy(), predictions)]
    for contrast, target, reference in [
        ('clocks_minus_no_time', 'clocks', 'no_clock'),
        ('history_minus_clocks', 'full', 'clocks'),
        ('full_minus_no_time', 'full', 'no_clock'),
    ]:
        intervals.append(dict(contrast=contrast, **paired_interval(blocks, target, reference)))
    intervals = pd.DataFrame(intervals).set_index('contrast').sort_index()
    expected_intervals = pd.read_csv(PUBLISHED / 'paired_log_loss.csv')
    expected_intervals = expected_intervals[expected_intervals.split == TEST[0]].set_index('contrast')
    interval_gap = compare_numbers(intervals, expected_intervals.loc[intervals.index],
                                   ['delta_log_loss', 'lower_95', 'upper_95'])
    intervals.to_csv(output / 'recomputed_paired_intervals.csv')
    subgroups = compare_subgroups(paired).set_index(['dimension', 'group']).sort_index()
    expected_subgroups = pd.read_csv(ROOT / 'results/model_comparison/clock_subgroups.csv')
    expected_subgroups = expected_subgroups.set_index(['dimension', 'group']).sort_index()
    subgroup_gap = compare_numbers(subgroups, expected_subgroups, list(subgroups.columns))
    subgroups.to_csv(output / 'recomputed_subgroups.csv')

    robustness = run_robustness(source, PUBLISHED / 'selection.json').set_index('check').sort_index()
    expected_robustness = pd.read_csv(ROOT / 'results/model_comparison/robustness.csv')
    expected_robustness = expected_robustness.set_index('check').sort_index()
    robustness_columns = [*SCORES, 'train_games', 'train_moves', 'test_games', 'test_moves',
                          'train_events', 'test_events', 'shared_players']
    robustness_gap = compare_numbers(robustness, expected_robustness, robustness_columns)
    robustness.to_csv(output / 'recomputed_robustness.csv')

    manifest = json.loads((ROOT / 'results/model_comparison/report_figures/manifest.json')
                          .read_text(encoding='utf-8'))
    checked_sources = {}
    for figure in manifest['figures'].values():
        for name, digest in figure['sources'].items():
            content = (ROOT / name).read_bytes()
            actual = hashlib.sha256(content).hexdigest()
            if actual != digest:
                raise AssertionError(f'Figure source hash changed for {name}')
            checked_sources[name] = actual

    absolute_gap = np.abs(calibration.predicted_probability - calibration.observed_rate)
    weighted_gap = float(np.average(absolute_gap, weights=calibration.moves))
    baseline = float(metrics.loc['no_time', 'log_loss'])
    clock_gain = baseline - float(metrics.loc['clocks', 'log_loss'])
    total_gain = baseline - float(metrics.loc[FULL, 'log_loss'])
    disjoint = robustness.loc['player_disjoint_10pp']
    summary = dict(
        data=counts,
        environment=dict(python=platform.python_version(), numpy=np.__version__,
                         pandas=pd.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__,
                         xgboost=xgboost.__version__, joblib=joblib.__version__, thread_limit=4),
        checks=dict(labels_recomputed=int(finite.sum()), rule_applicable=int(impossible.sum()),
                    validation_review='Recomputed means and checked game separation; validation models were not refitted.',
                    validation_mean_max_difference=validation_gap,
                    final_week_metric_max_difference=metric_gap,
                    calibration_max_difference=calibration_gap,
                    paired_interval_max_difference=interval_gap,
                    subgroup_max_difference=subgroup_gap,
                    robustness_max_difference=robustness_gap,
                    figure_source_hashes=checked_sources),
        interpretation=dict(
            relative_log_loss_reduction_pct=100 * total_gain / baseline,
            starting_clock_share_of_reduction_pct=100 * clock_gain / total_gain,
            weighted_decile_calibration_gap_pp=100 * weighted_gap,
            largest_decile_calibration_gap_pp=100 * float(absolute_gap.max()),
            highest_risk_decile_moves=int(calibration.iloc[-1].moves),
            highest_risk_decile_event_rate_pct=100 * float(calibration.iloc[-1].observed_rate),
            disjoint_training_move_retention_pct=100 * float(disjoint.train_moves) / int(train.sum()),
            disjoint_shared_players=int(disjoint.shared_players),
            evaluation='Reused September 24-30 period; no new independent test.',
            calibration='Descriptive risk groups from the same evaluation period.',
            uncertainty='Whole-game bootstrap; cross-game player dependence remains.',
            disjoint='Training amount and player composition both change.'))
    write_json(output / 'review_summary.json', summary)
    print(json.dumps(summary['checks'], indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'results/model_comparison/review_2026_11_23')
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        review(args.output)
