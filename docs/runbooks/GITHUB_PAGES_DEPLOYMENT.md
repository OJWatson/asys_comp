# GitHub Pages Deployment Runbook (Static Reviewer Site)

## Deployment model
This project now uses a **hybrid deployment split**:

- **GitHub Pages (static):** reviewer-facing explainer/results/risk/planner pages + generated JSON artifacts.
- **Non-static services (elsewhere):** ASReview LAB container, label sync/reconciliation hooks, retraining pipeline jobs.

This keeps reviewer content low-friction and globally accessible while preserving operational workflows in controlled runtime environments.

## Repository structure for Pages

```text
app/
  index.html
  asreview-explainer.html
  methods-results.html
  why-more-review.html
  how-many-more.html
  static/
  data/artifacts/
scripts/
  build_github_pages_site.sh
  run_static_site_checks.sh
  smoke_test_static_site.py
  content_integrity_check.py
.github/workflows/
  deploy-github-pages.yml
site/                      # generated build artifact (publish target)
```

## Local build and preview
```bash
cd /home/kana/git/asys/screening-model
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
python3 -m http.server 8080 --directory site
```

Open: `http://127.0.0.1:8080/`

## CI publishing workflow
Workflow file: `.github/workflows/deploy-github-pages.yml`

Pipeline stages:
1. Install pinned Python dependencies (`requirements.lock.txt`).
2. Refresh app artifacts (`scripts/run_data_refresh.sh`).
3. Build Pages bundle (`scripts/build_github_pages_site.sh --skip-refresh`).
4. Validate integrity + static smoke (`scripts/run_static_site_checks.sh`).
5. Upload `site/` as Pages artifact.
6. Deploy to GitHub Pages via `actions/deploy-pages`.

## GitHub repository settings
In GitHub repo settings:
1. **Settings → Pages → Source**: select **GitHub Actions**.
2. Ensure branch protections allow workflow run on `main`.
3. (Optional) Configure custom domain and enforce HTTPS.

## Non-static components (explicit separation)
- ASReview LAB local/staging operations: `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- Integration roundtrip checks: `scripts/run_lab_roundtrip_checks.sh`
- Full local deployment runbook: `analysis/DEPLOYMENT_RUNBOOK.md`

## Failure triage
- If static smoke fails: run `scripts/run_static_site_checks.sh` locally and inspect missing/invalid files under `site/`.
- If checksum integrity fails: rerun `scripts/run_data_refresh.sh` and confirm `app/data/artifacts/run_manifest.json` is regenerated.
- If Pages deploy job fails but build passes: verify repo Pages source is set to **GitHub Actions**.
