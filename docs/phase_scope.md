# RecoveryOS Phase Scope

**Status:** Proposed scope map  
**Execution source:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Product source:** [PRD.md](./PRD.md)  
**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)

## 1. Purpose

This document defines the business and technical boundary of each implementation phase. `IMPLEMENTATION_PLAN.md` owns the detailed sprint/task sequence; this document explains what each phase delivers, what it must not absorb, and how it is accepted. The repository currently has no implementation, so every phase is `PLANNED`.

## 2. Scope conventions

- `MVP` means required for the Buildathon product boundary.
- `Stretch` may be implemented only after the first vertical slice is safe.
- `Future` is not a phase completion dependency.
- `Out of Scope` must not be represented as implemented behavior.
- Every phase requires relevant unit/integration tests, E2E tests for functionality built so far, regression E2E tests, and objective exit criteria. Documentation is not a phase completion prerequisite.

## 3. Phase scope matrix

| Phase | Business capability | Primary dependency | Status |
|---|---|---|---|
| 0 | Reproducible engineering baseline | None | Planned |
| 1 | Durable financial/workflow persistence | Phase 0 | Planned |
| 2 | Trusted, normalized, idempotent events | Phase 1 | Planned |
| 3 | One case per obligation and legal lifecycle | Phase 2 | Planned |
| 4 | Explainable diagnosis and economic prioritization | Phase 3 | Planned |
| 5 | Safe advisory AI | Phase 4 | Planned |
| 6 | Deterministic bounded decisioning | Phase 5 | Planned |
| 7 | Durable asynchronous execution | Phase 6 | Planned |
| 8 | Provider adapters and reproducible simulation | Phase 7 | Planned |
| 9 | Authoritative recovery and race safety | Phase 8 | Planned |
| 10 | Systemic degradation restraint | Phase 9 | Planned |
| 11 | Recovery measurement and lift | Phase 9 | Planned |
| 12 | Typed application API | Core services | Planned |
| 13 | Merchant operations dashboard | Phase 12 | Planned |
| 14 | Authentication, RBAC, tenant isolation | Phase 12 | Planned |
| 15 | Security, audit, and observability hardening | Core runtime | Planned |
| 16 | Reliability and complete test matrix | Core runtime | Planned |
| 17 | Full integrated workflow | Phases 1–16 core paths | Planned |
| 18 | Release validation and Buildathon demo | Phase 17 | Planned |

## 4. Detailed phase definitions

### Phase 0 — Foundation & Repository Baseline

**Phase Objective:** Establish the pnpm/Turborepo workspace, app/package boundaries, configuration validation, and quality gates.

**Business Capability:** None directly; enables predictable delivery of RecoveryOS.

**Technical Scope:** Workspace manifests, `apps/web`, `apps/api`, `packages/ui`, scripts, CI, lint, typecheck, build, and environment shape.

**In Scope:** Greenfield repository bootstrap, shared UI package boundary, root commands, CI gate, UI architecture check, `.env.example`.

**Out of Scope:** Payment workflows, database schema, real provider credentials, product UI, and microservices.

**Dependencies:** Git and approved runtime availability.

**Inputs:** Architecture baseline, decisions, repository state.

**Outputs:** Installable workspace with failing-fast configuration and quality commands.

**Major Components:** Root workspace, Turborepo, package manifests, CI/scripts.

**Data Impact:** None.

**API Impact:** None.

**Security Impact:** Secret placeholders only; no credentials.

**Testing Scope:** Install, task discovery, lint/typecheck/build smoke, configuration validation.

**Risks:** Wrong package boundary or unnecessary dependency growth.

**Acceptance Criteria:** Clean install and quality commands run; shared UI cannot be bypassed; CI detects failures.

**Phase Exit Criteria:** Reproducible repository baseline exists and no product implementation shortcut is hidden.

### Phase 1 — Database & Persistence

**Phase Objective:** Provide migrated PostgreSQL persistence with constraints and transactional repository primitives.

**Business Capability:** Durable storage for obligations, cases, events, actions, jobs, and audit.

**Technical Scope:** SQLAlchemy models, Alembic migrations, repositories, unit-of-work/transaction patterns, locks, indexes.

