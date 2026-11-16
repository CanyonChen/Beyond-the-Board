# Dataset Documentation — DSC5001 SixSixGoSmooth

**Project**: Predicting Chess Blunders Under Time Pressure

**Data owner**: Wenxi GUAN (60237406)

**Deliverables**:

| File | Description |
|------|-------------|
| `moves.csv.gz` | Main dataset (gzip-compressed, one row = one move). Read directly with `pd.read_csv('moves.csv.gz')`. |
| `fetch_games.py` | Script that pulls games from the Lichess API (reproducible). |
| `build_from_api.py` | Script that extracts features and labels from the fetched game JSON (reproducible). |
| `README_data.md` | This document. |

## 0. Sample Size (actual)

- Fetched: **150 players**, **12,131 games** (2026-09, rated blitz 180+0, with engine analysis + clocks).
- Unit of analysis: **953,174 moves**, of which 939,039 (98.5%) are labeled.
- Label distribution: `y=1` (blunder) 78,805 moves, **8.29%**.
- Rating bands (by move count): 2500+ 38.7% / 2200–2499 27.0% / 1900–2199 9.6% / 1600–1899 12.4% / <1600 12.3%. The sample skews toward active strong players (they play far more games per month), but the mid/low bands still hold ~320k moves in absolute terms.

---

## 1. Data Source

- **Source**: Lichess public API (`lichess.org/api`), September 2026 rated blitz games.
- **Raw scale**: Lichess's full September standard-game archive is ~29.2 GB (~89.6M games). This project **does not download the full archive**; it pulls a small, condition-filtered subset via the API instead.
- **License**: CC0 (public domain).
- **Endpoint**: `GET /api/games/user/{username}` with `perfType=blitz`, `rated=true`, `analysed=true`, `clocks=true`, `evals=true`, and `since`/`until` locking the range to 2026-09.

> Why the API instead of the 29.2 GB archive: the Lichess monthly archive throttles a single HTTP connection (~1 MB/s), returns HTTP 429 for multi-threaded downloads, and its torrent is cold (few seeders), so downloading 29.2 GB is impractical. The API pulls exactly the filtered subset we need, orders of magnitude smaller.

## 2. Filtering & Sampling (Scope)

From the API response, only games meeting all of the following are kept:

1. Time control **180+0** (3 minutes per side, no increment) — coarse-filtered with `perfType=blitz`, then confirmed via the clock array.
2. Both players' ratings are numeric and present.
3. **Engine analysis present** (`analysed=true`; returns an `analysis` array with a per-move `eval`).
4. **Clocks present** (`clocks=true`; returns a per-move `clocks` array).

**Sampling method (snowball + band-aware priority)**:

- Seed: Lichess blitz leaderboard top-100 (covers the high 2600+ band).
- Expansion: for every player fetched, their **opponents** (with ratings) from the returned games are added to the queue, so the player pool naturally spreads across rating bands.
- Band-aware priority: when fetching, players from **under-represented bands** are preferred, so we don't sample only strong players.
- Band definitions: casual (<1600) / intermediate (1600–1899) / advanced (1900–2199) / expert (2200–2499) / master (2500+).

**Important limitation (must be acknowledged)**: this is a **snowball, band-stratified sample of active players** — **not** the site-wide random reservoir sampling envisioned in the original proposal. The sample skews toward **active players who played blitz in September and whose games were engine-analysed**, which may differ from the site-wide rating distribution. Generalisability of the conclusions must be worded cautiously.

## 3. Unit of Analysis

**One row = one move**, nested within a game and a player.

- Each game contributes multiple rows (one per move).
- The same player appears on multiple rows (multiple moves) within a game.

## 4. Label Definition (y)

