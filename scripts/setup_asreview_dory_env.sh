#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv-dory}"
REQ_FILE="${REQ_FILE:-$REPO_ROOT/requirements-dory.lock.txt}"

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Missing lock file: $REQ_FILE" >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
pip install -r "$REQ_FILE"

"$VENV_DIR/bin/asreview" --version
"$VENV_DIR/bin/asreview" dory --version
"$VENV_DIR/bin/asreview" algorithms

echo

echo "ASReview Dory environment ready: $VENV_DIR"
echo "Use it with: source $VENV_DIR/bin/activate"