**In Scope:** All entities supported by `DATA_MODEL.md`, integer money, tenant keys, uniqueness, foreign keys, job leases.

**Out of Scope:** Event ingestion behavior, provider calls, UI, and model inference.

**Dependencies:** Phase 0 and PostgreSQL runtime.

**Inputs:** Canonical data model and migration configuration.

**Outputs:** Fresh database migration and repository interfaces/implementations.

**Major Components:** `apps/api` persistence/config/migrations.

**Data Impact:** Creates baseline schema.

**API Impact:** None or internal persistence only.

**Security Impact:** Tenant constraints, secret-free connection config, least privilege assumptions.

**Testing Scope:** Migration, constraint, rollback, transaction, locking, tenant-scope tests.

**Risks:** Incorrect unique constraints or floating-point fields.

**Acceptance Criteria:** Duplicate identities are rejected; transactions are atomic; fresh migration succeeds.

**Phase Exit Criteria:** Repositories support required domain invariants and concurrency primitives.

### Phase 2 — Event Ingestion & Idempotency

**Phase Objective:** Turn provider/simulator input into trusted canonical events exactly once.

**Business Capability:** Reliable revenue-risk event intake.

**Technical Scope:** Webhook validation, signature verification, normalization, correlation IDs, processed-event identity, replay.

**In Scope:** Payment, checkout, subscription, invoice, opt-out, action, and incident event categories.

**Out of Scope:** Case scoring, AI, execution, dashboard, and multi-provider expansion.

**Dependencies:** Phase 1 and provider fixtures.

**Inputs:** Signed provider-style payloads.

**Outputs:** Canonical persisted event or safe rejection/duplicate result.

**Major Components:** API ingestion, adapters, event application service.

**Data Impact:** Revenue events and processed event records.

**API Impact:** Webhook boundary only.

**Security Impact:** Signature/replay checks, input limits, redaction.

**Testing Scope:** Invalid signature, malformed payload, duplicate/concurrent delivery, replay.

**Risks:** Spoofed event or duplicate domain effect.

**Acceptance Criteria:** Invalid signatures mutate nothing; duplicate events are no-ops.

**Phase Exit Criteria:** Events are validated, normalized, correlated, persisted, and idempotent.

### Phase 3 — Recovery Case Engine

**Phase Objective:** Create one Recovery Case per business obligation and enforce its lifecycle.

**Business Capability:** Unified revenue-risk workflow across payment attempts and sources.

**Technical Scope:** Obligation identity, case association, attempts, state machine, transition audit.

**In Scope:** Order, checkout, subscription cycle, invoice identity; legal/illegal transitions; terminal states.

**Out of Scope:** AI, external action, advanced analytics, and UI polish.

**Dependencies:** Phases 1–2.

**Inputs:** Canonical eligible events and authoritative obligation references.

**Outputs:** Case/attempt records and auditable state transitions.

**Major Components:** Domain, application, persistence, audit.

**Data Impact:** Obligations, cases, attempts, case evidence references, audit.

**API Impact:** Internal service contract only.

**Security Impact:** Merchant/customer scoping.

**Testing Scope:** Identity, concurrent creation, all state transitions, terminal restrictions, audit atomicity.

**Risks:** Multiple cases for one obligation.

**Acceptance Criteria:** Multiple attempts converge on one case; illegal transitions are rejected.

**Phase Exit Criteria:** Case identity and state machine are correct independently of AI/UI.

### Phase 4 — Root Cause & Deterministic Scoring

**Phase Objective:** Explain why money is at risk and prioritize by expected economic value.

**Business Capability:** Better next action than generic retry/reminder.

**Technical Scope:** Root-cause mapping, probability v1, Expected Recoverable Revenue, priority v1.

**In Scope:** Configurable coefficients, confidence, evidence, versions, clamping, deterministic tie-breaks.

**Out of Scope:** Production ML training, LLM probability, provider execution.

**Dependencies:** Phase 3, scoring config, integer money.

**Inputs:** Case attempts, method, failure, customer metadata, incident facts.

**Outputs:** Diagnosis and score snapshots.

**Major Components:** Diagnosis/scoring modules and application analysis.

**Data Impact:** Case score fields and evidence/recommendation inputs.

