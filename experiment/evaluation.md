# Evaluation protocol

## Question and prediction time

At the start of a player's turn, does adding the two clocks improve the predicted probability of a serious error beyond ratings and the board? How much do the player's earlier clock changes add? Separately, compare model families and the logical restriction implied by the outcome. All inputs must exist before that move is played.

For an engine score in centipawns from the mover's perspective, use `W(c) = 100 / (1 + exp(-0.00368208 c))`. The primary event is a loss of at least ten percentage points between the position before the move and the position after it. The constrained prediction equals zero if `W(before) < 10` and otherwise equals the model's probability. A missing before-score alone cannot establish a structural zero. The rule uses the pre-move score only. Record violations of this rule in both the development and evaluation data.

## Data versions

1. **Distributed table.** Reproduce the previously selected prevalence, logistic and histogram boosting baselines on the archived feature definitions. Compare against the archived counts and metrics before attributing any changes to the models.
2. **Source-verified games.** The intended population is rated standard chess with 180 seconds and no increment. Use explicit time-control metadata wherever available. Verify raw clock alignment and the moving player's own history. Record the denominator at each selection step and the treatment of mate evaluations. If full source verification is unavailable, record coverage and report the mixed historical cohort as such. A clock reading alone does not confirm a game's time control.
3. Model comparisons must use exactly the same moves and labels within each cohort. A change in cohort, clocks or labels is a data revision. Scores from different cohorts cannot measure the benefit of changing an algorithm.

**Clock-history quality amendment.** During source audit and before the full comparison was fitted, we found non-monotone clocks even in games officially marked 180+0. Exclude a whole game if either player's own clock increases by more than one second relative to their previous clock (including the 180-second initial value). Use the official centisecond series for this test. Smaller rises are treated as zero elapsed time. The threshold is an audit decision, separate from the proposal. A large increase makes elapsed thinking time ambiguous and does not by itself establish a recording error.

## Fitting and selection

Keep entire games together. Use September 1–8, 1–13 and 1–18 for training, with validation on September 9–13, 14–18 and 19–23 respectively. Fit all learned transformations on the training portion of each window. Choose the model on the equally weighted mean of the three validation log losses. No tuning on September 24–30. The team had already seen outcomes from that week, so the follow-up reports it as a reused temporal evaluation.

Compare the selected histogram gradient boosting model against a fixed CPU histogram XGBoost configuration. Hold the observations and underlying features constant. Evaluate the same probability vector with and without the label constraint to isolate its contribution. Compare nested input sets for the selected family: ratings and board, add starting clocks, then add earlier own-clock changes. Keep paired rows in the same order across all comparisons.

## Endpoints and uncertainty

Log loss is primary. Also report average precision, ROC AUC, Brier score and observed prevalence. Estimate paired differences by resampling whole games with replacement. State the subtraction direction and interval method. The estimates describe the observed annotated sample; repeated players, selection for analysis and time control can affect interpretation.

Explore the incremental value of the two clocks and own-clock history in opening, middlegame and endgame, and for mover ratings below 1600, 1600–2199 and at least 2200. Report counts and paired game-level intervals. These descriptive subgroups overlap across dimensions and do not establish a causal clock effect or a formal interaction.

For the proposal's adjusted risk curves, fit the fixed logistic model with the label restriction on development games. Within each final-week phase and rating band, set the mover's clock to that group's observed 10th, 25th, 50th, 75th and 90th percentiles. Keep the other inputs at their observed values and recompute clock-derived terms at each value. Report the mean predicted risk over the same moves at every grid point. This profile is model-dependent and is descriptive: changing a clock alone need not correspond to an achievable game history.

## Sensitivity analyses from the proposal

On the source-verified cohort, keep the development-selected tree family and hyperparameters fixed. Refit for 5- and 15-point declines, and for a 150-centipawn loss. When the primary model uses the probability constraint, adjust the bound for each percentage-point outcome and omit it for the centipawn outcome. Include distinct move and event counts; losses across different outcomes are on different prevalence scales.

For mate-inclusive outcomes, use the win proxy itself as the pre-move evaluation feature so that forced outcomes have well-defined endpoints, 0 and 100. Fit the same model once on finite evaluations and once with the additional mate rows under this representation. Use a separate sensitivity fit after removing all development games that share either player with the reused final week. Verify zero player overlap, report retention and score on exactly the same test moves as the unrestricted model. This sensitivity changes the amount and composition of training data.
