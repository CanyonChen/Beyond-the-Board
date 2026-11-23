"""Recover the exact public Lichess games listed in the archived move table."""

import argparse
import csv
import gzip
import hashlib
import json
import time
from pathlib import Path

import requests


def download_batch(session, ids, target):
    temporary = target.with_suffix('.part')
    for attempt in range(5):
        try:
            response = session.post(
                'https://lichess.org/api/games/export/_ids',
                params={'clocks': 'true', 'evals': 'true', 'moves': 'true', 'pgnInJson': 'true'},
                data=','.join(ids), timeout=(15, 180), stream=True,
            )
            with response:
                if response.status_code == 429:
                    time.sleep(max(60, int(response.headers.get('Retry-After', 60))))
                    continue
                response.raise_for_status()
                returned = set()
                with gzip.open(temporary, 'wt', encoding='utf-8') as out:
                    for line in response.iter_lines():
                        if line:
                            game = json.loads(line)
                            game_id = game['id']
                            if game_id not in ids or game_id in returned:
                                raise ValueError('Unexpected or repeated ID in Lichess response')
                            returned.add(game_id)
                            out.write(json.dumps(game, separators=(',', ':')) + '\n')
                if not returned:
                    raise ValueError('The Lichess export returned no games')
                temporary.replace(target)
                return len(returned)
        except (requests.RequestException, ValueError, OSError):
            if attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError('Lichess rate limit persisted across retries; rerun to resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/moves.csv.gz'))
    parser.add_argument('--out-dir', type=Path, default=Path('data/raw/recovered'))
    args = parser.parse_args()
    with gzip.open(args.source, 'rt', encoding='utf-8') as source:
        ids = sorted({row['game_id'] for row in csv.DictReader(source)})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    batches = []
    with requests.Session() as session:
        session.headers.update({'Accept': 'application/x-ndjson', 'Content-Type': 'text/plain',
                                'User-Agent': 'DSC5001-chess-blunder-study/1.0'})
        for start in range(0, len(ids), 250):
            batch = ids[start:start + 250]
            digest = hashlib.sha256(','.join(batch).encode()).hexdigest()[:12]
            target = args.out_dir / f'batch_{start:05d}_{digest}.ndjson.gz'
            batches.append(target.name)
            if target.exists():
                continue
            count = download_batch(session, batch, target)
            print(f'{start + len(batch)}/{len(ids)} requested; {count}/{len(batch)} returned',
                  flush=True)
    manifest = {'requested_game_count': len(ids), 'batch_files': batches,
                'sorted_id_sha256': hashlib.sha256(','.join(ids).encode()).hexdigest()}
    temporary = args.out_dir / 'manifest.part'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.out_dir / 'manifest.json')


if __name__ == '__main__':
    main()
