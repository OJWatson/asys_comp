# Deployment Runbook (Analysis Scope)

This file is now a short index to avoid duplicate operational docs.

## Canonical runbooks

- GitHub Pages deployment: `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md`
- ASReview LAB local/staging path: `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- ASReview LAB live-server path: `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`

## Analysis-specific commands

Full refresh from analysis outputs into app artifacts:

```bash
scripts/run_analysis_and_report_refresh.sh
```

Fast artifact refresh only:

```bash
scripts/run_data_refresh.sh
```

Integrity checks:

```bash
scripts/content_integrity_check.py --artifacts-dir app/data/artifacts
```

For release status, see:
- `analysis/archive/reports/RELEASE_READINESS_REPORT.md`
