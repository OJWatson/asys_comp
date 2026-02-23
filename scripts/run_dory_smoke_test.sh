#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

DORY_PYTHON="${DORY_PYTHON:-$REPO_ROOT/.venv-dory/bin/python}"
ASREVIEW_BIN="${ASREVIEW_BIN:-$REPO_ROOT/.venv-dory/bin/asreview}"

"$PYTHON_BIN" scripts/smoke_test_dory_integration.py \
  --dory-python "$DORY_PYTHON" \
  --asreview-bin "$ASREVIEW_BIN" \
  --n-stop "${DORY_N_STOP:-30}"
