# Scaling Playbook: ASReview + CrowdScreen + Dory for Very Large Screening Corpora

> Audience: review teams moving from ~300 labeled records to hundreds of thousands/millions of unlabeled records.
>
> Context: tailored to this repository (`asys_comp`) and its current ASReview workflow (`analysis/`, `integration/`, `infra/asreview-lab/`).

---

## 0) Executive summary (recommended path for this repo)

If you want one practical default path:

1. **Keep Covidence (if used) as the governance/adjudication system of record** for formal dual-screen decisions and PRISMA traceability.
2. **Use ASReview LAB as the prioritization engine** (active learning) to decide what humans screen next.
3. **Use CrowdScreen when you have many reviewers** and need parallel AI-guided assignment.
4. **Use Dory for harder corpora** (multilingual, noisy, very large) after baseline benchmarking.
5. **Do not jump to autonomous exclusion early.** Require explicit risk gates, audit sampling, and drift controls before any selective auto-decision policy.

---

## 1) Recommended architecture (Covidence vs ASReview roles)

### 1.1 Role split if you use both systems (recommended for high-assurance reviews)

| System | Primary role | What should live there | What should *not* live there |
|---|---|---|---|
| Covidence | Governance + consensus + reporting | Final include/exclude decisions, conflict resolution, full-text stage, PRISMA counts, audit record for publication | Experimental model ranking logic, rapid model iteration |
| ASReview LAB | Prioritization + active-learning loop | Ranked queue generation, iterative human labeling, simulation, model diagnostics | Final irreversible exclusion policy without safeguards |
| `asys_comp` repo | Reproducible analytics + integration bridge | Training scripts, ranking exports, sync/reconcile hooks, dashboards, run manifests | Manual one-off decisions without logged artifacts |

### 1.2 Architecture pattern in this repo

```text
Search exports (RIS/CSV/etc)
  -> canonical record table in repo (deduped, versioned)
  -> ASReview/LAB screening queue (ranked)
  -> human labels (LAB/CrowdScreen or Covidence)
  -> label normalization + reconciliation (integration/asreview_lab_hooks.py)
  -> model refresh + new ranked queue
  -> final consensus and publication-grade decisions
```

### 1.3 Choose one of these operating modes

| Mode | When to use | Pros | Tradeoff |
|---|---|---|---|
| **ASReview-first** | You need speed and tight active-learning control | Fast model iteration; easy simulation | You must build stronger governance discipline yourself |
| **Covidence-first with ASReview assist** | Clinical/publication environment with strict SOPs | Strong audit/compliance posture | Extra integration overhead |
| **Hybrid (recommended here)** | You need both scale and conservative risk control | Best balance of speed + defensibility | Requires clear role boundaries |

---

## 2) Data lifecycle and run versioning (seed 300 -> v2 large ingest)

Treat each major corpus change as a **versioned run family**.

### 2.1 Naming convention

Use immutable run IDs:

- `R001_seed300`
- `R002_add_250k_2026Q1`
- `R003_add_1p2M_multisource_2026Q2`

Recommended folder pattern:

```text
data/screening_runs/
  R001_seed300/
  R002_add_250k_2026Q1/
  R003_add_1p2M_multisource_2026Q2/
```

### 2.2 Lifecycle stages

| Stage | Output | Owner | Gate to continue |
|---|---|---|---|
| Ingest raw exports | source snapshots + checksums | data steward | all sources logged, file hashes captured |
| Normalize + dedupe | canonical `records.csv` | data engineer | duplicate-rate report reviewed |
| Seed labeling | `labels_events.csv` | reviewers | class balance + seed quality checked |
| Active-learning cycles | ranked queue + batch labels | screening team | KPI dashboard within expected range |
| Consensus/adjudication | `consensus_decisions.csv` | senior reviewers | conflicts resolved, reasons logged |
| Freeze snapshot | manifest + archive | project lead | reproducible package complete |

### 2.3 **New run vs append** decision table (critical)

| Situation | Append to current run? | Start new run? | Why |
|---|---|---|---|
| <5% new records, same topic/query window | ✅ Usually | ❌ | distribution likely stable |
| 5–25% new records, same topic but new time window | ⚠️ Maybe | ✅ preferred | drift possible; compare run-level KPIs |
| New databases / changed eligibility framing / multilingual expansion | ❌ | ✅ required | model assumptions changed materially |
| Major dedupe algorithm change | ❌ | ✅ required | record universe changed |
| You need publication-grade reproducibility cut | ❌ | ✅ required | freeze immutable evidence trail |

