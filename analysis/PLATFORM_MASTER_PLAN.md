# PLATFORM_MASTER_PLAN

## 0) Purpose and scope
This document is an execution-ready master plan for turning the current ASReview analysis into a reviewer-facing platform that combines:
1. A public-facing website that explains ASReview and this project.
2. A technical analysis portal with methods, results, and risk interpretation.
3. A reviewer workflow to continue screening in ASReview LAB.
4. Continuous model updates and transparent reporting as labels accumulate.

Primary repo context: `/home/kana/git/asys/screening-model`.

---

## 1) Current state and evidence baseline

### 1.1 Existing analysis assets already in repo
- Baseline/improved model training + evaluation scripts:
  - `analysis/train_asreview.py`
  - `analysis/train_asreview_improved.py`
  - `analysis/run_asreview_next_steps.py`
- Existing output families:
  - `analysis/outputs/improved/*`
  - `analysis/outputs/next_steps/*`
- Existing reports:
  - `analysis/ASREVIEW_IMPROVEMENT_REPORT.md`
  - `analysis/NEXT_STEPS_EXECUTION_REPORT.md`

### 1.2 Why additional review is still needed
From prior outputs:
- High-recall operation still had non-zero residual false-negative risk at stopping points.
- At 90%-target stopping policy (`asreview_prior_1p1n`), average stop near ~197 docs left meaningful residual FN risk.
- At 95%-target policy, average stop near ~221 docs lowered risk but still left expected residual FN.

New planning simulations (`analysis/outputs/planning_simulations/*`) reinforce this:
- **Medium prevalence (observed) estimates:**
  - 90%-policy baseline implied ~4 expected FN; +50 screening reduced FN to ~0.87; +100 reduced FN to ~0.
  - 95%-policy baseline implied ~2 expected FN; +50 screening reduced FN to ~0.77; +79 (cap in this dataset) reduced FN to ~0.
- Practical implication: a staged extension (+50 first, then reassess, then continue if needed) is justified by risk reduction.

---

## 2) Product vision and operating model

## 2.1 End-state capabilities
1. **Public Website**
   - Explains ASReview and this project’s methodology in plain language.
   - Displays current status metrics and what they mean for reviewers.
2. **Technical Analysis Section**
   - Full reproducible methods, assumptions, data lineage, and outputs.
   - Versioned run manifests and model comparison views.
3. **Reviewer Workspace + ASReview LAB**
   - Reviewers invited, onboarded, and assigned projects.
   - Seamless handoff from website portal to LAB screening tasks.
4. **Continuous Update Engine**
   - Scheduled/triggered retraining and re-ranking.
   - Automatic refresh of dashboard metrics and risk summaries.

## 2.2 Success definition
- Reviewers can continue screening with clear instructions and minimal friction.
- Stakeholders can see current projected FN/FP risk and estimated remaining workload.
- Every published metric is reproducible from versioned code/data/config.
- Operational changes are auditable and reversible.

---

## 3) Architecture decisions (ADR-style)

## 3.1 Decision A — Platform architecture
**Decision:** Modular web platform + workflow services + ASReview LAB integration.

**Chosen topology:**
- Frontend website + reviewer portal (Next.js)
- Backend API (FastAPI)
- Worker service for ML/reports (Python Celery/RQ)
- Metadata DB (PostgreSQL)
- Queue/cache (Redis)
- Object storage for artifacts (S3/MinIO)
- ASReview LAB service (containerized)

**Why:**
- Fits current Python-based analytics stack.
- Clean separation between UI, orchestration, and model pipelines.
- Supports incremental rollout without rewriting existing scripts immediately.

## 3.2 Decision B — Data and artifact persistence
**Decision:**
- PostgreSQL for structured operational data.
- Object store for model binaries, rankings, simulation outputs, and manifests.
- Git + DVC (or git-annex equivalent) for versioned data snapshots where needed.

## 3.3 Decision C — Model lifecycle
**Decision:**
- Maintain explicit model registry metadata (version, training data hash, config hash, metrics).
- Promotion gates: `candidate -> validated -> production`.