**API Impact:** Internal analysis data.

**Security Impact:** Minimized customer evidence.

**Testing Scope:** Pure score, missing data, range, arithmetic, ordering, and version tests.

**Risks:** False confidence or financial total contamination.

**Acceptance Criteria:** Scores are explainable/configured and never alter actual recovered totals.

**Phase Exit Criteria:** Analysis output is stable input to AI and policy.

### Phase 5 — AI Recommendation Layer

**Phase Objective:** Add useful, constrained interpretation without giving AI financial authority.

**Business Capability:** Evidence-based next-best-action recommendation.

**Technical Scope:** AIProvider, structured schema, prompt/model versions, fallback, evaluation.

**In Scope:** Registered actions, reason/evidence/confidence, timeout, malformed response handling.

**Out of Scope:** Arbitrary tools, direct execution, AI-generated probability, autonomous payment truth.

**Dependencies:** Phase 4 and action registry.

**Inputs:** Minimized evidence and scoring context.

**Outputs:** Validated recommendation or safe fallback.

**Major Components:** AI adapter, recommendation service, evaluation fixtures.

**Data Impact:** Recommendations and evidence snapshots.

**API Impact:** Internal application contract.

**Security Impact:** Prompt injection resistance, redaction, provider secret protection.

**Testing Scope:** Schema, unsafe output, timeout, unavailable provider, low confidence, evaluation set.

**Risks:** Hallucinated action or provider outage.

**Acceptance Criteria:** Every output is allow-listed/validated and has a safe fallback.

**Phase Exit Criteria:** AI and fallback use the same downstream policy path.

### Phase 6 — Policy Engine & Decisioning

**Phase Objective:** Make every action deterministic, bounded, tenant-configurable, and auditable.

**Business Capability:** Safe autonomy and human approval.

**Technical Scope:** Policy schema/version, precedence, contact limits, quiet hours, incident suppression, approvals, stops.

**In Scope:** All PRD policy results and policy version persistence.

**Out of Scope:** External provider effects and enterprise RBAC.

**Dependencies:** Phases 3–5, policy tables, role seam.

**Inputs:** Recommendation/fallback, case/payment/incident/customer/policy context.

**Outputs:** Policy decision, approval task, schedule/stop/suppress result.

**Major Components:** Policy evaluator, config, approval service, audit.

**Data Impact:** Policies, versions, decisions, action intent.

**API Impact:** Internal decision contract.

**Security Impact:** Policy Admin controls and approval authorization.

**Testing Scope:** Every precedence branch, conflict, approval, terminal/opt-out, channel and limit test.

**Risks:** AI/policy bypass or mutable rule hardcoding.

**Acceptance Criteria:** No forbidden action executes; policy version/rule is auditable.

**Phase Exit Criteria:** Policy is the sole authority over execution permission.

### Phase 7 — Durable Jobs, Scheduler & Worker

**Phase Objective:** Execute scheduled work safely across retries and restarts.

**Business Capability:** Timely recovery intervention without duplicate contact.

**Technical Scope:** Durable jobs, leases, claims, retries, cancellation, dead-letter status, startup reconciliation.

**In Scope:** PostgreSQL-backed jobs and dedicated worker.

**Out of Scope:** Redis/hosted queue without decision change; unbounded retries.

**Dependencies:** Phase 6, database locks, action identity.

**Inputs:** Allowed/scheduled actions.

**Outputs:** Claimed/executed/cancelled/retried/dead-lettered job outcomes.

**Major Components:** Scheduler, worker, action service, provider interface.

**Data Impact:** Scheduled jobs and actions.

**API Impact:** Health/operational visibility later.

**Security Impact:** Worker identity, secret handling, policy recheck.

**Testing Scope:** Claims, lease expiry, restart, retry/backoff, cancellation, duplicate execution.

**Risks:** Lost work or duplicate outbound effect.

**Acceptance Criteria:** Jobs survive restart and execute at most once per idempotency key.

**Phase Exit Criteria:** Worker is durable, bounded, observable, and last-mile safe.

### Phase 8 — Provider Integrations & Simulator

**Phase Objective:** Supply honest provider/test adapters and reproducible synthetic batches.

**Business Capability:** Realistic Buildathon scenarios without fake totals.

