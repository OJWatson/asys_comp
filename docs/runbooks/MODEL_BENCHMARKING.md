# Model Benchmarking Runbook (NLP / Abstract Screening)

This runbook describes how to run and extend the NLP benchmark used for the e5cr7 screening workflow.

## What this benchmark compares

`analysis/benchmark_nlp_models.py` compares:

1. **Current baseline**
   - `baseline_lr_word_tfidf`
2. **Current improved model**
   - `improved_calibrated_svm_word_char`
3. **Additional candidate models**
   - Lightweight candidates (always benchmarked by default):
     - `candidate_lr_word_char`
     - `candidate_calibrated_sgd_word_char`
     - `candidate_lr_elasticnet_word_char`
     - `candidate_linear_svc_isotonic_word_char`
     - `candidate_lsa_lr`
     - `candidate_sgd_word_char`
     - `candidate_cnb_word_tfidf`
   - Optional heavy candidate (auto-enabled only when dependency exists):
     - `candidate_st_minilm_lr` (requires `sentence-transformers`)

It also records blocked models (for example **ASReview Nemo** or optional heavy models) when required extensions/dependencies are not present.

---

## How to run benchmarks

From repo root:

```bash
# Activate environment first
source .venv/bin/activate

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
scripts/run_analysis_and_report_refresh.sh
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

This ensures benchmark outputs are propagated into:

- `app/data/artifacts/methods_results.json`
- `app/data/artifacts/run_manifest.json`
- `site/data/artifacts/*` (after build)

---

## Metrics and protocol

The benchmark uses **RepeatedStratifiedKFold** to keep comparisons fair across models.

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

## How to add a new model

1. Open `analysis/benchmark_nlp_models.py`.
2. Add a `ModelSpec` entry in `build_specs()`.
3. Implement builder logic in `build_model(...)` for the new `builder_key`.
4. Re-run benchmark and smoke checks:

```bash
python analysis/benchmark_nlp_models.py
python scripts/smoke_test_benchmarks.py
```

5. Refresh app artifacts and rebuild site:

```bash
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

---

## Reproducibility and limitations

- Lightweight defaults are deliberate (CPU-only, scikit-learn-first).
- Results are dataset-specific (300 records in current e5cr7 snapshot).
- If class balance shifts or labels are updated, re-run benchmark before interpreting winners.
- Runtime is machine-dependent; compare times **within the same environment**.

---

## Heavy/optional models (including Nemo)

If heavy models or Nemo are unavailable:

1. Keep benchmark running with lightweight default model set.
2. Record blockers in `analysis/outputs/benchmarks/environment_model_availability.json`.
3. Surface blocker reason in `methods_results.json` so the website remains transparent.

### Nemo enablement diagnosis (current environment)

Observed state from environment discovery:

- ASReview version: `2.2`
- ASReview extras exposed: `dev`, `docs`, `lint`, `test` (no `nemo` extra)
- Registered classifiers: `logistic`, `nb`, `rf`, `svm` (no `nemo` entry point)
- Nemo modules import check: none available (`asreview_nemo`, `asreviewcontrib.*.nemo`, `asreview_models.nemo`)

Install attempts run during this update:

```bash
pip install "asreview[nemo]"   # warns: asreview 2.2 does not provide the extra 'nemo'
pip install asreview-nemo       # no matching distribution found
pip install asreview-models     # no matching distribution found
```

Conclusion: Nemo is currently **blocked by missing extension distribution** in this environment.

### Optional heavy stack instructions

To enable heavier benchmark slots (including `candidate_st_minilm_lr` and ASReview dory-powered models), install:

```bash
source .venv/bin/activate
pip install -r requirements-optional-heavy-nlp.lock.txt
```

This optional stack intentionally lives outside `requirements.lock.txt` because it pulls large dependencies (torch/transformers).

When a Nemo extension becomes available:

1. Install the Nemo extension package in the active benchmark environment.
2. Confirm detection in `environment_model_availability.json` (`environment.nemo.status == "available"`).
3. Add a Nemo model builder/evaluation path in `analysis/benchmark_nlp_models.py`.
4. Re-run benchmark + site refresh.
