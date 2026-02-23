# Render Deployment Runbook (ASReview LAB)

## Purpose
Deploy ASReview LAB runtime from this repository to Render, then bind shared LAB DNS.

---

## 1) Create Render Web Service

1. Render dashboard → **New +** → **Web Service**.
2. Connect GitHub repo: `OJWatson/asys_comp`.
3. Root directory: `infra/asreview-lab`.
4. Runtime: **Docker**.
5. Branch: `main`.
6. Enable auto-deploy (recommended).

---

## 2) Configure runtime

- Internal port: `5000`
- Health check path: `/`
- Environment variable:
  - `ASREVIEW_LAB_PORT=5000`

Optional org-specific secrets may be added per security policy.

---

## 3) Validate service health

- Wait for initial deploy success in Render logs.
- Open generated `*.onrender.com` URL.
- Confirm ASReview LAB UI loads.

---

## 4) Bind shared LAB DNS

At DNS provider, add:

| Type | Host | Target | TTL |
|---|---|---|---|
| CNAME | `lab` | `<render-service>.onrender.com` | 300 |

Validate:

```bash
dig +short lab.ojwatson.co.uk CNAME
curl -I https://lab.ojwatson.co.uk/
```

---

## 5) Update compendium links

Edit `app/data/compendium_catalog.json`:
- `shared_lab.entrypoint_url` → `https://lab.ojwatson.co.uk`
- keep `projects[].legacy_lab_url` during migration window

Commit + push to trigger static-site rebuild.

---

## 6) Rollback

- Use previous Render deploy from Render dashboard.
- If DNS issue, revert CNAME to previous LAB host target.
