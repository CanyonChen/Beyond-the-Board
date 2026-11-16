#!/usr/bin/env python3
"""
build_from_api.py — DSC5001 Group SixSixGoSmooth

Turn the raw games (NDJSON from fetch_games.py, one Lichess API game object per
line) into the move-level dataset `moves.csv`.

Reuses the already-validated label & feature helpers from build_dataset.py
(winning_chance, phase_of, nonpawn_material_total, side_material_cp) so the
two pipelines produce identical semantics.

Alignment (verified against the API):
    moves[i]     = UCI move for ply i (0-indexed)
    clocks[i+1]  = mover's clock (centiseconds) AFTER ply i; clocks[0] is the
                   initial 18003 cs (= 3 min).  Note: we convert to seconds.
    analysis[i]  = engine eval AFTER ply i, White perspective, {"eval": cp}
                   or {"mate": n} (n>0 = White mates).

Label (proposal, page 2):
    y = 1 if the mover's winning-chance W(c) drops by >= 10 pp across the move,
        else 0.  W(c) = 100 / (1 + exp(-0.00368208 c)).

Usage
-----
    python scripts/build_from_api.py --input data/raw_games.ndjson \
        --output output/moves.csv
"""

import argparse
import csv
import json
import math
import sys

import chess

# Import the shared, already-validated helpers from build_dataset.
sys.path.insert(0, "scripts")
import build_dataset as bd


MATE_CP = bd.MATE_CP
BLUNDER_THRESHOLD = bd.BLUNDER_THRESHOLD
TC_BASE_SECONDS = bd.TC_BASE_SECONDS

FEATURE_COLUMNS = bd.FEATURE_COLUMNS  # reuse the same column order


def eval_to_white_cp(analysis_entry):
    """analysis_entry -> White-perspective centipawns, or None.

    Handles {"eval": <cp>} and {"mate": <n>} (n>0 = White mates).
    """
    if not analysis_entry:
        return None
    if "eval" in analysis_entry:
        return float(analysis_entry["eval"])
    if "mate" in analysis_entry:
        n = int(analysis_entry["mate"])
        return MATE_CP if n > 0 else -MATE_CP
    return None


