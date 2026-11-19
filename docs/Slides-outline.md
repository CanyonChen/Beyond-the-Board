# Presentation Outline (Model Implementation Part)

Target: 10–12 minute team presentation. Slides 4–7 are the modelling core and
belong to the model-implementation role; slides 1–3 and 8–12 are shared and
should be reviewed by the integration lead before the final run-through.

Every figure referenced below already exists in `results/` as PDF (vector, use
this for slides) and PNG (for previews).

| # | Slide | Content | Asset |
|---|---|---|---|
| 1 | Title | Project title, group name, members | – |
| 2 | Question | Does remaining time improve next-move blunder prediction beyond rating and the position? Four sub-questions: incremental value, nonlinearity, model comparison | – |
| 3 | Data at a glance | 9/2026 Lichess 180+0; 913,510 moves / 11,812 games; 8.31% blunders; duplicate rows removed; 30 UTC days | Dataset summary table (evaluation section) |
| 4 | How a blunder is defined | Prediction time = start of turn; winning-chance mapping; 10 pp drop rule; why not a fixed pawn loss | Formula block, no asset |
| 5 | What the models see | Feature groups table; the four design-matrix blocks (splines, standardised linear, phase, interactions); 38 columns | `docs/Methodology.md` §3.3–3.4 |
| 6 | Model implementation | Prevalence baseline, L2 logistic with splines and interactions, histogram boosting with early stopping disabled and a 9-point grid; natural class distribution | `docs/Methodology.md` §3.5 |
| 7 | Validation design | Three expanding windows, locked final week, selection by mean log loss, threshold from validation | Diagram: three bars + locked block |
| 8 | Headline result | Test-week log loss 0.231 (boosting) / 0.267 (logistic) / 0.288 (benchmark); AUC 0.823; AP 0.280 vs 0.084 prevalence | Test-week performance table (evaluation section) |
| 9 | Is the gap real? | Paired bootstrap over whole games: Δ log loss −0.035 [−0.037, −0.034]; Δ AP +0.113 [+0.107, +0.120] | Table 4 |
| 10 | Are probabilities usable? | Calibration on test week; boosting tracks the diagonal; logistic drifts in the tails | `results/calibration.pdf` |
| 11 | What drives the prediction | Permutation importance: pre-move evaluation dominant; clock small marginally | `results/feature_importance.pdf` |
| 12 | Does time actually help? | Ablation: removing clocks costs 0.005 log loss; removing the evaluation costs boosting 0.021 but the linear model nothing | Table 5 |
| 13 | Robustness | Label thresholds 5/15 pp and 150 cp keep the ranking; player-disjoint and mate-inclusive checks not available | Table 6 + one line on limitations |
| 14 | Takeaways | Time carries information beyond rating and position; the flexible model earns its complexity mainly through nonlinear use of position strength; calibrated probabilities are achievable | – |

## Speaker notes to prepare

1. **Definition slide** — be explicit that this is a study-defined threshold,
   not an official Lichess label, and why a fixed pawn loss distorts decisive
   positions.
2. **Implementation slide** — expect a question on why early stopping is off:
   its internal split ignores games, so it would leak within a game; the
   iteration budget is fixed instead.
3. **Validation slide** — emphasise the test week is touched once, and that the
   operating threshold comes from validation, not from the test set.
4. **Ablation slide** — the interesting nuance: the pre-move evaluation matters
   to boosting but not to the linear model. Be ready to explain that this is why
   the two models differ, and that permutation importance understates the clock
   because it correlates with the position.
5. **Limitations** — say plainly: no player identifiers, no mate evaluations,
   single month and time control, observational data.

## Assets checklist before the run-through

- [ ] `results/calibration.pdf`, `results/feature_importance.pdf`,
      `results/eda_rates.pdf` copied into the slide deck as vector graphics
- [ ] Tables 3–6 typed as native slides tables (not screenshots)
- [ ] One slide-level number per figure, rounded consistently with the
      evaluation section once its final numbers are fixed
- [ ] Figure captions aligned with the evaluation section, which owns the
      final wording
