# ASYS Screening Workflow Handbook

> Audience: anyone (students, collaborators, reviewers, or new team members) who needs a practical, plain-English, technically accurate map of how the ASReview workflow works in this repository.
>
> Scope: this guide explains the end-to-end workflow from dataset import to screening decisions and reporting outputs, including model behavior, metrics, simulation logic, and day-to-day decision rules.

---

## 0) Start here in 2 minutes (orientation)

If you only remember five things, remember these:

1. **The project optimizes for high recall, not high precision.**
   In evidence screening, missing relevant studies (false negatives) is usually more costly than reviewing extra irrelevant studies (false positives).
2. **Scores are rankings first, labels second.**
   The model is mainly used to sort records so likely-relevant items are screened earlier.
3. **Outputs are dynamic during active screening.**
   As labels accumulate, model rankings and estimated risk can change.
4. **Simulation outputs are planning aids, not truth.**
   They estimate likely false negatives/false positives under assumptions (including prevalence assumptions).
5. **Use staged screening decisions (+50, then reassess) rather than one big irreversible jump.**

### Web companion sync note (source-of-truth policy)

- Canonical handbook content is this markdown file.
- Website reader view lives at `app/handbook.html` and intentionally simplifies structure for scan-first onboarding.
- Manual sync rule: update this markdown first, then mirror any changed guidance/decision logic in `app/handbook.html`, then run static site checks before publish.

---

## 1) End-to-end workflow map (dataset import -> screening decisions -> analysis outputs)

Below is the workflow actually implemented in this repository.

```text
Input data (Excel)
  data/screening_input.xlsx
        |
        v
Baseline training script
  analysis/train_asreview.py
  -> outputs/metrics.json
  -> outputs/ranking_test.csv
  -> outputs/model.joblib
        |
        v
Improved model comparison
  analysis/train_asreview_improved.py
  -> outputs/improved/model_summary.csv
  -> outputs/improved/metrics_best.json
  -> outputs/improved/comparison_baseline_vs_improved.csv
  -> outputs/improved/best_model.joblib
        |
        v
Next-step diagnostics + active-learning simulation
  analysis/run_asreview_next_steps.py
  -> outputs/next_steps/*.csv + *.json
  -> leakage-safe production queue
        |
        v
Planning simulations for extra screening budgets
  analysis/planning_simulations.py
  -> outputs/planning_simulations/simulation_results.csv
  -> outputs/planning_simulations/recommended_next_screening_targets.md
        |
        v
App artifact refresh (what the site reads)
  scripts/refresh_app_data.py
  -> app/data/artifacts/*.json
        |
        v
Reviewer-facing outputs
  app/projects-e5cr7.html (and other site pages)
  + LAB queue/label roundtrip via integration/asreview_lab_hooks.py
```

### Practical command sequence

For a full analysis + artifact refresh, use:

```bash
scripts/run_analysis_and_report_refresh.sh
```

This runs:

1. `analysis/train_asreview.py`
2. `analysis/train_asreview_improved.py`
3. `analysis/run_asreview_next_steps.py`
4. `analysis/planning_simulations.py`
5. `scripts/refresh_app_data.py`
6. `scripts/content_integrity_check.py`

### Where screening operations plug in

Operational loop with ASReview LAB is handled via:

- queue export: `integration/asreview_lab_hooks.py export-queue`
- label sync: `integration/asreview_lab_hooks.py sync-labels`
- roundtrip reconciliation: `integration/asreview_lab_hooks.py reconcile-roundtrip`

So conceptually:

1. Generate ranking queue.
2. Screen in LAB.
3. Export labels.
4. Sync + reconcile.
5. Re-run analyses to update recommendations.

### Dory integration path in this repo (optional)

When you need a Dory-backed simulation pass with the same ASYS data contracts:

```bash
scripts/setup_asreview_dory_env.sh
scripts/run_asreview_dory_workflow.sh
```

This workflow prepares `record_id/title/abstract/included`, runs `asreview simulate` with Dory components, and exports sequence+summary artifacts in `integration/outputs/dory/`.

Focused runbook: `docs/runbooks/ASREVIEW_DORY_INTEGRATION.md`

---

## 2) Active-learning lifecycle: why outputs update as screening progresses

In active learning, the model does **not** stay fixed.

### Lifecycle in plain language

1. **Seed labels** (known relevant/irrelevant, or random) initialize the learner.
2. Model ranks unscreened records by estimated relevance.
3. Reviewers screen top suggestions.
4. New labels are added to training data.
5. Model retrains/re-scores, producing a new ranking.
6. Repeat until stopping policy says stop (or team decision says continue).

