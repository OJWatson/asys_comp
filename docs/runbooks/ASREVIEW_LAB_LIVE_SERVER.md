# ASReview LAB Live-Server Runbook

## Scope
Harden and deploy ASReview LAB on a live server while keeping the static explainer on GitHub Pages.

This runbook is intentionally pragmatic and includes the **minimal manual steps** that cannot be fully automated from this repository.

---

## Target architecture (recommended)

- Ubuntu host with Docker Engine + Docker Compose plugin
- LAB container from `infra/asreview-lab/`
- Reverse proxy (Nginx/Caddy) with HTTPS
- Optional: firewall restricting direct port exposure

---

## 1) Host prerequisites (manual)

On the target host:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

Open only required ports (typically 80/443).

---

## 2) Deploy repository and configuration

```bash
git clone git@github.com:OJWatson/asys_e5cr7.git
cd asys_e5cr7/infra/asreview-lab
cp .env.example .env
```

Adjust `.env` values for your host/network policy.

Optional examples:
- `ASREVIEW_LAB_PORT=5000` (container listener)

---

## 3) Start LAB runtime

```bash
docker compose up -d --build
docker compose ps
```

Health check:

```bash
curl -I http://127.0.0.1:5000
```

---

## 4) Reverse proxy + TLS (manual, environment-specific)

Required manual action:
1. configure DNS for your LAB hostname,
2. configure reverse proxy virtual host to forward to `127.0.0.1:5000`,
3. issue TLS certificate (Let's Encrypt or organizational PKI).

Why manual: domain ownership, certificate policy, and ingress rules are org-specific and cannot be safely automated from this repo.

---

## 5) Operational checks

- LAB UI reachable at the HTTPS endpoint
- Queue import works using `infra/asreview-lab/data/queue_for_lab.csv`
- Label export + sync + reconciliation complete without errors

Recommended command after first live run:

```bash
cd /path/to/asys_e5cr7
scripts/run_lab_roundtrip_checks.sh
```

---

## 6) Minimum hardening checklist

- [ ] Docker service enabled on boot
- [ ] LAB reachable only via reverse proxy (no public raw :5000 exposure)
- [ ] HTTPS certificate active and auto-renewal configured
- [ ] Host firewall configured
- [ ] Runtime `.env` stored with least-privilege access
- [ ] Backup plan documented for any persisted LAB project data

---

## 7) Exact remaining manual steps for production go-live

1. **DNS + TLS setup** for LAB endpoint.
2. **Firewall and ingress policy approval** per organization standards.
3. **Ops ownership assignment** (who handles incident/backup/restore).

These are mandatory for a real production launch and are intentionally left manual due to security and governance requirements.