**Rule of thumb:** if your team asks “can we still compare this directly to prior metrics?”, start a new run.

### 2.4 Example trajectory for your current state

- **Now:** `R001_seed300` (current ~300 labels)
- **Next:** `R002_add_large_unlabeled` (first bulk ingest + strict overlap design)
- **Then:** `R003_multilingual_or_cross-domain` (consider Dory + additional safeguards)

---

## 3) Ingestion strategy for huge unlabeled corpora

### 3.1 Required ingestion principles

1. **Immutable source snapshots** (never overwrite raw exports).
2. **Stable `record_id` generation** (same record = same ID across runs).
3. **Layered deduplication** (exact first, fuzzy second, manual for borderline).
4. **Chunking for throughput** (don’t load millions as one monolith in UI workflows).
5. **Rich metadata retained** for auditing and drift analysis.

### 3.2 Recommended `record_id` strategy

Use deterministic hash over normalized bibliographic fingerprint:

`sha1(lower(title)|lower(first_author)|year|doi_or_pmid)`

If DOI/PMID missing, fallback to title+author+year hash and mark `id_confidence="fallback"`.

### 3.3 Dedupe pipeline

| Step | Method | Keep/discard rule |
|---|---|---|
| Exact DOI/PMID dedupe | exact key match | keep highest metadata completeness |
| Exact title-year dedupe | normalized exact string | keep record with abstract present |
| Fuzzy title dedupe | trigram/cosine/Jaro-Winkler | score >= threshold -> candidate pair review |
| Human confirm pass | reviewer adjudication for uncertain pairs | log decision in dedupe audit file |

### 3.4 Chunking strategy at scale

For millions of records, create **operational chunks** (e.g., 50k–200k):

- `chunk_id = C0001, C0002, ...`
- preserve global rank and global `record_id`
- track `ingest_batch_id` and `chunk_id` in every downstream label record

### 3.5 Minimum metadata fields to preserve

- source database
- source query string/version
- retrieval date
- language
- publication year
- DOI/PMID/other identifiers
- dedupe method outcome

---

## 4) Active-learning operating cadence (batch sizes + retrain rhythm)

### 4.1 Practical cadence by maturity

| Phase | Typical label volume | Batch size | Retrain frequency | Goal |
|---|---|---|---|---|
| Warm-up | 300 -> 800 | 25–50 | every batch | stabilize early ranking |
| Expansion | 800 -> 5,000 | 50–100 | every batch (or every 2 batches) | maximize relevant yield |
| Scale | 5,000+ | 100–250 | every 1–2 batches | throughput with monitoring |
| Tail | late-stage low-yield | 100–250 + audits | every batch | verify stopping confidence |

### 4.2 Daily/weekly operating rhythm

- **Daily:** screen assigned batch, sync labels, update queue.
- **2–3x per week:** KPI review (yield, disagreement, drift, recall proxy).
- **Weekly:** overlap/kappa review + adjudication backlog burn-down.
- **Per run milestone:** stopping gate review with senior sign-off.

### 4.3 Suggested command loop in this repo

```bash
# 1) Produce/refresh ranked output and diagnostics
scripts/run_analysis_and_report_refresh.sh

# 2) Export queue to LAB/CrowdScreen import format
python integration/asreview_lab_hooks.py export-queue \
  --ranking analysis/outputs/next_steps/production_ranking_leakage_safe.csv \
  --output infra/asreview-lab/data/queue_for_lab.csv

# 3) After reviewers label in LAB, normalize and reconcile
python integration/asreview_lab_hooks.py sync-labels \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_labels_snapshot.json

python integration/asreview_lab_hooks.py reconcile-roundtrip \
  --queue infra/asreview-lab/data/queue_for_lab.csv \
  --labels infra/asreview-lab/data/lab_labels_export.csv \
  --output integration/outputs/lab_roundtrip_report.json
```

---

## 5) Multi-reviewer design: overlap + kappa + adjudication

### 5.1 Assignment policy (recommended baseline)

