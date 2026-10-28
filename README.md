# Beyond the Board: Time-Aware Blunder Prediction in Chess

**CityUHK DSC5001 Group Project | SixSixGoSmooth**

This project investigates whether remaining time helps predict a player's next-move blunder beyond player ratings and board information. Predictions will use only information available at the start of the player's turn. The focus is on predictive accuracy, calibration, and interpretability; the analysis will not establish a causal effect of time pressure.

## Research Questions

- Does clock information improve next-move blunder prediction?
- How does the association vary across player ratings and game phases?
- Does gradient boosting improve on an interpretable logistic regression model?

## Planned Approach

- **Data:** Sample rated standard-chess games from the September 2026 [Lichess Open Database](https://database.lichess.org/), restricted to `180+0` games (three minutes per player, no increment) with valid clocks and engine evaluations. The plan is to sample up to 100 candidate games per UTC day, at most 3,000 before quality checks.
- **Target:** Predict a study-defined serious error: a drop of at least 10 percentage points in an engine-derived winning-chance proxy. This is not the official Lichess blunder label.
- **Features:** Starting clocks, ratings, previous thinking times, game phase, and pre-move board and evaluation features.
- **Models:** A prevalence baseline, L2-regularized logistic regression with splines and interactions, and histogram gradient boosting.
- **Validation:** Expanding temporal validation within 1-23 September 2026, followed by a held-out test on 24-30 September. Entire games stay together, and preprocessing is fitted within each training window.
- **Evaluation:** Log loss as the primary metric, supported by average precision, ROC AUC, Brier score, and calibration plots. Planned checks include removing clock features and varying the error threshold.

Planned tools: **Python, python-chess, pandas, scikit-learn, and matplotlib**.

## Documents

- [Project proposal (PDF)](docs/Team-Proposal-SixSixGoSmooth.pdf)
- [Project proposal (Word)](docs/Team-Proposal-SixSixGoSmooth.docx)
- [Group information (Word)](docs/5001_GroupSixSixGoSmooth.docx)

## Project Status

The repository currently contains the project proposal and group documentation. Data collection, implementation, experiments, and the final report are planned work; no empirical results are available yet.

Raw chess archives, generated datasets, model artifacts, and local temporary files are excluded from Git through [`.gitignore`](.gitignore).

## License

This project is licensed under the [MIT License](LICENSE).
