# Netlify Go-Live Checklist (OJWatson/asys_e5cr7)

## A) Repository readiness (must be green before Netlify import)

- [ ] `netlify.toml` exists at repo root.
- [ ] Build command is deterministic and uses committed artifacts.
- [ ] Publish directory is `site`.
- [ ] Redirects exist for `/` and extensionless page routes.
- [ ] Run locally:
  - `scripts/build_github_pages_site.sh --skip-refresh`
  - `scripts/run_static_site_checks.sh`

---

## B) Netlify project setup (manual UI)

- [ ] Netlify: **Add new site** → **Import existing project**.
- [ ] Provider: **GitHub**.
- [ ] Repo selected: `OJWatson/asys_e5cr7`.
- [ ] Branch: `main`.
- [ ] Netlify detected `netlify.toml` (or manual build/publish values entered).
- [ ] First deploy completed successfully.

---

## C) DNS + custom subdomain (`ojwatson.co.uk`)

- [ ] Domain added in Netlify Domain management.
- [ ] DNS record created at provider:
  - preferred: `CNAME <subdomain> -> <site-name>.netlify.app`
  - fallback: ALIAS/ANAME or Netlify apex A records where required.
- [ ] Netlify DNS verification passes.
- [ ] TLS certificate issued and HTTPS active.

---

## D) Access control

### Explainer site (Netlify)
- [ ] Choose one:
  - [ ] Visitor/password protection (if plan supports), or
  - [ ] controlled preview sharing, or
  - [ ] advanced Basic Auth middleware approach.

### LAB runtime (separate path)
- [ ] LAB not exposed unauthenticated to public internet.
- [ ] Reverse proxy auth/VPN/IP restrictions in place.
- [ ] Operational ownership defined for LAB credentials and access review.

---

## E) Post-deploy validation

- [ ] `/` redirects to `/asreview-explainer.html`.
- [ ] All explainer pages load successfully.
- [ ] Artifact JSON endpoints return HTTP 200.
- [ ] No critical browser-console errors.
- [ ] Stakeholder smoke test sign-off captured.

---

## F) Rollback readiness

- [ ] Team knows Netlify **Deploys → Publish deploy** rollback path.
- [ ] Last known-good deploy identified.
- [ ] Git revert procedure on `main` documented.
- [ ] DNS rollback values captured if domain cutover fails.

---

## References
- `netlify.toml`
- `docs/runbooks/NETLIFY_DEPLOYMENT.md`
- `docs/runbooks/DOMAIN_DNS_SETUP.md`
- `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`