**Technical Scope:** Payment/messaging/AI/scheduler adapters and seeded simulator.

**In Scope:** Razorpay Test Mode where configured, simulated messaging, provider failure injection, seeded event distributions.

**Out of Scope:** Claims of live proprietary network data; voice; unapproved providers.

**Dependencies:** Phases 1–7.

**Inputs:** Adapter contracts, seed/configuration, provider fixtures.

**Outputs:** Events/outcomes through the normal workflow.

**Major Components:** Integrations and simulator.

**Data Impact:** Events, cases, actions, costs, outcomes.

**API Impact:** Simulator controls later.

**Security Impact:** No real credentials in fixtures; labels.

**Testing Scope:** Contract parity, same-seed reproducibility, provider errors/rate limits.

**Risks:** Bypassing workflow with direct fake counters.

**Acceptance Criteria:** Derived dashboard totals come from persisted workflow outcomes.

**Phase Exit Criteria:** Real/test/simulated adapters are explicit and interchangeable.

### Phase 9 — Payment Reconciliation & Race Conditions

**Phase Objective:** Make authoritative success stop recovery and prevent stale outreach.

**Business Capability:** Correct recovered money and customer-safe intervention.

**Technical Scope:** Success reconciliation, cancellation, refunds/reversals, preflight and concurrency.

**In Scope:** Payment before/during worker execution, duplicate success, ambiguous provider response.

**Out of Scope:** Multi-touch attribution complexity.

**Dependencies:** Phases 7–8 and payment identity.

**Inputs:** Verified payment success/status and open case/jobs.

**Outputs:** Recovered case, exact amount, cancelled future work, adjustment records.

**Major Components:** Reconciliation, worker, payment adapter, attribution hook.

**Data Impact:** Payment attempts, obligations, cases, jobs, actions, audit.

**API Impact:** Success/status flows.

**Security Impact:** Server-authoritative verification.

**Testing Scope:** All payment races, duplicate success, refunds, reversals, recovery corrections.

**Risks:** Double-counting or message after payment.

**Acceptance Criteria:** No stale action sends; provider success is counted exactly once.

**Phase Exit Criteria:** Financial truth is correct under adversarial ordering.

### Phase 10 — Incident Detection & Suppression

**Phase Objective:** Recognize systemic degradation and avoid mass outreach.

**Business Capability:** Intelligent restraint during provider incidents.

**Technical Scope:** Configurable rolling detector, incident evidence/confidence, association, suppression, resolution/cooldown.

**In Scope:** Method/bank/gateway/issuer/error/merchant/region correlation where available.

**Out of Scope:** Proprietary real-time network telemetry.

**Dependencies:** Phase 9 event/payment facts and policy/jobs.

**Inputs:** Payment outcomes and configured baseline/current windows.

**Outputs:** Incident and affected-case suppression/rescheduling.

**Major Components:** Incident detector, case/policy/job services.

**Data Impact:** Incidents and case associations.

**API Impact:** Incident operational view later.

**Security Impact:** Tenant-scoped operational data.

**Testing Scope:** Threshold, correlation, flapping, resolution, suppression, cooldown.

**Risks:** False incident or mass contact.

**Acceptance Criteria:** Incident is not a financial obligation and affected outreach is suppressed visibly.

**Phase Exit Criteria:** Degradation demo works and targeted recovery resumes after cooldown.

### Phase 11 — Attribution & Recovery Measurement

**Phase Objective:** Measure natural versus assisted recovery and treatment lift.

**Business Capability:** Prove incremental recovery and intervention ROI honestly.

**Technical Scope:** Assignment, case attribution, windows, outcome classifications, metrics/read models.

**In Scope:** Control/treatment, natural/assisted/suppressed/unrecovered, costs, refunds/reversals.

**Out of Scope:** Complex multi-touch marketing attribution or causal certainty claims.

**Dependencies:** Reconciliation, actions, cases, experiment configuration.

**Inputs:** Case assignments, actions, verified success, adjustments.

**Outputs:** Case-level attribution and dashboard aggregates.

**Major Components:** Experiment/attribution/metrics services.

**Data Impact:** Experiments, assignments, attribution records.

**API Impact:** Metrics/experiments endpoints later.