### Why your dashboard numbers can change

As more labels are added:

- the decision boundary shifts,
- threshold behavior shifts,
- recall/precision estimates shift,
- recommended additional screening can shift.

This is expected. In active review, metrics are a moving snapshot, not a final fixed verdict.

### Repository-specific simulation of this lifecycle

`analysis/run_asreview_next_steps.py` simulates query/update loops across multiple seeds and seed strategies, tracking:

- docs screened over time,
- recall progression,
- recent non-hit streaks,
- SAFE-like upper bounds for remaining relevant records,
- stop-policy trigger points.

---

## 3) Model-by-model explainer (baseline, improved, features, SVM, ranking vs classification, thresholds)

### 3.1 Data representation used by all models

- Input text is `title + abstract` concatenated.
- Labels are normalized into binary:
  - include -> `1`
  - exclude -> `0`
- Main text features are **TF-IDF** variants (word n-grams and/or character n-grams).

### 3.2 Baseline model (pre-improvement reference)

Implemented in `analysis/train_asreview.py`:

- Features: word-level TF-IDF, ngram range `(1, 2)`.
- Classifier: `LogisticRegression` with `class_weight="balanced"`.
- Default threshold for class label: `0.5`.
- Evaluation: single holdout split (`test_size=0.2`, default random state 42).

### What this means conceptually

- Logistic regression computes a weighted sum of TF-IDF features.
- Applies sigmoid to produce a probability-like score (include likelihood).
- Anything >= 0.5 is predicted include; otherwise exclude.

In this dataset, the 0.5 threshold collapsed to near-all-exclude behavior (precision/recall = 0 at threshold 0.5 in baseline run), even though ranking metrics were not zero.

### 3.3 Improved candidate models

Implemented in `analysis/train_asreview_improved.py` with three contenders:

1. `lr_word_tfidf_balanced`
   - Logistic regression + word TF-IDF.
2. `cnb_word_tfidf`
   - Complement Naive Bayes + word TF-IDF.
3. `calibrated_svm_word_char` (**selected best in current outputs**)
   - Linear SVM (`LinearSVC`) using combined:
     - word TF-IDF (1-2 grams)
     - character TF-IDF (`char_wb`, 3-5 grams)
   - followed by probability calibration (`CalibratedClassifierCV`, sigmoid).

### 3.4 What SVM is doing conceptually

A linear SVM finds a hyperplane separating relevant vs irrelevant examples with maximum margin.

- Raw SVM output is a **distance/margin score**, not a calibrated probability.
- Calibration step maps margins to probability-like scores.
- This helps when you need thresholding or probability-style interpretation.

Why word+char features help:

- word n-grams capture semantic cues,
- char n-grams capture robust subword patterns, spelling variants, abbreviations.

### 3.5 Ranking vs classification (critical distinction)

- **Ranking use-case** (primary): order records by likely relevance so humans screen top items first.
- **Classification use-case** (secondary): force binary include/exclude at a threshold.

In high-imbalance evidence screening, ranking quality is often more informative than threshold-0.5 classification accuracy.

### 3.6 Thresholding in this repo

Improved script tunes thresholds on validation data for recall targets:

- threshold for ~90% recall target,
- threshold for ~95% recall target.

Interpretation:

- Lower thresholds increase recall but usually reduce precision.
- Higher thresholds usually improve precision but may miss relevant studies.

In current outputs, threshold tuning and cross-seed analyses show threshold variability, which is expected in small/imbalanced settings.

---

## 4) Metrics deep guide (with toy worked examples)

Below are the key metrics used in this project.

### 4.1 Confusion matrix basics

For binary screening:

- **TP**: relevant study correctly identified
- **FP**: irrelevant study flagged as relevant
- **FN**: relevant study missed
- **TN**: irrelevant study correctly left out

### Precision

\[
\text{Precision} = \frac{TP}{TP+FP}
\]

Interpretation: “Of items we flagged, how many were truly relevant?”

### Recall

\[
\text{Recall} = \frac{TP}{TP+FN}
\]

Interpretation: “Of all truly relevant studies, how many did we catch?”

### 4.2 Toy example A (precision/recall)

Suppose after screening 100 records:

- TP = 18
- FP = 42
- FN = 2
- TN = 38

Then:

- Precision = 18 / (18 + 42) = 0.30
- Recall = 18 / (18 + 2) = 0.90

This is a typical high-recall/low-precision pattern: many false alarms, but few misses.

