# ASReview LAB Live-Server Runbook

## Scope
Deploy and harden ASReview LAB on a live host while keeping the static compendium on GitHub Pages/Netlify.

This runbook includes the minimum manual steps that cannot be safely automated from this repository.
For a Render-only quick path, see `docs/runbooks/RENDER_LAB_DEPLOYMENT.md`.

---

## Target architecture (recommended)

- LAB runtime built from `infra/asreview-lab/`
- Host option A: Ubuntu VM + Docker Compose
- Host option B: Render Web Service (Docker deploy)
- Shared LAB hostname (e.g. `lab.ojwatson.co.uk`) pointing to chosen runtime
- Optional legacy project hostname maintained temporarily for backward compatibility

---

## Option A: Ubuntu host with Docker Compose

### 1) Host prerequisites

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

Open only required ports (typically 80/443 at reverse proxy).

### 2) Deploy repository and configuration

```bash
git clone git@github.com:OJWatson/asys_e5cr7.git
cd asys_e5cr7/infra/asreview-lab
cp .env.example .env
```

Adjust `.env` values for host/network policy.

### 3) Start LAB runtime

```bash
docker compose up -d --build
docker compose ps
curl -I http://127.0.0.1:5000
```

### 4) Reverse proxy + TLS (manual)

1. Configure DNS for LAB hostname.
2. Configure reverse proxy vhost to forward to `127.0.0.1:5000`.
3. Issue TLS certificate (Let's Encrypt or org PKI).

---

## Option B: Render deployment (Docker)

### 1) Create service

1. Render dashboard → **New +** → **Web Service**.
2. Connect repo `OJWatson/asys_e5cr7`.
3. Root directory: `infra/asreview-lab`.
4. Environment: Docker.
5. Auto-deploy: enable for `main` (recommended).

### 2) Runtime settings

- Port: `5000`
- Health check path: `/`
- Instance type: at least starter tier suitable for LAB usage

### 3) Environment variables

Set in Render service settings:
- `ASREVIEW_LAB_PORT=5000`
- any additional secrets required by your org policy

### 4) Validate deployment

- Ensure Render service status is healthy.
- Open Render URL and confirm LAB UI loads.

---

## Shared-lab cutover + compatibility links

1. Point `lab.ojwatson.co.uk` (or chosen shared hostname) to the active LAB runtime.
2. Keep legacy endpoint active during migration window.
3. Update static compendium links in `app/data/compendium_catalog.json`:
   - `shared_lab.entrypoint_url` → shared hostname
   - `projects[].legacy_lab_url` → legacy endpoint (while retained)
4. Redeploy static site.

---

## Operational checks

- LAB UI reachable at HTTPS endpoint
- Queue import works using `infra/asreview-lab/data/queue_for_lab.csv`
- Label export + sync + reconciliation complete without errors

Recommended command after first live run:

```bash
cd /path/to/asys_e5cr7
scripts/run_lab_roundtrip_checks.sh
```

---

## Minimum hardening checklist

- [ ] LAB reachable only through intended ingress path
- [ ] HTTPS certificate active and auto-renewal configured
- [ ] Host/network firewall configured
- [ ] Runtime `.env` / secrets protected with least privilege
- [ ] Backup and restore plan documented
- [ ] Ops owner assigned for incidents and maintenance

---

## Mandatory manual steps

1. DNS + TLS setup for shared LAB endpoint.
2. Firewall and ingress policy approval.
3. Operational ownership assignment.

These are intentionally manual due to security/governance requirements.
