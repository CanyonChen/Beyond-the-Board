# Chess blunder model comparison

The archived move table and the reconstructed 180+0 cohort answer separate questions. The first run checks whether the published scores can be reproduced. The second compares models on games whose time controls and turn-start clocks were checked against the official exports.

With verified clocks and finite engine labels, 839,176 moves from 11,253 games entered the main comparison. Histogram gradient boosting with the probability rule achieved the lowest three-window mean log loss, 0.23987, followed by the fixed XGBoost configuration with the rule at 0.24073. On the previously published test week, adding the two clocks changed HGB log loss from 0.23617 to 0.23528. Adding the mover's thinking history brought it to 0.23515. The combined change was −0.00102 (95% whole-game bootstrap interval −0.00143 to −0.00066).

## Reproduce the archived scores

Run from the repository root with the packages in `requirements.txt`.

```bash
python scripts/reproduce_baselines.py
```

`baseline_folds.csv` compares the published and reproduced values for each available split. `baseline_validation_means.csv` gives each of the three development windows equal weight. `baseline_reproduction.json` records the software versions, row counts and largest observed numerical difference.

## Train and score the verified cohort

After rebuilding `data/processed/moves_verified.csv.gz`, run the following commands from the repository root.

```bash
python scripts/compare_models.py --input data/processed/moves_verified.csv.gz --history provided
python scripts/predict_comparison.py --model results/model_comparison/verified_180_0/selected_model.joblib --input data/processed/moves_verified.csv.gz --output tmp/scored.csv.gz
python scripts/test_model_comparison.py
```

The main outcome is a drop of at least 10 percentage points between two finite engine scores, from the mover's perspective. All models receive only features available at the beginning of the turn. The prevalence model and archived L2 logistic specification are refitted on the same observations as histogram gradient boosting and XGBoost. Both tree models receive the same transformed features. Each has one fixed configuration, and training uses natural class frequencies.

The three expanding splits train on September 1–8, 1–13 and 1–18, then validate on 9–13, 14–18 and 19–23, respectively. For each fitted model we evaluate its original probabilities and a deterministic rule. If the current win proxy is below 10%, a ten-percentage-point loss is impossible and the rule assigns zero risk. The selected tree and rule minimize the equally weighted mean of the three validation log losses using all features. September 24–30 served as the published project's test period and is reused for supplementary comparisons.

The reduced models preserve the selected tree configuration and rule. `no_time` uses rating and position features. `clocks` adds the two turn-start clocks, clock share and interactions with rating and phase. `clocks_and_history` also adds the mover's previous thinking time, their rolling three-turn mean and a missing-history indicator. These are refitted models, so their differences quantify the incremental predictive value of each input group.

| File in `verified_180_0/` | Contents |
| --- | --- |
| `selection.json` | Input hash and counts, exact model settings, software versions, development selection made before scoring the final week |
| `fold_metrics.csv` and `validation_means.csv` | Per-window and mean scores for the model, rule and input comparisons |
| `published_test_metrics.csv` | Supplementary final-week log loss, Brier score, ROC-AUC and average precision |
| `paired_log_loss.csv` | Paired differences and 95% percentile intervals from 1,000 whole-game resamples. Development results resample within windows and average the three effects equally. |
| `selected_calibration.csv` | Final-week counts and mean predicted and observed risks by quantile of the selected probability |
| `selected_model.joblib` | Locally generated inference bundle fitted on September 1–23 |
| `run_summary.json` | Frozen model choice, interpretation of the comparison and a saved-model score check |

The prediction command accepts the same pre-move feature columns as the supplied move table. Labels are optional. It returns a game identifier, ply, probability and scoring status in input order. A missing pre-move engine evaluation leaves the probability blank. When using a new model bundle, keep its scikit-learn and XGBoost versions with the inference environment.
