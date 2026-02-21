# Netlify Deployment Runbook (GitHub + Custom Domain)

## Purpose
Deploy the static explainer site from `OJWatson/asys_e5cr7` to Netlify, attach a custom subdomain on `ojwatson.co.uk`, and keep a safe rollback path.

## What this uses
- Repo: `OJWatson/asys_e5cr7` (branch: `main`)
- Netlify config: `netlify.toml`
- Build output directory: `site/` (generated during build)
- Build command (deterministic):
  - `./scripts/build_github_pages_site.sh --skip-refresh && ./scripts/run_static_site_checks.sh`

---

## 1) Pre-flight checks (local)

Run before connecting Netlify:

```bash
cd /home/kana/git/asys/screening-model
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
```

Expected:
- all checks pass,
- `site/` is generated,
- pages + `data/artifacts/*.json` are present.

---

## 2) Import from GitHub in Netlify (click-by-click)

1. Log in to Netlify.
2. Click **Add new site** → **Import an existing project**.
3. Choose **GitHub**.
4. Authorize Netlify for GitHub (if prompted).
5. Select repository: **OJWatson/asys_e5cr7**.
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
   - `/asreview-explainer.html`
   - `/methods-results.html`
   - `/why-more-review.html`
   - `/how-many-more.html`
4. Verify redirect behavior:
   - `/` → `/asreview-explainer.html`
   - `/methods-results` → `/methods-results.html`
5. Verify JSON endpoints return 200:
   - `/data/artifacts/overview.json`
   - `/data/artifacts/methods_results.json`
   - `/data/artifacts/fn_fp_risk.json`
   - `/data/artifacts/simulation_planner.json`

---

## 4) Attach custom subdomain (`*.ojwatson.co.uk`)

1. In Netlify site, go to **Domain management**.
2. Click **Add a domain**.
3. Enter desired host, e.g. `screening.ojwatson.co.uk`.
4. Continue and keep Netlify’s DNS target value visible (usually `<site-name>.netlify.app`).
5. Add DNS records at the `ojwatson.co.uk` DNS provider (see `docs/runbooks/DOMAIN_DNS_SETUP.md`).
6. Back in Netlify, click **Verify DNS configuration**.
7. Once verified, enable **HTTPS / provision certificate**.

---

## 5) Access protection options (explainer site)

### Option A (preferred if plan supports): Netlify Visitor Access / password protection
- Path: **Site configuration** → **Access control** → **Visitor access**.
- Enable site-wide protection and set a shared password.
- Best for a lightweight “invite-only explainer” without code changes.

### Option B: Team/member-only preview workflow
- Keep production public/private as needed, but share only deploy preview links with approved reviewers.
- Use this for short review windows.

### Option C (advanced): HTTP Basic Auth via Netlify Edge Function
- Implement auth middleware in the repo (not enabled by default here).
- Use only if strict per-request basic auth is required.

---

## 6) LAB-side authentication expectations (separate from Netlify)

The Netlify explainer is not the ASReview LAB runtime.

For LAB operations (`infra/asreview-lab/`), enforce separately:
- authentication at reverse proxy (basic auth/OIDC/SSO),
- network restrictions (VPN/IP allow-list),
- least-privilege user accounts,
- no unauthenticated public LAB endpoint.

Use:
- `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`

---

## 7) Post-deploy validation checklist

- [ ] Netlify deploy from `main` is green.
- [ ] All four explainer pages render without console errors.
- [ ] Artifact JSON endpoints return HTTP 200.
- [ ] Custom subdomain resolves and serves the Netlify deploy.
- [ ] TLS certificate is active.
- [ ] Access controls (if enabled) work as expected.

---

## 8) Rollback procedure

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
