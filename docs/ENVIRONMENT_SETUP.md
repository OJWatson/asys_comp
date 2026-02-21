# Environment Setup (Pinned)

All commands are local-only and do not require external credentials.

## 1) Create and activate virtualenv
```bash
python3.10 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

## 2) Install pinned dependencies
```bash
pip install -r requirements.lock.txt
```

## 3) Prepare local config
```bash
cp config/app_refresh_config.example.json config/app_refresh_config.json
```

## 4) Refresh analysis outputs and app artifacts
```bash
scripts/run_analysis_and_report_refresh.sh
```

(Quicker data-only refresh):
```bash
scripts/run_data_refresh.sh
```

## 5) Run smoke test (local app server)
```bash
scripts/run_smoke_test.sh
```

## 6) Launch reviewer-facing web app
```bash
scripts/run_web_app.sh
```

Then open:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/asreview-explainer.html`
- `http://127.0.0.1:8000/methods-results.html`
- `http://127.0.0.1:8000/why-more-review.html`
- `http://127.0.0.1:8000/how-many-more.html`

## 7) Build and validate GitHub Pages static bundle
```bash
scripts/build_github_pages_site.sh
scripts/run_static_site_checks.sh
python3 -m http.server 8080 --directory site
```

## Reproducible one-shot command
```bash
scripts/run_mvp_refresh_and_smoke.sh
```
