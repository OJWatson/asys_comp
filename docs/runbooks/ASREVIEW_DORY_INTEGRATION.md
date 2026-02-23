# ASReview Dory Integration Runbook

## Purpose in this repository

ASReview Dory is used here as an **alternative ASReview model stack** for:

1. trying stronger/modern classifiers/feature extractors than the default stack,
2. running reproducible simulation checks on ASYS screening data,
3. exporting Dory run outputs back into versioned repo artifacts for audit and follow-up planning.

This runbook focuses on the operational path implemented in:

- `integration/asreview_dory_hooks.py`
- `scripts/setup_asreview_dory_env.sh`
- `scripts/run_asreview_dory_workflow.sh`
- `scripts/run_dory_smoke_test.sh`

---

## 1) Install/setup (reproducible)

### Why a separate env?

`asreview-dory` has a much heavier dependency stack (ASReview LAB runtime + Torch/Transformers/XGBoost) than the base analysis environment.
To avoid destabilizing the main project venv, use a dedicated environment.

### Create the Dory environment

```bash
scripts/setup_asreview_dory_env.sh
```

What this does:

- creates `.venv-dory`
- installs pinned dependencies from `requirements-dory.lock.txt`
- verifies plugin registration with `asreview --version`, `asreview dory --version`, and `asreview algorithms`

> Pinset note: `requirements-dory.lock.txt` is validated on Linux x86_64 (this repo host baseline). If you run on a different OS/arch, regenerate a platform-specific lock.

### Manual equivalent

```bash
python3.10 -m venv .venv-dory
source .venv-dory/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dory.lock.txt
asreview --version
asreview dory --version
asreview algorithms
```

---

## 2) Data preparation for Dory-compatible workflow

The integration hook standardizes inputs into ASReview tabular schema with:

- `record_id`
- `title`
- `abstract`
- `included` (0/1 or blank)

### A) Prepare directly from canonical ASYS spreadsheet

```bash
.venv-dory/bin/python integration/asreview_dory_hooks.py prepare-dataset \
  --records data/screening_input.xlsx \
  --dataset-output integration/outputs/dory/dory_simulation_dataset.csv \
  --labels-output integration/outputs/dory/dory_labels_export.csv \
  --manifest-output integration/outputs/dory/dory_prepare_manifest.json \
  --require-complete-labels
```

### B) Prepare from ranking + external labels (LAB/CrowdScreen export)

```bash
.venv-dory/bin/python integration/asreview_dory_hooks.py prepare-dataset \
  --records analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --dataset-output integration/outputs/dory/dory_dataset_from_lab.csv \
  --manifest-output integration/outputs/dory/dory_prepare_from_lab_manifest.json
```

If labels are partial, omit `--require-complete-labels`.
For ASReview `simulate`, labels must be complete.

---

## 3) Run Dory-backed screening flow (practical callable path)

### One-shot workflow (prepare -> simulate -> export)

```bash
scripts/run_asreview_dory_workflow.sh
```

Default one-shot settings:

- classifier: `xgboost` (Dory)
- feature extractor: `tfidf` (lightweight, no model download)
- querier: `max`
- balancer: `balanced`
- priors: 1 included / 1 excluded

### Explicit simulation command

```bash
.venv-dory/bin/python integration/asreview_dory_hooks.py run-simulate \
  --dataset integration/outputs/dory/dory_simulation_dataset.csv \
  --project-output integration/outputs/dory/dory_simulation.asreview \
  --asreview-bin .venv-dory/bin/asreview \
  --classifier xgboost \
  --feature-extractor tfidf \
  --n-prior-included 1 \
  --n-prior-excluded 1 \
  --seed 42 \
  --n-stop 80
```

### Optional model cache / inventory

```bash
.venv-dory/bin/asreview dory list
.venv-dory/bin/asreview dory cache sbert xgboost
```

---

## 4) Export outputs back into repo artifacts

```bash
.venv-dory/bin/python integration/asreview_dory_hooks.py export-results \
  --project integration/outputs/dory/dory_simulation.asreview \
  --sequence-output integration/outputs/dory/dory_simulation_sequence.csv \
  --summary-output integration/outputs/dory/dory_simulation_summary.json
```

Produced artifacts:

- `integration/outputs/dory/dory_simulation_sequence.csv`:
  per-label action sequence with cumulative relevant found and recall-at-step.
- `integration/outputs/dory/dory_simulation_summary.json`:
  compact run summary for reporting and handoff.
- `integration/outputs/dory/dory_simulation_run_meta.json`:
  command/runtime metadata from simulation execution.

---

## 5) Multi-reviewer + kappa pathway (CrowdScreen / LAB)

Use this repo’s operational split:

1. **Queue generation**
   - existing queue export via `integration/asreview_lab_hooks.py export-queue`
2. **Reviewer assignment in LAB/CrowdScreen**
   - enforce overlap fraction (typically 20–30%)
3. **Label extraction and normalization**
   - `integration/asreview_lab_hooks.py sync-labels`
4. **Roundtrip integrity checks**
   - `integration/asreview_lab_hooks.py reconcile-roundtrip`
5. **Dory simulation / stress test**
   - convert merged records+labels via `asreview_dory_hooks.py prepare-dataset`
   - run Dory simulation to compare yield/recall trajectory under alternative model components
6. **Kappa/adjudication governance**
   - compute agreement externally from overlap labels (pairwise kappa)
   - only promote automation if kappa and audit gates remain stable

Related playbook:

- `docs/SCALING_PLAYBOOK_ASREVIEW_CROWDSCREEN_DORY.md`

---

## 6) Validation commands

Base repo checks:

```bash
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
scripts/run_smoke_test.sh
```

Dory-specific smoke:

```bash
scripts/run_dory_smoke_test.sh
```

---

## 7) Known boundaries / blockers

1. **Simulation is not live multi-user screening**
   - `asreview simulate` is a replay/simulation path over labeled data.
   - True live multi-reviewer operations still occur in LAB/CrowdScreen deployment.

2. **Heavy dependency footprint**
   - Dory stack is substantially larger than base project dependencies.
   - Use dedicated `.venv-dory` and pinned lockfile.

3. **Transformer-based Dory feature extractors require model downloads**
   - options like `sbert`, `labse`, `multilingual-e5-large` may need network access and more RAM/CPU/GPU.
   - use `tfidf` for lightweight smoke and CI-safe checks.

4. **ASReview simulate requires fully labeled datasets**
   - if labels are incomplete, prepare step succeeds but simulate should not be used until labels are complete.

---

## 8) Troubleshooting

### `Dataset ... got dataset without any labels`

Cause: label column missing or tokens not normalized.
Fix: run `prepare-dataset` and inspect `dory_prepare_manifest.json` to confirm labeled row counts.

### `Project path is not empty`

Cause: ASReview output target already exists (`.asreview` or `.asreview.tmp`).
Fix: remove stale output or use a fresh `--project-output` path.

### Dory algorithms not listed in `asreview algorithms`

Cause: wrong interpreter/environment.
Fix: use `.venv-dory/bin/asreview` and verify with `asreview dory --version`.

### Slow runtime / memory pressure

- reduce `--n-stop`
- keep `--feature-extractor tfidf`
- avoid large transformer models unless required for benchmark runs