## 3.4 Decision D — Continuous updates
**Decision:**
- Event-triggered retraining on label batch completion + nightly scheduled validation run.
- Dashboard refresh only after validation pass.

## 3.5 Decision E — Human oversight
**Decision:**
- No fully autonomous policy updates.
- Stop/restart decisions and policy threshold changes require reviewer-lead approval.

---

## 4) Deployment topology

## 4.1 Environments
- **Local dev**: Docker Compose (single host).
- **Staging**: Cloud VM(s) or k8s namespace with production-like config.
- **Production**: Hardened environment, managed DB backups, TLS, monitoring, alerting.

## 4.2 Core services
- `web` (Next.js)
- `api` (FastAPI)
- `worker` (Celery/RQ)
- `scheduler` (periodic jobs)
- `postgres`
- `redis`
- `minio`/S3 client
- `asreview-lab`
- `reverse-proxy` (Traefik/Nginx)
- `observability` (Prometheus + Grafana + Loki/ELK)

## 4.3 Network and trust boundaries
- Public ingress: website + docs pages.
- Authenticated ingress: reviewer portal + admin.
- Internal-only: queue, DB, worker, object storage API.
- ASReview LAB behind authenticated proxy with project-scoped access.

---

## 5) Data model (minimum viable schema)

## 5.1 Entities
1. `projects`
   - `id`, `name`, `status`, `created_at`, `owner_id`, `asreview_project_id`
2. `records`
   - `id`, `project_id`, `source_id`, `title`, `abstract`, `metadata_json`, `dedup_key`
3. `labels`
   - `id`, `record_id`, `project_id`, `reviewer_id`, `decision`, `decision_time`, `source` (lab/manual/import)
4. `reviewers`
   - `id`, `email`, `name`, `role`, `active`
5. `screening_batches`
   - `id`, `project_id`, `batch_type`, `size`, `created_at`, `completed_at`
6. `model_versions`
   - `id`, `project_id`, `version_tag`, `training_data_hash`, `code_commit`, `config_hash`, `status`
7. `model_metrics`
   - `id`, `model_version_id`, `metric_name`, `metric_value`, `split`, `timestamp`
8. `rankings`
   - `id`, `model_version_id`, `record_id`, `rank`, `score`, `priority_bucket`
9. `simulation_runs`
   - `id`, `project_id`, `scenario_name`, `input_manifest_hash`, `output_artifact_uri`, `created_at`
10. `audit_events`
   - `id`, `actor_id`, `event_type`, `entity_type`, `entity_id`, `payload_json`, `timestamp`

## 5.2 Data retention and deletion
- Keep immutable metric snapshots and model manifests.
- Soft-delete operational rows where appropriate.
- Hard-delete only via audited admin runbook.

---

## 6) Pipelines (end-to-end)

## 6.1 Pipeline P1 — Ingestion and normalization
1. Import bibliographic data.
2. Validate schema and required fields.
3. Normalize text fields and identifiers.
4. Deduplicate.
5. Persist records + ingestion report.

## 6.2 Pipeline P2 — Screening queue generation
1. Use active model to score records.
2. Build leakage-safe ranking export.
3. Assign priority buckets.
4. Sync queue to reviewer portal and/or ASReview LAB.

## 6.3 Pipeline P3 — Screening label sync
1. Poll/pull labels from ASReview LAB.
2. Validate and append to `labels`.
3. Trigger model update eligibility checks.

## 6.4 Pipeline P4 — Retraining and evaluation
1. Build training snapshot from approved labels.
2. Train candidate model(s).
3. Evaluate with fixed protocol + seed sweep.
4. Register artifacts and metrics.
5. Promote if acceptance criteria pass.

## 6.5 Pipeline P5 — Simulation refresh
1. Recompute additional-screening scenarios (+50/+100/+200/+400).
2. Update FN/FP risk projections by prevalence bands.
3. Publish latest simulation tables and recommendation note.

## 6.6 Pipeline P6 — Website/report publication
1. Render technical markdown + metrics into static/SSR pages.
2. Version outputs with timestamp and model version.
3. Publish with changelog and run manifest link.

---

## 7) UX plan

