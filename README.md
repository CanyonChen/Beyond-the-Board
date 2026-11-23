# Beyond the Board: Time-Aware Blunder Prediction in Chess

CityUHK DSC5001 · SixSixGoSmooth

At the start of a turn, can the time on the two chess clocks help predict a serious error after accounting for the position and the players' ratings? We use a ten-percentage-point drop in an engine-derived winning-chance score as the outcome. Predictions use information available before the move. The study measures predictive value in observed games.

The source-verified analysis covers **839,176 labelled moves from 11,253 games**. Validation selected histogram gradient boosting with a label-derived probability constraint. On the previously examined final week, log loss fell from **0.236168** using position and ratings to **0.235275** with starting clocks and **0.235150** with the mover's recent clock history. The fixed XGBoost comparison with the same constraint scored **0.235851**. [Model comparisons and uncertainty](results/model_comparison/verified_180_0/paired_log_loss.csv)

## Read the project

- The [project report](docs/report/Beyond_the_Board_Report.pdf) and its [editable LaTeX source](docs/report/main.tex) describe the research question, data audit, experiments and limitations.
- The [Canvas slide PDF](docs/pre/Team-SixSixGoSmooth-PPT.pdf) and [offline presentation](docs/pre/deck.html) present the findings in ten slides. The six speakers have a combined rehearsal target of 7 minutes 30 seconds. Press **N** in the HTML deck for the English script and supporting data. The [figure manifest](results/model_comparison/report_figures/manifest.json) identifies the inputs for the four report plots.
- The [experiment ledger](experiment/results.md) records the original reproduction and revised comparisons. The [evaluation protocol](experiment/evaluation.md) defines the samples, time windows, endpoints and sensitivity analyses.
- The [complete English presentation script](docs/Full-Presentation-Script.pdf) assigns all ten slides across six speakers and includes the full spoken text and handovers. An [editable version](docs/Full-Presentation-Script.md) is available for rehearsal changes.
- The [23 November evaluation review](docs/Evaluation-Review-Senyuan-WU.md) records Senyuan WU's evaluation checks and the refined conclusions. Senyuan presents slides 8–10 in the current recording plan.
- The [data guide](data/README_data.md) documents source recovery, the official 180+0 filter, clock alignment and the construction of labels and pre-move features.
- The [Chinese progress log](docs/Project_Progress.md) records the team's dated updates and the follow-up work. Read the [handoff](handoff.md) for remaining tasks.
- Historical materials include the [proposal](docs/Team-Proposal-SixSixGoSmooth.pdf), [group roster](docs/5001_GroupSixSixGoSmooth.docx), [original model specification](docs/Methodology.md) and [archived results](docs/Results.md). The [presentation outline](docs/Slides-outline.md) gives the six speakers’ timings and sources. Canvas also requires an all-member Zoom recording of at most eight minutes. The [contribution and source-code appendix](docs/Team-SixSixGoSmooth-Appendix.pdf) lists each member’s documented work. It links the original GitHub revision and embeds the [code used for the submitted analysis](docs/appendix-assets/Beyond-the-Board-source.zip).

## Which result answers the question?

The original run used the distributed table in `data/moves.csv.gz`. An audit against the Lichess game exports identified mixed time controls and a shifted clock index: on all 913,510 labelled moves, the column named opponent clock contained the mover's reading after the current move. The original tables in `results/` are retained for reproduction. The current study rebuilds pre-move features from verified rated standard games with an initial 180 seconds and no increment. Compare models and feature sets within that same cohort.

The study evaluates prevalence, L2 logistic regression, histogram gradient boosting and XGBoost. Two controlled comparisons separate the contribution of starting clocks from earlier time use and measure the effect of enforcing the mathematical lower limit on the outcome. The three development windows select the model. The September 24–30 comparison reuses a week previously reported by the group.

## Run locally

From this repository root, install the listed [Python requirements](requirements.txt) in a virtual environment. Commands below use that environment's Python.

```text
python scripts/reproduce_baselines.py
python scripts/compare_models.py --input data/processed/moves_verified.csv.gz --history provided
python scripts/clock_subgroups.py tmp/clock_predictions.csv.gz results/model_comparison/clock_subgroups.csv
python scripts/adjusted_clock_curves.py data/processed/moves_verified.csv.gz results/model_comparison
python scripts/check_robustness.py data/processed/moves_verified.csv.gz results/model_comparison/verified_180_0/selection.json results/model_comparison/robustness.csv
python scripts/predict_comparison.py --model results/model_comparison/verified_180_0/selected_model.joblib --input data/processed/moves_verified.csv.gz --limit 200 --output tmp/scored_moves.csv
python scripts/plot_report_figures.py
python docs/report/refresh_tables.py
```

The data guide includes commands to reconstruct the verified table from the archived game IDs. The [fitted model](results/model_comparison/verified_180_0/selected_model.joblib) can score eligible rows directly in the recorded environment. The comparison script also rebuilds it and checks that loading it reproduces the reported probabilities. After refreshing the tables, compile the report from its own directory.

```text
cd docs/report
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Beyond_the_Board_Report main.tex
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Beyond_the_Board_Report main.tex
```

## Project records and license

Append a dated Chinese entry to the progress log for each project update. Record the contributor, files, results and next task. The code is distributed under the [MIT License](LICENSE).
