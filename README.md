# ASYS Compendium (e5cr7-first)

Release-ready repository for a two-path delivery model:

1. **Compendium static site** (GitHub Pages / Netlify) with a front-facing multi-project landing page and project deep-dives.
2. **ASReview LAB runtime path** for active screening operations and label roundtrips.

---

## Project purpose

This repository packages analysis outputs, reviewer-facing narrative, and operational hooks needed to:

- explain project performance and residual-risk tradeoffs,
- support staged screening decisions,
- move screened labels through a repeatable ASReview LAB loop,
- publish an auditable static site from reproducible artifacts,
- scale from a single project (`e5cr7`) to a compendium of projects.

---

## Architecture split

| Path | What it serves | Location | Runtime |
|---|---|---|---|
| Compendium static site | Home + project deep-dives (consolidated per-project docs) | `app/` → built to `site/` | GitHub Actions + Pages / Netlify |
| ASReview LAB (live) | Reviewer labeling runtime | `infra/asreview-lab/` | Docker Compose / Render / live server |
| Integration bridge | Queue export, label sync, reconciliation | `integration/asreview_lab_hooks.py` | Local/server Python |

---

## Repository layout

- `analysis/` reproducible model outputs and reports
- `app/` static app source and generated JSON artifacts (`app/data/artifacts/`)
- `docs/SCREENING_WORKFLOW_HANDBOOK.md` comprehensive screening workflow handbook for model workflow, metrics, and decision-making
- `docs/SCALING_PLAYBOOK_ASREVIEW_CROWDSCREEN_DORY.md` practical scaling playbook for very large screening corpora (run versioning, overlap/kappa, CrowdScreen, Dory, and automation guardrails)
- `docs/runbooks/ASREVIEW_DORY_INTEGRATION.md` focused Dory integration runbook (install, prepare, simulate, export, and validation)
- `docs/runbooks/` deployment runbooks (Pages + Netlify + LAB local/live)
- `infra/asreview-lab/` LAB container scaffolding and config templates
- `integration/` queue/label integration hooks
- `scripts/` build, refresh, smoke, and integrity checks
- `MIGRATION_PLAN.md` migration rationale, IA, and extension conventions
- `DEPLOY_CHECKLIST.md` exact deployment steps (Render/Netlify/DNS)

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

Run expanded NLP benchmark (baseline vs improved vs candidate models):

```bash
source .venv/bin/activate
python analysis/benchmark_nlp_models.py
python scripts/smoke_test_benchmarks.py
```

Optional heavy NLP path (embedding-based candidate + ASReview dory extension models):

```bash
source .venv/bin/activate
pip install -r requirements-optional-heavy-nlp.lock.txt
```

See runbook: `docs/runbooks/MODEL_BENCHMARKING.md`

Optional: install and run ASReview Dory integration workflow in dedicated env:

```bash
scripts/setup_asreview_dory_env.sh
scripts/run_asreview_dory_workflow.sh
scripts/run_dory_smoke_test.sh
```

See runbook: `docs/runbooks/ASREVIEW_DORY_INTEGRATION.md`

Run local app:

```bash
scripts/run_web_app.sh
```

---

## Deployment paths

### A) Compendium static site (GitHub Pages)

```bash
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

CI deploy workflow: `.github/workflows/deploy-github-pages.yml`.

Runbook:
- `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md`

### A2) Netlify (static compendium + custom domain)

- Netlify build/publish settings are codified in `netlify.toml`.
- Deterministic build command:
  - `./scripts/build_github_pages_site.sh --skip-refresh && ./scripts/run_static_site_checks.sh`
- Runbooks:
  - `docs/runbooks/NETLIFY_DEPLOYMENT.md`
  - `docs/runbooks/DOMAIN_DNS_SETUP.md`

### B) ASReview LAB runtime

Local/staging:
- `docs/runbooks/ASREVIEW_LAB_LOCAL.md`

Live server hardening + cutover:
- `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`

---

## Status and roadmap

### Current status
- ✅ Compendium home and e5cr7 deep-dive structure implemented with novice-friendly orientation copy.
- ✅ Legacy explainer routes retained via redirects/stub pages for backward compatibility.
- ✅ Static Pages/Netlify build + smoke checks in place.
- ✅ LAB integration hooks support export/sync/reconcile loop.
- ⚠️ Production domain and LAB endpoint ownership still requires environment-specific manual setup.

### Near-term roadmap
1. Add second project deep-dive using conventions in `MIGRATION_PLAN.md`.
2. Point shared LAB gateway to final production hostname.
3. Enable branch protection requiring CI checks before merges.
4. Add periodic backup + restore drill for LAB runtime data.
