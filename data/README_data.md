# Data for the chess blunder study

The analysis unit is one player's turn in a Lichess game. The prediction uses information available before that player starts deciding. The target measures the fall in the engine's estimate of that player's winning chances after the move.

## Original sample and recovery

The team originally sampled publicly available, analysed rated blitz games from September 2026. It started with leaderboard players, followed their opponents and prioritised rating bands with lower coverage. This favours active players and games that already have engine analysis. The archived file contains 953,174 rows and 11,833 distinct Lichess game IDs. Repeated observations and moves without usable labels account for some of the difference between the archive and the analysis samples.

| File | Purpose |
| --- | --- |
| `data/moves.csv.gz` | Original uploaded table, preserved for comparison. |
| `data/raw/recovered/batch_*.ndjson.gz` | Locally cached official game exports containing the clock settings, full moves, PGN clock annotations and engine evaluations. |
| `data/processed/moves_verified.csv.gz` | Rebuilt table used for the revised analysis. |
| `data/processed/recovery_counts.json` | Counts by official time control, inclusion/exclusion reason, games, moves and label availability. |
| `data/processed/clock_audit.json` | Coverage of the legacy game IDs, per-ply comparisons of two JSON indexing conventions against official PGN clocks, and the corresponding audit of the legacy opponent-clock column. |

The eight-character IDs in the archive identify the actual public games. The recovery script sends those IDs to the official bulk export API and caches each completed batch locally. The sampler retains games explicitly marked rated, standard, initial time 180 seconds and increment 0, with a UTC start date in September 2026, two ratings, valid moves, engine evaluations and aligned clocks. The API's broader blitz classification alone allows multiple time controls. The local cache retains the source of every accepted row. [Lichess documentation for exports by ID](https://github.com/lichess-org/api/blob/master/doc/specs/tags/games/api-games-export-_ids.yaml)

### Recovered analysis sample, 20 November 2026

All 11,833 requested game IDs were returned. In the full archive, 11,302 games had official time control 180+0. The other settings were 300+0 (281), 180+2 (209), 300+3 (40) and 180+1 (1). Sequential eligibility checks removed 37 games played from a supplied starting position, then 520 other-time-control games, then 23 games whose clock gains exceeded the tolerance below. Eleven of the 37 supplied-position games also had a different time control. The largest excluded clock increase was 535.28 seconds. [Recovery counts](processed/recovery_counts.json)

| Primary analysis | Games | Moves with finite scores | Serious errors |
| --- | ---: | ---: | ---: |
| Development, 1–23 September | 8,621 | 642,668 | 53,398 |
| Reused chronological test week, 24–30 September | 2,632 | 196,508 | 16,401 |
| Total | 11,253 | 839,176 | 69,799 |

The rebuilt table retains 888,993 turns, including moves with incomplete or mate-valued evaluations. The alternative label with mate endpoints is available on 875,889 turns. The primary sample includes 6,823 distinct player identifiers, with both players known in every game.

## Turn-start information

For each game, the exporter compares the JSON clock in centiseconds at index `i` with the rounded PGN clock shown after move `i`. It requires an agreement within half a second on every ply. Certain exports have an additional terminal clock entry, which lies outside the recorded moves. Before a player's first turn their clock starts at 180 seconds. Afterwards the player's most recent completed move supplies their starting clock. The opponent's clock comes from the opponent's most recent completed turn.

For each side the first recorded clock is compared with the 180-second start and subsequent clocks with that side's previous clock. If any official centisecond value increases by more than 1 second, the whole game is excluded from the time-use analysis. An increase could reflect extra time or a clock correction, and ordinary elapsed time cannot be recovered for that interval. The 1-second tolerance was chosen during the data audit before fitting the revised models. The original proposal specified checking invalid clock histories and left the numerical threshold open.