## 7.1 Public website IA
- Home: What ASReview is + why this project exists.
- Methods: Full technical methodology and assumptions.
- Results: Current metrics, risk projections, simulation charts.
- Reviewer page: How to join and use screening workflow.
- Governance: Reproducibility, versioning, and audit policy.

## 7.2 Reviewer portal UX
- Dashboard: assigned projects, pending batches, current risk estimate.
- Screening handoff: launch to ASReview LAB with context.
- Progress: docs screened, recall proxy, projected FN range.
- Notifications: “new model available”, “batch target reached”, “validation passed/failed”.

## 7.3 Admin UX
- Invite/revoke reviewers.
- Configure thresholds and batch goals.
- Trigger retraining/simulation jobs.
- View audit logs and deployment status.

---

## 8) ASReview LAB integration strategy

## 8.1 Integration mode
- Run ASReview LAB as a dedicated service in same deployment domain (or subdomain).
- Maintain project mapping table between internal `projects.id` and LAB project IDs.

## 8.2 Data handshake
- Export queue to LAB-compatible dataset format.
- Import reviewer decisions at fixed intervals (e.g., every 10 min) or webhook-driven when possible.
- Keep immutable sync checkpoints with hashes.

## 8.3 Reviewer invitation workflow
1. Admin creates project in portal.
2. Admin uploads/links dataset and configures threshold policy.
3. Admin sends invite emails with one-time token.
4. Reviewer accepts invitation and completes onboarding.
5. Reviewer is provisioned in LAB with project role.
6. Reviewer starts screening batches (default +50 batch sprint).
7. Labels sync back to platform; dashboard updates.

## 8.4 Conflict handling
- Multi-reviewer conflicts routed to lead adjudication queue.
- All adjudications logged with before/after label state.

---

## 9) Reproducibility framework

## 9.1 Environment pinning
- Python environment lockfile (`requirements.lock` or `poetry.lock`).
- Container image digest pinning for all deployable services.
- Explicit OS/base image versions.

## 9.2 Data/version control
- Version raw input snapshots with checksum manifests.
- Track derived datasets and outputs with DVC-style metadata.
- Every report references exact input hashes and code commit.

## 9.3 Run logs and manifests
Each run writes:
- `run_id`
- git commit SHA
- config file hash
- data snapshot hash
- start/end timestamps
- command line + environment summary
- artifact URIs

## 9.4 Model registry and lineage
For each promoted model:
- Training dataset/version
- Hyperparameters
- Validation metrics
- Calibration metadata
- Promotion approver + timestamp

## 9.5 Audit trails
- All threshold changes, promotions, rollbacks, and manual overrides logged in `audit_events`.
- Immutable append-only export of critical events for compliance.

---

## 10) Security and privacy

## 10.1 Identity and access
- SSO/OAuth2 where available.
- RBAC roles: `reviewer`, `lead`, `admin`, `ops`.
- Least privilege by default.

## 10.2 Data security
- TLS in transit.
- Encryption at rest for DB/object storage.
- Secrets in vault/secret manager, never in repo.

## 10.3 Operational security controls
- MFA for admin accounts.
- Session timeout + token rotation.
- IP allowlisting for admin endpoints (if feasible).
- Dependency and container vulnerability scanning in CI.

## 10.4 Privacy posture
- Store only minimum metadata needed for screening process.
- Redact personal data from logs.
- Define retention period and deletion workflow.

---

## 11) Validation protocol and acceptance criteria

## 11.1 Validation tiers
1. **Unit/integration checks** (pipeline correctness).
2. **Model validation checks** (AP, recall-target metrics, drift checks).
3. **Operational checks** (sync reliability, dashboard freshness).
4. **Reviewer acceptance checks** (UX + onboarding flow).

## 11.2 Core acceptance criteria (initial release)
- AC-1: End-to-end ingest -> screen -> retrain -> publish cycle completes in staging.
- AC-2: Reproducibility: rerun with same snapshot reproduces metrics within tolerance.
- AC-3: Simulation refresh generates all required artifacts and publishes latest recommendation.
- AC-4: Reviewer invite-to-first-screen action time < 15 minutes median.
- AC-5: Backup restore test completed successfully.
- AC-6: Security baseline (RBAC, TLS, secrets) verified.

