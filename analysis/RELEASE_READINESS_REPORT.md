# RELEASE_READINESS_REPORT

Date: 2026-02-21
Repository: `OJWatson/asys_comp`
Branch: `main`

## Executive status

- **Code/docs hardening:** ✅ complete for this release candidate.
- **GitHub Pages pipeline:** ✅ build + static checks pass locally.
- **ASReview LAB roundtrip tooling:** ✅ command path executes locally.
- **Production live status:** ⚠️ not yet live for Pages or LAB (manual external steps remain).

---

## 1) Hygiene and release hardening completed

- `.gitignore` tightened to prevent re-tracking local env/cache/build/runtime artifacts.
- Runtime/deployment docs consolidated and duplicated planning docs archived under `analysis/archive/`.
- Added/updated top-level and component READMEs for clearer operator handoff.
- LAB compose hardening applied:
  - bind host defaults to loopback (`127.0.0.1`),
  - `init: true`,
  - healthcheck,
  - named volume for LAB state persistence.
- GitHub Pages build script now explicitly fails fast when app artifacts are missing.

---

## 2) Validation executed (2026-02-21)

Commands run:

```bash
scripts/run_data_refresh.sh
scripts/run_smoke_test.sh
scripts/build_github_pages_site.sh --skip-refresh
scripts/run_static_site_checks.sh
scripts/run_lab_roundtrip_checks.sh
```

Results:

- `run_data_refresh.sh`: success
  - run id: `20260221T132502Z-97890ff5`
  - manifest: `app/data/artifacts/run_manifest.json`
- `run_smoke_test.sh`: success (all 5 pages + artifact endpoints reachable)
- `build_github_pages_site.sh --skip-refresh`: success (`site/` generated)
- `run_static_site_checks.sh`: success (artifact integrity + static smoke passed)
- `run_lab_roundtrip_checks.sh`: success (export/sync/reconcile completed)

LAB roundtrip note:
- Example labels (`record_id` 1,2) do not match the generated queue IDs in this sample run, so reconciliation reports `labels_not_in_queue > 0`. This is expected with placeholder/example label files and does **not** block code release.

---

## 3) Current live status

### GitHub Pages live URL
- Target URL: `https://ojwatson.github.io/asys_comp/`
- **Current status:** not confirmed live from this repo run (requires Pages repo setting + deploy workflow completion).

### ASReview LAB production runtime
- **Current status:** not live from this repo run.
- Local/staging deployment path is documented and validated; production host cutover remains manual.

---

## 4) Blocking items / remaining manual actions

1. In GitHub repo settings, set **Pages Source = GitHub Actions**.
2. Push `main` and confirm successful `deploy-github-pages` workflow run.
3. Verify public Pages URL content using `docs/runbooks/GITHUB_PAGES_DEPLOYMENT.md` post-deploy checklist.
4. Provision production LAB host and execute `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`.
5. Complete LAB DNS + reverse proxy + TLS configuration.
6. Assign operational ownership for LAB backup/restore + incident handling.
