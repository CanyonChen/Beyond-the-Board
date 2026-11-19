# -*- coding: utf-8 -*-
"""
Score moves with the frozen model written by train_model.py.

The saved bundle references the feature pipeline defined in ``train_model``,
so this module registers that import path before unpickling.

Usage:
    python scripts/predict.py --input data/moves.csv.gz --output scored.csv
    python scripts/predict.py --input data/moves.csv.gz --limit 5000
"""
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402

import train_model  # noqa: E402  (required to unpickle the feature pipeline)
from train_model import engineer_features  # noqa: E402

BUNDLE_PATH = BASE_DIR.parent / "results" / "final_models.joblib"


def load_bundle(path=BUNDLE_PATH):
    return joblib.load(path)


def score(frame, bundle):
    """Return the blunder probability for every row of a move-level frame."""
    raw = engineer_features(frame.reset_index(drop=True))
    raw = raw.reindex(columns=bundle["raw_columns"], fill_value=0.0)
    pipeline = bundle["feature_pipeline"]
    model = bundle["models"][bundle["delivery_model"]]
    return model.predict_proba(pipeline.transform(raw))[:, 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True,
                        help="CSV or CSV.GZ with move-level rows")
    parser.add_argument("--output", default=None,
                        help="optional CSV path for the scored rows")
    parser.add_argument("--limit", type=int, default=None,
                        help="score only the first N rows")
    args = parser.parse_args()

    bundle = load_bundle()
    frame = pd.read_csv(args.input)
    if args.limit:
        frame = frame.head(args.limit)

    probability = score(frame, bundle)
    threshold = bundle["thresholds"][bundle["delivery_model"]]
    result = frame.copy()
    result["blunder_probability"] = probability
    result["blunder_prediction"] = (probability >= threshold).astype(int)

    print(f"scored {len(result):,} rows | threshold={threshold:.4f} | "
          f"positive rate={result['blunder_prediction'].mean():.4f}")
    if args.output:
        result.to_csv(args.output, index=False)
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
