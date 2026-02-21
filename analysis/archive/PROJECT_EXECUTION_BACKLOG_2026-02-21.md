# PROJECT_EXECUTION_BACKLOG

Prioritized implementation backlog for the reviewer-facing ASReview platform.

Legend:
- Priority: P0 (highest) -> P3
- Estimate: engineer-days (ED)
- Type: FE / BE / Data / MLOps / Ops / UX / Docs

## Execution status snapshot (Phase-2 update: 2026-02-21)

- ✅ **Done:** P0-01, P0-02, P0-03, P0-05
- 🟡 **In progress (advanced this run):**
  - P0-06 (CI baseline): GitHub Pages publish workflow + static integrity/smoke checks added; still missing broader lint/test gates and PR-required checks policy
  - P1-09 (ASReview LAB deploy path): local containerized runbook hardened with roundtrip reconciliation checks
  - P1-11 / P1-12 (LAB queue + sync): queue export manifest + sync reconciliation report now emitted for reviewer ops integrity
  - P2-07 (public methods/results pages): refactored for static-host compatibility and GitHub Pages deployment
  - P2-09 (reproducibility rerun checks): deterministic artifact integrity checks and static-site smoke checks added (CI-wired)
  - DOC-02 / DOC-03: reviewer/admin deployment docs expanded with GitHub Pages + hybrid architecture workflow
- ⏳ **Not started / deferred:** P1-01, P1-02, P1-03, P1-04, P1-05, P1-06, P1-07, P1-08, P1-10, P1-13, P2-01..P2-06, P2-08, P2-10..P2-13, P3-01..P3-08

---

## P0 — Must start immediately

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P0-01 | Freeze and version simulation artifacts (`planning_simulations`) | Data/Docs | 1 | None | CSV/JSON/MD artifacts published with manifest + commit hash |
| P0-02 | Define canonical config schema for runs (YAML/JSON) | Data/MLOps | 1 | P0-01 | All analysis scripts consume validated config file |
| P0-03 | Add run metadata manifest standard (`run_id`, data hash, code SHA) | Data/MLOps | 2 | P0-02 | Every run emits manifest JSON; CI fails if absent |
| P0-04 | Decide and document architecture ADRs (service boundaries + storage) | Arch/Docs | 1 | None | ADR docs merged and approved |
| P0-05 | Create platform skeleton directories (`platform/`, `infra/`, `docs/runbooks/`) | BE/Ops | 1 | P0-04 | Repository tree in place with README stubs |
| P0-06 | Set up baseline CI (lint/test/artifact schema checks) | Ops | 2 | P0-05 | CI green with required checks enforced on PR |
| P0-07 | Reviewer policy decision checkpoint (+50 staged batch) | Product/Domain | 0.5 | P0-01 | Signed decision note committed |

---

## P1 — Core platform MVP

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P1-01 | Implement PostgreSQL schema (projects, records, labels, model_versions, audit_events) | BE | 3 | P0-05 | Alembic migrations applied in local + staging |
| P1-02 | Build FastAPI service skeleton + health endpoints | BE | 2 | P1-01 | `/health`, `/ready`, `/version` pass smoke tests |
| P1-03 | Implement auth + RBAC roles (reviewer/lead/admin) | BE/Ops | 3 | P1-02 | Role-protected endpoints tested |
| P1-04 | Build project/reviewer management endpoints | BE | 3 | P1-03 | CRUD endpoints documented and tested |
| P1-05 | Build label ingestion endpoint + validation | BE/Data | 3 | P1-01,P1-02 | Invalid payloads rejected; valid labels persisted |
| P1-06 | Build minimal frontend shell (dashboard, project list, login) | FE | 4 | P1-02,P1-03 | Reviewer can sign in and view assigned projects |
| P1-07 | Implement object-storage artifact writer + manifest uploader | Data/Ops | 2 | P1-02 | Artifacts uploaded with checksums |
| P1-08 | Add structured logging and request correlation IDs | BE/Ops | 1 | P1-02 | Logs include trace/run IDs |

---

## P1.5 — ASReview LAB integration MVP

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P1-09 | Deploy ASReview LAB in staging (container + proxy + auth gate) | Ops | 2 | P0-05 | LAB accessible in staging behind auth |
| P1-10 | Build project mapping table (`project_id <-> lab_project_id`) | BE | 1 | P1-01,P1-09 | Mapping persisted and queryable |
| P1-11 | Export queue in LAB-compatible format | Data/BE | 2 | P1-05,P1-10 | Project export imports cleanly into LAB |
| P1-12 | Implement periodic label sync from LAB to platform | BE/Data | 3 | P1-10,P1-11 | New LAB labels appear in platform <15 min |
| P1-13 | Reviewer invitation workflow (token invite + role assignment) | BE/FE | 3 | P1-03,P1-04,P1-09 | Reviewer invited and can start first screening batch |

