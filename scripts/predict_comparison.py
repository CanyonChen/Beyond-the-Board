"""Score move-level CSV data with the saved development-selected comparison model."""

import argparse
import os
from pathlib import Path

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '4'

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from comparison_features import score_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True, help='Project move table, CSV or CSV.GZ. Labels are optional.')
    parser.add_argument('--output', type=Path, required=True, help='Scored CSV or CSV.GZ.')
    parser.add_argument('--limit', type=int, help='Read at most this many source rows.')
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error('--limit must be positive')
    model = joblib.load(args.model)
    data = pd.read_csv(args.input, nrows=args.limit)
    with threadpool_limits(limits=4):
        output = score_frame(data, model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"{output.blunder_probability.count()} of {len(output)} rows scored; wrote {args.output}")


if __name__ == '__main__':
    main()
