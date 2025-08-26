#!/usr/bin/env python3
"""
gauntlet.py — run a gauntlet (your engine vs chosen opponents) with cutechess-cli.

Core ideas
- CLI-only (no rating here): produce a PGN you can feed to BayesElo later.
- Hardware-agnostic "publish" mode via node-limited control.
- Guarded fallback via seconds-per-move if an engine ignores nodes.
- Full control via --tc if you want classic time controls.

Prereqs in your repo (defaults, all overrideable):
- tools/bin/cutechess-cli      (built by your bootstrap)
- engines/stockfish            (Homebrew symlink via bootstrap)
- openings/neutral_50.pgn      (or any PGN book)

Examples
---------
# Portable publish control (node-limited), EUT vs SF at several strengths
tools/gauntlet.py \
  --eut engines/my_engine --eut-name MyEngine \
  --sf-nodes 300,1000,3000,15000 \
  --nodes-per-move 15000 \
  --games 200 --concurrency 8

# Guarded fallback (time-per-move) if an engine ignores nodes:
tools/gauntlet.py \
  --eut engines/misbehaving --eut-name BadEngine \
  --sf-nodes 300,1000,3000 \
  --st 0.25 --timemargin 2000 \
  --games 200 --concurrency 8

# Explicit opponents and classic time control:
tools/gauntlet.py \
  --eut engines/my_engine --eut-name MyEngine \
  --opponent Igel=engines/igel --opponent Ethereal=engines/ethereal \
  --tc "5+0.05" \
  --games 100 --concurrency 6
"""
from __future__ import annotations
import argparse, os, shlex, subprocess, sys, datetime
from typing import List

# ---------- utilities ----------

def require_executable(path: str, label: str | None = None) -> str:
    if not (os.path.isfile(path) and os.access(path, os.X_OK)):
        sys.exit(f"❌ Not executable: {path}" + (f" ({label})" if label else ""))
    return path

def require_file(path: str, label: str | None = None) -> str:
    if not os.path.isfile(path):
        sys.exit(f"❌ File not found: {path}" + (f" ({label})" if label else ""))
    return path

