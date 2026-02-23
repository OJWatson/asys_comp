# Reviewer-Facing Web App

Static reviewer-facing app backed by generated JSON artifacts in `app/data/artifacts/` and compendium metadata in `app/data/compendium_catalog.json`.

## Pages
- `index.html` (compendium home)
- `projects-e5cr7.html` (deep dive)
- `asreview-explainer.html`
- `methods-results.html`
- `why-more-review.html`
- `how-many-more.html`
- `lab.html` (shared LAB landing)
- `lab-e5cr7.html` (project LAB landing)

## Local preview server

```bash
python3 scripts/refresh_app_data.py --config config/app_refresh_config.json
python3 app/server.py --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## GitHub Pages / Netlify bundle

```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
```

Build output is written to `site/` (generated, untracked) and used by deployment workflows.
