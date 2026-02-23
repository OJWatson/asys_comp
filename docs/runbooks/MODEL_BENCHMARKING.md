# Model Benchmarking Runbook (NLP / Abstract Screening)

This runbook describes the benchmark pipeline used for e5cr7, including **Dory extension comparisons**, **neural variants**, and a staged runtime protocol.

Source-of-truth Dory inventory:
- https://github.com/asreview/asreview-dory

## What this benchmark compares

`analysis/benchmark_nlp_models.py` now evaluates three groups:

1. **Lightweight stage (default: 5x3 CV)**
   - Baseline + improved model
   - Advanced sparse-text linear candidates
2. **Heavy stage (default: 3x1 CV, runtime-bounded)**
   - Practical neural baselines (`candidate_mlp_lsa`, MiniLM+MLP)
   - MiniLM embedding + LR
   - Dory classifiers (`xgboost`, `adaboost`, `dynamic-nn`, `nn-2-layer`, `warmstart-nn`) when runnable
3. **Blocked/skipped model slots**
   - Explicitly recorded with reasons (dependency missing, probe failure, runtime budget skip, etc.)

The run emits a full combo sweep matrix with status per model: `attempted/succeeded/failed/skipped`.

---

## Runtime controls (explicit)

Key controls:

- `--lightweight-splits`, `--lightweight-repeats`
- `--heavy-splits`, `--heavy-repeats`
- `--disable-heavy-stage`
- `--max-heavy-models`
- `--max-total-runtime-seconds`
- `--per-model-runtime-seconds`

Defaults are set for reproducible CPU runs while still allowing heavier model attempts.

---

## Environment setup

### Lightweight-only environment

```bash
source .venv/bin/activate
pip install -r requirements.lock.txt
```

### Heavy/Dory-enabled environment

```bash
source .venv-dory/bin/activate
pip install -r requirements.lock.txt
pip install -r requirements-optional-heavy-nlp.lock.txt
pip install -r requirements-dory.lock.txt
```

---

## How to run benchmark + smoke checks

```bash
# recommended for full staged sweep
source .venv-dory/bin/activate

python analysis/benchmark_nlp_models.py
python scripts/smoke_test_benchmarks.py
```

Useful alternatives:

```bash
# lightweight-only fast run
python analysis/benchmark_nlp_models.py --disable-heavy-stage

# strict runtime-bounded full run
python analysis/benchmark_nlp_models.py \
  --max-heavy-models 6 \
  --max-total-runtime-seconds 3600 \
  --per-model-runtime-seconds 600
```

---

## Output artifacts

- `analysis/outputs/benchmarks/model_benchmark_fold_metrics.csv`
- `analysis/outputs/benchmarks/model_benchmark_summary.csv`
- `analysis/outputs/benchmarks/model_benchmark_summary.json`
- `analysis/outputs/benchmarks/model_combo_attempt_matrix.csv`
- `analysis/outputs/benchmarks/model_combo_attempt_matrix.json`
- `analysis/outputs/benchmarks/environment_model_availability.json`
- `analysis/outputs/benchmarks/MODEL_BENCHMARK_REPORT.md`

---

## Full refresh path (benchmark → app/site)

```bash
python analysis/benchmark_nlp_models.py
python scripts/smoke_test_benchmarks.py
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
scripts/run_smoke_test.sh
```

This propagates benchmark and combo-matrix outcomes into:
- `app/data/artifacts/methods_results.json`
- `app/data/artifacts/run_manifest.json`

---

## Interpreting Dory + neural results

Use the benchmark summary table for ranking metrics (`AP`, `WSS@95`, `recall@20`, `precision@20`) and use combo matrix statuses to understand coverage and blockers.

When Dory is installed, the benchmark validates each Dory classifier with a small probe before evaluation. Neural Dory models are run on dense TF-IDF→SVD features to stay feasible on CPU.