| Stream | Share of records | Who screens | Purpose |
|---|---|---|---|
| Primary stream | 70–80% | single assigned reviewer | throughput |
| Overlap QA stream | 20–30% | double-screened | agreement measurement |
| Adjudication stream | all conflicts + sampled auto-decisions | senior adjudicator(s) | final consensus and safety |

### 5.2 Kappa computation plan

- Compute **Cohen’s kappa** for pairwise reviewer combinations weekly.
- Also track:
  - raw agreement,
  - prevalence-adjusted interpretation,
  - disagreement direction (include-vs-exclude asymmetry).

Interpretation guardrails (heuristic):

| Kappa | Interpretation | Action |
|---|---|---|
| >= 0.80 | strong | maintain cadence |
| 0.67–0.79 | acceptable but watch | targeted calibration meeting |
| < 0.67 | concerning | pause high-automation plans; retrain reviewer calibration |

### 5.3 Adjudication protocol

1. Generate conflict queue from overlap labels.
2. Require reason codes (`population mismatch`, `design`, `outcome`, etc.).
3. Adjudicator sets final decision + rationale.
4. Feed consensus label back into training set.
5. Track reviewer-specific disagreement hotspots for coaching.

---

## 6) Stopping policy and risk gates toward selective auto-decisions

### 6.1 Use multi-signal stopping (not one metric)

Stop/slow only when all are stable:

1. **Low recent yield**: very few includes in recent screened window.
2. **Recall proxy high**: simulation/validation suggests near-target recall.
3. **Upper-bound remaining relevant low**: conservative bound below team threshold.
4. **Agreement stable**: overlap and kappa not degrading.
5. **No major drift**: new chunks similar enough to trained distribution.

### 6.2 Risk-gate ladder

| Gate | Human involvement | Allowed automation | Required evidence |
|---|---|---|---|
| G0 (default) | Full human review | None | baseline QA only |
| G1 | Human reviews all excludes; AI prioritizes order | ranking only | stable yield + agreement for >=2 review cycles |
| G2 | Human reviews all includes + sampled excludes | selective low-risk auto-exclude candidates | kappa >=0.8, drift controlled, audit pass |
| G3 | Human audits random + risk-targeted samples | constrained auto-decisions in pre-specified strata only | sustained KPI performance across run versions |

**Recommendation for current stage (~300 labels): remain at G0/G1.**

---

## 7) Explicit guardrails for autonomous exclusion (non-negotiable)

Autonomous exclusion is high risk in evidence synthesis. Use these guardrails:

1. **Never auto-exclude records lacking abstract/title quality** (missingness can hide relevance).
2. **Never auto-exclude rare populations/outcomes without stratified checks.**
3. **Never enable auto-exclusion in a new run before overlap/kappa stabilization.**
4. **Always perform random audit sampling** of machine-excluded records (minimum fixed sample + risk-based sample).
5. **Always keep reversible decisions** (machine exclusions are provisional until audit window closes).
6. **Trigger immediate rollback to human-only** if drift or miss-rate alarms fire.

Minimum audit policy example:

- Randomly audit at least `max(200, 1%)` of machine-excluded records per run segment.
- If critical miss(es) found in audit, expand audit + suspend auto-exclusion.

---

## 8) ASReview CrowdScreen: role and setup pattern

### 8.1 Where CrowdScreen fits

Use CrowdScreen when:

- you have many screeners,
- need parallelized assignment,
- want centralized logging of who labeled what and when.

### 8.2 Practical setup pattern for this repo

1. Build ranked queue in repo (`analysis/outputs/next_steps/production_ranking_leakage_safe.csv`).
2. Export queue (`integration/asreview_lab_hooks.py export-queue`).
3. Import into ASReview/CrowdScreen server project.
4. Invite reviewers and define overlap policy externally (team SOP).
5. Export labels to `infra/asreview-lab/data/lab_labels_export.csv`.
6. Run `sync-labels` and `reconcile-roundtrip` locally for audit + refresh.

### 8.3 CrowdScreen strengths and limits

| Strength | Limitation |
|---|---|
| Massive parallel throughput | Requires governance of reviewer calibration |
| Full action logging | Does not replace final adjudication SOP |
| Works with AI ranking | Quality still depends on label quality and overlap controls |

---

## 9) ASReview Dory: where it helps, where it doesn’t, integration options

ASReview Dory is an official ASReview extension with more advanced components (e.g., heavier and multilingual-capable options) intended for harder/larger datasets.

