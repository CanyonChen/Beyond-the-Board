"""Compare JSON clock indexing against official PGNs and the frozen legacy move table."""

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from build_from_api import CLOCK_TAG, open_text


def audit(source_dir, archived):
    state = {str(i): {'n': 0, 'within_pgn_rounding': 0, 'sum_abs_s': 0.0, 'max_abs_s': 0.0}
             for i in (0, 1)}
    clocks = {}
    manifest = json.loads((source_dir / 'manifest.json').read_text(encoding='utf-8'))
    for name in manifest['batch_files']:
        source = source_dir / name
        with open_text(source, 'r') as stream:
            for line in stream:
                g = json.loads(line)
                series = g.get('clocks') or []
                clocks[g['id']] = series
                tags = [3600 * int(h) + 60 * int(m) + float(s)
                        for h, m, s in CLOCK_TAG.findall(g.get('pgn') or '')]
                if len(tags) != len(g.get('moves', '').split()):
                    continue
                # Compare both conventions on exactly the same plies.
                for i, tag in enumerate(tags[:len(series) - 1]):
                    for offset in (0, 1):
                        stats = state[str(offset)]
                        seconds = abs(series[i + offset] / 100 - tag)
                        stats['n'] += 1
                        stats['within_pgn_rounding'] += seconds <= 0.500001
                        stats['max_abs_s'] = max(stats['max_abs_s'], seconds)
                        stats['sum_abs_s'] += seconds
    for stats in state.values():
        stats['mean_abs_s'] = stats.pop('sum_abs_s') / stats['n'] if stats['n'] else None
    counts = Counter()
    seen = defaultdict(set)
    with gzip.open(archived, 'rt', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            gid, ply = row['game_id'], int(row['ply'])
            if ply in seen[gid]:
                continue
            seen[gid].add(ply)
            if (gid not in clocks or not row['y'] or not row['clk_opponent'] or ply <= 0
                    or ply >= len(clocks[gid])):
                continue
            series = clocks[gid]
            old = float(row['clk_opponent'])
            counts['archived_labeled_plies_with_clocks'] += 1
            counts['agrees_with_movers_current_post_move_clock'] += abs(old - series[ply] / 100) < 1e-8
            counts['agrees_with_opponents_correct_turn_start_clock'] += abs(old - series[ply - 1] / 100) < 1e-8
    return {'requested_game_ids': len(seen), 'returned_game_ids': len(clocks),
            'missing_game_ids': sorted(seen.keys() - clocks.keys()),
            'json_vs_rounded_pgn_by_index_offset': state, 'archived_clk_opponent': dict(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path('data/raw/recovered'))
    parser.add_argument('--archived', type=Path, default=Path('data/moves.csv.gz'))
    parser.add_argument('--out', type=Path, default=Path('data/processed/clock_audit.json'))
    args = parser.parse_args()
    report = audit(args.source_dir, args.archived)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
