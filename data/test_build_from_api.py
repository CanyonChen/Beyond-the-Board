import json
import tempfile
import unittest
from pathlib import Path

from data.build_from_api import aligned_clocks, build, extract


def sample():
    return {
        'id': 'sample01', 'rated': True, 'variant': 'standard', 'createdAt': 1788220800000,
        'clock': {'initial': 180, 'increment': 0},
        'players': {'white': {'rating': 1500, 'user': {'id': 'white'}},
                    'black': {'rating': 1400, 'user': {'id': 'black'}}},
        'moves': 'f3 e5 g4 Qh4#', 'clocks': [17900, 17600, 17400, 16800, 0],
        'pgn': ' '.join('[%clk 0:02:' + s + ']' for s in ('59', '56', '54', '48')),
        'analysis': [{'eval': 0}, {'eval': 0}, {'mate': -1}, {'mate': 0}],
    }


class TestRecovery(unittest.TestCase):
    def test_turn_start_and_historical_think_times(self):
        rows, reason = extract(sample())
        self.assertIsNone(reason)
        self.assertEqual([r['clk_mover'] for r in rows], [180, 180, 179, 176])
        self.assertEqual([r['clk_opponent'] for r in rows], [180, 179, 176, 174])
        self.assertEqual([r['prev_think_time'] for r in rows], [None, None, 1, 4])
        self.assertEqual([r['think_time_mean3'] for r in rows], [None, None, 1, 4])
        self.assertEqual(rows[2]['pre_move_eval_cp'], 0)
        self.assertIsNone(rows[2]['post_move_eval_cp'])
        self.assertIsNone(rows[2]['y'])
        self.assertEqual(rows[2]['y_mate_inclusive'], 1)
        self.assertEqual(rows[3]['post_move_win_pct'], 100)
        self.assertEqual(rows[3]['y_mate_inclusive'], 0)
        self.assertNotEqual(rows[0]['white_player_id'], rows[0]['black_player_id'])

    def test_clock_alignment_against_pgn(self):
        game = sample()
        self.assertEqual(aligned_clocks(game['clocks'][:-1], game['pgn'], 4),
                         [179, 176, 174, 168])
        self.assertIsNone(aligned_clocks(game['clocks'][1:], game['pgn'], 4))
        self.assertIsNone(aligned_clocks(game['clocks'], '', 4))

    def test_rolling_mean_uses_the_same_player_only(self):
        game = sample()
        seconds = [179, 175, 177, 168, 174, 158, 170, 146, 165]
        game.update(moves='e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O',
                    clocks=[100 * s for s in seconds], analysis=[{'eval': 0}] * len(seconds),
                    pgn=' '.join(f'[%clk 0:{s // 60:02d}:{s % 60:02d}]' for s in seconds))
        rows, reason = extract(game)
        self.assertIsNone(reason)
        self.assertEqual(rows[8]['prev_think_time'], 4)
        self.assertEqual(rows[8]['think_time_mean3'], 3)
        self.assertEqual(rows[7]['think_time_mean3'], (5 + 7 + 10) / 3)

    def test_requires_explicit_time_control_and_complete_legal_game(self):
        for clock in ({'initial': 300, 'increment': 0}, {'initial': 180, 'increment': 2}, {}):
            rows, reason = extract(dict(sample(), clock=clock))
            self.assertEqual((rows, reason), ([], 'time_control_other_or_missing'))
        self.assertEqual(extract(dict(sample(), moves='f3 e5 g4 Qa8'))[1], 'invalid_move_sequence')

    def test_increase_is_checked_at_the_first_turn_and_within_each_colour(self):
        for clocks, tags in (([18101, 17600, 17400, 16800], [181, 176, 174, 168]),
                             ([17900, 17600, 18001, 16800], [179, 176, 180, 168])):
            pgn = ' '.join(f'[%clk 0:{s // 60:02d}:{s % 60:02d}]' for s in tags)
            self.assertEqual(extract(dict(sample(), clocks=clocks, pgn=pgn))[1],
                             'clock_gain_above_tolerance')

    def test_recovery_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'batch_input.ndjson'
            games = [dict(sample(), id='sample02'), sample()]
            source.write_text('\n'.join(map(json.dumps, games)), encoding='utf-8')
            first = build([source], root / 'first.csv.gz')
            source.write_text('\n'.join(map(json.dumps, reversed(games))), encoding='utf-8')
            second = build([source], root / 'second.csv.gz')
            self.assertEqual(first['output_file_sha256'], second['output_file_sha256'])
            self.assertEqual(first['decompressed_csv_sha256'], second['decompressed_csv_sha256'])


if __name__ == '__main__':
    unittest.main()