def run(cmd: List[str]):
    print("→", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(f"❌ cutechess-cli failed with exit code {proc.returncode}")

def ts_pgn(prefix: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("runs", exist_ok=True)
    return f"runs/{prefix}_{ts}.pgn"

def openings_args(path: str, plies: int, policy: str) -> List[str]:
    return ["-openings", f"file={path}", "format=pgn", "order=random", f"plies={plies}", f"policy={policy}"]

def adjudication_args(draw_mv: int, draw_cnt: int, draw_score: int,
                      resign_cnt: int, resign_score: int,
                      maxmoves: int | None) -> List[str]:
    out = ["-draw", f"movenumber={draw_mv}", f"movecount={draw_cnt}", f"score={draw_score}",
           "-resign", f"movecount={resign_cnt}", f"score={resign_score}"]
    if maxmoves:
        out += ["-maxmoves", str(maxmoves)]
    return out

def control_args(args) -> List[str]:
    base = ["-each", "proto=uci", "ponder=false",
            f"option.Hash={args.hash}", f"option.Threads={args.threads}"]
    # Choose exactly one control style
    if args.nodes_per_move is not None:
        base += ["tc=inf", f"nodes={args.nodes_per_move}"]
    elif args.st is not None:
        base += [f"st={args.st}"]
        if args.timemargin is not None:
            base += [f"timemargin={args.timemargin}"]
    elif args.tc is not None:
        base += [f"tc={args.tc}"]
    else:
        sys.exit("❌ You must specify one control: --nodes-per-move OR --st OR --tc")
    return base

# ---------- engine arg builders ----------

def engine_eut(name: str, cmd_path: str) -> List[str]:
    return ["-engine", f"name={name}", f"cmd={cmd_path}", "proto=uci"]

def engine_sf_nodes(sf_path: str, nodes_list: List[int]) -> List[str]:
    out: List[str] = []
    for n in nodes_list:
        out += ["-engine", f"name=SF_N{n}", f"cmd={sf_path}", "proto=uci", f"nodes={n}"]
    return out

def engine_named(path_map: List[str]) -> List[str]:
    """
    path_map items look like:  Name=/abs/or/relative/path
    """
    out: List[str] = []
    for spec in path_map:
        if "=" not in spec:
            sys.exit("❌ --opponent must be of the form Name=/path/to/bin")
        name, path = spec.split("=", 1)
        out += ["-engine", f"name={name}", f"cmd={require_executable(path, name)}", "proto=uci"]
    return out

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="Run a cutechess gauntlet (EUT vs opponents) and write a PGN.")
    ap.add_argument("--runner", default="tools/bin/cutechess-cli", help="path to cutechess-cli")
    ap.add_argument("--openings", default="openings/neutral_50.pgn", help="opening PGN file")
    ap.add_argument("--plies", type=int, default=12, help="opening plies to play")
    ap.add_argument("--policy", choices=["round","random"], default="round", help="opening pairing policy")
    ap.add_argument("--concurrency", type=int, default=8, help="parallel games")
    ap.add_argument("--threads", type=int, default=1, help="UCI Threads per engine")
    ap.add_argument("--hash", type=int, default=16, help="UCI Hash (MB) per engine")
    ap.add_argument("--pgn", default=None, help="output PGN path (default runs/gauntlet_YYYYmmdd_HHMMSS.pgn)")
    ap.add_argument("--pgn-style", choices=["min","full"], default="min", help="PGN verbosity")
    ap.add_argument("--wait", type=int, default=0, help="cutechess -wait ms before killing stuck engine")
    ap.add_argument("--recover", action="store_true", help="auto-resume on crashes")

    # Control styles (choose one)
    g = ap.add_argument_group("time control (choose one)")
    g.add_argument("--nodes-per-move", type=int, help="portable: nodes per move (sets tc=inf nodes=N)")
    g.add_argument("--st", type=float, help="guarded: seconds per move (e.g., 0.25)")
    g.add_argument("--timemargin", type=int, help="guarded: extra ms grace per move (e.g., 2000 with --st)")
    g.add_argument("--tc", type=str, help='classic tc string, e.g., "5+0.05" or "40/10+0.1"')

    # EUT
    ap.add_argument("--eut", required=True, help="path to your UCI engine binary")
    ap.add_argument("--eut-name", default="EUT", help="display name for your engine")

    # Opponents
    ap.add_argument("--stockfish", default="engines/stockfish", help="path to Stockfish (for --sf-nodes)")
    ap.add_argument("--sf-nodes", default=None, help="CSV list of Stockfish node budgets, e.g., 300,1000,3000")
    ap.add_argument("--opponent", action="append",
                    help="additional opponents as Name=/path/to/bin (repeatable)")

    # Adjudication
    ap.add_argument("--draw-movenumber", type=int, default=80)
    ap.add_argument("--draw-movecount", type=int, default=8)
    ap.add_argument("--draw-score", type=int, default=10)
    ap.add_argument("--resign-movecount", type=int, default=3)
    ap.add_argument("--resign-score", type=int, default=900)
    ap.add_argument("--maxmoves", type=int, default=200)

    # Tournament size
    ap.add_argument("--games", type=int, default=200, help="total games (colors alternate)")
    args = ap.parse_args()

    # Validate basics
    runner = require_executable(args.runner, "cutechess-cli")
    openings = require_file(args.openings, "openings PGN")
    eut = require_executable(args.eut, "EUT")
    if args.sf_nodes:
        require_executable(args.stockfish, "Stockfish")

    # Start assembling command
    pgn_path = args.pgn or ts_pgn("gauntlet")
    cmd: List[str] = [
        runner,
        "-tournament","gauntlet",
        "-concurrency", str(args.concurrency),
        "-pgnout", pgn_path
    ]
    if args.pgn-style == "min":
        cmd.append("min")

    cmd += openings_args(openings, args.plies, args.policy)
    cmd += control_args(args)

    # EUT
    cmd += engine_eut(args.eut_name, eut)

    # Opponents
    if args.sf_nodes:
        nodes = [int(x) for x in args.sf_nodes.split(",")]
        cmd += engine_sf_nodes(args.stockfish, nodes)
    if args.opponent:
        cmd += engine_named(args.opponent)

    # Adjudication & safety
    cmd += adjudication_args(args.draw_movenumber, args.draw_movecount, args.draw_score,
                             args.resign_movecount, args.resign_score, args.maxmoves)
    cmd += ["-games", str(args.games), "-repeat", "-wait", str(args.wait)]
    if args.recover:
        cmd += ["-recover"]

    # Run
    run(cmd)
    print(f"✅ Wrote PGN: {pgn_path}")

if __name__ == "__main__":
    main()
