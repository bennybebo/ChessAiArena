#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$REPO_ROOT/tools/vendor"
BIN="$REPO_ROOT/tools/bin"

mkdir -p "$BIN"

# 1) System deps
# Qt + CMake for cutechess; ninja speeds up builds (optional)
brew install qt cmake ninja || true

# 2) Build cutechess-cli (CMake)
pushd "$VENDOR/cutechess"
mkdir -p build && cd build
# If CMake can't find Qt, add: -DCMAKE_PREFIX_PATH="$(brew --prefix qt)"
cmake -G Ninja ..
ninja
# Find the CLI binary and link it into tools/bin
CUTE_BIN="$(find . -name cutechess-cli -type f | head -n1)"
ln -sf "$PWD/$CUTE_BIN" "$BIN/cutechess-cli"
popd

# 3) BayesElo (download source and build)
pushd "$VENDOR"
mkdir -p bayeselo && cd bayeselo
curl -L -o bayeselo.tar.bz2 https://www.remi-coulom.fr/Bayesian-Elo/bayeselo.tar.bz2
tar xjf bayeselo.tar.bz2
# The archive unpacks into a directory; enter it (name can vary, so cd to the only subdir)
cd "$(find . -maxdepth 1 -type d -not -name '.' | head -n1)"
make
ln -sf "$PWD/bayeselo" "$BIN/bayeselo"
popd

echo "Done. Binaries:"
ls -l "$BIN" "$REPO_ROOT/engines" || true