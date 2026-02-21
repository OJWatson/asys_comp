## ASReview-Style Pipeline Audit (based on `analysis/train_asreview.py`, `analysis/outputs/metrics.json`, `analysis/outputs/ranking_test.csv`)

### 1) Top issues ranked by impact

| Rank | Issue | Evidence | Why it matters |
|---|---|---|---|
| 1 | **Thresholding collapses recall under imbalance** | `analysis/outputs/metrics.json`: precision/recall/F1 = `0.0`; class counts `257:43` (~14.3% positive). `analysis/train_asreview.py:292` uses fixed `0.5` threshold. In ranking output, only 1 item is `>=0.5` and it is a false positive. | In binary mode, relevant studies are effectively missed. |
| 2 | **High-recall screening efficiency is poor (ASReview goal miss)** | `wss@95 = -0.0333` in `metrics.json`; positives appear at ranks `3, 7, 10, 15, 21, 22, 25, 39, 59` in `ranking_test.csv`. | To reach ~95% recall, you must screen ~59/60 docs (~98.3%), worse than random baseline expectation. |
| 3 | **Pipeline is not actually ASReview-style active learning** | `analysis/train_asreview.py:268-323` does one static train/test split and one fit; no iterative query/update loop, no seed sensitivity, no stopping-rule simulation. | Reported metrics do not represent real active-learning behavior in screening workflows. |
| 4 | **Potential label leakage/exposure in output artifacts** | `analysis/train_asreview.py:318-333` writes full `test_rows`; `ranking_test.csv` contains `final_decision`, `_label`, `true_label`, notes/exclude-code fields. | If this file is reused as a screening queue or future training input, it leaks gold labels and rationale. |
| 5 | **Metric blind spots hide failure modes** | Accuracy is `0.8333` despite zero recall; only 9 positives in test (each miss shifts recall by 11.1%). No CIs, confusion matrix, calibration metrics, or workload-recall curves beyond a few cutoffs. | Gives false confidence and weak decision support for deployment. |
| 6 | **Reproducibility is partial** | `random_state` is set/saved (`analysis/train_asreview.py:227-229`, `336-350`) but no input hash, package versions, git SHA, or saved split indices. | Hard to reproduce exact runs or compare changes reliably. |

---

### 2) Concrete improvement actions

1. **Decouple ranking from binary decisioning**  
Use ranking for reviewer ordering; if binary labels are needed, tune threshold on validation data for target recall (not fixed 0.5), and calibrate probabilities.

2. **Add true ASReview simulation mode**  
Implement iterative active-learning replay (seed positives + sequential updates + stopping criteria) and report recall-vs-workload curves.

3. **Leakage hardening**  
Export two files:  
- blinded queue: `id, text, score, rank`  
- evaluation-only file: true labels/notes  
Also enforce strict input-column allowlist and fail closed if ambiguous columns are detected.

4. **Upgrade evaluation under imbalance**  
Add confusion matrix, recall at workload fractions (5/10/20/30%), last-relevant rank, AULC, calibration (Brier/ECE), and repeated-seed confidence intervals.

5. **Strengthen reproducibility**  
Persist train/test IDs, input checksum, dependency versions, git commit hash, and deterministic sort tie-breakers.

---

### 3) Expected impact

- **Threshold tuning + calibration:** converts current binary mode from recall `0.0` to materially usable recall (on this split, thresholds around `0.35–0.40` would have recovered many positives).  
- **Active-learning simulation:** reveals true early-yield behavior and stopping risk; should prevent overestimating real-world work savings.  
- **Leakage controls:** prevents accidental contamination and reviewer bias from labeled outputs.  
- **Richer metrics + repeated runs:** gives reliable go/no-go evidence instead of single-split volatility.

---

### 4) Quick validation plan

1. **Repro baseline**: rerun current script with same seed; verify identical ranking hash and metrics.  
2. **Threshold/calibration check**: tune on validation folds, then evaluate once on held-out test.  
3. **AL simulation**: run 20–50 seeded simulations, report median + IQR for WSS@95, recall@workload, last-relevant rank.  
4. **Leakage/repro gates**: CI checks that screening queue has no label columns, and run metadata (hashes/versions/splits) is present.