### 4.3 Average Precision (AP)

AP summarizes precision across recall levels along the ranking (precision-recall curve area).

Toy ranking of 10 records, true relevant at ranks 1, 3, 8:

- P@1 = 1/1 = 1.00
- P@3 = 2/3 = 0.667
- P@8 = 3/8 = 0.375

AP (simplified discrete form) ≈ (1.00 + 0.667 + 0.375) / 3 = **0.681**.

Why AP matters here: AP rewards getting relevant studies near the top of the queue.

### 4.4 ROC-AUC

ROC-AUC is the probability a random positive gets a higher score than a random negative.

Toy example:

- Positive scores: 0.9, 0.6
- Negative scores: 0.8, 0.5, 0.2

Compare all positive-negative pairs (2 × 3 = 6): positives score higher in 5/6 pairs -> ROC-AUC = **0.833**.

Caveat in imbalanced screening: ROC-AUC can look acceptable while precision remains operationally low.

### 4.5 Recall@k and Precision@k

- **Recall@k**: fraction of all relevant studies found in top k ranked records.
- **Precision@k**: fraction relevant within top k.

Toy example:

- 100 records total, 20 relevant total.
- Top 10 contains 6 relevant.

Then:

- Precision@10 = 6/10 = 0.60
- Recall@10 = 6/20 = 0.30

These are highly actionable for “how useful is the first chunk of screening?” decisions.

### 4.6 WSS@95 (Work Saved over Sampling at 95% recall)

In this repository definition:

\[
\text{WSS@95} = 0.95 - \frac{k_{95}}{N}
\]

- \(N\) = total records
- \(k_{95}\) = number screened to reach 95% recall in ranked list

Toy example 1:

- N = 1000
- Need k95 = 700 to reach 95% recall
- WSS@95 = 0.95 - 0.70 = **0.25** (25% work saved vs random)

Toy example 2 (poor high-recall efficiency):

- N = 1000
- Need k95 = 980
- WSS@95 = 0.95 - 0.98 = **-0.03** (worse than random baseline at this target)

Negative WSS@95 is possible and important: it means high-recall retrieval is expensive in workload terms.

### 4.7 Prevalence assumptions

Prevalence = proportion of truly relevant studies in full candidate pool.

Simulation module uses sensitivity bands:

- low: 10%
- medium: observed prevalence (for current data about 43/300 ≈ 14.3%)
- high: 20%

Why prevalence matters:

- With low prevalence, precision can stay low even if recall is strong.
- FN/FP burden estimates are prevalence-sensitive; do not interpret them as prevalence-free truth.

---

## 5) Why precision may be low here (and why that can still be acceptable)

Low precision in this context is not automatically a failure.

### Structural reasons precision can be low

1. **Class imbalance**: many more excludes than includes.
2. **Conservative high-recall policy**: lower thresholds pull in more borderline records.
3. **Semantic overlap**: many irrelevant abstracts look similar to relevant ones.
4. **Small training signal early in screening**: model uncertainty is high initially.
5. **Optimization target mismatch**: ranking for recall is not identical to maximizing binary precision.

### Why this can be acceptable

In systematic-style screening, the higher-risk error is often FN (missing relevant study), not FP (reading extra irrelevant study).

So a policy like “precision modest, recall high” can be rational if:

- FN risk is dropping materially,
- workload remains manageable,
- decisions are audited and staged.

### Practical framing

Ask: “Are we reducing expected FN enough per extra screening effort?”

Not just: “Is precision high?”

---

## 6) Simulation module explainer (what is simulated, assumptions, FN/FP estimates, uncertainty, immediate vs contingent targets)

There are **two simulation layers**.

### 6.1 Layer A: active-learning process simulation (`run_asreview_next_steps.py`)

Simulates iterative screening behavior across seed strategies and random seeds.

### What is simulated

- initial seed selection strategy,
- iterative query/update loop,
- recall trajectory as screening progresses,
- stop-policy triggers:
  - oracle target recall (90/95),
  - no-hit window,
  - SAFE-like expected remaining upper bound.

### Main assumptions

- Historical labels represent ground truth.
- Simulated learner behavior approximates operational ranking updates.
- Seed strategy and random seeds can materially affect trajectory.

### 6.2 Layer B: planning simulation (`planning_simulations.py`)

Turns stop-point baselines into additional-screening scenarios (+50/+100/+200/+400) with prevalence bands.

### What is simulated

- starting from baseline stop points (e.g., recall-target-90 and recall-target-95 policies),
- estimate recall progression for extra screening budget,
- convert budget + recall estimate into TP/FP/TN/FN approximations,
- report trade-offs (FN reduction vs extra workload).