- **Prediction timing**: *before* the move is played (i.e., at the moment it is the mover's turn).
- **Label**: `y = 1` means "blunder"; `y = 0` means non-blunder; `NULL` means undecidable (missing before/after evaluation).
- **Rule**: convert the engine evaluation (centipawns) from White's perspective to the **current mover's perspective**, then map it to a win probability via

  ```
  W(c) = 100 / (1 + exp(-0.00368208 · c))
  ```

  If the move causes the win probability to drop by **≥ 10 percentage points**, then `y = 1`.

- **Note**: this is a project-defined "serious error" threshold (per the proposal), **not** Lichess's official blunder label. Using a relative drop in win probability rather than a fixed "lost a pawn" avoids distortion in already-decided positions.
- **Mate evaluations**: `[%eval #N]` is mapped to a ±2000 cp proxy before computing the win probability.
- **Missing values**: when a move lacks a before or after evaluation, `y` is set to `NULL`. These rows are **kept** (for inspection) but must be filtered out before modelling.

## 5. Data Dictionary

| Field | Type | Meaning | Range / Notes |
|-------|------|---------|---------------|
| `game_id` | str | Unique game identifier (first 12 chars of MD5) | Used for grouping by game |
| `date` | str | Game UTC date | `YYYY-MM-DD`, used for temporal splits |
| `fullmove` | int | Full-move number (turn count) | Starts at 1 |
| `ply` | int | Half-move index | Starts at 0; even = White, odd = Black |
| `mover_is_white` | int | Whether the mover is White | 0/1 |
| `clk_mover` | float | **Mover's** remaining time (seconds) at the start of this move | 180 on the first move |
| `clk_opponent` | float | **Opponent's** remaining time (seconds) at the start of this move | 180 on the first move |
| `mover_rating` | int | Mover's rating | |
| `opp_rating` | int | Opponent's rating | |
| `rating_diff` | int | Rating difference (mover − opponent) | |
| `prev_think_time` | float | The mover's own think time on the previous move (seconds) | NULL on first move |
| `think_time_mean3` | float | Mean of the mover's own think time over the last 3 moves (seconds) | Fewer than 3 moves → average over available |
| `material_adv_cp` | int | Material advantage (centipawns, mover's perspective) | pawn=100, knight/bishop=300, rook=500, queen=900 |
| `nonpawn_material` | int | Total non-pawn material of both sides | N/B=3, R=5, Q=9 (king excluded) |
| `legal_moves` | int | Number of legal moves before the move | Rough position-complexity proxy |
| `in_check` | int | Whether the mover is in check before the move | 0/1 |
| `phase` | str | Game phase | `opening` / `middlegame` / `endgame` |
| `pre_move_eval_cp` | float | Engine evaluation before the move (centipawns, mover's perspective) | NULL on the first move |
| `y` | int | Label: whether it is a blunder | 0/1/NULL |

### Phase Classification

- `opening`: fullmove ≤ 10 (first 10 turns).
- `endgame`: total non-pawn material of both sides ≤ 14.
- Otherwise: `middlegame`.

## 6. Key Notes for the Modelling Teammate

1. **Do not shuffle-and-split naively.** Moves within the same game are not independent — cross-validation / splits **must group by `game_id`**, otherwise leakage occurs.
2. **Temporal split** (per proposal): games from 2026-09-24 to 09-30 form the **held-out test set**; 09-01 to 09-23 are used for training/validation (3 expanding windows: train 1-8/1-13/1-18, validate 9-13/14-18/19-23).
3. **Rows where `y` is NULL** must be filtered before modelling, but first check their proportion (may reveal a pattern in missing evaluations).
4. **`prev_think_time`, `think_time_mean3`, `pre_move_eval_cp` contain NULLs** (first move / first few moves). Handle them during modelling (the proposal mentions history-missing indicator variables).
5. **Standardisation/scaling, spline fitting, and hyperparameter tuning** must all be done within each training window, never across windows.
6. Class imbalance: blunders are usually a minority class. The actual `y=1` proportion is reported; see Section 0.

## 7. Reproducibility

- Fetch: `python scripts/fetch_games.py --target-players 150 --out data/raw_games.ndjson` (snowball sampling, resumable; the `.seen` file records already-fetched players).
- Feature extraction: `python scripts/build_from_api.py --input data/raw_games.ndjson --output output/moves.csv`.
- Compression (the raw CSV exceeds GitHub's 100 MB limit, hence the gzip delivery): `gzip -c moves.csv > moves.csv.gz`.
- The time range is locked to 2026-09 via `--since` / `--until` (millisecond timestamps).
- Label threshold, win-probability function, and feature definitions live in the constants at the top of `build_from_api.py` and in Sections 4 and 5 of this document.