## 11.3 Model gate criteria (example)
- Candidate model must not degrade AP by >2% relative from current production unless approved with rationale.
- Candidate must meet configured recall policy evidence threshold and pass calibration sanity checks.
- Candidate promotion requires lead sign-off.

---

## 12) Operations and SRE plan

## 12.1 Observability
- Metrics: job durations, queue lag, model refresh latency, sync errors, API latency.
- Logs: structured JSON logs with run IDs and project IDs.
- Alerts:
  - Label sync stalled > 30 min
  - Retrain pipeline failed
  - Dashboard data older than SLA

## 12.2 SLO examples
- 99% API availability (business hours).
- < 15 min label sync freshness.
- < 60 min model refresh after batch completion (normal load).

## 12.3 Incident response
- Severity matrix (SEV1/SEV2/SEV3).
- On-call rota for ops/admin.
- Post-incident review template in repo.

---

## 13) Exact runbooks

## 13.1 Local development runbook
Prereqs:
- Docker + Docker Compose
- Python 3.10+
- Node 20+

Steps:
1. Clone repo and enter:
   ```bash
   cd /home/kana/git/asys/screening-model
   ```
2. Create env file:
   ```bash
   cp .env.example .env
   ```
3. Start platform stack:
   ```bash
   docker compose -f infra/docker-compose.dev.yml up -d
   ```
4. Install Python deps:
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```
5. Run DB migrations:
   ```bash
   alembic upgrade head
   ```
6. Start API:
   ```bash
   uvicorn platform_api.main:app --reload --host 0.0.0.0 --port 8000
   ```
7. Start worker:
   ```bash
   celery -A platform_worker.celery_app worker -l INFO
   ```
8. Start frontend:
   ```bash
   cd web && pnpm install && pnpm dev
   ```
9. Smoke test:
   ```bash
   ./scripts/smoke_local.sh
   ```

## 13.2 Staging deployment runbook
1. Merge to `main` with green CI.
2. Build and push images:
   ```bash
   ./scripts/build_and_push.sh --env staging
   ```
3. Apply infra changes:
   ```bash
   ./scripts/deploy_infra.sh --env staging
   ```
4. Run migrations:
   ```bash
   ./scripts/run_migrations.sh --env staging
   ```
5. Deploy services:
   ```bash
   ./scripts/deploy_app.sh --env staging
   ```
6. Run staging validation suite:
   ```bash
   ./scripts/validate_release.sh --env staging
   ```
7. Promote staging release tag if all checks pass.

## 13.3 Production deployment runbook
1. Confirm approved release tag and rollback tag.
2. Freeze admin config changes during release window.
3. Deploy in order:
   ```bash
   ./scripts/deploy_infra.sh --env prod
   ./scripts/run_migrations.sh --env prod
   ./scripts/deploy_app.sh --env prod
   ```
4. Run post-deploy checks:
   ```bash
   ./scripts/smoke_prod.sh
   ./scripts/check_freshness.sh --max-age-min 15
   ```
5. Announce release + known changes.

## 13.4 Rollback runbook
Trigger rollback if SEV1 or failed release criteria.

Steps:
1. Route traffic to safe mode (read-only dashboards if needed).
2. Roll app services back:
   ```bash
   ./scripts/rollback_app.sh --env prod --to-tag <previous_tag>
   ```
3. If migration incompatible, execute DB rollback plan:
   ```bash
   ./scripts/rollback_db.sh --env prod --to-revision <rev>
   ```
4. Re-run smoke tests and verify data integrity.
5. Publish incident note + ETA for reattempt.

## 13.5 Backup and restore runbook
Backup schedule:
- DB full backup nightly, WAL/archive every 15 min.
- Object storage versioning enabled.
- Weekly restore drill in staging.

Commands (example wrappers):
```bash
./scripts/backup_db.sh --env prod
./scripts/backup_artifacts.sh --env prod
./scripts/restore_db.sh --env staging --backup-id <id>
./scripts/restore_artifacts.sh --env staging --snapshot <id>
```

Acceptance for backup drills:
- Restore completes within agreed RTO.
- Restored metrics and artifact manifests match checksums.

---

## 14) Documentation standards and repository conventions

## 14.1 Standards
- Every analysis/report must state:
  - data snapshot id
  - code commit
  - configuration
  - date/time and owner
- Use markdown with stable heading structure.
- Include machine-readable output sidecars (CSV/JSON) for every key table.

## 14.2 Proposed folder conventions
```text
analysis/
  outputs/
    planning_simulations/
    model_runs/
  reports/
