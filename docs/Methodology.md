# Methodology: Model Construction and Implementation

**Scope.** This material covers how the models were specified, implemented and
selected. It states what the pipeline computes and how it is reproduced; it does
not interpret test-week performance, which belongs to the evaluation part of the
report. Configuration-by-configuration validation scores are in
`results/selection.json`; test-week numbers are written by the same script to
`results/metrics.json` and are reported in the evaluation section.

## 3.1 Prediction time and target

A prediction is made at the start of the mover's turn, before any time is spent
on the current move. Every input is therefore measurable at that moment: the
mover's starting clock comes from their previous move, the opponent's clock from
the immediately preceding ply, and historical thinking times only from completed
earlier turns. Board inputs describe the position before the move. The current
move's elapsed time, the resulting position, annotation symbols and the game
result are never used as predictors.

## 3.2 Label

Let `c_before` and `c_after` be adjacent engine evaluations in centipawns, both
expressed from the mover's perspective. With the Lichess mapping
`W(c) = 100 / (1 + exp(-0.00368208 c))`, the label is

```
y = 1  if  W(c_before) - W(c_after) >= 10 percentage points,  else y = 0
```

This is a study-defined threshold for a serious error, not an official Lichess
label. Evaluations are used exactly as delivered: there is no centipawn cap and
no sentinel substitution for missing values. Rows without a finite evaluation on
both sides of the move cannot be labelled and are excluded.

The stored label was re-derived from adjacent evaluations inside the pipeline
and reproduced on 903,656 of 903,656 checkable rows (agreement 1.0000). A
duplicate scan removed 25,872 fully duplicated rows (298 games had been written
twice), leaving 913,510 labelled moves from 11,812 games.

## 3.3 Predictors

| Group | Variables |
|---|---|
| Clock | mover's remaining seconds, opponent's remaining seconds, clock share |
| Player | mover rating, opponent rating, rating difference |
| Time use | previous own thinking time, three-turn mean, history-missing flag |
| Board | material advantage (cp), non-pawn material, legal-move count, in check, phase |
| Position strength | pre-move engine evaluation (cp) |
| Structure | full-move number, colour |

Opening is moves 1–10; endgame is combined non-pawn material ≤ 14 points,
otherwise middlegame. `log(1 + seconds)` is used wherever the clock enters a
smooth term or an interaction.

## 3.4 Design matrix

One transformer builds the design matrix inside each training window, so no
quantity is learned on validation or test data:

1. **Spline bases** — cubic B-splines (`n_knots = 4`, `degree = 3`,
   `include_bias = False`) for `log(1 + mover clock)`, `log(1 + opponent clock)`,
   mover rating and move number. Knots are placed uniformly over the training
   range of each window.
2. **Standardised linear block** — clock share, rating difference, opponent
   rating, previous thinking time, three-turn mean, missing-history flag,
   material advantage, non-pawn material, legal moves, check flag, colour, and
   the pre-move evaluation. Standardised on training data and clipped to ±10
   standard deviations to keep the optimiser stable.
3. **Phase coding** — one indicator per phase (opening, middlegame, endgame).
4. **Interactions** — `log(1 + mover clock) × rating` and
   `log(1 + mover clock) × phase` for all three phases, standardised with the
   linear block.

The resulting matrix has 38 columns. The same matrix is used for both models, so
the comparison isolates the functional form rather than the inputs.

## 3.5 Models

Training always uses the natural class distribution: no class weights and no
resampling, so that predicted probabilities can be read as probabilities and
scored with log loss.

| Model | Specification |
|---|---|
| Prevalence benchmark | Constant prediction equal to the training-window error rate |
| L2 logistic regression | L2 penalty, `lbfgs`, `max_iter = 1000`, `C ∈ {0.03, 0.1, 0.3, 1}` |
| Histogram gradient boosting | `early_stopping = False`, `max_iter = 250`; grid over `max_leaf_nodes ∈ {15, 31, 63}`, `learning_rate ∈ {0.05, 0.10}`, `min_samples_leaf ∈ {50, 100}`, `l2_regularization ∈ {1, 10}` |

Five boosting and four logistic configurations were evaluated, within the
pre-registered limit of twelve per model. Internal early stopping is disabled,
as required by the proposal: with the default behaviour the boosting model draws
a random validation split that ignores `game_id`, which would let the same game
inform both fitting and stopping.

## 3.6 Validation and selection

| Element | Implementation |
|---|---|
| Expanding windows | train 1–8 / validate 9–13; train 1–13 / validate 14–18; train 1–18 / validate 19–23 September |
| Locked test set | games dated 24–30 September, evaluated once |
| Grouping | whole games stay in one set (`game_id`) |
| Selection rule | minimum mean validation log loss across the three windows |
| Refit | selected configuration refitted on days 1–23, then evaluated |
| Operating threshold | F1-optimal point chosen on the 19–23 September validation window, applied unchanged to the test week |

Selection is therefore driven by probabilistic accuracy, not by a thresholded
score, and the test week never influences hyper-parameter or threshold choice.

### Selection outcome

| Model | Selected configuration | Mean validation log loss |
|---|---|---|
| L2 logistic regression | `C = 1.0` | 0.26770 |
| Histogram gradient boosting | 31 leaves, learning rate 0.05, 100 samples per leaf, L2 = 10 | 0.23523 |

The nine configurations span 0.26770–0.26822 (logistic) and 0.23523–0.23561
(boosting); the full per-window table is in `results/selection.json`. Because
every boosting configuration lies within 0.0004 log loss of the best, the
choice inside that family is not material and is reported only for
completeness.

## 3.7 Metrics

Log loss is the primary metric. Alongside it the pipeline reports the Brier
score, ROC-AUC, average precision next to the test prevalence, mean predicted
probability, and a calibration plot computed on ten quantile bins. Precision,
recall and F1 are reported at the validation-chosen threshold rather than at
0.5. Differences between models are given 95% percentile intervals from 1,000
bootstrap resamples of whole test games, applied to both log loss and average
precision.

## 3.8 Robustness checks

| Check | Implementation |
|---|---|
| Drop clock and thinking-time inputs | Same configuration refitted without clock variables and without clock interactions (21 columns) |
| Drop pre-move evaluation | Same configuration refitted without the engine score (37 columns) |
| Label sensitivity | Labels rebuilt at 5 pp, 15 pp and a 150 cp loss, same split and configuration |
| Player-disjoint check | Not available: the table carries no player identifiers |
| Mate-inclusive analysis | Not available: the annotated sample holds finite evaluations only |

## 3.9 Reproducibility

- `scripts/train_model.py` runs the whole protocol; `--quick` runs a 1,500-game
  smoke test in under a minute.
- Random seed 42; validation and test splits are determined by date, so results
  do not depend on split randomness.
- `scripts/predict.py` scores new rows with the frozen bundle;
  `scripts/plot_importance.py` regenerates the importance figure from
  `results/feature_importance.csv`.
- Environment: Python 3.14, scikit-learn 1.9.1, pandas 2.3.3, numpy 2.5.4
  (`requirements.txt`). A full run takes about seven minutes on a laptop.
