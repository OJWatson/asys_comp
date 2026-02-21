# ASReview Screening Model Platform

Release-ready repository for a two-path delivery model:

1. **GitHub Pages static explainer site** for transparent reviewer communication.
2. **ASReview LAB runtime path** for active screening operations and label roundtrips.

---

## Project purpose

This repository packages the analysis outputs, reviewer-facing narrative, and operational hooks needed to:

- explain model performance and residual-risk tradeoffs,
- support staged screening decisions,
- move screened labels through a repeatable ASReview LAB loop,
- publish an auditable static site from reproducible artifacts.

---

## Architecture split

| Path | What it serves | Location | Runtime |
|---|---|---|---|
| GitHub Pages (static) | Explainer + methods + FN/FP framing + planner pages | `app/` → built to `site/` | GitHub Actions + Pages |
| ASReview LAB (live) | Reviewer labeling runtime | `infra/asreview-lab/` | Docker Compose / live server |
| Integration bridge | Queue export, label sync, reconciliation | `integration/asreview_lab_hooks.py` | Local/server Python |

---

## Repository layout

- `analysis/` reproducible model outputs and reports
- `app/` static web app source and generated JSON artifacts (`app/data/artifacts/`)
- `docs/runbooks/` deployment runbooks (Pages + LAB local/live)
- `infra/asreview-lab/` LAB container scaffolding and config templates
- `integration/` queue/label integration hooks
- `scripts/` build, refresh, smoke, and integrity checks

Historical planning/progress material is archived under `analysis/archive/`.

---

## Quickstart (local)

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.lock.txt

cp config/app_refresh_config.example.json config/app_refresh_config.json
scripts/run_data_refresh.sh
scripts/run_smoke_test.sh
```

Run local app:

```bash
scripts/run_web_app.sh
```

---

## Deployment paths

### A) GitHub Pages (static explainer)

```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
```

CI deploy workflow: `.github/workflows/deploy-github-pages.yml`.

Full runbook and go-live checklist:
- `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md`

### B) ASReview LAB runtime

Local/staging:
- `docs/runbooks/ASREVIEW_LAB_LOCAL.md`

Live server hardening + manual cutover steps:
- `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`

---

## Status and roadmap

### Current status
- ✅ Repository hygiene hardened (tracked local env/build artifacts removed).
- ✅ Static Pages pipeline is build- and deploy-ready.
- ✅ LAB integration hooks support export/sync/reconcile loop.
- ⚠️ Final production go-live still requires environment-specific manual steps (domain/TLS/secrets/ops ownership).

### Near-term roadmap
1. Turn on GitHub Pages source = **GitHub Actions** and validate live URL.
2. Provision live LAB host and apply `ASREVIEW_LAB_LIVE_SERVER.md` runbook.
3. Add branch protection requiring CI checks before merges.
4. Add periodic backup + restore drill for LAB runtime data.
