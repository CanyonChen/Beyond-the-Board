"""Small regression checks for own-side history, probability gating and paired scoring."""

import unittest

import numpy as np
import pandas as pd

from compare_models import paired_interval
from comparison_features import apply_rule, feature_spec, regroup_clock_history, rule_mask
import train_model as original


class ComparisonTests(unittest.TestCase):
    def test_only_earlier_turns_for_same_player(self):
        one = pd.DataFrame({'game_id': 'game', 'ply': range(8),
                            'mover_is_white': [1, 0] * 4,
                            'clk_mover': [180, 180, 177, 173, 172, 172, 163, 165]})
        rows = pd.concat([one, one.iloc[[4]]], ignore_index=True).sample(frac=1, random_state=0)
        got = regroup_clock_history(rows).sort_values('ply').drop_duplicates('ply')
        np.testing.assert_allclose(got.prev_think_time, [np.nan, np.nan, 3, 7, 5, 1, 9, 7], equal_nan=True)
        np.testing.assert_allclose(got.think_time_mean3, [np.nan, np.nan, 3, 7, 4, 4, 17/3, 5], equal_nan=True)

    def test_gate_uses_only_pre_move_position(self):
        impossible = rule_mask([-1000, -100, 0, 1000])
        p = np.full(4, .15)
        np.testing.assert_array_equal(apply_rule(p, impossible, True), [0, .15, .15, .15])
        np.testing.assert_array_equal(apply_rule(p, impossible, False), p)

    def test_reduced_input_groups_exclude_clock_or_history_everywhere(self):
        numeric = [*original.SPLINE_BASE, *original.LINEAR_BASE]
        raw = pd.DataFrame({name: np.arange(8, dtype=float) for name in numeric})
        raw['phase'] = ['opening', 'middlegame'] * 4
        alter_clock = raw.copy()
        alter_clock[original.CLOCK_SPLINE + original.CLOCK_LINEAR] += 2
        alter_history = raw.copy()
        alter_history[['prev_think_time', 'think_time_mean3', 'think_missing']] += 2
        no_time = feature_spec(raw, 'no_time')
        clocks = feature_spec(raw, 'clocks')
        np.testing.assert_array_equal(no_time.transform(raw), no_time.transform(alter_clock))
        np.testing.assert_array_equal(clocks.transform(raw), clocks.transform(alter_history))
        self.assertFalse(np.allclose(clocks.transform(raw), clocks.transform(alter_clock)))

    def test_identical_predictions_have_zero_paired_difference(self):
        p = np.array([0., .2, .9, .8])
        fold = (np.array([0, 0, 1, 1]), ['a', 'a', 'b', 'b'], {'a': p, 'b': p.copy()})
        stats = paired_interval([fold, fold], 'a', 'b', n_boot=30)
        self.assertEqual((stats['delta_log_loss'], stats['lower_95'], stats['upper_95']), (0., 0., 0.))


if __name__ == '__main__':
    unittest.main()
