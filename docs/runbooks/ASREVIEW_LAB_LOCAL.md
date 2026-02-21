# ASReview LAB Local/Staging Runbook

## Purpose
Run ASReview LAB locally (or on a staging host) and execute the queue → labels → reconciliation loop.

---

## 1) Start LAB

```bash
cd /home/kana/git/asys/screening-model/infra/asreview-lab
cp .env.example .env
docker compose up --build -d
```

Verify:

```bash
docker compose ps
curl -I http://127.0.0.1:5000
```

---

## 2) Export queue for LAB

```bash
cd /home/kana/git/asys/screening-model
python3 integration/asreview_lab_hooks.py export-queue \
  --ranking analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --output infra/asreview-lab/data/queue_for_lab.csv \
  --manifest-output integration/outputs/lab_queue_export_manifest.json
```

Import `infra/asreview-lab/data/queue_for_lab.csv` into LAB.

---

## 3) Sync labels from LAB export

Export labels from LAB to:
`infra/asreview-lab/data/lab_labels_export.csv`

Then run:

```bash
python3 integration/asreview_lab_hooks.py sync-labels \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_labels_snapshot.json
```

---

## 4) Reconcile queue/labels integrity

```bash
python3 integration/asreview_lab_hooks.py reconcile-roundtrip \
  --queue infra/asreview-lab/data/queue_for_lab.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_roundtrip_report.json
```

One-shot helper:

```bash
scripts/run_lab_roundtrip_checks.sh
```

---

## 5) Stop LAB

```bash
cd infra/asreview-lab
docker compose down
```

---

## Notes

- `infra/asreview-lab/data/*.csv` and `integration/outputs/*.json` are intentionally untracked runtime artifacts.
- Example formats are provided in:
  - `infra/asreview-lab/data/queue_for_lab.example.csv`
  - `infra/asreview-lab/data/lab_labels_export.example.csv`
