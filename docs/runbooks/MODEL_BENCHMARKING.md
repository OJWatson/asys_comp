# Model Benchmarking Runbook (NLP / Abstract Screening)

This runbook describes how to run and extend the NLP benchmark used for the e5cr7 screening workflow, including **ASReview Dory** classifier comparisons.

Source-of-truth docs for Dory model inventory:
- https://github.com/asreview/asreview-dory

## What this benchmark compares

`analysis/benchmark_nlp_models.py` compares:

1. **Current baseline**
   - `baseline_lr_word_tfidf`
2. **Current improved model**
   - `improved_calibrated_svm_word_char`
3. **Additional core candidates** (lightweight, reproducible)
   - `candidate_lr_word_char`
   - `candidate_lsa_lr`
   - `candidate_sgd_word_char`
   - `candidate_cnb_word_tfidf`
4. **ASReview Dory classifiers (when available + runnable in this environment)**
   - `dory_xgboost_word_tfidf`
   - `dory_adaboost_word_tfidf`

The benchmark script verifies Dory availability by:
- installed entry points (from `asreview.models.classifiers` / `asreview.models.feature_extractors`), and
- runnable sparse TF-IDF probe fit/predict for documented Dory classifiers.

Blocked models (for example Nemo, Dory neural-network classifiers, or unavailable plugin components) are recorded with explicit reasons.

---

## Why compare Dory models here

Dory extends ASReview with extra classifier/feature-extractor options. We compare feasible Dory classifiers against current project models to answer a practical question:

> Do Dory-provided options improve ranking quality (AP/WSS/recall@k) enough to justify operational complexity?

This keeps model choice evidence-based rather than extension-driven.

---

## Environment setup for Dory benchmarking

Dory is intentionally heavier than the base `.venv` stack. Use a Dory-enabled Python environment for benchmark generation.

Example:

```bash
# from repo root
python3.10 -m venv .venv-dory
source .venv-dory/bin/activate
pip install -U pip
pip install asreview==2.2 asreview-dory==1.2.2

# sanity checks
asreview --version
asreview dory --version
asreview algorithms
```

If you benchmark without Dory installed, the script still runs but records Dory classifiers as blocked/unavailable.

---

## How to run benchmarks

From repo root:

```bash
# Activate Dory-capable env first (recommended for this runbook)
source .venv-dory/bin/activate

# Run benchmark
python analysis/benchmark_nlp_models.py

# Optional smoke check for benchmark outputs
python scripts/smoke_test_benchmarks.py
```

Outputs are written to:

- `analysis/outputs/benchmarks/model_benchmark_fold_metrics.csv`
- `analysis/outputs/benchmarks/model_benchmark_summary.csv`
- `analysis/outputs/benchmarks/model_benchmark_summary.json`
- `analysis/outputs/benchmarks/environment_model_availability.json`
- `analysis/outputs/benchmarks/MODEL_BENCHMARK_REPORT.md`

---

## Full refresh pipeline including benchmark + site artifacts

```bash
# after benchmark outputs are regenerated
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
scripts/run_smoke_test.sh
```

This propagates benchmark outputs into:

- `app/data/artifacts/methods_results.json`
- `app/data/artifacts/run_manifest.json`
- `site/data/artifacts/*` (after build)

---

## Metrics and protocol (fairness)

The benchmark uses **RepeatedStratifiedKFold** so all models (core + Dory) share exactly the same split protocol.

Default protocol:

- Splits: 5
- Repeats: 3
- Random state: 42
- Input: `data/screening_input.xlsx`

Reported metrics:

- `average_precision`
- `roc_auc`
- `precision@10`, `recall@10`
- `precision@20`, `recall@20`
- `precision@50`, `recall@50`
- `wss@95`
- runtime notes (`fit_seconds`, `score_seconds`) and approximate feature-space size

---

## Dory scope and constraints in this benchmark

Included Dory classifiers in this pipeline:
- `xgboost`
- `adaboost`

Skipped Dory classifiers (with explicit reasons in artifacts):
- `dynamic-nn`, `nn-2-layer`, `warmstart-nn`
  - these fail sparse TF-IDF probe (require dense input), making them impractical for this repo’s sparse-text, repeated-CV benchmark protocol.

Dory feature extractors (`sbert`, `mxbai`, `labse`, `multilingual-e5-large`, `gtr-t5-large`, `xlm-roberta-large`, `doc2vec`) are discovered and reported, but transformer-based extractors are not enabled in the default benchmark due model-download/runtime footprint.

---

## How to add a new model

1. Open `analysis/benchmark_nlp_models.py`.
2. Add/update `ModelSpec` entries in `build_specs(...)`.
3. Implement builder logic in `build_model(...)` for the new `builder_key`.
4. Ensure availability logic includes entry-point + runnable-probe checks where relevant.
5. Re-run benchmark and smoke checks:

```bash
python analysis/benchmark_nlp_models.py
python scripts/smoke_test_benchmarks.py
```

6. Refresh app artifacts and rebuild site:

```bash
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

---

## Reproducibility and limitations

- Results are dataset-specific (current e5cr7 snapshot).
- If labels shift or class balance changes, re-run benchmark before interpreting winners.
- Runtime is machine-dependent; compare times **within the same environment**.
- Dory-enabled runs should be generated in a Dory-capable environment and captured with the availability JSON for auditability.
