# Reviewer-Facing MVP App

Static, reviewer-friendly web app with artifact-backed content.

## Pages
- `index.html` (redirects to explainer)
- `asreview-explainer.html`
- `methods-results.html`
- `why-more-review.html`
- `how-many-more.html`

## Local run (dynamic preview server)
```bash
python3 scripts/refresh_app_data.py --config config/app_refresh_config.json
python3 app/server.py --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## GitHub Pages static bundle
```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
```

Bundle output is written to `site/` (including `.nojekyll`) and is ready for GitHub Pages artifact upload.
