#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || true

PGN="${1:-runs/quick_sf_vs_sf.pgn}"
BIN="./tools/bin/bayeselo"

# BayesElo is interactive; we feed it a small script via heredoc.
# 'offset 0 SF1' anchors SF1 at 0 Elo; change the name/value to anchor differently.
"$BIN" <<EOF
readpgn $PGN
elo
mm
ratings
offset 0 SF1
ratings
x
EOF