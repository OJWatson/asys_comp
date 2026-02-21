# ASReview LAB Local Deployment Scaffolding

This scaffolding runs ASReview LAB locally for reviewer workflow integration.

## Quick start
```bash
cd infra/asreview-lab
cp .env.example .env
docker compose up --build
```

LAB should be reachable at `http://127.0.0.1:5000`.

## Local integration flow
1. Export queue from analysis outputs (+ manifest):
```bash
python3 integration/asreview_lab_hooks.py export-queue \
  --ranking analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --output infra/asreview-lab/data/queue_for_lab.csv \
  --manifest-output integration/outputs/lab_queue_export_manifest.json
```
2. Import `infra/asreview-lab/data/queue_for_lab.csv` into ASReview LAB.
3. Export labels from LAB and save as `infra/asreview-lab/data/lab_labels_export.csv`.
4. Sync exported labels into local artifact cache:
```bash
python3 integration/asreview_lab_hooks.py sync-labels \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_labels_snapshot.json
```
5. Reconcile completion and integrity:
```bash
python3 integration/asreview_lab_hooks.py reconcile-roundtrip \
  --queue infra/asreview-lab/data/queue_for_lab.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_roundtrip_report.json
```

See `analysis/DEPLOYMENT_RUNBOOK.md` and `docs/runbooks/ASREVIEW_LAB_LOCAL.md` for full runbooks.
