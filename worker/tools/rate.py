#!/usr/bin/env python3
"""
rate.py v0 — Relative Elo rater (mean-centered)

- Input: a PGN of finished games.
- Output (stdout): JSON with relative (mean-centered) Elo and sigma per player.
- No anchors, no calibration. Errors go to stderr and non-zero exit.

Usage:
  rate.py --pgn runs/gauntlet_....pgn
  rate.py --pgn runs/gauntlet_....pgn --engine-name EUT
  rate.py --pgn runs/... --bayeselo tools/bin/bayeselo
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, shlex
from typing import Dict, Tuple, List

def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)

def run_bayeselo(bayeselo_bin: str, pgn: str) -> str:
    script = "readpgn {p}\nelo\nmm\nratings\nx\n".format(p=pgn)
    try:
        proc = subprocess.Popen(
            [bayeselo_bin],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        die(f"❌ BayesElo not found: {bayeselo_bin}")
    out, _ = proc.communicate(script)
    if proc.returncode != 0:
        die(f"❌ BayesElo failed ({proc.returncode})\n{out}")
    return out

def parse_ratings(output: str) -> Dict[str, Tuple[float, float]]:
    """
    Parse common BayesElo 'ratings' table formats.
    Returns { name: (elo, sigma) }.
    """
    ratings: Dict[str, Tuple[float, float]] = {}
    lines = output.splitlines()

    # Pattern A: columns with rank, name, elo, err
    pat_cols = re.compile(r'^\s*\d+\s+(.+?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\b')
    # Pattern B: "Name : 1234 +/- 35"
    pat_pm   = re.compile(r'^\s*(.+?)\s*:\s*(-?\d+(?:\.\d+)?)\s*\+/\-\s*(\d+(?:\.\d+)?)\s*$')
    # Fallback: "Name  Elo  Err"
    pat_fb   = re.compile(r'^\s*(.+?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$')

    # Try to start after a header line that mentions Name and Elo
    start = 0
    for i, ln in enumerate(lines):
        if ("Name" in ln) and ("Elo" in ln):
            start = i + 1
            break

    for ln in lines[start:]:
        ln = ln.rstrip()
        if not ln.strip():
            continue
        m = pat_cols.match(ln) or pat_pm.match(ln) or pat_fb.match(ln)
        if m:
            name = m.group(1).strip()
            elo  = float(m.group(2))
            err  = float(m.group(3))
            ratings[name] = (elo, err)

    if not ratings:
        tail = "\n".join(lines[-40:])
        die("❌ Could not parse BayesElo ratings output.\n--- tail ---\n" + tail)

    return ratings

def mean_center(ratings: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float]]:
    if not ratings:
        return ratings
    mean = sum(elo for elo, _ in ratings.values()) / len(ratings)
    return {name: (elo - mean, sigma) for name, (elo, sigma) in ratings.items()}

def main():
    ap = argparse.ArgumentParser(description="Relative Elo rater (mean-centered) using BayesElo.")
    ap.add_argument("--pgn", required=True, help="path to PGN file")
    ap.add_argument("--bayeselo", default="tools/bin/bayeselo", help="path to bayeselo binary")
    ap.add_argument("--engine-name", help="if set, only output this engine's row")
    args = ap.parse_args()

    if not os.path.isfile(args.pgn):
        die(f"❌ PGN not found: {args.pgn}")
    if not (os.path.isfile(args.bayeselo) and os.access(args.bayeselo, os.X_OK)):
        die(f"❌ BayesElo not executable: {args.bayeselo}")

    raw_out = run_bayeselo(args.bayeselo, args.pgn)
    raw = parse_ratings(raw_out)  # {name: (elo, sigma)}
    rel = mean_center(raw)

    # Build JSON payload
    rows: List[dict] = []
    for name, (elo, sigma) in sorted(rel.items(), key=lambda kv: kv[1][0], reverse=True):
        rows.append({"name": name, "elo": elo, "sigma": sigma})

    payload = {
        "version": "0",
        "mode": "relative-only",
        "pgn": args.pgn,
        "ratings": rows,
        "notes": "Relative Elo, mean-centered; not calibrated to any external scale."
    }

    if args.engine_name:
        row = next((r for r in rows if r["name"] == args.engine_name), None)
        if not row:
            die(f"❌ engine '{args.engine_name}' not found among players: {[r['name'] for r in rows]}")
        print(json.dumps({
            "version": "0",
            "mode": "relative-only",
            "pgn": args.pgn,
            "engine": row,
            "notes": "Relative Elo, mean-centered; not calibrated."
        }))
    else:
        print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
