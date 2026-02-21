# Recommended Next Screening Targets

## Recommendation logic
- Prefer the smallest additional-screening increment that meaningfully reduces expected FN while retaining useful work-saved percentage.
- Use medium-prevalence scenarios as primary planning signal; check low/high as sensitivity bounds.

## Recommended targets
1. **Immediate target: +50 additional records**
   - Expected to materially reduce FN in both threshold policies while preserving non-trivial work saved.
   - Operationally feasible as a short sprint batch.
2. **Contingent target: move to +100 total additional records**
   - Use if confidence requirements are strict (e.g., risk tolerance near 95%+ recall expectations).
   - In this dataset, larger requests (+200/+400) are capped by remaining unscreened records.

## Policy-specific guidance
- If operating at recall_target_90, +100 effectively exhausts the current unscreened pool (cap).
- If operating at recall_target_95, +79 effectively exhausts the current unscreened pool (cap reached from +100 request onward).

## Practical next action
- Schedule a two-stage screening sprint: +50 now, reassess model metrics and residual-risk estimate, then decide whether to continue to the +100-equivalent cap for the current dataset.
