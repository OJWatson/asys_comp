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

"$PYTHON_BIN" integration/asreview_lab_hooks.py export-queue \
  --ranking analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --output infra/asreview-lab/data/queue_for_lab.csv \
  --manifest-output integration/outputs/lab_queue_export_manifest.json

"$PYTHON_BIN" integration/asreview_lab_hooks.py sync-labels \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_labels_snapshot.json

"$PYTHON_BIN" integration/asreview_lab_hooks.py reconcile-roundtrip \
  --queue infra/asreview-lab/data/queue_for_lab.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_roundtrip_report.json
