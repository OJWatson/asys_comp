# GitHub Pages Deployment Runbook

## Purpose
Deploy the reviewer-facing static explainer site from this repository using GitHub Actions.

## Deployment model
- Source pages: `app/*.html`, `app/static/*`, `app/data/artifacts/*.json`
- Build output (ephemeral): `site/`
- Publisher: `.github/workflows/deploy-github-pages.yml`

`site/` is generated and not tracked in git.

---

## Pre-flight (local)

```bash
cd /home/kana/git/asys/screening-model
scripts/run_data_refresh.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

Expected result:
- static smoke test passes,
- artifact integrity check passes,
- `site/` contains all 5 pages + `data/artifacts/*.json`.

---

## GitHub settings (one-time)

1. Open **Repo Settings → Pages**.
2. Set **Build and deployment / Source = GitHub Actions**.
3. Ensure Actions are allowed for the repository.
4. (Optional) configure custom domain and enforce HTTPS.

---

## Publish flow

1. Push to `main`.
2. Workflow runs:
   - install pinned dependencies,
   - refresh app artifacts,
   - build static bundle,
   - run static checks,
   - upload and deploy Pages artifact.
3. Confirm workflow status is green in Actions tab.

Manual trigger fallback:
- `deploy-github-pages` workflow supports `workflow_dispatch`.

---

## Go-live checklist

- [ ] `scripts/run_static_site_checks.sh` passes locally.
- [ ] `deploy-github-pages` workflow completed successfully on `main`.
- [ ] GitHub Pages source set to **GitHub Actions**.
- [ ] Live URL opens and serves latest commit content.
- [ ] Navigation links and artifact-backed sections render on all pages.

---

## Post-deploy validation

Use the live URL (typically `https://ojwatson.github.io/asys_e5cr7/`):

1. `index.html` redirects to `asreview-explainer.html`.
2. Verify each page loads:
   - `/asreview-explainer.html`
   - `/methods-results.html`
   - `/why-more-review.html`
   - `/how-many-more.html`
3. Open browser devtools and confirm these JSON endpoints return `200`:
   - `/data/artifacts/overview.json`
   - `/data/artifacts/methods_results.json`
   - `/data/artifacts/fn_fp_risk.json`
   - `/data/artifacts/simulation_planner.json`
4. Confirm no console errors related to missing assets or fetch failures.

---

## Failure triage

- Build fails locally: rerun `scripts/run_data_refresh.sh` then static checks.
- Workflow fails at deploy stage only: verify Pages source is set to **GitHub Actions**.
- Live site is stale: confirm latest successful workflow corresponds to expected commit SHA.
