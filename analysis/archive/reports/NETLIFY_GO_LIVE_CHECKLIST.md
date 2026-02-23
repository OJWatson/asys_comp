# Netlify Go-Live Checklist (OJWatson/asys_comp)

## A) Repository readiness (must be green before Netlify import)

- [ ] `netlify.toml` exists at repo root.
- [ ] Build command is deterministic and uses committed artifacts.
- [ ] Publish directory is `site`.
- [ ] Redirects/aliases exist for project and lab routes.
- [ ] Run locally:
  - `scripts/build_github_pages_site.sh --skip-refresh`
  - `scripts/run_static_site_checks.sh`

---

## B) Netlify project setup (manual UI)

- [ ] Netlify: **Add new site** → **Import existing project**.
- [ ] Provider: **GitHub**.
- [ ] Repo selected: `OJWatson/asys_comp`.
- [ ] Branch: `main`.
- [ ] Netlify detected `netlify.toml` (or manual build/publish values entered).
- [ ] First deploy completed successfully.

---

## C) DNS + custom compendium subdomain (`ojwatson.co.uk`)

- [ ] Domain added in Netlify Domain management.
- [ ] DNS record created:
  - preferred: `CNAME asys -> <site-name>.netlify.app`
- [ ] Netlify DNS verification passes.
- [ ] TLS certificate issued and HTTPS active.

---

## D) Shared LAB linkage (separate runtime path)

- [ ] Shared LAB endpoint (e.g. `lab.ojwatson.co.uk`) deployed and reachable.
- [ ] `app/data/compendium_catalog.json` updated with:
  - [ ] `shared_lab.entrypoint_url`
  - [ ] `projects[].legacy_lab_url` as needed.
- [ ] Netlify redeployed after catalog update.

---

## E) Post-deploy validation

- [ ] `/` serves compendium home.
- [ ] `/projects/e5cr7` route works.
- [ ] Legacy explainer pages still load.
- [ ] `/lab` and `/lab/e5cr7` pages load.
- [ ] Artifact + catalog JSON endpoints return HTTP 200.
- [ ] No critical browser-console errors.

---

## F) Rollback readiness

- [ ] Team knows Netlify **Deploys → Publish deploy** rollback path.
- [ ] Last known-good deploy identified.
- [ ] Git revert procedure on `main` documented.
- [ ] DNS rollback values captured if domain cutover fails.

---

## References
- `netlify.toml`
- `MIGRATION_PLAN.md`
- `DEPLOY_CHECKLIST.md`
- `docs/runbooks/NETLIFY_DEPLOYMENT.md`
- `docs/runbooks/DOMAIN_DNS_SETUP.md`
- `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`
