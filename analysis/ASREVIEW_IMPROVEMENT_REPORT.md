# ASReview Screening Model Improvement Report

## Scope and execution
- Working directory: `/home/kana/git/asys/screening-model`
- Baseline pipeline audited with Codex CLI in PTY mode and **xhigh reasoning**:
  - `analysis/train_asreview.py`
  - `analysis/outputs/metrics.json`
  - `analysis/outputs/ranking_test.csv`
- Audit artifact: `analysis/outputs/improved/codex_audit.md`
- Research artifact: `analysis/outputs/improved/codex_research_notes.md`

## Baseline diagnosis (from audit)
Key baseline issues identified:
1. Fixed threshold (`0.5`) with heavy class imbalance caused binary collapse (`precision=0`, `recall=0`, `f1=0`).
2. High-recall screening efficiency was poor (`wss@95 = -0.0333`).
3. Evaluation was mostly single-split and not aligned to ASReview-style active-learning behavior.
4. Ranking output included label-like columns, increasing leakage risk if reused operationally.
5. Reproducibility metadata was partial.

## What changed
Implemented a new script without deleting baseline:
- New file: `analysis/train_asreview_improved.py`

### Concrete upgrades in the new pipeline
1. **Better imbalance handling**
- Added multiple imbalance-aware model variants:
  - `lr_word_tfidf_balanced` (class-weighted logistic regression)
  - `cnb_word_tfidf` (ComplementNB)
  - `calibrated_svm_word_char` (LinearSVC + probability calibration + word+char TF-IDF)

2. **Threshold tuning for recall targets (0.90 / 0.95)**
- Added validation split and threshold search for target recall levels.
- Saved tuned thresholds and their test-set metrics:
  - `threshold_recall_0.90`
  - `threshold_recall_0.95`
  - `precision@thr_recall_0.90`, `recall@thr_recall_0.90`
  - `precision@thr_recall_0.95`, `recall@thr_recall_0.95`

3. **Richer ranking/PR-oriented evaluation**
- Added: `average_precision`, `max_f1_over_thresholds`, PR-derived precision at recall targets.
- Added workload-oriented measures:
  - `screening_fraction_at_recall_0.90`, `screening_fraction_at_recall_0.95`
  - `first_relevant_rank`, `last_relevant_rank`
  - `wss@90`, `wss@95`
  - `recall@k` and `precision@k` for k = 10, 20, 30, 50.

4. **Stronger model/feature variant vs baseline**
- Added `calibrated_svm_word_char` (word + char TF-IDF with calibrated margin model), which became best by selection rule.

5. **Reproducible configuration and deterministic seeds**
- Deterministic `random_state` and seeded NumPy/random.
- Saved run metadata in `run_config_improved.json` including split sizes and class counts.

## Why these changes should help (linked to research)
Research and docs used are listed in detail at `analysis/outputs/improved/codex_research_notes.md`. Main links that drove implementation:
- ASReview software framing and imbalance context: https://www.nature.com/articles/s42256-020-00287-7
- ASReview prior/seed setup guidance: https://asreview.readthedocs.io/en/stable/lab/project_create.html
- PR-first evaluation for imbalanced tasks: https://pmc.ncbi.nlm.nih.gov/articles/PMC4349800/
- Calibration rationale and implementation:
  - https://proceedings.mlr.press/v70/guo17a.html
  - https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV
- Stopping criteria guidance for screening workflows:
  - https://systematicreviewsjournal.biomedcentral.com/articles/10.1186/s13643-020-01521-4

## Experiments run
## Baseline rerun
- Command: baseline script rerun to a clean comparison location.
- Output: `analysis/outputs/improved/baseline_repro/metrics.json`

## Improved experiments
- Script: `analysis/train_asreview_improved.py`
- Models tested:
  - `lr_word_tfidf_balanced`
  - `cnb_word_tfidf`
  - `calibrated_svm_word_char`
- Selection rule:
  - `max(average_precision, then wss@95, then recall@20, then recall@50)`
- Best selected config:
  - `calibrated_svm_word_char`

## Baseline vs improved metrics (best config)
Source: `analysis/outputs/improved/comparison_baseline_vs_improved.csv`

| metric | baseline | improved_best | delta |
|---|---:|---:|---:|
| accuracy | 0.8333 | 0.8000 | -0.0333 |
| precision | 0.0000 | 0.2000 | +0.2000 |
| recall | 0.0000 | 0.1111 | +0.1111 |
| f1 | 0.0000 | 0.1429 | +0.1429 |
| average_precision | 0.2594 | 0.3486 | +0.0892 |
| roc_auc | 0.6601 | 0.6492 | -0.0109 |
| r_precision | 0.2222 | 0.3333 | +0.1111 |
| wss@95 | -0.0333 | -0.0167 | +0.0167 |
| precision@20 | 0.2000 | 0.2500 | +0.0500 |
| recall@20 | 0.4444 | 0.5556 | +0.1111 |
| recall@50 | 0.8889 | 0.8889 | +0.0000 |

Interpretation:
- Major improvements in ranking quality and early retrieval (`average_precision`, `r_precision`, `recall@20`).
- Binary classification is no longer degenerate at threshold 0.5 (recall and F1 are non-zero).
- `wss@95` improved but remains below zero, indicating further work is needed for strong high-recall work-saving.

## Key output artifacts
- New training script: `analysis/train_asreview_improved.py`
- Final report: `analysis/ASREVIEW_IMPROVEMENT_REPORT.md`
- Audit notes: `analysis/outputs/improved/codex_audit.md`
- Research notes/sources: `analysis/outputs/improved/codex_research_notes.md`
- Baseline reproducibility run:
  - `analysis/outputs/improved/baseline_repro/metrics.json`
  - `analysis/outputs/improved/baseline_repro/ranking_test.csv`
- Improved experiment outputs:
  - `analysis/outputs/improved/model_summary.csv`
  - `analysis/outputs/improved/leaderboard.md`
  - `analysis/outputs/improved/metrics_by_model.json`
  - `analysis/outputs/improved/metrics_best.json`
  - `analysis/outputs/improved/comparison_baseline_vs_improved.csv`
  - `analysis/outputs/improved/comparison_table.md`
  - `analysis/outputs/improved/run_config_improved.json`
  - `analysis/outputs/improved/best_model.joblib`
  - `analysis/outputs/improved/ranking_test_calibrated_svm_word_char.csv`

## Recommended next steps for deeper ASReview workflow improvement
1. Add **active-learning simulation loop** (query/update iterations) and evaluate stopping policies directly, not only static holdout metrics.
2. Add **nested CV + seed sweeps** to stabilize threshold tuning and reduce split sensitivity.
3. Add **leakage-safe production ranking export** (hide true labels/decision fields for operational queues).
4. Add **target-recall stopping diagnostics** (statistical stopping and SAFE-style checks) to improve decision confidence at high recall.
5. Test **ASReview-specific priors/seed strategies** (known relevant + known irrelevant templates) and quantify recall-at-workload gains.
