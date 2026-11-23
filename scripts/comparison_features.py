"""Input and feature contract shared by comparison training and inference."""

import numpy as np
import pandas as pd

import train_model as original


FEATURE_SETS = ('no_time', 'clocks', 'clocks_and_history')
HISTORY = ('prev_think_time', 'think_time_mean3', 'think_missing')


def regroup_clock_history(frame):
    """Derive nonnegative changes in one side's clock before its current turn.

    For archives of mixed time controls these are clock changes, not a verified
    thinking duration. Complete preceding plies are required for each game.
    """
    keys = ['game_id', 'mover_is_white']
    events = frame[['game_id', 'mover_is_white', 'ply', 'clk_mover']].drop_duplicates()
    if events.duplicated(['game_id', 'ply']).any():
        raise ValueError('Conflicting clock entries for a single game/ply.')
    events = events.sort_values(['game_id', 'ply'])
    side = events.groupby(keys, sort=False)
    if not events.groupby('game_id', sort=False)['ply'].min().eq(0).all():
        raise ValueError('Clock regrouping needs the move history from ply zero.')
    previous_ply = side['ply'].shift()
    gap = previous_ply.notna() & events['ply'].sub(previous_ply).ne(2)
    if gap.any():
        raise ValueError('A game is missing prior turns needed for clock history.')
    events['prev_think_time'] = (side['clk_mover'].shift() - events['clk_mover']).clip(lower=0)
    rolled = events.groupby(keys, sort=False)['prev_think_time'].rolling(3, min_periods=1).mean()
    events['think_time_mean3'] = rolled.reset_index(level=[0, 1], drop=True)
    lookup = events.set_index(['game_id', 'ply'])
    rows = pd.MultiIndex.from_frame(frame[['game_id', 'ply']])
    result = frame.copy()
    for column in HISTORY[:2]:
        result[column] = lookup[column].reindex(rows).to_numpy()
    return result


def feature_spec(raw_train, level):
    if level not in FEATURE_SETS:
        raise ValueError(f'Unknown input group {level!r}')
    splines = list(original.SPLINE_BASE)
    linear = list(original.LINEAR_BASE)
    if level == 'no_time':
        splines = [name for name in splines if name not in original.CLOCK_SPLINE]
        linear = [name for name in linear if name not in original.CLOCK_LINEAR]
    elif level == 'clocks':
        linear = [name for name in linear if name not in HISTORY]
    # Fit every feature-selection decision on this training window only.
    linear = [c for c in linear if raw_train[c].nunique(dropna=False) > 1]
    return original.BlunderFeatures(spline_columns=splines, linear_columns=linear,
                                    use_interactions=level != 'no_time').fit(raw_train)


def rule_mask(pre_move_cp):
    # Below 10%, the current mover cannot lose ten percentage points on this ply.
    return original.winning_chance(pre_move_cp) < original.LABEL_PP


def apply_rule(probabilities, ineligible, enabled):
    p = np.asarray(probabilities, dtype=np.float64)
    return np.where(ineligible, 0., p) if enabled else p


def score_frame(frame, bundle):
    """Score the supplied rows, preserving order; a pre-move evaluation is required."""
    if bundle['history'] == 'regroup-clock':
        frame = regroup_clock_history(frame)
    out = frame[['game_id', 'ply']].reset_index(drop=True).copy()
    out['blunder_probability'] = np.nan
    out['score_status'] = 'missing_pre_move_eval'
    have_eval = np.isfinite(frame['pre_move_eval_cp'].to_numpy(dtype=float))
    if have_eval.any():
        valid = frame.loc[have_eval].reset_index(drop=True)
        raw = original.engineer_features(valid)
        values = bundle['features'].transform(raw)
        p = bundle['model'].predict_proba(values)[:, 1]
        mask = rule_mask(valid['pre_move_eval_cp'])
        out.loc[have_eval, 'blunder_probability'] = apply_rule(p, mask, bundle['rule'])
        out.loc[have_eval, 'score_status'] = 'scored'
    return out