### How FN/FP estimates are produced

For each scenario:

1. choose assumed total relevant count from prevalence band,
2. estimate recall at screened budget,
3. compute:
   - TP = recall × total relevant,
   - FN = total relevant - TP,
   - FP = screened docs - TP,
   - TN = remaining non-relevant among unscreened.

These are deterministic arithmetic outputs **conditional on assumptions**.

### Uncertainty and limitations (important)

- It is a planning approximation, not a Bayesian posterior over all uncertainties.
- Recall-vs-budget alignment is interpolated from prior traces.
- Dataset is only 300 records in current run; many large +additional scenarios hit cap.
- If candidate pool changes, these results can become stale.

### 6.3 Immediate vs contingent targets

Current recommendation artifact (`recommended_next_screening_targets.md`) states:

- **Immediate target**: +50 records
- **Contingent target**: move to +100 total additional if risk tolerance requires stronger confidence

Operational meaning:

1. Screen +50 now (quick risk-reduction sprint).
2. Reassess updated labels + metrics + residual FN estimate.
3. If needed, continue toward +100-equivalent cap for current pool.

---

## 7) Baseline-vs-improved comparator clarity (exact baseline definition + caveats)

### Exact baseline definition in this repo

When you read `baseline_vs_improved` tables, baseline means:

- the **pre-improvement pipeline** implemented in `analysis/train_asreview.py` (word TF-IDF + class-weighted logistic regression, threshold 0.5),
- run under its baseline split configuration,
- represented by baseline metrics artifact used in improved comparison step.

Improved means:

- best selected candidate from `analysis/train_asreview_improved.py`, currently `calibrated_svm_word_char`,
- selected by rule: `max(average_precision, then wss@95, then recall@20, then recall@50)`.

### Caveats when interpreting comparison tables

1. **Single split sensitivity**: one train/test split can over/understate differences.
2. **Small positive count in test fold**: threshold metrics can be volatile.
3. **Threshold dependence**: `@0.5` metrics can look weak while ranking metrics improve.
4. **Metric trade-offs are normal**: e.g., AP can improve while ROC-AUC is flat/slightly down.
5. **Comparator is historical snapshot**: after new labels, both baseline and improved runs may shift.

Use comparator as directional evidence, not absolute truth.

---

## 8) Decision playbook for a student (what to do this week)

This is the practical operating checklist.

### 8.1 This week’s default plan

1. Confirm current recommended policy and target from:
   - `analysis/outputs/planning_simulations/recommended_next_screening_targets.md`
2. Export queue and screen **+50** records in LAB.
3. Sync labels and run reconciliation checks.
4. Re-run analysis refresh pipeline.
5. Compare new FN/FP estimates and stop-policy outcomes.
6. Decide whether to continue to contingent target (+100 total additional).

### 8.2 Checks before adding +50 screens

Before committing reviewer time, check:

- Queue integrity manifest exists and record IDs are unique.
- Reconciliation report from previous batch has no major mismatch.
- Prevalence assumption for planning is still sensible.
- Current recommended target has not already hit cap (remaining unscreened too small).

### 8.3 Checks before moving from +50 to +100

Only escalate if at least one of these holds:

- residual FN estimate still above team tolerance,
- confidence requirement is strict (e.g., near-95% recall target governance),
- updated rankings still show plausible yield in next tranche.

Pause/escalate discussion if:

- incremental yield appears near-zero,
- cap is effectively reached,
- new labels reveal drift or annotation inconsistency.

### 8.4 When to retrain / rerun analyses

Rerun full analysis pipeline when:

- a new screening batch is completed (especially +50 scale),
- label distribution changes noticeably,
- policy decisions depend on updated risk numbers,
- before publishing or briefing stakeholders.

Minimum rerun set for decision updates is effectively the full chain in `scripts/run_analysis_and_report_refresh.sh`.

---

## 9) Glossary (explicit terms)

**Active learning**: iterative learning where model selects (or prioritizes) what to label next, then retrains as new labels arrive.

**AP (Average Precision)**: area-like summary of precision-recall curve; emphasizes ranking quality for positives.

**ASReview LAB**: interactive tool used by reviewers to screen records with ML-assisted prioritization.

**Baseline model**: pre-improvement reference pipeline (`analysis/train_asreview.py`) used for comparison.

**Brier score**: probability calibration error metric (lower generally better calibrated probabilities).

**Calibration**: transforming model scores/margins so they better behave like probabilities.

