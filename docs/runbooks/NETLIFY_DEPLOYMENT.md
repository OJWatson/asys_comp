# Netlify Deployment Runbook (Compendium + Custom Domain)

## Purpose
Deploy the static compendium site from `OJWatson/asys_comp` to Netlify, attach a custom subdomain, and preserve backward-compatible routes.

## What this uses
- Repo: `OJWatson/asys_comp` (branch: `main`)
- Netlify config: `netlify.toml`
- Build output directory: `site/` (generated during build)
- Build command (deterministic):
  - `./scripts/build_github_pages_site.sh --skip-refresh && ./scripts/run_static_site_checks.sh`

---

## 1) Pre-flight checks (local)

```bash
cd /path/to/asys_comp
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

Expected:
- all checks pass,
- `site/` is generated,
- compendium pages + JSON endpoints are present.

---

## 2) Import from GitHub in Netlify

1. Log in to Netlify.
2. Click **Add new site** → **Import an existing project**.
3. Choose **GitHub**.
4. Authorize Netlify for GitHub (if prompted).
5. Select repository: **OJWatson/asys_comp**.
6. Branch to deploy: **main**.
7. Build settings:
   - Netlify should auto-detect `netlify.toml`.
   - If it does not, set manually:
     - **Build command**: `./scripts/build_github_pages_site.sh --skip-refresh && ./scripts/run_static_site_checks.sh`
     - **Publish directory**: `site`
8. Click **Deploy site**.

---

## 3) First deploy verification

After deploy succeeds:

1. Open **Deploys** and confirm latest deploy is **Published**.
2. Open the generated Netlify URL.
3. Verify pages load:
   - `/`
   - `/projects-e5cr7.html`
   - `/asreview-explainer.html`
   - `/methods-results.html`
   - `/why-more-review.html`
   - `/how-many-more.html`
   - `/lab.html`
   - `/lab-e5cr7.html`
4. Verify route aliases:
   - `/projects/e5cr7` → `/projects-e5cr7.html`
   - `/e5cr7` → `/projects/e5cr7`
   - `/lab` → `/lab.html`
   - `/lab/e5cr7` → `/lab-e5cr7.html`
5. Verify JSON endpoints return 200:
   - `/data/artifacts/overview.json`
   - `/data/artifacts/methods_results.json`
   - `/data/artifacts/fn_fp_risk.json`
   - `/data/artifacts/simulation_planner.json`
   - `/data/compendium_catalog.json`

---

## 4) Attach custom subdomain (`*.ojwatson.co.uk`)

1. In Netlify site, go to **Domain management**.
2. Click **Add a domain**.
3. Enter desired host, e.g. `asys.ojwatson.co.uk`.
4. Continue and keep Netlify’s DNS target value visible (usually `<site-name>.netlify.app`).
5. Add DNS records at the `ojwatson.co.uk` DNS provider (see `docs/runbooks/DOMAIN_DNS_SETUP.md`).
6. Back in Netlify, click **Verify DNS configuration**.
7. Once verified, enable **HTTPS / provision certificate**.

---

## 5) Shared-lab link strategy (content-level)

Netlify hosts the static compendium only. LAB runtime URL destinations are configured in:
- `app/data/compendium_catalog.json`

Required go-live edit:
1. Set `shared_lab.entrypoint_url` to the shared production LAB hostname.
2. Set each project `legacy_lab_url` to current/legacy project endpoint (if retained).
3. Redeploy Netlify.

This preserves a stable UX path (`/lab`, `/lab/e5cr7`) while allowing backend endpoint migration.

---

## 6) Post-deploy validation checklist

- [ ] Netlify deploy from `main` is green.
- [ ] Compendium home + e5cr7 deep-dive render without console errors.
- [ ] Legacy explainer pages still render.
- [ ] Artifact JSON + compendium catalog JSON endpoints return HTTP 200.
- [ ] Custom subdomain resolves and serves the Netlify deploy.
- [ ] TLS certificate is active.

---

## 7) Rollback procedure

### Fast rollback (no Git revert)
1. Netlify → **Deploys**.
2. Select last known-good deploy.
3. Click **Publish deploy**.

### Source rollback (Git)
1. Revert problematic commit on `main`.
2. Push.
3. Netlify auto-builds a new deploy.
4. Promote/publish if required.

### DNS rollback (if domain issue)
1. Repoint subdomain to previous host target (or remove CNAME).
2. Keep old service active until DNS TTL expires.

---

## External blockers

Only Netlify account-owner actions are external blockers:
- connecting GitHub app authorization,
- clicking **Deploy site**,
- adding/verifying custom domain,
- enabling access control features in Netlify UI.
