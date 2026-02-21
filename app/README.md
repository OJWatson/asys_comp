# Reviewer-Facing Web App

Static reviewer-facing app backed by generated JSON artifacts in `app/data/artifacts/`.

## Pages
- `index.html` (redirect entry)
- `asreview-explainer.html`
- `methods-results.html`
- `why-more-review.html`
- `how-many-more.html`

## Local preview server

```bash
python3 scripts/refresh_app_data.py --config config/app_refresh_config.json
python3 app/server.py --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## GitHub Pages bundle

```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
```

Build output is written to `site/` (generated, untracked) and used by the Pages deployment workflow.