### 9.1 Dory helps most when

- corpus is multilingual,
- title/abstract language is noisy/heterogeneous,
- baseline models plateau in early recall,
- compute resources are available.

### 9.2 Dory does **not** solve

- poor/biased labels,
- absent adjudication,
- governance requirements,
- domain shift without monitoring.

### 9.3 Integration options

| Option | Pattern | When to choose |
|---|---|---|
| A: Benchmark first | Run simulation comparisons vs baseline in a fully labeled subset | safest default |
| B: Side-by-side production trial | Dory ranks one stream, baseline ranks another; compare yield/disagreement | when team has capacity for controlled experiment |
| C: Promote to default | Use Dory model as main ranking engine per run family | only after sustained KPI win and stable audits |

Install note (environment-dependent):

```bash
pip install asreview-dory
```

Expect heavier compute and slower retraining than lightweight baselines.

---

## 10) Suggested KPI dashboard (what to monitor every cycle)

Track these in one run-level dashboard.

| KPI | Definition | Data source in repo | Cadence | Alert threshold |
|---|---|---|---|---|
| Recall proxy | estimated recall from simulation/validation curves | `analysis/outputs/next_steps/*.csv` | weekly | below target band |
| Precision@k / yield | includes found per batch (or per 100 screened) | label events + ranking | each batch | sustained decline |
| Work saved | unscreened fraction at current recall proxy | planning simulation outputs | weekly | lower than expected |
| Disagreement rate | proportion conflicting in overlap set | overlap labels | weekly | increasing trend |
| Kappa | reviewer agreement corrected for chance | overlap labels | weekly | <0.67 caution, <0.6 severe |
| Drift index | lexical/embedding shift of new chunk vs training corpus | ingest metadata + text stats | per ingest chunk | exceeds preset limit |
| Auto-exclusion audit miss rate | relevant found in machine-excluded audit sample | audit sample log | per auto segment | any severe miss triggers rollback |

---

## 11) First 30-day implementation checklist

### Week 1 — Foundations

- [ ] Define run naming/versioning convention (`R00x_*`).
- [ ] Finalize canonical CSV schemas (records, labels, consensus).
- [ ] Freeze current seed set as `R001_seed300` snapshot.
- [ ] Document overlap and adjudication SOP (owner + SLA).

### Week 2 — Ingestion hardening

- [ ] Ingest first large unlabeled tranche.
- [ ] Run deterministic ID generation + dedupe pipeline.
- [ ] Produce chunk manifests and duplicate audit report.
- [ ] Validate import/export roundtrip with `reconcile-roundtrip`.

### Week 3 — Multi-reviewer operations

- [ ] Launch reviewer assignments with 20–30% overlap.
- [ ] Compute first weekly kappa and disagreement diagnostics.
- [ ] Hold calibration session on top disagreement reasons.
- [ ] Update model cadence (batch size + retrain schedule).

### Week 4 — Safety gates and next-step automation planning

- [ ] Create KPI dashboard review template.
- [ ] Define explicit G0/G1/G2 gate criteria and sign-off authority.
- [ ] Trial Dory in benchmark mode on a controlled subset.
- [ ] Decide: stay at G1 or run a constrained G2 pilot with audits.

---

## 12) Concrete CSV schemas for this repo

Use these as the canonical contracts across scripts and teams.

### 12.1 `records_master.csv` (record schema)

Recommended path per run:

`data/screening_runs/<RUN_ID>/records_master.csv`

| Column | Type | Required | Description |
|---|---|---|---|
| record_id | string | ✅ | stable unique ID (deterministic hash/fingerprint) |
| title | string | ✅ | record title |
| abstract | string | ✅ | abstract text (empty allowed but flagged) |
| year | int | ⛔ | publication year |
| authors | string | ⛔ | raw authors string |
| journal | string | ⛔ | source venue |
| doi | string | ⛔ | DOI if present |
| pmid | string | ⛔ | PMID if present |
| language | string | ⛔ | language code/name |
| source_db | string | ✅ | source system/database |
| source_query_id | string | ✅ | query version identifier |
| retrieved_at_utc | datetime | ✅ | retrieval timestamp |
| ingest_batch_id | string | ✅ | ingest batch identifier |
| chunk_id | string | ✅ | operational chunk tag |
| dedupe_status | string | ✅ | `unique`/`dedupe_removed`/`manual_keep` etc. |
| id_confidence | string | ✅ | `exact_id`/`fallback` |

