# Environment Setup (Pinned)

## 1) Create and activate virtualenv

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 2) Install pinned dependencies

```bash
pip install -r requirements.lock.txt
```

## 3) Prepare local config

```bash
cp config/app_refresh_config.example.json config/app_refresh_config.json
```

## 4) Refresh app artifacts

```bash
scripts/run_data_refresh.sh
```

(Full end-to-end analysis rerun, including NLP benchmark refresh)

```bash
scripts/run_analysis_and_report_refresh.sh
python scripts/smoke_test_benchmarks.py
```

## 5) Run smoke tests

```bash
scripts/run_smoke_test.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

## 6) Optional: ASReview Dory dedicated environment

```bash
scripts/setup_asreview_dory_env.sh
scripts/run_asreview_dory_workflow.sh
scripts/run_dory_smoke_test.sh
```

This uses `.venv-dory` and `requirements-dory.lock.txt` to avoid destabilizing the base env.

## 7) Run local app

```bash
scripts/run_web_app.sh
```

Open: `http://127.0.0.1:8000/` (compendium home)

## 8) LAB integration checks

```bash
scripts/run_lab_roundtrip_checks.sh
```

---

See also:
- `README.md`
- `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md`
- `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- `docs/runbooks/ASREVIEW_DORY_INTEGRATION.md`