---

## P2 — Continuous model and reporting workflow

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P2-01 | Worker queue service (Celery/RQ) for retraining + simulations | Data/MLOps | 2 | P1-02,P1-07 | Async jobs run and report status |
| P2-02 | Register existing scripts as pipeline tasks | Data | 3 | P2-01 | Train/eval/sim tasks callable via API |
| P2-03 | Model registry tables + artifact contracts | Data/BE | 2 | P1-01,P2-01 | Candidate/validated/production states supported |
| P2-04 | Promotion gate evaluator (metrics + policy checks) | Data/MLOps | 3 | P2-02,P2-03 | Failing candidates blocked from promotion |
| P2-05 | Automatic simulation refresh on batch completion | Data | 2 | P2-02 | New `planning_simulations` artifacts generated automatically |
| P2-06 | Dashboard cards for FN/FP risk and workload projection | FE/BE | 3 | P2-05,P1-06 | Updated risk projections visible to reviewers |
| P2-07 | Public methods/results pages from markdown + JSON | FE/Docs | 3 | P2-05 | Website shows latest versioned reports |
| P2-08 | Changelog + run manifest page | FE/BE | 2 | P2-03,P2-05 | Every published update links to run metadata |

---

## P2.5 — Validation, QA, and governance

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P2-09 | Reproducibility rerun test in CI (fixed snapshot) | Data/Ops | 2 | P2-02 | CI rerun metrics within tolerance |
| P2-10 | Data quality checks (schema, missingness, duplicates) | Data | 2 | P1-05 | DQ report generated per ingestion |
| P2-11 | Conflict/adjudication queue for multi-reviewer disagreements | FE/BE | 3 | P1-13 | Lead can resolve conflicts with audit log |
| P2-12 | Audit event coverage (threshold changes, promotions, rollbacks) | BE | 2 | P2-03 | All critical actions logged and queryable |
| P2-13 | UAT with reviewer cohort (scripted test cases) | UX/Product | 2 | P2-06,P2-11 | UAT report complete with pass/fail checklist |

---

## P3 — Production hardening and launch

| ID | Item | Type | Estimate | Dependencies | Acceptance criteria |
|---|---|---|---:|---|---|
| P3-01 | Staging/prod IaC (networking, storage, secrets wiring) | Ops | 4 | P1-09 | Environments reproducible from IaC |
| P3-02 | Observability stack (Prometheus/Grafana/Loki + alerts) | Ops | 3 | P1-08 | Alert rules active and tested |
| P3-03 | Backup + restore automation scripts | Ops | 2 | P1-01,P1-07 | Successful weekly restore drill |
| P3-04 | Rollback automation (app + migration-safe DB strategy) | Ops/BE | 3 | P3-01 | Rollback tested in staging |
| P3-05 | Security hardening (MFA, RBAC audit, vuln scans) | Ops/Sec | 3 | P3-01 | Security checklist signed off |
| P3-06 | Performance/load test for API + worker queues | BE/Ops | 2 | P2-01 | Meets latency and freshness SLO targets |
| P3-07 | Production cutover runbook dry-run | Ops/Product | 1 | P3-01..P3-06 | Dry-run complete with issues resolved |
| P3-08 | Launch + hypercare week | All | 5 | P3-07 | No critical open issues after hypercare |

---

## Cross-cutting documentation backlog

| ID | Item | Estimate | Done when |
|---|---|---:|---|
| DOC-01 | API contract docs (OpenAPI + examples) | 1 ED | Published and linked from portal |
| DOC-02 | Reviewer onboarding guide (5-10 min path) | 1 ED | New reviewer can complete without assistance |
| DOC-03 | Admin operations handbook | 2 ED | Covers invites, reruns, rollbacks, incident actions |
| DOC-04 | Incident response + postmortem templates | 0.5 ED | Templates versioned in `docs/runbooks/` |
| DOC-05 | Data dictionary + metric definitions | 1 ED | All dashboard metrics traceable to formulas |

---

## Suggested sprint sequence (first 4 sprints)

### Sprint 1 (focus: foundations)
- P0-01..P0-07
- P1-01, P1-02

### Sprint 2 (focus: MVP API + UI)
- P1-03..P1-08
- P1-09

### Sprint 3 (focus: LAB integration)
- P1-10..P1-13
- P2-01

### Sprint 4 (focus: model/report loop)
- P2-02..P2-08
- P2-09

---

## Backlog governance
- Re-prioritize weekly using risk + value + dependency constraints.
- Any change to threshold policy or promotion gate must include:
  1) rationale,
  2) expected FN/FP impact,
  3) rollback path,
  4) approver.
- Keep this backlog aligned with `analysis/PLATFORM_MASTER_PLAN.md` milestones.
