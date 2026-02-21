#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RUN_REFRESH=1
if [[ "${1:-}" == "--skip-refresh" ]]; then
  RUN_REFRESH=0
fi

if [[ "$RUN_REFRESH" -eq 1 ]]; then
  scripts/run_data_refresh.sh
fi

SITE_DIR="$REPO_ROOT/site"
rm -rf "$SITE_DIR"
mkdir -p "$SITE_DIR"

cp "$REPO_ROOT"/app/*.html "$SITE_DIR"/
cp -r "$REPO_ROOT"/app/static "$SITE_DIR"/static
cp -r "$REPO_ROOT"/app/data "$SITE_DIR"/data

touch "$SITE_DIR/.nojekyll"

echo "GitHub Pages site bundle built at: $SITE_DIR"
