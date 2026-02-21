#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT="${PORT:-8080}"

scripts/build_github_pages_site.sh

echo "Serving GitHub Pages preview at http://127.0.0.1:${PORT}"
python3 -m http.server "$PORT" --directory site
