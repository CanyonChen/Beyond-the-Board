"""Compare a fixed HGB and XGBoost on identical chronological chess samples."""

import argparse
import hashlib
import os
from pathlib import Path
import platform

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '4'

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

import train_model as original
from comparison_features import (FEATURE_SETS, apply_rule, feature_spec, regroup_clock_history,
                                 rule_mask, score_frame)
from reproduce_baselines import DEFAULT_OUTPUT, FOLDS, ROOT, SCORES, TEST, archived_configs, split_rows, write_json


FULL = 'clocks_and_history'
TREE_FAMILIES = ('hgb', 'xgb')
XGB_CONFIG = dict(n_estimators=250, max_depth=5, learning_rate=.05, min_child_weight=5,
                  reg_lambda=10, subsample=1., colsample_bytree=1., max_bin=255,
                  tree_method='hist', objective='binary:logistic', eval_metric='logloss',
                  random_state=original.RANDOM_STATE, n_jobs=4)


def read_data(path, history):
    df = pd.read_csv(path, usecols=original.USE_COLS)
    source_rows = len(df)
    df = df.drop_duplicates().sort_values(['game_id', 'ply']).reset_index(drop=True)
    duplicate_rows = source_rows - len(df)
    if df.duplicated(['game_id', 'ply']).any():
        raise ValueError('Conflicting source rows for one game/ply.')
    if history == 'regroup-clock':
        df = regroup_clock_history(df)
    to_keep = (df['y'].isin([0, 1]) & df['ply'].gt(0) & np.isfinite(df['pre_move_eval_cp']))
    df = df.loc[to_keep].reset_index(drop=True)
    df['y'] = df['y'].astype('int8')
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    data = dict(source=path.name, sha256=digest, history=history, source_rows=source_rows,
                identical_duplicates=duplicate_rows, moves=len(df), games=int(df.game_id.nunique()),
                positives=int(df.y.sum()), prevalence=float(df.y.mean()))
    return df, data


def candidate(family, configs):
    if family == 'xgb':
        return XGBClassifier(**XGB_CONFIG)
    if family == 'hgb':
        return original.make_hgb(configs['hgb'])
    return original.make_logistic(configs['logistic'])


def evaluate(df, raw, fold, groups, configs, records, full_fit):
    train, valid = split_rows(df, fold)
    y_train = df.loc[train, 'y'].to_numpy()
    y = df.loc[valid, 'y'].to_numpy()
    mask = rule_mask(df.loc[valid, 'pre_move_eval_cp'])
    if y[mask].any():
        raise ValueError(f'A positive label violates the mathematical rule in {fold[0]}.')
    trains = int(train.sum())
    games = df.loc[valid, 'game_id'].to_numpy()
    n_games = int(pd.Series(games).nunique())
    returned = {}
    def record(family, level, gate, values):
        p = apply_rule(values, mask, gate)
        stats = original.probability_metrics(y, p)
        row = dict(split=fold[0], family=family, inputs=level, gate=gate,
                   train_moves=trains, valid_moves=len(y), valid_games=n_games,
                   positives=int(y.sum()), rule_applicable=int(mask.sum()), **stats)
        records.append(row)
        returned[(family, level, gate)] = p
        print(f"{fold[0]} {family} {level} gate={gate} LL={stats['log_loss']:.8f}", flush=True)
    if FULL in groups:
        record('prevalence', 'constant', False, np.full(len(y), y_train.mean()))
    for level, families in groups.items():
        transformer = feature_spec(raw.loc[train], level)
        x_train = transformer.transform(raw.loc[train])
        x_valid = transformer.transform(raw.loc[valid])
        for family in families:
            model = candidate(family, configs).fit(x_train, y_train)
            values = model.predict_proba(x_valid)[:, 1]
            for gate in (False, True):
                record(family, level, gate, values)
            if fold == TEST and level == FULL:
                full_fit[family] = (transformer, model)
    return returned


def average_validation(records):
    frame = pd.DataFrame(records)
    return (frame[frame.split.str.startswith('validation_')]
            .groupby(['family', 'inputs', 'gate'], as_index=False)[list(SCORES)].mean())


