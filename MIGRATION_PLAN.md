# MIGRATION_PLAN.md

## Objective
Migrate `asys_comp` from a single-project explainer into a compendium-style structure while preserving legacy routes and ASReview LAB operational continuity.

---

## Decision: repo naming strategy (safe path now)

**Chosen now:** keep repository name `asys_comp` for low-risk migration.

Rationale:
- avoids breaking existing CI integrations and Pages/Netlify bindings,
- allows immediate IA migration with no permission dependencies,
- supports incremental expansion toward multi-project compendium.

Future rename target (optional): `asys_comp`.

---

## Implemented information architecture

### Core pages
- `/` → compendium home (`index.html`)
- `/projects/e5cr7` → e5cr7 deep dive (`projects-e5cr7.html`)
- `/lab` → shared LAB landing (`lab.html`)
- `/lab/e5cr7` → e5cr7 LAB landing (`lab-e5cr7.html`)

### Legacy pages retained
- `/asreview-explainer(.html)`
- `/methods-results(.html)`
- `/why-more-review(.html)`
- `/how-many-more(.html)`

---

## Backward compatibility + redirect strategy

Netlify redirects in `netlify.toml` preserve readable routes and aliases:
- `/projects/e5cr7` → `/projects-e5cr7.html`
- `/e5cr7` → `/projects/e5cr7`
- `/lab` → `/lab.html`
- `/lab/e5cr7` → `/lab-e5cr7.html`
- existing explainer aliases retained (e.g., `/asreview-explainer`)

Local server route compatibility is mirrored in `app/server.py`.

---

## Shared-lab domain strategy

Configuration file: `app/data/compendium_catalog.json`

Key fields:
- `shared_lab.entrypoint_url`: stable shared-lab entrypoint (preferred)
- `projects[].legacy_lab_url`: project-specific fallback URL (temporary compatibility)

Migration approach:
1. Keep fallback URL live during transition.
2. Move users/CTAs to shared gateway (`/lab`).
3. Decommission legacy per-project URL only after validation period.

---

## Conventions for adding new projects

When adding a new project `<slug>`:

1. Add page `app/projects-<slug>.html` with `data-page="project-<slug>"`.
2. Add route aliases:
   - Netlify: `/projects/<slug>` → `/projects-<slug>.html`
   - Local server: route in `app/server.py`.
3. Add project entry in `app/data/compendium_catalog.json`:
   - `slug`, `name`, `status`, `summary`, `focus`, `stage`,
   - `deep_dive_path`, `lab_path`, `legacy_lab_url`.
4. Add render logic in `app/static/app.js` for project page.
5. Update smoke tests:
   - `scripts/smoke_test.py`
   - `scripts/smoke_test_static_site.py`
6. Run build/smoke checks before merge.

---

## Optional future repo rename (`asys_comp` → `asys_comp`)

If permissions allow:

```bash
# from local clone with GitHub CLI authenticated
gh repo rename asys_comp --repo OJWatson/asys_comp
```

Post-rename local remote update:

```bash
git remote set-url origin git@github.com:OJWatson/asys_comp.git
# or HTTPS:
# git remote set-url origin https://github.com/OJWatson/asys_comp.git

git remote -v
```

Optional Pages/Netlify follow-up:
- verify GitHub Pages URL changes and update docs,
- reconnect Netlify repo binding if it does not auto-follow.

---

## Migration complete criteria

- Compendium home is default landing page.
- e5cr7 deep-dive page is populated.
- Legacy explainer/method pages remain accessible.
- Shared LAB + fallback links are visible from UI.
- Smoke tests pass for legacy and new routes.
