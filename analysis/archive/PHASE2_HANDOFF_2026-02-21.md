# PHASE2_HANDOFF

Date: 2026-02-21

## Objective covered
Continue beyond MVP with production-readiness emphasis, plus OJ update to prioritize GitHub Pages-compatible deployment.

## What changed

### 1) GitHub Pages-first static deployment path
- Refactored app pages for static hosting compatibility (relative links/assets/data fetches).
- Added `app/index.html` redirect entry point.
- Added static site bundle build script: `scripts/build_github_pages_site.sh`.
- Added static smoke validator: `scripts/smoke_test_static_site.py`.
- Added one-command static validation runner: `scripts/run_static_site_checks.sh`.
- Added local Pages preview helper: `scripts/run_github_pages_preview.sh`.

### 2) CI publishing workflow for Pages
- Added workflow: `.github/workflows/deploy-github-pages.yml`.
- Workflow steps: dependency install -> artifact refresh -> site build -> static checks -> upload Pages artifact -> deploy Pages.

### 3) Reproducibility/ops hardening
- Added `scripts/content_integrity_check.py`:
  - validates run manifest artifact checksums,
  - validates recommendation target coherence,
  - validates FN/FP baseline row presence.
- Wired integrity check into refresh scripts:
  - `scripts/run_data_refresh.sh`
  - `scripts/run_analysis_and_report_refresh.sh`
  - `scripts/run_mvp_refresh_and_smoke.sh`

### 4) ASReview LAB integration improvements beyond basic hooks
- Enhanced `integration/asreview_lab_hooks.py`:
  - `export-queue` now emits queue manifest (checksum/distribution/score-range)
  - `sync-labels` retained with robust normalization
  - new `reconcile-roundtrip` command for queue-vs-label integrity/completion checks
- Added wrapper: `scripts/run_lab_roundtrip_checks.sh`
- New generated artifacts:
  - `integration/outputs/lab_queue_export_manifest.json`
  - `integration/outputs/lab_roundtrip_report.json`

### 5) Documentation updates
- Updated deployment runbook: `analysis/DEPLOYMENT_RUNBOOK.md`
- Added Pages runbook: `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md`
- Updated LAB runbook: `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- Updated integration docs: `integration/README.md`, `infra/asreview-lab/README.md`
- Updated environment/app docs: `docs/ENVIRONMENT_SETUP.md`, `app/README.md`

## Exact run commands used in this phase
```bash
cd /home/kana/git/asys/screening-model
scripts/run_data_refresh.sh
scripts/run_smoke_test.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
scripts/run_lab_roundtrip_checks.sh
```

## Key output artifacts
- Static deploy bundle: `site/`
- Pages workflow: `.github/workflows/deploy-github-pages.yml`
- Artifact integrity checks: `scripts/content_integrity_check.py`
- Static smoke checks: `scripts/smoke_test_static_site.py`
- LAB reconciliation output: `integration/outputs/lab_roundtrip_report.json`

## Remaining blockers / next actions
1. **External/GitHub settings blocker:** GitHub Pages must be set to **Source = GitHub Actions** in repository settings for live publish.
2. **Repo governance blocker:** required-check enforcement on PRs (for P0-06 completion) must be configured in branch protection rules.
3. **Deferred platform scope:** API/DB/auth model lifecycle services remain unimplemented (post-MVP architecture milestones).
