# Simulation Summary: Additional Screening Planning

## Scope
- Strategy baseline: `asreview_prior_1p1n` from `analysis/outputs/next_steps/`.
- Threshold policy scenarios: recall-targeted 90% and 95%.
- Additional screening scenarios requested: +50, +100, +200, +400.
- Prevalence sensitivity bands: low (10%), medium (observed), high (20%).

## Method (planning approximation)
1. Use active-learning traces to estimate recall-vs-screening progression.
2. Anchor baseline at the observed stopping-policy means:
   - recall_target_90: 197 docs screened, recall 0.907.
   - recall_target_95: 221 docs screened, recall 0.953.
3. Convert each scenario to TP/FP/TN/FN by treating the screened budget as selected records and unscreened as deferred records.
4. Cap additional screening at remaining documents in this 300-record dataset (cap flag shown in outputs).

## Medium-prevalence highlights
### recall_target_90
- +50 requested (effective +50): TP=42.13, FN=0.87, recall=0.980, precision=0.171, work_saved=53 docs (17.7%), FN reduction vs baseline=3.13.
- +100 requested (effective +100): TP=43.00, FN=0.00, recall=1.000, precision=0.145, work_saved=3 docs (1.0%), FN reduction vs baseline=4.00.
- +200 requested (effective +103): TP=43.00, FN=0.00, recall=1.000, precision=0.143, work_saved=0 docs (0.0%), FN reduction vs baseline=4.00.
- +400 requested (effective +103): TP=43.00, FN=0.00, recall=1.000, precision=0.143, work_saved=0 docs (0.0%), FN reduction vs baseline=4.00.

### recall_target_95
- +50 requested (effective +50): TP=42.23, FN=0.77, recall=0.982, precision=0.156, work_saved=29 docs (9.7%), FN reduction vs baseline=1.23.
- +100 requested (effective +79): TP=43.00, FN=0.00, recall=1.000, precision=0.143, work_saved=0 docs (0.0%), FN reduction vs baseline=2.00.
- +200 requested (effective +79): TP=43.00, FN=0.00, recall=1.000, precision=0.143, work_saved=0 docs (0.0%), FN reduction vs baseline=2.00.
- +400 requested (effective +79): TP=43.00, FN=0.00, recall=1.000, precision=0.143, work_saved=0 docs (0.0%), FN reduction vs baseline=2.00.

## Notes
- Scenarios with `cap_reached=true` exceed available unscreened records in the current dataset; effective additional screening is capped.
- For operational planning beyond this dataset, re-run this simulation after ingesting a larger candidate pool.