**Cap reached**: requested additional screening exceeds remaining unscreened records; effective additional is truncated.

**Character n-grams (`char_wb`)**: subword feature fragments from text that help robustness to spelling/format variation.

**Class imbalance**: strong skew between irrelevant and relevant class counts.

**Confusion matrix**: TP/FP/TN/FN table used to derive core classification metrics.

**Contingent target**: second-stage optional screening increment (here, move toward +100 total additional).

**Decision threshold**: score cutoff used to convert ranked scores into binary include/exclude labels.

**False negative (FN)**: relevant study missed by current screening/classification policy.

**False positive (FP)**: irrelevant study flagged/surfaced as potentially relevant.

**FeatureUnion**: scikit-learn mechanism combining multiple feature extractors (here word + char TF-IDF).

**F1 score**: harmonic mean of precision and recall.

**Immediate target**: first-stage recommended screening increment (here, +50).

**Leakage-safe queue**: production ranking export with label-like/sensitive columns removed.

**Linear SVM (`LinearSVC`)**: linear classifier that separates classes by maximizing margin; outputs margin scores.

**Logistic regression**: linear probabilistic classifier using sigmoid-transformed weighted features.

**NDCG**: ranking metric emphasizing gains near top ranks.

**Nested CV**: validation strategy with inner loop (e.g., threshold tuning) and outer loop (performance estimation) to reduce overfitting bias.

**No-hit window**: stopping heuristic based on long run of recently screened non-relevant records.

**Prevalence**: proportion of truly relevant records in candidate pool.

**Precision**: of predicted relevant, fraction truly relevant.

**Precision@k**: fraction relevant among top-k ranked records.

**Priority bucket**: high/medium/low operational queue tier based on score quantiles.

**R-precision**: precision at rank R, where R = number of relevant documents.

**Recall**: of truly relevant, fraction found.

**Recall@k**: fraction of all relevant documents found within top-k ranked records.

**Residual risk**: remaining concern (often FN-related) after current stopping point.

**ROC-AUC**: ranking-discrimination metric: probability positive outranks negative.

**SAFE-like rule**: heuristic based on an upper bound of expected remaining relevant records to trigger stop decisions.

**Screened fraction**: proportion of dataset reviewed at a point in the process.

**TF-IDF**: term-frequency/inverse-document-frequency representation of text features.

**Threshold tuning for recall target**: selecting cutoff so validation recall meets target (e.g., 0.90/0.95).

**True negative (TN)**: irrelevant study correctly not flagged.

**True positive (TP)**: relevant study correctly surfaced.

**WSS@95**: work saved over random sampling at 95% recall; can be negative if workload is high.

---

## 10) FAQ (common confusion points)

### Q1) “Why is precision low even when model is ‘better’?”

Because “better” here often means better **ranking for high recall** and lower FN risk, not necessarily high binary precision at a fixed threshold.

### Q2) “Does low precision mean we should stop using ML?”

Not necessarily. If recall gains and FN reduction per workload are acceptable, ML prioritization can still be useful.

### Q3) “Should I trust threshold-0.5 metrics?”

Treat them as one view only. For screening, emphasize AP, recall@k, and policy-level FN/workload trade-offs.

### Q4) “If ROC-AUC is okay, are we safe?”

No. ROC-AUC can look decent while practical precision and high-recall workload remain challenging.

### Q5) “Why do +200 and +400 sometimes look identical to +100?”

Because this dataset is small; additional requests can hit remaining-record cap.

### Q6) “Can I compare current numbers directly to last month’s without caveats?”

Only if data pool, labels, and split/evaluation setup are comparable. Active learning evolves; snapshots are time-dependent.

### Q7) “What is the single most important risk to watch?”

Residual false negatives at the chosen stopping policy, balanced against reviewer workload.

### Q8) “When in doubt, what should I do?”

Run staged screening (+50), sync labels, rerun full refresh, and reassess with updated simulation outputs before escalating.

---

## Appendix: key files to keep open while working

- `analysis/train_asreview.py`
- `analysis/train_asreview_improved.py`
- `analysis/run_asreview_next_steps.py`
- `analysis/planning_simulations.py`
- `analysis/outputs/improved/metrics_best.json`
- `analysis/outputs/improved/comparison_baseline_vs_improved.csv`
- `analysis/outputs/next_steps/stopping_policy_summary.csv`
- `analysis/outputs/planning_simulations/recommended_next_screening_targets.md`
- `integration/asreview_lab_hooks.py`

This is your core “control panel” for model understanding + operational decisions.
