# DEPLOYMENT_RUNBOOK

This runbook covers deployment of the reviewer-facing web deliverable with a **GitHub Pages-first** strategy and explicit separation for non-static components.

## Deployment strategy (current)
- **Static reviewer site (primary):** GitHub Pages from `site/` bundle.
- **Non-static operations:** local/staging runtime for ASReview LAB + integration hooks.

## Deployment status dashboard

| Component | Status | Command to verify |
|---|---|---|
| Analysis + app artifact refresh pipeline | Ready | `scripts/run_analysis_and_report_refresh.sh` |
| Artifact integrity checks | Ready | `scripts/content_integrity_check.py --artifacts-dir app/data/artifacts` |
| GitHub Pages static site bundling | Ready | `scripts/build_github_pages_site.sh` |
| Static bundle smoke checks | Ready | `scripts/run_static_site_checks.sh` |
| GitHub Actions Pages publish workflow | Ready | `.github/workflows/deploy-github-pages.yml` |
| ASReview LAB local scaffolding | Ready (scaffold) | `cd infra/asreview-lab && docker compose up --build -d` |
| Queue export/sync/reconcile hooks | Ready | `scripts/run_lab_roundtrip_checks.sh` |

## 0) Prerequisites
- Python 3.10+
- Optional: Docker + Docker Compose (ASReview LAB scaffolding)
- GitHub repository with Pages enabled (source: **GitHub Actions**)

## 1) Setup environment (pinned)
```bash
cd /home/kana/git/asys/screening-model
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.lock.txt
```

## 2) Refresh analysis outputs + app artifacts
```bash
cp config/app_refresh_config.example.json config/app_refresh_config.json
scripts/run_analysis_and_report_refresh.sh
```
Optional faster refresh (skip model reruns):
```bash
scripts/run_data_refresh.sh
```
Expected outputs:
- `app/data/artifacts/overview.json`
- `app/data/artifacts/methods_results.json`
- `app/data/artifacts/fn_fp_risk.json`
- `app/data/artifacts/simulation_planner.json`
- `app/data/artifacts/run_manifest.json`

## 3) Local smoke test (app server)
```bash
scripts/run_smoke_test.sh
```
Expected message:
- `Smoke test passed: artifacts + all reviewer pages are reachable.`

## 4) Build GitHub Pages static bundle
```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
```
Expected outputs:
- `site/index.html`
- `site/asreview-explainer.html`
- `site/methods-results.html`
- `site/why-more-review.html`
- `site/how-many-more.html`
- `site/data/artifacts/*.json`
- `site/.nojekyll`

Preview locally:
```bash
python3 -m http.server 8080 --directory site
```

## 5) GitHub Actions publishing
Workflow file:
- `.github/workflows/deploy-github-pages.yml`

Publishing flow:
1. Push changes to `main` (or run `workflow_dispatch`).
2. Workflow refreshes artifacts, builds `site/`, runs static checks.
3. Workflow uploads `site/` and deploys via `actions/deploy-pages`.

Repository settings prerequisite:
- **Settings → Pages → Source = GitHub Actions**

## 6) ASReview LAB local scaffolding (non-static path)
```bash
cd infra/asreview-lab
cp .env.example .env
docker compose up --build -d
```
Verify:
```bash
docker compose ps
curl -I http://127.0.0.1:5000
```

## 7) Integration hook workflow (export/sync/reconcile)
From repo root:
```bash
scripts/run_lab_roundtrip_checks.sh
```
Generated outputs:
- `integration/outputs/lab_queue_export_manifest.json`
- `integration/outputs/lab_labels_snapshot.json`
- `integration/outputs/lab_roundtrip_report.json`

## 8) Shutdown LAB
```bash
cd infra/asreview-lab
docker compose down
```

## 9) Troubleshooting
- If page content is stale: rerun `scripts/run_data_refresh.sh` and rebuild with `scripts/build_github_pages_site.sh`.
- If static smoke fails on port conflict: run `./.venv/bin/python scripts/smoke_test_static_site.py --site-dir site --port 8785`.
- If checksum integrity fails: regenerate artifacts and re-check `app/data/artifacts/run_manifest.json`.
- If Pages deploy job fails despite successful build: confirm GitHub Pages source is set to **GitHub Actions**.