platform/
  api/
  worker/
  web/
infra/
  docker/
  terraform/
  k8s/
scripts/
docs/
  runbooks/
  adr/
```

## 14.3 Naming conventions
- Runs: `YYYYMMDD_HHMM_<project>_<purpose>`
- Models: `<project>_v<major>.<minor>.<patch>`
- Artifacts include SHA256 manifest files.

---

## 15) Roadmap, milestones, dependencies, effort estimates

## 15.1 Milestone roadmap (high-level)

### M0 — Foundation hardening (1-2 weeks)
- Standardize env, manifests, run metadata.
- Finalize simulation artifacts and recommendation workflow.

### M1 — Core platform skeleton (2-3 weeks)
- API + DB + auth + minimal frontend shell.
- Basic project/reviewer management.

### M2 — ASReview LAB integration (2-3 weeks)
- Project sync, reviewer invitation, label ingestion.
- End-to-end screening handoff.

### M3 — Continuous model update engine (2-4 weeks)
- Retrain pipeline, model registry, promotion gates.
- Automatic dashboard refresh.

### M4 — Public website + technical reporting (2-3 weeks)
- Methods/results pages.
- Versioned simulation + risk updates.

### M5 — Hardening and production launch (2-3 weeks)
- Security controls, observability, backup drills, runbooks validation.

Estimated total: **11-18 weeks** depending staffing and infra readiness.

## 15.2 Dependencies
- Infrastructure provisioning (domains, TLS, storage, DB).
- Identity provider decision (or local auth fallback).
- Reviewer availability for UAT.
- Data governance sign-off.

## 15.3 Team assumptions
- 1 technical lead / architect
- 1 backend/data engineer
- 1 frontend engineer
- 0.5 MLOps/DevOps engineer
- 0.5 reviewer lead/domain expert for acceptance and policy decisions

---

## 16) Risks and mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---:|---|
| Overconfidence in stopping policy | Missed relevant studies | Medium | Enforce staged +50 then reassess; keep FN projection visible |
| Label sync inconsistency with LAB | Data drift / wrong retraining | Medium | Idempotent sync, checkpoints, reconciliation jobs |
| Reproducibility drift | Loss of trust | Medium | Mandatory manifests + lockfiles + CI reproducibility tests |
| Reviewer onboarding friction | Low adoption | Medium | Guided onboarding + short training + support loop |
| Security misconfiguration | High | Low-Med | RBAC audits, secret manager, staging pen test |
| Deployment rollback complexity | High | Low-Med | Pretested rollback scripts + migration strategy |

---

## 17) Immediate execution sequence (next 10 working days)
1. Lock and publish simulation outputs (already generated under `analysis/outputs/planning_simulations/`).
2. Approve staged screening plan (+50 now, reassess, then continue if required).
3. Scaffold platform directories (`platform/`, `infra/`, `docs/runbooks/`).
4. Implement minimal API + schema for projects/reviewers/labels/model_versions.
5. Stand up ASReview LAB staging instance and test invitation + sync.
6. Build first reviewer dashboard with current simulation and risk cards.
7. Add CI checks for run manifests and output schema validation.

---

## 18) Definition of done (program level)
Program is done when all are true:
- Website, technical analysis pages, and reviewer workflow are live.
- ASReview LAB is integrated with invitation + sync workflows.
- Continuous model updates run reliably with validation gates.
- Reproducibility and audit controls are operational.
- Backup/restore and rollback runbooks are tested and signed off.
- Stakeholders can inspect current FN/FP risk and planned screening volumes from published simulation outputs.