**Security Impact:** Tenant-scoped analytics and PII minimization.

**Testing Scope:** Assignment, windows, duplicate success, multiple actions, adjustment.

**Risks:** Misleading lift or duplicate recovery.

**Acceptance Criteria:** Totals reconcile and limitations are visible.

**Phase Exit Criteria:** Measurement is reproducible, case-level, and labeled.

### Phase 12 — API Layer

**Phase Objective:** Expose typed safe application contracts for web and operations.

**Business Capability:** Usable access to cases, metrics, actions, and health.

**Technical Scope:** FastAPI routes, Pydantic schemas, OpenAPI client, errors, pagination, webhooks, health.

**In Scope:** Dashboard/cases/detail/incidents/approvals/policies/metrics/simulator/health.

**Out of Scope:** Frontend implementation and arbitrary admin endpoints.

**Dependencies:** Core services and auth seam.

**Inputs:** Authenticated requests and webhook events.

**Outputs:** Typed responses and safe errors.

**Major Components:** API routes/dependencies/schemas.

**Data Impact:** Read projections and authorized mutations.

**API Impact:** Creates first public application contract.

**Security Impact:** Input validation and authorization hooks.

**Testing Scope:** Contract, schema, pagination, safe errors, signatures, mutation rechecks.

**Risks:** Domain logic in routes or contract drift.

**Acceptance Criteria:** Web can consume typed API without duplicating domain rules.

**Phase Exit Criteria:** API is safe and sufficient for dashboard/E2E.

### Phase 13 — Merchant Dashboard / Frontend

**Phase Objective:** Make the recovery value and decisions understandable within seconds.

**Business Capability:** Merchant operations command center.

**Technical Scope:** Shared UI, dashboard, cases, incidents, policies, experiments, health, errors.

**In Scope:** Responsive Tailwind/shadcn experience, shared tokens/components in `packages/ui/src`.

**Out of Scope:** Financial logic in UI, generic chatbot, reusable components under web app.

**Dependencies:** Phase 12 API and Phase 0 UI package.

**Inputs:** Typed API responses and permission context.

**Outputs:** Interactive screens and operational actions.

**Major Components:** `apps/web`, `packages/ui/src`.

**Data Impact:** None directly; reads/actions through API.

**API Impact:** Consumes dashboard/case/health contracts.

**Security Impact:** Presentation hiding only; server remains authority.

**Testing Scope:** Component accessibility, route/API states, responsive/E2E flows.

**Risks:** Stale data or misleading metrics.

**Acceptance Criteria:** Dashboard answers five key questions; case timeline is reconstructable.

**Phase Exit Criteria:** Responsive, accessible, usable operations UI.

### Phase 14 — Authentication, Authorization & Tenant Isolation

**Phase Objective:** Protect every API/read/action boundary with validated identity and scope.

**Business Capability:** Safe multi-merchant operations.

**Technical Scope:** JWT/JWKS, local demo auth separation, membership roles, tenant query enforcement.

**In Scope:** Viewer/Operator/Admin and all documented permission boundaries.

**Out of Scope:** Enterprise permission builder and complex organization hierarchy.

**Dependencies:** API, membership schema, dashboard controls.

**Inputs:** Validated bearer claims and merchant membership.

**Outputs:** Authorized application context or safe denial.

**Major Components:** Auth dependencies, memberships, repository scopes.

**Data Impact:** Users/memberships and audit actor fields.

**API Impact:** All protected endpoints.

**Security Impact:** Core security boundary.

**Testing Scope:** Token, role matrix, cross-tenant reads/writes/jobs/metrics/audit.

**Risks:** Frontend-only authorization or scope leakage.

**Acceptance Criteria:** Unauthorized/cross-tenant actions are denied and audited.

**Phase Exit Criteria:** Server-side auth/RBAC/isolation is complete.

### Phase 15 — Security, Audit & Observability

**Phase Objective:** Harden the platform and make failures reconstructable.

**Business Capability:** Trustworthy operations and incident response.

**Technical Scope:** Rate limits, secret rotation hooks, TLS/encryption assumptions, PII/redaction, audit, metrics, health, errors, optional traces.

**In Scope:** PRD/NFR controls and operational dashboards.

