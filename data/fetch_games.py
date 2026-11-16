#!/usr/bin/env python3
"""
fetch_games.py — DSC5001 Group SixSixGoSmooth

Fetch Lichess rated blitz (180+0) games with engine analysis via the public
API, using SNOWBALL sampling so we cover the whole rating range without a
29 GB download.

Why snowball
------------
We study "blunders under time pressure". The leaderboard alone gives only GMs
(2600+), which would bias the sample. Instead we:

  1. Seed the queue with the leaderboard top-100 (high band).
  2. For every player we pull, we also harvest their OPPONENTS (with ratings)
     from the returned games and push them onto the queue.
  3. Because opponents span the whole rating range, the player pool naturally
     spreads across bands as the snowball grows.

Every player is fetched once (deduped via a seen-set persisted to disk), so the
script is resumable: re-run with the same --out and it keeps going from where it
left off.

Games are saved as NDJSON (one JSON object per line) for build_from_api.py.

Rate limits (anonymous): ~20 games/sec. One request per player + sleep keeps us
polite and avoids HTTP 429.

Usage
-----
    python scripts/fetch_games.py \
        --target-players 150 --max-games 600000 \
        --since 1788220800000 --until 1790812800000 \
        --out data/raw_games.ndjson

    # pilot
    python scripts/fetch_games.py --target-players 10 --out data/raw_pilot.ndjson
"""

import argparse
import json
import os
import sys
import time
from collections import Counter

import requests

UA_HEADERS = {
    "User-Agent": "DSC5001-chess-blunder-study/1.0 (student project; contact via course)",
    "Accept": "application/x-ndjson",
}

API = "https://lichess.org/api"
PERF_TYPE = "blitz"

# Rating bands, for reporting only (we don't need to force-fill them; snowball
# spreads naturally).
RATING_BANDS = [
    (0, 1599, "casual"),
    (1600, 1899, "intermediate"),
    (1900, 2199, "advanced"),
    (2200, 2499, "expert"),
    (2500, 9999, "master"),
]


def get_top_players(n, perf_type=PERF_TYPE):
    r = requests.get(f"{API}/player/top/{n}/{perf_type}", headers=UA_HEADERS, timeout=30)
    r.raise_for_status()
    users = r.json().get("users", [])
    out = []
    for u in users:
        rating = u.get("perfs", {}).get(perf_type, {}).get("rating")
        out.append((u["id"], u["username"], rating))
    return out


def fetch_player_games(username, since, until, max_games=5000):
    params = {
        "since": since,
        "until": until,
        "max": max_games,
        "perfType": PERF_TYPE,
        "rated": "true",
        "analysed": "true",
        "clocks": "true",
        "evals": "true",
        "moves": "true",
        "tags": "true",
        "opening": "false",
        "literate": "false",
    }
    r = requests.get(f"{API}/games/user/{username}", headers=UA_HEADERS,
                     params=params, timeout=120, stream=True)
    if r.status_code == 429:
        raise RuntimeError("429 rate-limited")
    r.raise_for_status()

    games = []
    for line in r.iter_lines(decode_unicode=True):
        line = line.strip()
        if not line:
            continue
        try:
            games.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return games


def opponents_of(game):
    """Yield (id, username, rating) for both players in a game, if present."""
    for color in ("white", "black"):
        p = game["players"].get(color, {})
        u = p.get("user")
        if u and u.get("name") and u.get("id"):
            yield u["id"], u["name"], p.get("rating")


def band_of(rating):
    if rating is None:
        return "unknown"
    for lo, hi, label in RATING_BANDS:
        if lo <= rating <= hi:
            return label
    return "unknown"


def load_seen(seen_path):
    if os.path.exists(seen_path):
        with open(seen_path) as fh:
            return set(line.strip() for line in fh if line.strip())
    return set()


def save_seen(seen_path, seen):
    tmp = seen_path + ".tmp"
    with open(tmp, "w") as fh:
        for u in sorted(seen):
            fh.write(u + "\n")
    os.replace(tmp, seen_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-players", type=int, default=150)
    ap.add_argument("--top-n", type=int, default=100)
    ap.add_argument("--since", type=int, default=1788220800000)
    ap.add_argument("--until", type=int, default=1790812800000)
    ap.add_argument("--max-per-player", type=int, default=3000)
    ap.add_argument("--max-games", type=int, default=600000)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    seen_path = args.out + ".seen"
    seen = load_seen(seen_path)
    print(f"[fetch] resumed: {len(seen)} players already fetched", file=sys.stderr)

    # Seed queue with leaderboard (rating known).
    queue = []  # (id, username, rating_or_None)
    print("[fetch] seeding from leaderboard ...", file=sys.stderr)
    for pid, uname, rating in get_top_players(args.top_n, PERF_TYPE):
        if uname not in seen:
            queue.append((pid, uname, rating))

    print(f"[fetch] seed queue size: {len(queue)}", file=sys.stderr)

    total_games = 0
    fetched_count = 0
    failed = []
    band_counts = Counter()

    # Open output in append mode so a re-run resumes without clobbering.
    out = open(args.out, "a")
    try:
        while queue and fetched_count < args.target_players and total_games < args.max_games:
            # Prefer players from under-represented bands so the sample spreads
            # across the rating range instead of draining the GM seed first.
            def band_key(item):
                return band_counts.get(band_of(item[2]), 0)
            queue.sort(key=band_key)
            pid, username, rating = queue.pop(0)
            if username in seen:
                continue
            seen.add(username)

            try:
                games = fetch_player_games(username, args.since, args.until,
                                           max_games=args.max_per_player)
            except Exception as e:
                print(f"[fetch] FAIL {username}: {e}", file=sys.stderr)
                failed.append(username)
                save_seen(seen_path, seen)
                time.sleep(args.sleep * 2)
                continue

            kept = 0
            for g in games:
                if not g.get("clocks") or not g.get("analysis"):
                    continue
                out.write(json.dumps(g) + "\n")
                kept += 1
                # Harvest opponents for the snowball.
                for oid, oname, orating in opponents_of(g):
                    if oname not in seen:
                        queue.append((oid, oname, orating))

            total_games += kept
            fetched_count += 1

            band = band_of(rating)
            band_counts[band] += 1
            print(f"[fetch] {username:>24} (r={rating}, {band}) -> {kept} games "
                  f"| cum games {total_games} | queue {len(queue)} | fetched {fetched_count}",
                  file=sys.stderr)

            if fetched_count % 20 == 0:
                save_seen(seen_path, seen)
                out.flush()

            time.sleep(args.sleep)
    finally:
        out.close()
        save_seen(seen_path, seen)

    print(f"\n[done] fetched {fetched_count} players, {total_games} games", file=sys.stderr)
    if failed:
        print(f"[done] failed ({len(failed)}): {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
