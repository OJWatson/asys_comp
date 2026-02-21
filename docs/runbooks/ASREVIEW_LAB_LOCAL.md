# ASReview LAB Local Runbook

## Purpose
Local deployment + integration loop for reviewer operations without cloud credentials.

## Start LAB
```bash
cd infra/asreview-lab
cp .env.example .env
docker compose up --build -d
```

## Verify service
```bash
docker compose ps
curl -I http://127.0.0.1:5000
```

## Export queue for LAB (+ export manifest)
```bash
cd /home/kana/git/asys/screening-model
python3 integration/asreview_lab_hooks.py export-queue \
  --ranking analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --output infra/asreview-lab/data/queue_for_lab.csv \
  --manifest-output integration/outputs/lab_queue_export_manifest.json
```

## Import and screen in LAB
- In LAB UI, create/open project.
- Import `infra/asreview-lab/data/queue_for_lab.csv`.
- Complete screening batch.

## Sync labels + reconcile roundtrip integrity
```bash
python3 integration/asreview_lab_hooks.py sync-labels \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_labels_snapshot.json

python3 integration/asreview_lab_hooks.py reconcile-roundtrip \
  --queue infra/asreview-lab/data/queue_for_lab.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_roundtrip_report.json
```

## One-shot integration check
```bash
scripts/run_lab_roundtrip_checks.sh
```

## Stop LAB
```bash
cd infra/asreview-lab
docker compose down
```
