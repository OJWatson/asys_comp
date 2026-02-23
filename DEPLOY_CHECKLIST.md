# DEPLOY_CHECKLIST.md

Exact go-live checklist for compendium + LAB deployment.

---

## 0) Pre-deploy local verification (required)

```bash
cd /path/to/asys_e5cr7
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt

cp config/app_refresh_config.example.json config/app_refresh_config.json
scripts/run_data_refresh.sh
scripts/run_smoke_test.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

Pass condition:
- all commands exit 0.

---

## 1) Render deployment (ASReview LAB runtime)

### 1.1 Create service
1. Render dashboard → **New +** → **Web Service**.
2. Connect repo `OJWatson/asys_e5cr7`.
3. Root directory: `infra/asreview-lab`.
4. Environment: Docker.
5. Branch: `main`.
6. Enable Auto Deploy (recommended).

### 1.2 Runtime settings
- Port: `5000`
- Health check path: `/`
- Instance size: starter+ (per expected usage)

### 1.3 Environment variables
Set in Render:
- `ASREVIEW_LAB_PORT=5000`
- any org-required secrets/vars

### 1.4 Verify Render service
- Service status = healthy.
- Render URL opens ASReview LAB UI.

---

## 2) DNS for shared LAB endpoint

At DNS provider (`ojwatson.co.uk`):

| Type | Host | Target | TTL |
|---|---|---|---|
| CNAME | `lab` | `<render-service>.onrender.com` | 300 |

Validate:

```bash
dig +short lab.ojwatson.co.uk CNAME
curl -I https://lab.ojwatson.co.uk/
```

---

## 3) Netlify deployment (compendium static site)

### 3.1 Import project
1. Netlify → **Add new site** → **Import existing project**.
2. Select `OJWatson/asys_e5cr7`.
3. Branch: `main`.
4. Build command:
   `./scripts/build_github_pages_site.sh --skip-refresh && ./scripts/run_static_site_checks.sh`
5. Publish directory: `site`
6. Deploy site.

### 3.2 Attach compendium domain

Add DNS:

| Type | Host | Target | TTL |
|---|---|---|---|
| CNAME | `asys` | `<site-name>.netlify.app` | 300 |

In Netlify Domain Management:
- add `asys.ojwatson.co.uk`,
- verify DNS,
- enable HTTPS certificate.

Validate:

```bash
dig +short asys.ojwatson.co.uk CNAME
curl -I https://asys.ojwatson.co.uk/
```

---

## 4) Update shared-lab and fallback URLs in compendium content

Edit `app/data/compendium_catalog.json`:

- `shared_lab.entrypoint_url` → `https://lab.ojwatson.co.uk`
- `projects[slug=e5cr7].legacy_lab_url` → current e5cr7 URL (if retained), otherwise same shared URL

Commit and push to `main` so Netlify rebuilds.

---

## 5) Route and page verification (post-deploy)

Verify all routes in browser:
- `/`
- `/projects/e5cr7`
- `/asreview-explainer`
- `/methods-results`
- `/why-more-review`
- `/how-many-more`
- `/lab`
- `/lab/e5cr7`

Verify JSON endpoints:
- `/data/artifacts/overview.json`
- `/data/artifacts/methods_results.json`
- `/data/artifacts/fn_fp_risk.json`
- `/data/artifacts/simulation_planner.json`
- `/data/compendium_catalog.json`

---

## 6) Rollback plan

### Netlify rollback
1. Netlify → Deploys.
2. Select last known-good deploy.
3. Publish deploy.

### DNS rollback
1. Restore previous CNAME values for `asys` and/or `lab`.
2. Keep previous services alive until TTL expiry.

### Source rollback
1. Revert offending commit.
2. Push to `main`.
3. Re-verify routes + LAB links.

---

## 7) Completion sign-off

- [ ] Render LAB healthy
- [ ] `lab.ojwatson.co.uk` live
- [ ] Netlify compendium healthy
- [ ] `asys.ojwatson.co.uk` live
- [ ] shared/fallback LAB links updated in catalog
- [ ] new and legacy routes verified
- [ ] rollback path confirmed
