"""Refit the archived prevalence, logistic and HGB models without changing the archive."""

import argparse
import json
import os
from pathlib import Path
import platform

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '4'

import numpy as np
import pandas as pd
import scipy
import sklearn
from threadpoolctl import threadpool_limits

import train_model as original


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'results' / 'model_comparison'
FOLDS = [(f'validation_{i}', *days) for i, days in enumerate(original.WINDOWS, 1)]
TEST = ('published_test', *original.FIT_DAYS, *original.TEST_DAYS)
SCORES = ('log_loss', 'average_precision', 'roc_auc', 'brier', 'mean_prediction')


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def split_rows(df, fold):
    _, start, end, valid_start, valid_end = fold
    dates = df['date']
    train = original.day_mask(dates, start, end).to_numpy()
    valid = original.day_mask(dates, valid_start, valid_end).to_numpy()
    train_games = df.loc[train, 'game_id'].unique()
    valid_games = df.loc[valid, 'game_id'].unique()
    if np.intersect1d(train_games, valid_games).size:
        raise ValueError(f'Overlapping games in {fold[0]}')
    return train, valid


def archived_configs():
    selection = json.loads((ROOT / 'results' / 'selection.json').read_text(encoding='utf-8'))
    configs = {}
    for family, candidates in [('logistic', original.LR_CONFIGS), ('hgb', original.HGB_CONFIGS)]:
        name = selection['selected'][family]['name']
        configs[family] = next(c for c in candidates if c['name'] == name)
    return configs


def reproduce(output):
    output.mkdir(parents=True, exist_ok=True)
    df, sample = original.load_data()
    raw = original.drop_constant_columns(original.engineer_features(df), sample)
    y = df['y'].to_numpy()
    configs = archived_configs()
    selection = json.loads((ROOT / 'results' / 'selection.json').read_text(encoding='utf-8'))
    archive = json.loads((ROOT / 'results' / 'metrics.json').read_text(encoding='utf-8'))
    records = []
    for index, fold in enumerate([*FOLDS, TEST]):
        train, valid = split_rows(df, fold)
        transformer = original.BlunderFeatures().fit(raw.loc[train])
        x_train = transformer.transform(raw.loc[train])
        x_valid = transformer.transform(raw.loc[valid])
        reference = {}
        if fold == TEST:
            reference = archive['test']
        else:
            for family in configs:
                reference[family] = selection['selected'][family]['per_window'][index]
        for family in ['prevalence_benchmark', *configs]:
            if family == 'prevalence_benchmark':
                p = np.full(int(valid.sum()), y[train].mean())
            else:
                model = original.fit_family(family, configs[family], x_train, y[train])
                p = model.predict_proba(x_valid)[:, 1]
            stats = original.probability_metrics(y[valid], p)
            row = dict(split=fold[0], family=family, train_moves=int(train.sum()),
                       valid_moves=int(valid.sum()), **stats)
            if family in reference:
                row['archived_log_loss'] = reference[family]['log_loss']
                row['log_loss_minus_archive'] = stats['log_loss'] - reference[family]['log_loss']
            records.append(row)
            print(f"{fold[0]} / {family}: {stats['log_loss']:.8f}", flush=True)
        pd.DataFrame(records).to_csv(output / 'baseline_folds.csv', index=False)
    baseline = pd.DataFrame(records)
    means = baseline[baseline.split.str.startswith('validation')].groupby('family')[list(SCORES)].mean()
    means.to_csv(output / 'baseline_validation_means.csv')
    max_gap = baseline.groupby('family').log_loss_minus_archive.apply(lambda x: x.abs().max()).to_dict()
    payload = dict(data=sample, selected_configs=configs, sklearn=sklearn.__version__,
                   environment={'python': platform.python_version(), 'numpy': np.__version__,
                                'pandas': pd.__version__, 'scipy': scipy.__version__,
                                'sklearn': sklearn.__version__, 'thread_limit': 4},
                   max_absolute_log_loss_difference=max_gap,
                   published_test_note='Previously released outcomes, repeated here for reproduction.')
    write_json(output / 'baseline_reproduction.json', payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        reproduce(args.output)