def losses(y, p):
    eps = np.finfo(np.float64).eps
    p = np.clip(np.asarray(p, dtype=np.float64), eps, 1-eps)
    return np.where(y == 1, -np.log(p), -np.log1p(-p))


def paired_interval(blocks, target, reference, n_boot=1000):
    """Resample entire games within each time window, giving windows equal weight."""
    rng = np.random.default_rng(original.RANDOM_STATE)
    draws = np.zeros(n_boot)
    points = []
    for y, ids, predictions in blocks:
        codes, unique_games = pd.factorize(np.asarray(ids))
        delta = losses(y, predictions[target]) - losses(y, predictions[reference])
        game_deltas = np.bincount(codes, weights=delta)
        game_sizes = np.bincount(codes)
        for k in range(n_boot):
            pick = rng.integers(len(unique_games), size=len(unique_games))
            draws[k] += game_deltas[pick].sum() / game_sizes[pick].sum()
        points.append(float(delta.mean()))
    low, high = np.percentile(draws / len(blocks), [2.5, 97.5])
    return dict(delta_log_loss=float(np.mean(points)), lower_95=float(low), upper_95=float(high),
                bootstrap_resamples=n_boot)


def compare(path, history, output, subgroup_file):
    output.mkdir(parents=True, exist_ok=True)
    df, data = read_data(path, history)
    raw = original.engineer_features(df)
    configs = archived_configs()
    full_groups = {FULL: ['logistic', *TREE_FAMILIES]}
    records, blocks, fitted = [], {}, {}
    for fold in FOLDS:
        p = evaluate(df, raw, fold, full_groups, configs, records, fitted)
        _, valid = split_rows(df, fold)
        blocks[fold[0]] = (df.loc[valid, 'y'].to_numpy(), df.loc[valid, 'game_id'].to_numpy(), p)
        pd.DataFrame(records).to_csv(output / 'fold_metrics.csv', index=False)
    means = average_validation(records)
    eligible = means[(means.inputs == FULL) & means.family.isin(TREE_FAMILIES)]
    winner = eligible.sort_values(['log_loss', 'family', 'gate']).iloc[0]
    family, gate = str(winner.family), bool(winner.gate)
    selection = dict(family=family, gate=gate, development_log_loss=float(winner.log_loss),
                     selection='Lowest equal-window mean log loss among two fixed tree families x rule on/off, using all features.',
                     data=data, hgb_config=configs['hgb'], logistic_config=configs['logistic'], xgb_config=XGB_CONFIG,
                     versions={'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                               'scipy': scipy.__version__, 'sklearn': sklearn.__version__,
                               'xgboost': xgboost.__version__, 'joblib': joblib.__version__, 'thread_limit': 4})
    # Write the choice before scoring the previously published final week.
    write_json(output / 'selection.json', selection)
    print(f'Frozen development choice: {family} gate={gate}', flush=True)
    partial = {level: [family] for level in FEATURE_SETS if level != FULL}
    for fold in FOLDS:
        predictions = evaluate(df, raw, fold, partial, configs, records, fitted)
        blocks[fold[0]][2].update(predictions)
        pd.DataFrame(records).to_csv(output / 'fold_metrics.csv', index=False)
    test_predictions = evaluate(df, raw, TEST, {**full_groups, **partial}, configs, records, fitted)
    _, test = split_rows(df, TEST)
    test_rows = df.loc[test].copy()
    blocks[TEST[0]] = (test_rows.y.to_numpy(), test_rows.game_id.to_numpy(), test_predictions)
    all_scores = pd.DataFrame(records)
    all_scores.to_csv(output / 'fold_metrics.csv', index=False)
    average_validation(records).to_csv(output / 'validation_means.csv', index=False)
    all_scores[all_scores.split == TEST[0]].to_csv(output / 'published_test_metrics.csv', index=False)
    subgroup_file.parent.mkdir(parents=True, exist_ok=True)
    subgroup = test_rows[['game_id', 'mover_rating', 'phase', 'y']].copy()
    for level, column in zip(FEATURE_SETS, ['no_clock', 'clocks', 'full']):
        subgroup[column] = test_predictions[(family, level, gate)]
    subgroup.to_csv(subgroup_file, index=False)
    # Quantile groups may merge when the deterministic rule yields many exact zeros.
    bins = pd.qcut(subgroup['full'], q=10, duplicates='drop')
    calibration = (subgroup.groupby(bins, observed=True).agg(moves=('y', 'size'),
                   predicted_probability=('full', 'mean'), observed_rate=('y', 'mean'),
                   min_probability=('full', 'min'), max_probability=('full', 'max')).reset_index(drop=True))
    calibration.to_csv(output / 'selected_calibration.csv', index=False)
    comparisons = {
        'xgb_minus_hgb_ungated': (('xgb', FULL, False), ('hgb', FULL, False)),
        'xgb_minus_hgb_with_rule': (('xgb', FULL, True), ('hgb', FULL, True)),
        'selected_family_rule_minus_raw': ((family, FULL, True), (family, FULL, False)),
        'selected_minus_logistic': ((family, FULL, gate), ('logistic', FULL, gate)),
        'selected_minus_prevalence': ((family, FULL, gate), ('prevalence', 'constant', False)),
        'clocks_minus_no_time': ((family, 'clocks', gate), (family, 'no_time', gate)),
        'history_minus_clocks': ((family, FULL, gate), (family, 'clocks', gate)),
        'full_minus_no_time': ((family, FULL, gate), (family, 'no_time', gate)),
    }
    intervals = []
    for split, collections in [('development_equal_windows', [blocks[f[0]] for f in FOLDS]),
                               (TEST[0], [blocks[TEST[0]]])]:
        for name, (target, reference) in comparisons.items():
            intervals.append(dict(split=split, contrast=name, **paired_interval(collections, target, reference)))
    pd.DataFrame(intervals).to_csv(output / 'paired_log_loss.csv', index=False)
    transformer, model = fitted[family]
    bundle = dict(features=transformer, model=model, family=family, rule=gate, history=history,
                  input_group=FULL, training_dates=['2026-09-01', '2026-09-23'], data_sha256=data['sha256'])
    bundle_path = output / 'selected_model.joblib'
    joblib.dump(bundle, bundle_path, compress=3)
    # Exercise production scoring after serialisation against recorded final-week probabilities.
    game = str(test_rows.iloc[0].game_id)
    source_parts = (part[part.game_id == game] for part in pd.read_csv(path, chunksize=100_000, usecols=original.USE_COLS))
    source = pd.concat(source_parts).drop_duplicates(['game_id', 'ply'])
    check = score_frame(source.drop(columns='y'), joblib.load(bundle_path))
    expected = test_rows[['game_id', 'ply']].copy()
    expected['expected'] = test_predictions[(family, FULL, gate)]
    checked = check.merge(expected[expected.game_id == game], on=['game_id', 'ply'], validate='one_to_one')
    if checked.empty or not np.allclose(checked.blunder_probability, checked.expected, rtol=0, atol=1e-10):
        raise AssertionError('Saved-model inference failed to reproduce final-week probabilities.')
    write_json(output / 'run_summary.json', dict(selection=selection, inference_check_rows=len(checked),
               max_inference_difference=float((checked.blunder_probability - checked.expected).abs().max()),
               test_interpretation='Supplementary retest. This calendar week was already reported in the repository.',
               ablation='Only the development-selected tree family is refitted with reduced feature sets. The gate is held fixed across feature groups.',
               paired_intervals='Paired whole-game percentile bootstrap. Development windows have equal weight; repeated players may induce extra dependence.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--history', choices=['provided', 'regroup-clock'], required=True,
                        help='Use provided own-side history for verified data, or reconstruct clock changes in the legacy archive.')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT / 'verified_180_0')
    parser.add_argument('--subgroup-output', type=Path, default=ROOT / 'tmp' / 'clock_predictions.csv.gz')
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        compare(args.input, args.history, args.output, args.subgroup_output)