After a move, estimated elapsed time is the difference between that player's starting clock and the verified clock after their move, floored at zero for small recording fluctuations. Separate histories for White and Black supply the player's previous time and the mean of their last three completed turns. On each player's first turn these fields are missing. Historical time fields are updated after the current row is constructed.

The earlier extraction code used clock index `i+1` after move `i`. In every one of the 913,510 labelled archive moves, the stored opponent clock equalled the mover's clock after that move. It also kept one shared time history for both sides. Both problems are fixed when reconstructing from the game exports.

The official JSON at index `i` agreed with its PGN annotation to within half a second on all 926,332 plies for which both index conventions could be compared. Index `i+1` met that tolerance on 52,856 plies. In all 913,510 labeled legacy rows, the archived opponent-clock field equalled the current mover's clock **after** the move. This made future information available during the original evaluation. [Full clock audit](processed/clock_audit.json)

## Fields

| Fields | Meaning |
| --- | --- |
| `game_id`, `date`, `ply`, `fullmove`, `mover_is_white` | Original game ID, UTC starting date, zero-based half-move index, full-move number and moving colour. |
| `white_player_id`, `black_player_id` | Stable 24-hex-character prefixes of SHA-256 over the public lower-case player identifiers, for checking repeated players without putting player names in the model table. |
| `clk_mover`, `clk_opponent` | Seconds remaining for the mover and their opponent at turn start. |
| `mover_rating`, `opp_rating`, `rating_diff` | Both players' ratings and the mover's rating minus the opponent's rating. |
| `prev_think_time`, `think_time_mean3` | Seconds spent on the mover's most recent completed turn and mean over their last 1–3 completed turns. |
| `material_adv_cp`, `nonpawn_material` | Material advantage from the mover's perspective in centipawns and total non-pawn material in pawn units. Piece values are 1/3/3/5/9. |
| `legal_moves`, `in_check`, `phase` | Legal-move count, check status and game phase on the pre-move board. Opening is full moves 1–10, then endgame for ≤14 non-pawn points and middlegame otherwise. |
| `pre_move_eval_cp`, `post_move_eval_cp` | Finite pre-/post-move engine scores from the current mover's perspective. Missing for mates or absent annotations. |
| `pre_move_mate`, `post_move_mate` | Signed mate distance from the mover's perspective, when the engine returns a mate score. For distance zero, the resulting board determines which side is checkmated. |
| `pre_move_win_pct`, `post_move_win_pct` | The mover's winning-chance proxy, or 0/100 for a forced loss/win. Missing when the engine score is unavailable. |
| `y`, `y_mate_inclusive` | Binary study labels. The main label requires finite engine scores before and after the move. The sensitivity label also permits forced loss/win. Either label is missing if a required score is absent. |

The win proxy is `100 / (1 + exp(-0.00368208 × cp))`. A fall of at least 10 percentage points from pre-move to post-move counts as a serious error under the main definition. Both scores are from the same player's perspective. A forced mate never becomes an arbitrary finite centipawn value. Post-move fields, the mate-inclusive fields and player identifiers serve labeling or audit purposes only. Training features must be explicitly selected from eligible turn-start columns.

## Reproduction

Run the following from the repository root in the project Python environment.

```console
python data/refetch_sample.py
python data/build_from_api.py --input data/raw/recovered --output data/processed/moves_verified.csv.gz --audit data/processed/recovery_counts.json
python data/audit_clocks.py
python -m unittest data.test_build_from_api
```

The fetcher resumes completed batches. The clock audit compares the original IDs with all returned IDs. Public metadata and availability can change between retrievals. The local raw cache contains public account information and stays outside Git. The recovery counts contain SHA-256 checksums for the compressed output and the underlying CSV. The builder fixes row order, CSV line endings and gzip header metadata so a rebuild using the same export cache can be verified. For a new sample, `python data/fetch_games.py --out data/raw/new_sample.ndjson` runs the player-based crawler. This produces a different set of games as the live leaderboard changes. Pass the resulting NDJSON file to the same builder.