def game_to_rows(game):
    """One Lichess API game object -> list of move-level feature dicts."""
    moves = game.get("moves", "").split()
    clocks = game.get("clocks", [])   # centiseconds
    analysis = game.get("analysis", [])

    # Ratings.
    wp = game.get("players", {}).get("white", {})
    bp = game.get("players", {}).get("black", {})
    white_rating = wp.get("rating")
    black_rating = bp.get("rating")
    if white_rating is None or black_rating is None:
        return []

    # Date from createdAt (ms) -> YYYY-MM-DD.
    created = game.get("createdAt")
    if created:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
        game_date = dt.strftime("%Y-%m-%d")
    else:
        game_date = ""

    game_id = game.get("id", "")

    board = chess.Board()
    rows = []

    # Per-side last clock (seconds) after their most recent move; None if unknown.
    last_clk = {"white": None, "black": None}
    # Think history: (mover_is_white, seconds) for completed earlier turns.
    think_history = []
    # Eval AFTER previous move, White perspective (cp).
    prev_eval_white = None

    n = len(moves)
    for i in range(n):
        mover_is_white = (i % 2 == 0)
        move_uci = moves[i]

        # Clock after this move (belongs to mover). clocks has n+1 entries.
        clk_after = clocks[i + 1] / 100.0 if i + 1 < len(clocks) else None

        # Eval after this move (White perspective).
        eval_after_white = eval_to_white_cp(analysis[i]) if i < len(analysis) else None

        # Mover's starting clock = clock after their previous move (i-2), else 180.
        mover_side = "white" if mover_is_white else "black"
        if i < 2:
            mover_start_clk = TC_BASE_SECONDS
        else:
            mover_start_clk = last_clk.get(mover_side)

        # Opponent's starting clock = clock after the immediately preceding ply.
        opp_side = "black" if mover_is_white else "white"
        opp_start_clk = last_clk.get(opp_side) if i >= 1 else TC_BASE_SECONDS

        # Eval before this move = previous move's after-eval (White view).
        eval_before_white = prev_eval_white

        # Convert to mover perspective.
        eval_before_mover = (
            eval_before_white if mover_is_white else -eval_before_white
        ) if eval_before_white is not None else None
        eval_after_mover = (
            eval_after_white if mover_is_white else -eval_after_white
        ) if eval_after_white is not None else None

        # Label.
        y = None
        if eval_before_mover is not None and eval_after_mover is not None:
            drop = bd.winning_chance(eval_before_mover) - bd.winning_chance(eval_after_mover)
            y = 1 if drop >= BLUNDER_THRESHOLD else 0

        # Ratings.
        mover_rating = white_rating if mover_is_white else black_rating
        opp_rating = black_rating if mover_is_white else white_rating

        # Position descriptors BEFORE the move.
        legal_moves = board.legal_moves.count()
        in_check = int(board.is_check())
        nonpawn_mat = bd.nonpawn_material_total(board)
        material_adv_cp = (
            bd.side_material_cp(board, mover_is_white)
            - bd.side_material_cp(board, not mover_is_white)
        )
        phase = bd.phase_of(board, board.fullmove_number)

        # Time-usage history.
        prev_think_time = think_history[-1][1] if think_history else None
        recent = [t for _, t in think_history[-3:] if t is not None]
        think_time_mean3 = (sum(recent) / len(recent)) if recent else None

        row = {
            "game_id": game_id,
            "date": game_date,
            "fullmove": board.fullmove_number,
            "ply": i,
            "mover_is_white": int(mover_is_white),
            "clk_mover": mover_start_clk,
            "clk_opponent": opp_start_clk,
            "mover_rating": mover_rating,
            "opp_rating": opp_rating,
            "rating_diff": mover_rating - opp_rating,
            "prev_think_time": prev_think_time,
            "think_time_mean3": think_time_mean3,
            "material_adv_cp": material_adv_cp,
            "nonpawn_material": nonpawn_mat,
            "legal_moves": legal_moves,
            "in_check": in_check,
            "phase": phase,
            "pre_move_eval_cp": eval_before_mover,
            "y": y,
        }
        rows.append(row)

        # Advance state.
        if clk_after is not None:
            last_clk[mover_side] = clk_after
        if mover_start_clk is not None and clk_after is not None:
            think = max(0.0, mover_start_clk - clk_after)
            think_history.append((mover_is_white, think))
        else:
            think_history.append((mover_is_white, None))

        prev_eval_white = eval_after_white

        # Push move. Lichess API returns SAN-ish moves (e.g. "d4", "Nf3",
        # "O-O", "exd5"), not UCI, so use parse_san. Skip game on illegal move.
        try:
            board.push_san(move_uci)
        except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
            break

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="NDJSON raw games file")
    ap.add_argument("--output", required=True, help="output CSV path")
    args = ap.parse_args()

    all_rows = []
    n_games = 0
    n_skipped = 0

    with open(args.input) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            game = json.loads(line)
            rows = game_to_rows(game)
            if not rows:
                n_skipped += 1
                continue
            all_rows.extend(rows)
            n_games += 1

    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    # Summary.
    n_labeled = sum(1 for r in all_rows if r["y"] is not None)
    n_blunders = sum(1 for r in all_rows if r["y"] == 1)
    print(f"games: {n_games} (skipped {n_skipped})")
    print(f"total moves: {len(all_rows)}")
    print(f"labeled moves: {n_labeled} ({n_labeled/len(all_rows)*100:.1f}%)")
    if n_labeled:
        print(f"blunders (y=1): {n_blunders} ({n_blunders/n_labeled*100:.2f}% of labeled)")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
