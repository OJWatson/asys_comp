#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-}"
ASREVIEW_BIN="${ASREVIEW_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$REPO_ROOT/.venv-dory/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv-dory/bin/python"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [[ -z "$ASREVIEW_BIN" ]]; then
  if [[ -x "$REPO_ROOT/.venv-dory/bin/asreview" ]]; then
    ASREVIEW_BIN="$REPO_ROOT/.venv-dory/bin/asreview"
  else
    ASREVIEW_BIN="asreview"
  fi
fi

"$PYTHON_BIN" integration/asreview_dory_hooks.py run-workflow \
  --records data/screening_input.xlsx \
  --dataset-output integration/outputs/dory/dory_simulation_dataset.csv \
  --labels-output integration/outputs/dory/dory_labels_export.csv \
  --prepare-manifest-output integration/outputs/dory/dory_prepare_manifest.json \
  --project-output integration/outputs/dory/dory_simulation.asreview \
  --sequence-output integration/outputs/dory/dory_simulation_sequence.csv \
  --summary-output integration/outputs/dory/dory_simulation_summary.json \
  --simulation-meta-output integration/outputs/dory/dory_simulation_run_meta.json \
  --asreview-bin "$ASREVIEW_BIN" \
  --classifier "${DORY_CLASSIFIER:-xgboost}" \
  --feature-extractor "${DORY_FEATURE_EXTRACTOR:-tfidf}" \
  --querier "${DORY_QUERIER:-max}" \
  --balancer "${DORY_BALANCER:-balanced}" \
  --n-prior-included "${DORY_N_PRIOR_INCLUDED:-1}" \
  --n-prior-excluded "${DORY_N_PRIOR_EXCLUDED:-1}" \
  --seed "${DORY_SEED:-42}" \
  --n-stop "${DORY_N_STOP:-80}" \
  --verbose "${DORY_VERBOSE:-1}" \
  "$@"