Example:

```csv
record_id,title,abstract,year,doi,source_db,source_query_id,retrieved_at_utc,ingest_batch_id,chunk_id,dedupe_status,id_confidence
c4f1...,Example title,Example abstract,2024,10.1000/xyz,PubMed,Q1_2026,2026-02-23T00:00:00Z,B2026_01,C0001,unique,exact_id
```

### 12.2 `labels_events.csv` (label schema)

Recommended path per run:

`data/screening_runs/<RUN_ID>/labels_events.csv`

| Column | Type | Required | Description |
|---|---|---|---|
| label_event_id | string | ✅ | unique event ID |
| run_id | string | ✅ | run family ID |
| record_id | string | ✅ | FK to records table |
| reviewer_id | string | ✅ | reviewer identifier |
| decision | int | ✅ | `1=include`, `0=exclude` |
| decision_reason_code | string | ⛔ | optional taxonomy code |
| decision_confidence | int | ⛔ | reviewer confidence (e.g., 1–5) |
| screened_at_utc | datetime | ✅ | decision timestamp |
| assignment_type | string | ✅ | `primary`/`overlap`/`audit` |
| model_score_at_assignment | float | ⛔ | AI score shown at assignment |
| model_version | string | ⛔ | model ID/version |
| chunk_id | string | ✅ | operational chunk |

Example:

```csv
label_event_id,run_id,record_id,reviewer_id,decision,decision_reason_code,screened_at_utc,assignment_type,model_score_at_assignment,model_version,chunk_id
LE0001,R002_add_250k_2026Q1,c4f1...,rev_a,0,population_mismatch,2026-03-02T10:12:00Z,primary,0.082,svm_char_word_v3,C0001
```

### 12.3 `consensus_decisions.csv` (consensus/adjudication schema)

Recommended path per run:

`data/screening_runs/<RUN_ID>/consensus_decisions.csv`

| Column | Type | Required | Description |
|---|---|---|---|
| consensus_id | string | ✅ | unique consensus row ID |
| run_id | string | ✅ | run ID |
| record_id | string | ✅ | FK to records |
| final_decision | int | ✅ | final include/exclude |
| consensus_method | string | ✅ | `single`, `double_agree`, `adjudicated`, `audit_override` |
| reviewer_a_decision | int | ⛔ | overlap decision A |
| reviewer_b_decision | int | ⛔ | overlap decision B |
| adjudicator_id | string | ⛔ | who resolved conflict |
| adjudication_reason | string | ⛔ | rationale text/code |
| resolved_at_utc | datetime | ✅ | finalization time |
| eligible_for_training | bool | ✅ | whether to feed back into model training |

Example:

```csv
consensus_id,run_id,record_id,final_decision,consensus_method,reviewer_a_decision,reviewer_b_decision,adjudicator_id,adjudication_reason,resolved_at_utc,eligible_for_training
CS0099,R002_add_250k_2026Q1,c4f1...,1,adjudicated,0,1,senior_1,outcome_relevant,2026-03-04T16:40:00Z,true
```

### 12.4 Compatibility note with existing integration hooks

Current helper script expectations:

- queue export requires: `queue_rank, score_include, title, abstract, record_id, priority_bucket`
- label normalization accepts typical variants and outputs normalized fields equivalent to:
  - `record_id`
  - `decision` (0/1)
  - `decision_time`

Reference implementation: `integration/asreview_lab_hooks.py`

---

## Appendix A) Minimal governance policy template

Before each run starts, explicitly record:

- run objective and eligibility scope,
- gate level (G0/G1/G2/G3),
- who can approve gate transitions,
- audit sample size policy,
- rollback criteria,
- publication/reporting requirements.

This single page prevents most scaling failures.

---

## Appendix B) What to do next in this repo (immediate)

1. Create `R001_seed300` folder structure under `data/screening_runs/`.
2. Move current seed labels into the `labels_events.csv` schema.
3. Start `R002_*` as a **new run**, not an append, for the first major large ingest.
4. Enforce 20–30% overlap from day one of R002.
5. Keep automation at G0/G1 until kappa, drift, and audit signals are consistently stable.
