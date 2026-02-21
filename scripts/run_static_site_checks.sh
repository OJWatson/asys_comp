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

if [[ ! -d "$REPO_ROOT/site" ]]; then
  echo "Missing site/ bundle. Run scripts/build_github_pages_site.sh first." >&2
  exit 1
fi

"$PYTHON_BIN" scripts/content_integrity_check.py --artifacts-dir app/data/artifacts
"$PYTHON_BIN" scripts/smoke_test_static_site.py --site-dir site --port 8775
