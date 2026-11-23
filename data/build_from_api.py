"""Rebuild the September 2026 standard 180+0 sample from official Lichess game exports."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
from collections import Counter, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import chess


FIELDS = ('game_id date fullmove ply mover_is_white clk_mover clk_opponent mover_rating '
          'opp_rating rating_diff prev_think_time think_time_mean3 material_adv_cp '
          'nonpawn_material legal_moves in_check phase pre_move_eval_cp post_move_eval_cp '
          'pre_move_mate post_move_mate pre_move_win_pct post_move_win_pct '
          'white_player_id black_player_id y y_mate_inclusive').split()
PIECE_POINTS = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
CLOCK_TAG = re.compile(r'\[%clk (\d+):(\d+):([\d.]+)\]')
MISSING = (None, None, None)


def win_percent(cp):
    # An equivalent logistic form that cannot overflow at very negative scores.
    exp = math.exp(-abs(cp) * 0.00368208)
    return 100 * ((1 if cp >= 0 else exp) / (1 + exp))


def white_score(entry, board_after):
    """Return (finite centipawns, signed mate distance, win proxy) for White."""
    if 'eval' in entry and entry['eval'] is not None:
        cp = float(entry['eval'])
        return (cp, None, win_percent(cp)) if math.isfinite(cp) else MISSING
    if 'mate' in entry and entry['mate'] is not None:
        n = int(entry['mate'])
        if n == 0 and not board_after.is_checkmate():
            return MISSING
        white_wins = n > 0 if n else board_after.turn == chess.BLACK
        return None, n, 100.0 if white_wins else 0.0
    return MISSING


def for_mover(score, white):
    if white:
        return score
    cp, mate, pct = score
    return (-cp if cp is not None else None, -mate if mate is not None else None,
            100 - pct if pct is not None else None)


def player_key(player):
    user = player.get('user') or {}
    name = user.get('id') or user.get('name')
    return hashlib.sha256(name.lower().encode()).hexdigest()[:24] if name else None


def exclusion(game):
    if game.get('rated') is not True or game.get('variant') != 'standard':
        return 'not_rated_standard'
    clock = game.get('clock') or {}
    if clock.get('initial') != 180 or clock.get('increment') != 0:
        return 'time_control_other_or_missing'
    if not game.get('createdAt'):
        return 'missing_date'
    date = datetime.fromtimestamp(game['createdAt'] / 1000, timezone.utc).date().isoformat()
    if not ('2026-09-01' <= date <= '2026-09-30'):
        return 'outside_september_2026'
    players = game.get('players') or {}
    if not all(isinstance((players.get(side) or {}).get('rating'), (int, float))
               for side in ('white', 'black')):
        return 'missing_rating'
    if not game.get('analysis'):
        return 'no_engine_analysis'
    return None


def aligned_clocks(clocks, pgn, n):
    """Compare the centisecond JSON series with official per-ply PGN clock tags."""
    if len(clocks) not in (n, n + 1) or n == 0:
        return None
    tags = [3600 * int(h) + 60 * int(m) + float(s) for h, m, s in CLOCK_TAG.findall(pgn)]
    if len(tags) != n:
        return None
    seconds = [c / 100.0 for c in clocks[:n] if isinstance(c, (int, float)) and c >= 0]
    if len(seconds) != n or any(abs(a - b) > 0.500001 for a, b in zip(seconds, tags)):
        return None
    return seconds


def max_clock_gain(game):
    """Largest same-side clock increase in seconds, including each side's first turn."""
    series = (game.get('clocks') or [])[:len(game.get('moves', '').split())]
    initial = (game.get('clock') or {}).get('initial')
    if not isinstance(initial, (float, int)):
        return 0.0
    last = [100 * initial, 100 * initial]
    gain = 0.0
    for ply, centiseconds in enumerate(series):
        if not isinstance(centiseconds, (float, int)):
            continue
        color = ply % 2
        gain = max(gain, centiseconds - last[color])
        last[color] = centiseconds
    return gain / 100


