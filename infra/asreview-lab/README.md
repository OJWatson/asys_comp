# ASReview LAB Deployment Scaffolding

Container scaffolding for ASReview LAB runtime used by reviewer operations.

## Quick start (local/staging)

```bash
cd infra/asreview-lab
cp .env.example .env
docker compose up --build -d
```

LAB default URL: `http://127.0.0.1:5000`

## Data files

Runtime CSVs are intentionally untracked:
- `data/queue_for_lab.csv`
- `data/lab_labels_export.csv`

Format examples are provided:
- `data/queue_for_lab.example.csv`
- `data/lab_labels_export.example.csv`

## Integration loop

From repo root:

```bash
scripts/run_lab_roundtrip_checks.sh
```

## Runbooks

- Local/staging: `docs/runbooks/ASREVIEW_LAB_LOCAL.md`
- Live server hardening: `docs/runbooks/ASREVIEW_LAB_LIVE_SERVER.md`