**Out of Scope:** Full production compliance certification.

**Dependencies:** Core runtime and auth.

**Inputs:** Runtime events, failures, privileged actions.

**Outputs:** Logs/metrics/health/audit/security controls.

**Major Components:** Middleware, audit, logging, metrics, health.

**Data Impact:** Audit and operational telemetry.

**API Impact:** Health/error/rate-limit behavior.

**Security Impact:** Primary hardening phase.

**Testing Scope:** Redaction, rate limits, readiness, audit, secret non-leakage.

**Risks:** Missing correlation or excessive sensitive logging.

**Acceptance Criteria:** Operators can diagnose dependencies without secrets/PII leakage.

**Phase Exit Criteria:** Security/audit/observability controls meet PRD/NFR expectations.

### Phase 16 — Testing, Reliability & Failure Scenarios

**Phase Objective:** Prove correctness under expected and adversarial conditions.

**Business Capability:** Reliable recovery workflow, not only a happy-path demo.

**Technical Scope:** Layered tests, failure injection, E2E, concurrency, restart, DLQ/replay.

**In Scope:** All 20 mandatory scenarios in the implementation plan.

**Out of Scope:** Performance claims beyond measured demo/deployment targets.

**Dependencies:** Implemented core modules and test runtime.

**Inputs:** Seeded fixtures, provider fakes, test database.

**Outputs:** Passing test matrix and reproducible failure procedures.

**Major Components:** API/web/worker/provider test suites and CI.

**Data Impact:** Test-only databases/fixtures.

**API Impact:** Contract regression.

**Security Impact:** Auth/isolation/secret tests.

**Testing Scope:** Unit, integration, API, DB, worker, provider, E2E, AI evaluation, resilience.

**Risks:** False confidence from only happy-path tests.

**Acceptance Criteria:** Mandatory scenarios pass with no critical financial/safety defects.

**Phase Exit Criteria:** Full relevant suite passes and failure behavior is observable.

### Phase 17 — End-to-End Integration

**Phase Objective:** Combine the single-case vertical slice and the multi-case operational batch.

**Business Capability:** Demonstrable RecoveryOS product loop.

**Technical Scope:** Cross-module workflows, simulator batch, approval, incident, runbook operations.

**In Scope:** Failed UPI first slice and broader supported sources.

**Out of Scope:** Unapproved future capabilities.

**Dependencies:** Core paths from Phases 1–16.

**Inputs:** Clean environment and seeded data.

**Outputs:** Reconciled cases, actions, metrics, audit, and operator workflow.

**Major Components:** Whole system.

**Data Impact:** Full lifecycle.

**API Impact:** Integrated contracts.

**Security Impact:** Full auth and data boundaries exercised.

**Testing Scope:** Full vertical slice, batch E2E, restart, race, incident, fallback.

**Risks:** Integration drift between independently tested modules.

**Acceptance Criteria:** Clean run produces consistent derived results without manual edits.

**Phase Exit Criteria:** MVP workflow and operational recovery are integrated.

### Phase 18 — Final MVP Validation & Buildathon Demo

**Phase Objective:** Release a reproducible, honest, polished five-minute demonstration.

**Business Capability:** Prove measurable recovery value and intelligent restraint.

**Technical Scope:** Release hardening, clean setup, final checks, demo rehearsal, labels, troubleshooting.

**In Scope:** PRD MVP checklist, degradation story, race/fallback story, derived metrics.

**Out of Scope:** New features or scope expansion during demo preparation.

**Dependencies:** Phase 17 and all critical acceptance tests.

**Inputs:** Clean deployment and deterministic seed.

**Outputs:** Release candidate and Buildathon walkthrough.

**Major Components:** Whole product and demo configuration.

**Data Impact:** Final synthetic batch only.

**API Impact:** Stable release contracts.

**Security Impact:** Secret/PII/provider-claim review.

**Testing Scope:** Full suite, performance targets, smoke, demo rehearsal, reset/re-run.

**Risks:** Fixed totals, flaky setup, misleading labels.

**Acceptance Criteria:** Demo completes from clean state and shows derived recovery/attribution.

**Phase Exit Criteria:** MVP and Buildathon demo are reproducible, validated, and honestly presented.