def extract(game):
    reason = exclusion(game)
    if reason:
        return [], reason
    moves = game.get('moves', '').split()
    seconds = aligned_clocks(game.get('clocks') or [], game.get('pgn') or '', len(moves))
    if seconds is None:
        return [], 'missing_or_unaligned_clocks'
    if max_clock_gain(game) > 1.0:
        return [], 'clock_gain_above_tolerance'
    players = game['players']
    date = datetime.fromtimestamp(game['createdAt'] / 1000, timezone.utc).date().isoformat()
    ratings = [players['black']['rating'], players['white']['rating']]
    keys = {f'{side}_player_id': player_key(players[side]) for side in ('white', 'black')}
    board = chess.Board()
    clocks = {chess.WHITE: 180.0, chess.BLACK: 180.0}
    history = {chess.WHITE: deque(maxlen=3), chess.BLACK: deque(maxlen=3)}
    previous = MISSING
    analysis = game['analysis']
    rows = []
    for ply, san in enumerate(moves):
        white = board.turn
        own_history = history[white]
        start = clocks[white]
        material = {color: sum(value * chess.popcount(board.pieces_mask(piece, color))
                               for piece, value in PIECE_POINTS.items())
                    for color in (chess.WHITE, chess.BLACK)}
        nonpawn = sum(material.values()) - chess.popcount(board.pawns)
        phase = 'opening' if board.fullmove_number <= 10 else ('endgame' if nonpawn <= 14 else 'middlegame')
        row = dict(game_id=game['id'], date=date, fullmove=board.fullmove_number, ply=ply,
                   mover_is_white=int(white), clk_mover=start, clk_opponent=clocks[not white],
                   mover_rating=ratings[white], opp_rating=ratings[not white],
                   rating_diff=ratings[white] - ratings[not white],
                   prev_think_time=own_history[-1] if own_history else None,
                   think_time_mean3=sum(own_history) / len(own_history) if own_history else None,
                   material_adv_cp=100 * (material[white] - material[not white]),
                   nonpawn_material=nonpawn, legal_moves=board.legal_moves.count(),
                   in_check=int(board.is_check()), phase=phase, **keys)
        try:
            board.push_san(san)
        except ValueError:
            return [], 'invalid_move_sequence'
        after = white_score(analysis[ply] or {}, board) if ply < len(analysis) else MISSING
        cp0, mate0, w0 = for_mover(previous, white)
        cp1, mate1, w1 = for_mover(after, white)
        inclusive = int(w0 - w1 >= 10) if w0 is not None and w1 is not None else None
        row.update(pre_move_eval_cp=cp0, post_move_eval_cp=cp1, pre_move_mate=mate0,
                   post_move_mate=mate1, pre_move_win_pct=w0, post_move_win_pct=w1,
                   y=inclusive if cp0 is not None and cp1 is not None else None,
                   y_mate_inclusive=inclusive)
        rows.append(row)
        previous = after
        own_history.append(max(0.0, start - seconds[ply]))
        clocks[white] = seconds[ply]
    if not any(row['y_mate_inclusive'] is not None for row in rows):
        return [], 'no_comparable_engine_scores'
    return rows, None


@contextmanager
def open_text(path, mode):
    if mode == 'w' and path.suffix == '.gz':
        with (path.open('wb') as raw,
              gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz,
              io.TextIOWrapper(gz, encoding='utf-8', newline='') as text):
            yield text
        return
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, mode + 't', encoding='utf-8', newline='') as text:
        yield text


def build(sources, output):
    stats = Counter()
    controls = Counter()
    seen = set()
    largest_gain = 0.0
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name('.partial-' + output.name)
    with open_text(tmp, 'w') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        for source in sources:
            with open_text(source, 'r') as stream:
                games = (json.loads(line) for line in stream if line.strip())
                if source.name.startswith('batch_'):
                    games = sorted(games, key=lambda g: g['id'])
                for game in games:
                    game_id = game['id']
                    if game_id in seen:
                        stats['duplicate_game_records'] += 1
                        continue
                    seen.add(game_id)
                    clock = game.get('clock') or {}
                    controls[f"{clock.get('initial')}+{clock.get('increment')}"] += 1
                    rows, reason = extract(game)
                    if reason:
                        stats['excluded_' + reason] += 1
                        if reason == 'clock_gain_above_tolerance':
                            largest_gain = max(largest_gain, max_clock_gain(game))
                        continue
                    writer.writerows(rows)
                    stats['included_games'] += 1
                    stats['primary_labeled_games'] += any(r['y'] is not None for r in rows)
                    stats['rows'] += len(rows)
                    stats['primary_labeled_rows'] += sum(r['y'] is not None for r in rows)
                    stats['mate_inclusive_labeled_rows'] += sum(r['y_mate_inclusive'] is not None for r in rows)
    tmp.replace(output)
    with output.open('rb') as source:
        file_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    opener = gzip.open if output.suffix == '.gz' else open
    with opener(output, 'rb') as source:
        csv_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'unique_source_games': len(seen), 'time_controls': dict(controls),
            'clock_gain_tolerance_seconds': 1.0, 'largest_excluded_clock_gain_seconds': largest_gain,
            'output_file_sha256': file_hash, 'decompressed_csv_sha256': csv_hash, **stats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='NDJSON(.gz) file or recovered batches directory')
    parser.add_argument('--output', type=Path, default=Path('data/processed/moves_verified.csv.gz'))
    parser.add_argument('--audit', type=Path, help='Write aggregate sampling and exclusion counts as JSON')
    args = parser.parse_args()
    if args.input.is_dir():
        manifest = args.input / 'manifest.json'
        if not manifest.is_file():
            parser.error('The recovered directory lacks a completed fetch manifest. Finish refetch_sample.py first.')
        files = [args.input / name for name in json.loads(manifest.read_text())['batch_files']]
    else:
        files = [args.input]
    if not files:
        parser.error('No completed source batch files were found')
    stats = build(files, args.output)
    summary = json.dumps(stats, indent=2, sort_keys=True) + '\n'
    print(summary, end='')
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(summary, encoding='utf-8')


if __name__ == '__main__':
    main()
