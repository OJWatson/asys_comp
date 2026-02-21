# NEXT_STEPS Execution Report

## Implemented next recommended steps
1. Added active-learning simulation (query/update loop) with run-level traces and policy-based stop evaluation.
2. Added nested CV + seed sweeps for threshold stability at recall targets (0.90/0.95).
3. Added leakage-safe production ranking export + manifest of removed sensitive fields.
4. Added target-recall stopping diagnostics, including SAFE-like statistical upper-bound checks.
5. Added ASReview prior/seed strategy experiments (known relevant + known irrelevant templates).

## Data/config
- Columns detected: {'title': 'titles', 'abstract': 'abstract', 'label': 'final_decision'}
- Output directory: `/home/kana/git/asys/screening-model/analysis/outputs/next_steps`

## Nested CV + seed sweep results
- ap: 0.5635 ± 0.0996
- roc_auc: 0.8140 ± 0.0811
- threshold_recall_0.90: 0.1066 ± 0.0283
- threshold_recall_0.95: 0.0741 ± 0.0200
- recall@thr90: 0.8533 ± 0.1364
- recall@thr95: 0.9122 ± 0.1213
- precision@thr90: 0.2308 ± 0.0493
- precision@thr95: 0.1903 ± 0.0230

## Prior strategy simulation results
- Best strategy by workload to 95% recall: **asreview_prior_1p1n**
- Mean docs to 95% recall (best): 220.80
- Mean docs to 95% recall (worst): 225.20
- Improvement: 4.40 fewer docs screened to reach 95% recall

### Strategy table
| strategy | runs | docs_to_recall_0_90_mean | docs_to_recall_0_90_std | docs_to_recall_0_95_mean | docs_to_recall_0_95_std | wss90_mean | wss95_mean | first_relevant_rank_mean |
|---|---|---|---|---|---|---|---|---|
| asreview_prior_1p1n | 5 | 196.8000 | 20.3887 | 220.8000 | 5.4498 | 0.2440 | 0.2140 | 2.0000 |
| random_12_no_prior | 5 | 194.2000 | 4.6043 | 221.6000 | 6.0249 | 0.2527 | 0.2113 | 12.6000 |
| asreview_prior_2p10n | 5 | 204.4000 | 15.2414 | 225.2000 | 4.6043 | 0.2187 | 0.1993 | 11.0000 |

## Stopping diagnostics summary
| strategy | policy | docs_screened_mean | docs_screened_std | recall_mean | screened_fraction_mean | wss95_if_reached_mean |
|---|---|---|---|---|---|---|
| asreview_prior_1p1n | oracle_target_recall_90 | 196.8000 | 20.3887 | 0.9070 | 0.6560 | nan |
| asreview_prior_1p1n | oracle_target_recall_95 | 220.8000 | 5.4498 | 0.9535 | 0.7360 | 0.2140 |
| asreview_prior_1p1n | safe_like_upper_remaining<=1 | 287.2000 | 4.4944 | 0.9953 | 0.9573 | -0.0073 |
| asreview_prior_1p1n | no_hit_window_50 | 296.0000 | 8.9443 | 0.9953 | 0.9867 | -0.0367 |
| asreview_prior_1p1n | safe_like_and_no_hit_50 | 296.0000 | 8.9443 | 0.9953 | 0.9867 | -0.0367 |
| asreview_prior_2p10n | oracle_target_recall_90 | 204.4000 | 15.2414 | 0.9070 | 0.6813 | nan |
| asreview_prior_2p10n | oracle_target_recall_95 | 225.2000 | 4.6043 | 0.9535 | 0.7507 | 0.1993 |
| asreview_prior_2p10n | safe_like_upper_remaining<=1 | 289.0000 | 1.5811 | 1.0000 | 0.9633 | -0.0133 |
| asreview_prior_2p10n | no_hit_window_50 | 298.0000 | 4.4721 | 1.0000 | 0.9933 | -0.0433 |
| asreview_prior_2p10n | safe_like_and_no_hit_50 | 298.0000 | 4.4721 | 1.0000 | 0.9933 | -0.0433 |
| random_12_no_prior | oracle_target_recall_90 | 194.2000 | 4.6043 | 0.9070 | 0.6473 | nan |
| random_12_no_prior | oracle_target_recall_95 | 221.6000 | 6.0249 | 0.9535 | 0.7387 | 0.2113 |
| random_12_no_prior | safe_like_upper_remaining<=1 | 290.6000 | 0.5477 | 1.0000 | 0.9687 | -0.0187 |
| random_12_no_prior | no_hit_window_50 | 300.0000 | 0.0000 | 1.0000 | 1.0000 | -0.0500 |
| random_12_no_prior | safe_like_and_no_hit_50 | 300.0000 | 0.0000 | 1.0000 | 1.0000 | -0.0500 |

## Generated artifacts
- `analysis/outputs/next_steps/active_learning_traces.csv`
- `analysis/outputs/next_steps/active_learning_runs.csv`
- `analysis/outputs/next_steps/prior_strategy_summary.csv`
- `analysis/outputs/next_steps/stopping_policy_outcomes_by_run.csv`
- `analysis/outputs/next_steps/stopping_policy_summary.csv`
- `analysis/outputs/next_steps/nested_cv_seed_sweep_details.csv`
- `analysis/outputs/next_steps/nested_cv_seed_sweep_summary.csv`
- `analysis/outputs/next_steps/nested_cv_seed_sweep_per_seed.csv`
- `analysis/outputs/next_steps/production_ranking_leakage_safe.csv`
- `analysis/outputs/next_steps/production_ranking_manifest.json`

## What remains
- Validate stopping-policy choices with domain stakeholders before operational use.
- Add external validation on an independent screening dataset.
- Integrate simulation diagnostics into CI/regression tracking if this workflow is productized.
