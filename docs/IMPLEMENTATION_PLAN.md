# RecoveryOS Implementation Plan

**Status:** Active execution roadmap  
**Scope:** Buildathon MVP through final demo  
**Current repository:** Phase 5.1 implemented; Phase 5.2 deterministic fallback and evaluation work is next
**Product source of truth:** [PRD.md](./PRD.md)  
**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)  
**Data model:** [DATA_MODEL.md](./DATA_MODEL.md)  
**Decisions:** [DECISIONS.md](./DECISIONS.md)

## 1. Purpose

This document defines what must be implemented, in what dependency order, and how each unit is verified. It is an execution plan, not a second PRD, architecture document, data model, or decision log.

Work is organized as `PHASE → SPRINT → TASK → SUBTASK`. Every sprint must be implemented, tested, integrated, and verified before it is marked complete. Existing documentation is updated only when implementation materially changes its owned content. The plan protects the first thin end-to-end vertical slice and prevents a big-bang implementation.

## 2. Source documents

Before every sprint, read the relevant source documents:

- `PRD.md` — product scope, requirements, business rules, acceptance criteria, MVP boundary.
- `ARCHITECTURE.md` — chosen stack, runtime shape, module boundaries, dependency direction, infrastructure.
- `DATA_MODEL.md` — entities, constraints, indexes, transactions, idempotency, migrations.
- `DECISIONS.md` — rationale, alternatives, trade-offs, and status of major technical decisions.
- `IMPLEMENTATION_PLAN.md` — current sprint, dependencies, tasks, tests, integration gates, and exit criteria.

The repository began without implementation artifacts. Phases 0–4 now provide the runnable workspace, persistence baseline, event boundary, Recovery Case identity/state machine, deterministic diagnosis, and scoring. Existing correct documentation remains the review contract for later phases.

## 3. Current repository state

### Present

- `LICENSE`
- `docs/PRD.md` — approved product specification, v1.0.
- `docs/ARCHITECTURE.md` — proposed pnpm/Turborepo, Next.js, FastAPI, PostgreSQL, worker, adapter, auth, and observability baseline; Phase 0 runtime boundaries are implemented.
- `docs/DATA_MODEL.md` — proposed entities, constraints, indexes, migrations, and duplicate-prevention rules.
- `docs/DECISIONS.md` — single decision record with proposed baseline choices.
- Git repository on `main`, remote configured as the RecoveryOS GitHub repository.
- Root pnpm workspace and Turborepo task graph.
- `apps/web` Next.js TypeScript shell, `apps/api` FastAPI health boundary, and `packages/ui` shared UI package.
- Husky pre-commit quality hook, Prettier, ESLint, Ruff, mypy, Vitest, pytest, CI workflow, and smoke E2E script.
- Canonical signed event contract, webhook signature verification, normalized event persistence, and correlation-ID generation.
- Source-aware obligation identity resolution and one-case-per-obligation association for recoverable events.
- PRD-aligned Recovery Case state machine with transactional audited transitions and terminal-state protection.
- Provider-neutral, schema-validated AI recommendation contract with a minimized evidence boundary, typed provider failures, configured version capture, and advisory recommendation persistence.

### Missing

- Deterministic AI fallback orchestration, recommendation evaluation fixtures, repositories for remaining workflow entities, workers, payment/messaging adapters, simulator, frontend, auth, metrics, and deployment.
- PostgreSQL migration runtime, local Docker Compose, and baseline SQLAlchemy metadata are present; PostgreSQL runtime verification remains environment-dependent.
- Later phase documents such as event, state-machine, API, AI, policy, security, testing, observability, attribution, runbook, and demo contracts.

### Working assumption

The repository began greenfield and now contains the Phase 0 baseline. Discovery always takes precedence over this assumption. No existing implementation may be deleted or restructured without inspection and a documented decision.

## 4. Implementation principles

- Build the smallest production-credible modular monolith; do not introduce microservices or Redis without an approved decision change.
- Preserve one recoverable business obligation = one Recovery Case.
- Keep payment truth, money, state transitions, idempotency, scheduling, policy, authorization, and attribution deterministic.
- Keep AI advisory, structured, versioned, explainable, and behind `AIProvider`.
- Store monetary amounts as integer smallest units; never use floating-point financial arithmetic.
- Put reusable UI in `packages/ui/src`; use shared global CSS/design tokens; do not create reusable components in `apps/web/app/components`.
- Keep mutable business values in validated configuration, merchant policies, feature flags, or experiment overrides; never scatter magic values.
- Keep routes/controllers thin and business logic in application/domain modules.
- Add tests with the behavior, not after all implementation is finished.
- Update an existing source document only when implementation causes a material change to its owned information.
- Commit and push each completed sprint or coherent step to `origin/main` with a reviewable commit.
- Stop and update `DECISIONS.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, and this plan before proceeding if a decision conflict appears.

## 5. Documentation change rule

The current documentation set is intentionally limited to `PRD.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `DECISIONS.md`, and this plan. The coding agent must not create additional Markdown files as a prerequisite for a sprint or phase.

Documentation changes are conditional and exception-based. Before changing documentation, check whether the information is already owned by an existing document. Update only the relevant existing document when implementation materially changes product requirements, architecture, the data model, or an accepted technical decision. A product change requires explicit approval before `PRD.md` is changed. Do not create replacement documents, phase-specific documents, duplicate decision files, or documentation-only work items merely because a subsystem is being implemented.

Documentation quality is still required, but it is not a routine sprint completion gate. Implementation, tests, integration, E2E validation, and phase exit criteria determine completion.

## 6. Project Definition of Done

### Task

- Implementation is complete for the stated behavior.
- Unit/integration tests relevant to the task pass.
- Errors, authorization, idempotency, and observability are addressed where relevant.
- No business-critical value is hardcoded.

### Sprint

- All tasks and subtasks are complete.
- Required migrations are versioned and reversible/forward-safe as appropriate.
- Required tests pass, including negative paths.
- Any necessary updates to existing source documents are consistent and non-duplicated.
- Sprint exit criteria are objectively satisfied.
- Changes are committed and pushed.

### Phase

- Every sprint is complete.
- Phase-level tests and consistency review pass.
- No unresolved blocking issue is hidden in implementation.
- The next phase has all prerequisites available.

### Project

- All PRD MVP requirements and acceptance scenarios pass.
- Financial correctness, safety, tenant isolation, auditability, and resilience are demonstrated.
- The five-minute Buildathon demo is reproducible from a seeded dataset.
- Synthetic, simulated, sandbox, and real provider behavior are clearly labeled.

### Mandatory phase completion gate

After every phase, the coding agent MUST:

1. Complete all sprints in that phase.
2. Run the relevant unit and integration tests.
3. Run end-to-end tests for the functionality implemented so far.
4. Run regression E2E tests covering previously completed functionality.
5. Verify the phase exit criteria.
6. Resolve or record any critical defect or blocker.
7. Mark the phase complete only when the required E2E tests pass.
8. Proceed to the next phase only after this gate passes.

Documentation is not a phase-completion prerequisite. Existing source documents are updated only when implementation materially changes their owned content.

## 7. Phase overview

| Phase | Outcome | Parallelizable work |
|---|---|---|
| 0 | Runnable repository baseline and quality gates | UI shell planning may begin after package boundary is fixed |
| 1 | Migrated PostgreSQL schema and repositories | Fixtures can be prepared in parallel after schema contract |
| 2 | Validated, normalized, idempotent events | Provider fixture work can run in parallel |
| 3 | Correct Recovery Case identity and state machine | Case UI wireframes may proceed after response shapes are known |
| 4 | Root cause, probability, expected value, priority | Pure scoring tests can run independently |
| 5 | Structured AI recommendation and fallback | Prompt evaluation fixtures can run in parallel |
| 6 | Deterministic policy and approval decisions | Policy UI can be composed after API contract exists |
| 7 | Durable jobs and restart-safe worker | Worker test harness can run in parallel with adapters |
| 8 | Provider adapters and seeded simulator | Simulator generation and adapter contract tests can run in parallel |
| 9 | Success reconciliation and race safety | Payment provider test doubles can run in parallel |
| 10 | Incident detection and outreach suppression | Detector tests can run independently of frontend |
| 11 | Attribution and recovery measurement | Metrics read-model work can run after event/case facts exist |
| 12 | Typed API surface and operational endpoints | API schema review can run with frontend shell |
| 13 | Usable merchant dashboard | Screen composition can proceed in parallel with read API work |
| 14 | Auth, RBAC, and tenant isolation | Auth test fixtures can run in parallel with UI permission states |
| 15 | Security, audit, and observability hardening | Audit/metrics implementation may proceed in parallel |
| 16 | Full test and reliability matrix | Failure harness and E2E fixture work can run in parallel |
| 17 | Integrated vertical slice and operational readiness | Demo content can begin after stable flows |
| 18 | Validated MVP and Buildathon demo | Final presentation assets only after metrics are reproducible |

## 8. Detailed implementation phases

## Phase 0 — Foundation & Repository Baseline

### Sprint 0.1 — Repository bootstrap — COMPLETE

**Sprint Objective:** Create the approved pnpm/Turborepo workspace without implementing product behavior.

**Prerequisites:** Current repository inspection complete; architecture and decisions reviewed.

**Dependencies:** None beyond Git and approved runtime availability.

**Tasks**

- [x] Create root workspace manifests and Turborepo task configuration.
  - [x] Add `apps/web`, `apps/api`, `packages/ui`, and scripts workspace boundaries.
  - [x] Pin the package manager/runtime versions through repository configuration.
  - [x] Define `dev`, `build`, `lint`, `typecheck`, `test`, and validation task dependencies.
- [x] Create minimal app/package manifests with no unused dependencies.
- [x] Add repository ignore rules and `.env.example` placeholders without secrets.
- [x] Verify the root commands fail clearly when a required dependency/configuration is absent.

**Files / Modules Affected:** Root workspace manifests, `turbo.json`, app/package scaffolds, `.env.example`, scripts.

**Tests:** Workspace install, package graph, task discovery, and clean build/typecheck smoke checks.

**Sprint Exit Criteria:** Clean install succeeds from the lockfile; workspace tasks discover all packages; no product code or duplicate docs are introduced.

### Sprint 0.2 — Standards and CI baseline — COMPLETE

**Sprint Objective:** Establish repeatable quality gates before domain implementation.

**Prerequisites:** Sprint 0.1.

**Dependencies:** Workspace package scripts and runtime versions.

**Tasks**

- [x] Configure formatter, linter, TypeScript/Python type checks, and conventional commit expectations.
- [x] Add CI jobs for install, lint, typecheck, build, and test commands.
  - [x] Ensure CI uses the lockfile and does not depend on local credentials.
  - [x] Add changed-file or full Turborepo task execution as appropriate.
- [x] Add a UI architecture check that rejects reusable components under `apps/web/app/components`.
- [x] Add a configuration validation command and secret scan where tooling supports it.

**Files / Modules Affected:** CI workflow, root scripts, lint/format/type configuration, validation scripts.

**Tests:** Run each gate locally and in CI; intentionally validate a failing gate in a disposable change if safe.

**Sprint Exit Criteria:** CI blocks failed lint/typecheck/build/test; all gates pass on the clean baseline; commit/push workflow is documented.

**Phase 0 Exit Criteria:** COMPLETE — repository is a reproducible monorepo with quality gates, validated configuration entrypoints, smoke E2E coverage, and no unapproved implementation shortcuts.

## Phase 1 — Database & Persistence

### Sprint 1.1 — Schema migrations and database runtime — COMPLETE

**Sprint Objective:** Implement the PostgreSQL schema contract from `DATA_MODEL.md`.

**Prerequisites:** Phase 0 complete; database and migration library confirmed.

**Dependencies:** `DATA_MODEL.md`, PostgreSQL runtime, typed configuration.

**Tasks**

- [x] Create the baseline migration for merchants, users, memberships, customers, obligations, cases, attempts, events, processed events, policies, decisions, recommendations, actions, jobs, incidents, experiments, attribution, and audit.
  - [x] Use integer smallest-unit monetary fields and validated currency columns.
  - [x] Add foreign keys, unique constraints, and required operational indexes.
  - [x] Add tenant scope to every tenant-owned table.
- [x] Add local PostgreSQL startup and explicit migration commands.
- [x] Add migration configuration and failure reporting; do not migrate from application startup.

**Files / Modules Affected:** `apps/api` persistence/migrations/config; Docker/local database setup.

**Tests:** Apply and downgrade migrations against an empty temporary database; verify metadata and Recovery Case uniqueness with persistence tests; retain duplicate event/action/job/assignment verification for repository implementation in Sprint 1.2.

**Sprint Exit Criteria:** Fresh migration upgrade and downgrade succeed; baseline metadata exposes the required tenant and identity constraints; smallest-unit fields are integer-backed; no schema mutation occurs during API startup.

### Sprint 1.2 — Persistence repositories and transaction boundaries — COMPLETE

**Sprint Objective:** Provide repository/unit-of-work primitives without putting business rules in persistence.

**Prerequisites:** Sprint 1.1.

**Dependencies:** Schema, SQLAlchemy configuration, domain interfaces.

**Tasks**

- [x] Implement tenant-scoped repository interfaces and SQLAlchemy implementations for core entities.
  - [x] Keep provider/API types out of persistence models.
  - [x] Add explicit transaction and rollback handling through the persistence session boundary.
- [x] Implement reusable primitives for obligation/case lookup, action idempotency lookup, and due-job claiming.
- [x] Add row-lock/lease primitives required for concurrent case and worker operations.
- [x] Add bounded pagination primitives for future API queries.

**Files / Modules Affected:** `apps/api` domain interfaces, persistence models/repositories, transaction utilities.

**Tests:** Repository CRUD, rollback, unique constraint, concurrent insert, row-lock, tenant filter, and transaction atomicity tests.

**Sprint Exit Criteria:** Application services can persist/load core entities transactionally; tenant scope is enforced by repository construction and entity insertion; unique identity constraints remain database-enforced; due jobs can be claimed with a lease.

**Phase 1 Exit Criteria:** The canonical persistence schema is versioned and reversible; core repository and transaction primitives support tenant scope, financial types, identity constraints, bounded pagination, and leased job claiming; full event/case/business workflow repositories are added in the phases that consume them.

## Phase 2 — Event Ingestion & Idempotency

### Sprint 2.1 — Canonical event contract and webhook boundary — COMPLETE

**Sprint Objective:** Accept validated provider/simulator events and normalize them into canonical facts.

**Prerequisites:** Phase 1; provider event samples or fixtures.

**Dependencies:** Signature configuration, event schema, persistence transaction.

**Tasks**

- [x] Define canonical event types and validation rules.
  - [x] Cover payment failure/success, checkout, subscription, invoice, opt-out, action, and incident events.
  - [x] Preserve provider identity, source object, amount/currency, timestamps, and correlation ID.
- [x] Implement signature verification before domain mutation.
- [x] Implement request validation, safe error mapping, and normalized event persistence.
- [x] Generate correlation IDs when absent and persist them with accepted events.

**Files / Modules Affected:** `apps/api` API ingestion, integrations, event normalization, config, persistence.

**Tests:** Valid event, invalid payload, invalid signature, missing required field, timestamp handling, currency/amount validation, correlation ID, persistence, and tenant identity coverage.

**Sprint Exit Criteria:** Valid signed events are normalized and persisted; invalid signatures and malformed payloads create no domain mutation; API responses are safe and correlation IDs are retained.

### Sprint 2.2 — Event idempotency and replay behavior — COMPLETE

**Sprint Objective:** Make duplicate delivery and controlled replay safe.

**Prerequisites:** Sprint 2.1.

**Dependencies:** `processed_events`, obligation identity, transaction boundaries.

**Tasks**

- [x] Implement provider event idempotency with merchant/provider/event identity.
  - [x] Handle duplicate delivery using database uniqueness and existing-record reload behavior.
  - [x] Return prior processing status and correlation for safe duplicates.
- [x] Implement controlled replay semantics preserving original event identity.
- [x] Record accepted/failed processing outcomes in the processed-event and normalized-event records.
- [x] Prevent duplicate normalized event records and leave downstream case/financial effects to later idempotent consumers.

**Files / Modules Affected:** Event application service, persistence, ingestion route, audit/metrics hooks.

**Tests:** Same event twice, duplicate success/failure identity, replay, failed-first-processing retry, malformed replay, and no duplicate normalized records or financial effects.

**Sprint Exit Criteria:** Duplicate webhook/event delivery is database-convergent; replay preserves the original identity; failed processing can be safely re-queued; no duplicate normalized event record is created.

**Phase 2 Exit Criteria:** COMPLETE — ingestion validates, authenticates, normalizes, correlates, persists, deduplicates, and safely replays events; full obligation/case side effects remain owned by Phase 3 consumers.

## Phase 3 — Recovery Case Engine

### Sprint 3.1 — Obligation identity and case association — COMPLETE

**Sprint Objective:** Create exactly one Recovery Case per recoverable business obligation.

**Prerequisites:** Phase 2; obligation/case schema.

**Dependencies:** Order, checkout, subscription, invoice identity rules from PRD/DATA_MODEL.

**Tasks**

- [x] Implement source-specific obligation identity resolution.
  - [x] Payment/order: merchant + obligation scope.
  - [x] Checkout: merchant + checkout intent/source identity.
  - [x] Subscription: merchant + subscription/billing-cycle identity.
  - [x] Invoice: merchant + invoice identity.
- [x] Associate multiple events and payment attempts with the existing obligation/case.
- [x] Create the case and link normalized event state transactionally with an auditable `CASE_CREATED` record.
- [x] Reconcile duplicate case creation through database constraints and reload behavior.

**Files / Modules Affected:** Domain identity, case application service, persistence repositories, event handlers.

**Tests:** Multiple payment attempts, new obligation, repeated event/case association, non-recoverable success handling, missing-money rejection, customer association, and one-case identity enforcement.

**Sprint Exit Criteria:** Every supported recoverable source maps to one obligation/case identity; repeated events associate to the existing case; non-recoverable success events do not open cases; attempt limits come from validated configuration.

### Sprint 3.2 — State machine and lifecycle service — COMPLETE

**Sprint Objective:** Enforce legal Recovery Case transitions and audit every transition.

**Prerequisites:** Sprint 3.1.

**Dependencies:** PRD state matrix, audit repository, policy/status enums.

**Tasks**

- [x] Implement the explicit PRD transition table and guard evaluation.
  - [x] Reject illegal transitions without mutation.
  - [x] Protect `RECOVERED`, `OPTED_OUT`, `CANCELLED`, and `EXHAUSTED` from customer-facing progression.
- [x] Implement transition service with actor/reason/correlation metadata.
- [x] Add terminal-state closure timestamps and recovery/opt-out/cancellation/exhaustion paths.
- [x] Expose append-only audit history for case detail.

**Files / Modules Affected:** Domain state machine, application lifecycle service, audit, persistence.

**Tests:** Typical legal matrix path, illegal transition with no new audit, terminal progression rejection, success/terminal paths, opt-out, cancellation, exhaustion, and audit history.

**Sprint Exit Criteria:** State names and legal transitions match the PRD, every accepted transition is auditable, illegal/terminal progression is rejected, and merchant scoping is enforced.

**Phase 3 Exit Criteria:** COMPLETE — case identity, attempts, PRD state machine, terminal states, and audit timeline work independently of AI/UI.

## Phase 4 — Root Cause & Deterministic Scoring

### Sprint 4.1 — Root-cause classification — COMPLETE

**Sprint Objective:** Classify symptoms into actionable, explainable root-cause categories.

**Prerequisites:** Phase 3; normalized event/evidence facts.

**Dependencies:** Failure-code mapping, incident association interface, configuration.

**Tasks**

- [x] Implement deterministic root-cause mapping for temporary timeout, bank issue, insufficient funds, expired card, authentication failure, mandate failure, cancellation, abandonment, degradation, invalid instrument, merchant config, and unknown.
- [x] Add confidence/evidence completeness and unknown handling.
- [x] Persist the diagnosis category, confidence, and version with the case; retain evidence in the deterministic diagnosis result for downstream recommendation persistence.
- [x] Expose diagnosis as an input to strategy/scoring, never as payment truth.

**Files / Modules Affected:** `apps/api` scoring/diagnosis/application/evidence.

**Tests:** Known failure codes, missing data, active incident, unknown code, and versioned diagnosis output.

**Sprint Exit Criteria:** Diagnosis is deterministic, explainable, versioned, and covered by fixtures.

### Sprint 4.2 — Recovery probability, expected value, and priority — COMPLETE

**Sprint Objective:** Produce transparent, configurable economic scores.

**Prerequisites:** Sprint 4.1.

**Dependencies:** Typed scoring config, case evidence, integer money.

**Tasks**

- [x] Implement v1 probability scorer as a replaceable deterministic service.
  - [x] Apply configured base, temporary-failure adjustment, and incident penalty.
  - [x] Clamp probability and confidence and persist the scoring version.
- [x] Calculate Expected Recoverable Revenue using integer-safe rules; net recovery remains dependent on later action-cost and attribution implementation.
- [x] Calculate a deterministic confidence-adjusted priority score without changing financial totals.
- [x] Persist probability, expected value, priority, and versioned score fields without changing financial totals.

**Files / Modules Affected:** Scoring modules, config, case analysis service, persistence.

**Tests:** Probability ranges, clamping, amount/probability arithmetic, confidence-adjusted priority, and no mutation of recovered totals.

**Sprint Exit Criteria:** Every analyzed case receives a transparent, versioned probability, expected value, and deterministic priority score from validated runtime configuration.

**Phase 4 Exit Criteria:** COMPLETE — diagnosis and deterministic scoring are persisted for analyzed cases, exposed to downstream policy/AI boundaries, and independently tested with deterministic fixtures.

## Phase 5 — AI Recommendation Layer

### Sprint 5.1 — AI contract and provider adapter — COMPLETE

**Sprint Objective:** Add advisory AI recommendations with strict structured output.

**Prerequisites:** Phase 4; registered action enum; policy inputs.

**Dependencies:** AIProvider interface, configured provider credentials/model settings, evidence view.

**Tasks**

- [x] Define recommendation schema, action allow-list, parameter validation, evidence fields, confidence, fallback action, prompt version, model version, and schema version.
- [x] Implement provider-neutral adapter with timeout, safe input minimization, redaction-by-contract, and typed errors.
- [x] Version prompts/schema/configuration and persist the exact version references on recommendations.
- [x] Keep AI provider SDK types out of domain/application contracts.

**Files / Modules Affected:** `apps/api` AI adapter, schemas, config, application recommendation service.

**Tests:** Valid recommendation, unknown action, malformed parameters, forbidden/unsupported parameters, prompt/model metadata, timeout, provider error, tenant evidence isolation, stale case protection, and advisory persistence.

**Sprint Exit Criteria:** COMPLETE — AI can return a validated registered recommendation or a typed failure without mutating financial state; persisted recommendations retain source and version metadata and remain advisory.

### Sprint 5.2 — Deterministic fallback and AI evaluation

**Sprint Objective:** Ensure AI is optional and safe under failure or uncertainty.

**Prerequisites:** Sprint 5.1.

**Dependencies:** Deterministic diagnosis/scoring, action registry, policy boundary.

**Tasks**

- [ ] Implement fallback rules by root cause and case context.
- [ ] Route timeout, invalid output, low confidence, unavailable provider, and contradictory evidence to fallback/wait/escalation.
- [ ] Add recommendation explanation with evidence, confidence, scoring factors, and source.
- [ ] Build a fixed synthetic evaluation fixture for action appropriateness, unsafe output, schema validity, and fallback rate.

**Files / Modules Affected:** AI application service, deterministic fallback, evaluation fixtures, metrics.

**Tests:** AI unavailable, malformed output, low confidence, unsafe recommendation, fallback policy path, and recommendation explanation.

**Sprint Exit Criteria:** AI failure never blocks safe workflow or bypasses policy; fallback and source are visible/auditable.

**Phase 5 Exit Criteria:** A case can receive AI or deterministic recommendation through one validated contract and one downstream policy path.

## Phase 6 — Policy Engine & Decisioning

### Sprint 6.1 — Policy schema, versions, and configuration

**Sprint Objective:** Make all mutable recovery rules typed, versioned, and tenant-aware.

**Prerequisites:** Phase 5; merchant/policy tables.

**Dependencies:** Configuration hierarchy, RBAC Admin boundary, policy version persistence.

**Tasks**

- [ ] Define typed merchant policy schema for attempts, intervals, quiet hours, approval threshold, contact caps, sequence duration, channels, retries, suppression, and fallback.
- [ ] Implement startup/environment validation and merchant-policy validation.
- [ ] Implement policy version creation, activation, immutable history, and effective-value inspection.
- [ ] Prevent invalid policy changes from becoming active.

**Files / Modules Affected:** Policy schema/service, configuration, repositories, admin application boundary.

**Tests:** Valid/invalid values, timezone, probability/amount/duration validation, version activation, historical lookup, and tenant scope.

**Sprint Exit Criteria:** Every mutable policy value has a typed source; active and historical policy versions are reconstructable.

### Sprint 6.2 — Policy evaluation, approvals, and stopping rules

**Sprint Objective:** Enforce deterministic precedence over recommendations.

**Prerequisites:** Sprint 6.1.

**Dependencies:** Case state, payment verification interface, incident status, role/approval model.

**Tasks**

- [ ] Implement exact precedence: success, opt-out, terminal, stale/invalid, incident suppression, limits, interval, quiet hours, approval, channel, allow.
- [ ] Return `ALLOW`, `BLOCK`, `SCHEDULE`, `SUPPRESS`, `REQUIRE_APPROVAL`, or `STOP` with decisive rule and version.
- [ ] Implement approval queue and Admin approval/rejection audit.
- [ ] Implement stop/cancel behavior for success, opt-out, terminal state, exhaustion, and human resolution.

**Files / Modules Affected:** Policy evaluator, approval application service, case/action lifecycle, audit.

**Tests:** Each precedence branch, AI conflict, contact cap, interval, quiet hours, incident, approval, unavailable channel, terminal state, and policy version audit.

**Sprint Exit Criteria:** No action executes unless the policy result allows it or an authorized approval path resolves it.

**Phase 6 Exit Criteria:** Recommendations, fallback decisions, stopping rules, and human approval all pass through one authoritative policy engine.

## Phase 7 — Durable Jobs, Scheduler & Worker

### Sprint 7.1 — Durable job creation, cancellation, and claiming

**Sprint Objective:** Persist future work safely without introducing an unapproved queue.

**Prerequisites:** Phase 6; `scheduled_jobs` table.

**Dependencies:** PostgreSQL transactions/locks, action idempotency, policy decision.

**Tasks**

- [ ] Create jobs only from approved/scheduled policy decisions.
- [ ] Implement job idempotency, status, due time, lease, attempts, retry time, and correlation fields.
- [ ] Implement transactional claim/lease and cancellation.
- [ ] Implement retry/backoff configuration and dead-letter status.

**Files / Modules Affected:** Scheduler interface, persistence jobs, application action scheduling.

**Tests:** Duplicate job creation, concurrent claim, lease expiry, cancellation, retry timing, retry limit, dead-letter transition.

**Sprint Exit Criteria:** Jobs are durable, uniquely identifiable, claimable once, cancellable, and recoverable after lease expiry.

### Sprint 7.2 — Worker execution and startup reconciliation

**Sprint Objective:** Execute due jobs with last-mile safety checks and restart recovery.

**Prerequisites:** Sprint 7.1.

**Dependencies:** Provider interfaces, policy evaluator, payment verification, action service.

**Tasks**

- [ ] Implement worker loop with bounded polling, claim lease, timeout, and graceful shutdown.
- [ ] Re-check payment, case, opt-out, incident, policy, action idempotency, and stale recommendation immediately before execution.
- [ ] Execute through application service/provider adapter, record result, and schedule bounded retry.
- [ ] Reconcile expired leases and eligible open cases on startup.

**Files / Modules Affected:** Worker runtime, job handlers, application recheck service, observability.

**Tests:** Worker restart, expired lease, stale job, payment race, policy change, opt-out, provider retry, duplicate worker execution, graceful shutdown.

**Sprint Exit Criteria:** A due action is executed at most once per idempotency key and is cancelled when a preflight guard fails.

**Phase 7 Exit Criteria:** Durable scheduling and worker execution survive restarts, retries, cancellation, stale state, and duplicate delivery.

## Phase 8 — Provider Integrations & Simulator

### Sprint 8.1 — Payment, messaging, AI, and scheduler adapters

**Sprint Objective:** Provide testable provider implementations behind the approved interfaces.

**Prerequisites:** Phase 7; adapter contracts.

**Dependencies:** Razorpay Test Mode decision/config, simulated channels, AI contract.

**Tasks**

- [ ] Implement payment adapter for authoritative status lookup and permitted link/retry path.
- [ ] Implement simulated messaging adapter with delivery/failure outcomes and cost.
- [ ] Connect configured AI adapter and deterministic fallback.
- [ ] Implement adapter health and typed error mapping.
- [ ] Ensure provider-specific payloads do not leak into domain models.

**Files / Modules Affected:** `apps/api` integrations/adapters/config; provider fixtures.

**Tests:** Provider success/failure/rate-limit, adapter timeout, delivery status, health, idempotency, and simulator/provider contract parity.

**Sprint Exit Criteria:** Every external effect is adapter-mediated, typed, observable, and safely simulated in tests.

### Sprint 8.2 — Seeded simulator and scenario controls

**Sprint Objective:** Generate reproducible demo events whose outcomes come from actual workflow execution.

**Prerequisites:** Sprint 8.1; case/scoring/policy/worker paths.

**Dependencies:** Typed simulator config, deterministic seed, provider fakes.

**Tasks**

- [ ] Implement configurable seed, merchant count, transaction volume, payment mix, failure distributions, duplicates, opt-outs, high-value cases, natural/treatment recoveries, and provider failures.
- [ ] Implement explicit incident period and recovery period controls.
- [ ] Run events through ingestion rather than directly writing final dashboard totals.
- [ ] Label all synthetic/simulated output in API and UI data.

**Files / Modules Affected:** Simulator module, scripts, fixtures, config, provider fakes.

**Tests:** Same seed produces same input sequence; output totals derive from persisted events/cases/actions; duplicate and failure scenarios are included.

**Sprint Exit Criteria:** A seeded batch can exercise the workflow end-to-end without hardcoded totals or fake success counters.

**Phase 8 Exit Criteria:** Real/test/simulated provider paths share contracts and a reproducible simulator produces labeled workflow data.

## Phase 9 — Payment Reconciliation & Race Conditions

### Sprint 9.1 — Payment success reconciliation

**Sprint Objective:** Close cases only from authoritative success and cancel future work.

**Prerequisites:** Phase 8; successful event and payment lookup.

**Dependencies:** Case state service, job cancellation, attribution hooks, payment identity.

**Tasks**

- [ ] Implement success-event reconciliation against order/obligation/payment identity.
- [ ] Mark case recovered exactly once with verified amount/currency.
- [ ] Cancel all future jobs/actions for the case.
- [ ] Record reconciliation and recovered amount audit events.
- [ ] Add refund/reversal adjustment path without deleting original truth.

**Files / Modules Affected:** Reconciliation application service, payment adapter, case/action/job/attribution persistence.

**Tests:** Success after failure, duplicate success, success across open states, wrong obligation, partial/duplicate amount, refund, reversal, correction flow.

**Sprint Exit Criteria:** Message delivery/clicks/recommendations never create recovered revenue; provider success does, once.

### Sprint 9.2 — Last-moment race and concurrency hardening

**Sprint Objective:** Prove no customer-facing action occurs after payment or opt-out wins the race.

**Prerequisites:** Sprint 9.1; worker execution.

**Dependencies:** Locks/leases, action idempotency, injectable clock, provider test doubles.

**Tasks**

- [ ] Implement preflight recheck immediately before external effect.
- [ ] Coordinate success event and worker through transaction/lock/idempotency strategy.
- [ ] Define behavior when payment verification is temporarily unavailable: wait/retry/escalate, never contact blindly.
- [ ] Add safe reconciliation for in-flight action/provider response ambiguity.

**Files / Modules Affected:** Worker/action/reconciliation services, persistence locking, test harness.

**Tests:** Payment before worker, during preflight, during provider call, duplicate action retry, opt-out race, stale policy, concurrent success events.

**Sprint Exit Criteria:** Mandatory payment-race and duplicate-action scenarios pass deterministically.

**Phase 9 Exit Criteria:** Financial truth, reconciliation, refunds/reversals, cancellation, and concurrency are correct under adversarial ordering.

## Phase 10 — Incident Detection & Suppression

### Sprint 10.1 — Configurable degradation detector

**Sprint Objective:** Detect probable systemic payment degradation without creating financial obligations.

**Prerequisites:** Events, attempts, payment outcomes, configuration.

**Dependencies:** Rolling-window query support, incident schema, detector version.

**Tasks**

- [ ] Implement configurable baseline/current windows, minimum attempts/failures, degradation threshold, correlation dimensions, confidence, and version.
- [ ] Open incident only when sample and degradation conditions are met.
- [ ] Persist evidence, dimensions, confidence, and affected amount/count.
- [ ] Implement resolution threshold, recovery window, and cooldown.

**Files / Modules Affected:** Incident detector, repositories, config, metrics.

**Tests:** Below threshold, above threshold, correlated dimensions, unrelated failures, incident open/resolved/cooldown, noisy/flapping signals.

**Sprint Exit Criteria:** Detector is configurable, versioned, explainable, and incident totals never enter financial totals.

### Sprint 10.2 — Case association and outreach suppression

**Sprint Objective:** Delay/suppress affected cases and resume targeted recovery after resolution.

**Prerequisites:** Sprint 10.1; policy/jobs.

**Dependencies:** Case incident association, cancellation/rescheduling, dashboard/API readiness.

**Tasks**

- [ ] Associate affected cases with the active incident without changing obligation identity.
- [ ] Apply policy `SUPPRESS`/`WAIT` to new and scheduled outreach.
- [ ] Cancel or reschedule affected jobs safely.
- [ ] Re-score/re-evaluate unresolved cases after incident recovery/cooldown.

**Files / Modules Affected:** Incident/policy/case/job services, audit, metrics.

**Tests:** Incident suppression, scheduled cancellation, new case during incident, resolution recovery, no mass outreach, visible timeline.

**Sprint Exit Criteria:** The degradation demo proves restraint and targeted post-incident recovery.

**Phase 10 Exit Criteria:** Systemic degradation is detected, associated, suppressed, resolved, cooled down, and auditable without double-counting money.

## Phase 11 — Attribution & Recovery Measurement

### Sprint 11.1 — Experiment assignment and case attribution

**Sprint Objective:** Implement case-level natural/assisted/control/treatment outcomes.

**Prerequisites:** Reconciliation and action outcomes complete.

**Dependencies:** Experiment/assignment schema, configured attribution window, success ordering.

**Tasks**

- [ ] Assign eligible cases before treatment, persist immutable variant, and honor configured ratios/eligibility.
- [ ] Define qualifying treatment action and attribution window.
- [ ] Classify natural, assisted, unrecovered, suppressed, control, and treatment outcomes.
- [ ] Handle duplicate success, multiple interventions, refund/reversal adjustments, and event ordering.

**Files / Modules Affected:** Attribution/experiment application services, persistence, reconciliation.

**Tests:** Control/treatment assignment, natural recovery, assisted recovery, outside window, multiple actions, duplicate success, refund/reversal, suppressed case.

**Sprint Exit Criteria:** Each eligible case has one reconstructable case-level attribution result and explicit limitations.

### Sprint 11.2 — Recovery metrics and read models

**Sprint Objective:** Calculate dashboard/business metrics from persisted facts.

**Prerequisites:** Sprint 11.1; cases and actions.

**Dependencies:** Indexed queries/read models, integer money aggregation.

**Tasks**

- [ ] Implement revenue at risk, expected recoverable, recovered, natural, assisted, unrecovered, suppressed, cost, net recovery, rate, lift, and median time metrics.
- [ ] Segment by method, cause, strategy, channel, and incident where data supports it.
- [ ] Prevent incident/message/recommendation counts from entering financial totals.
- [ ] Add last-updated/freshness metadata and partial-data behavior.

**Files / Modules Affected:** Metrics/read-model services, repositories, API serializers.

**Tests:** Seeded expected aggregation, duplicate resistance, cost/net calculation, empty data, partial data, refresh/freshness.

**Sprint Exit Criteria:** Metrics are derived from case/payment/action/attribution facts and reconcile to source totals.

**Phase 11 Exit Criteria:** Recovery value and lift are measurable, reproducible, case-level, and honestly labeled.

## Phase 12 — API Layer

### Sprint 12.1 — Typed API contract and core endpoints

**Sprint Objective:** Expose the workflow through a stable, validated API for web and tests.

**Prerequisites:** Core application services through Phase 11.

**Dependencies:** FastAPI routing, Pydantic schemas, auth dependency seam, OpenAPI generation.

**Tasks**

- [ ] Define versioned endpoints for dashboard, cases, case detail/timeline, incidents, approvals, policies, experiments/metrics, simulator, and health.
- [ ] Map application errors to safe HTTP error categories.
- [ ] Generate/validate TypeScript client from OpenAPI; prohibit manual drift.
- [ ] Add pagination, filtering, sorting, tenant scope, and freshness metadata.

**Files / Modules Affected:** `apps/api` routes/schemas/dependencies; generated web client boundary.

**Tests:** API validation, response schema, authorization seam, pagination, filters, safe errors, OpenAPI generation, contract compatibility.

**Sprint Exit Criteria:** Web/test clients can consume typed API contracts without embedding domain logic or provider details.

### Sprint 12.2 — Webhooks, simulator controls, and operational endpoints

**Sprint Objective:** Expose controlled ingestion and operational visibility without unsafe controls.

**Prerequisites:** Sprint 12.1; auth boundary can be stubbed for local tests.

**Dependencies:** Ingestion, simulator, health/metrics services.

**Tasks**

- [ ] Add signed webhook endpoint and safe receipt response.
- [ ] Add Admin-scoped simulator start/status/reset controls with idempotent run identity.
- [ ] Add case action/approval endpoints with server-side policy rechecks.
- [ ] Add liveness/readiness, worker, integration, and freshness endpoints.

**Files / Modules Affected:** API routes/dependencies, simulator/application services, health checks.

**Tests:** Signature rejection, duplicate webhook, unauthorized simulator/action, stale worker, dependency degraded, case not found, safe error payload.

**Sprint Exit Criteria:** All mutation endpoints enforce application rules and expose useful operational state.

**Phase 12 Exit Criteria:** API is typed, tenant-ready, safe, testable, and sufficient for dashboard/E2E integration.

## Phase 13 — Merchant Dashboard / Frontend

### Sprint 13.1 — Shared UI and application shell

**Sprint Objective:** Build the shared design system and dashboard shell before feature screens.

**Prerequisites:** Phase 0 package boundary; API contract direction.

**Dependencies:** `packages/ui`, Tailwind/shadcn conventions, typed client.

**Tasks**

- [ ] Implement shared tokens/components in `packages/ui/src`.
  - [ ] Add `global.css` for colors, typography, spacing, themes, focus, and status tokens.
  - [ ] Add accessible buttons, cards, tables, badges, tabs, dialogs, forms, alerts, skeletons, empty/error states.
- [ ] Build `apps/web` application shell, navigation, responsive layout, and route composition.
- [ ] Add shared formatter for integer money/currency and timestamps without duplicating financial rules.
- [ ] Add loading, no-data, simulator-not-run, disconnected, and degraded states.

**Files / Modules Affected:** `packages/ui/src`, `apps/web` shell/layout/features.

**Tests:** Component accessibility, keyboard/focus, responsive smoke, formatter unit tests, loading/empty/error rendering.

**Sprint Exit Criteria:** Reusable UI exists only in `packages/ui/src`; shell is responsive and consumes the typed API boundary.

### Sprint 13.2 — Dashboard, cases, incident, and policy views

**Sprint Objective:** Deliver the operational experience required to understand and act on revenue risk.

**Prerequisites:** Sprint 13.1; API endpoints.

**Dependencies:** Metrics, case detail, incident, policy, health data.

**Tasks**

- [ ] Implement dashboard cards/charts/tables for at-risk, expected, recovered, natural/assisted, lift, costs, incidents, approvals, and system health.
- [ ] Implement case list filters/sorting and case detail timeline/recommendation/policy/action/reconciliation views.
- [ ] Implement incident view with baseline/current health, affected cases, suppression, resolution, and confidence.
- [ ] Implement policies, integrations, approvals, and experiments/measurement views.
- [ ] Keep pages under approximately 400–500 lines by extracting feature sections/components.

**Files / Modules Affected:** `apps/web` route composition/features; `packages/ui/src` reusable additions.

**Tests:** Route rendering, API loading/error/degraded states, permission presentation, case timeline, policy conflict display, dashboard metric formatting, E2E navigation.

**Sprint Exit Criteria:** A merchant can answer the five dashboard questions and inspect a complete case/incident decision trail.

**Phase 13 Exit Criteria:** Responsive, accessible, interactive dashboard and case operations are usable without domain logic in components.

## Phase 14 — Authentication, Authorization & Tenant Isolation

### Sprint 14.1 — Identity and RBAC enforcement

**Sprint Objective:** Enforce API-validated identity and Viewer/Operator/Admin permissions.

**Prerequisites:** API endpoints and membership schema.

**Dependencies:** JWT/JWKS configuration, local demo token path, RBAC matrix.

**Tasks**

- [ ] Implement token validation, expiry, issuer/audience checks, and configurable JWKS/signing source.
- [ ] Implement local demo identity separately from production-like authentication.
- [ ] Implement API/application authorization for view, manual retry, intervention, approval, policy, integrations, simulator, and audit operations.
- [ ] Add effective-role context to audit records without trusting client role claims outside validated identity.

**Files / Modules Affected:** API auth dependencies, membership repositories, configuration, web auth wiring.

**Tests:** Missing/expired/invalid token, role matrix, Admin-only mutation, Viewer denial, Operator allowed operation, audit actor identity.

**Sprint Exit Criteria:** Every protected API path enforces validated role and merchant scope; UI hiding is not the only control.

### Sprint 14.2 — Tenant isolation verification

**Sprint Objective:** Prevent cross-merchant data and action access.

**Prerequisites:** Sprint 14.1; all tenant-owned repositories/endpoints.

**Dependencies:** Merchant scope, query filters, foreign keys, audit.

**Tasks**

- [ ] Apply merchant scope to every read, write, job claim, audit query, metric, simulator, and provider context.
- [ ] Verify external IDs cannot cross-resolve between merchants.
- [ ] Add safe not-found/forbidden behavior without information leakage.
- [ ] Add tenant-aware seed fixtures and operational audit review.

**Files / Modules Affected:** All API application/repository query boundaries, auth tests, web data loaders.

**Tests:** Cross-tenant case/event/customer/job/policy/audit access attempts; ID collision; cross-tenant action; metric isolation.

**Sprint Exit Criteria:** Isolation tests pass for every tenant-owned aggregate and no endpoint derives scope from untrusted body data.

**Phase 14 Exit Criteria:** Authentication, RBAC, authorization, and tenant isolation are enforced server-side and audited.

## Phase 15 — Security, Audit & Observability

### Sprint 15.1 — Security hardening and audit completeness

**Sprint Objective:** Implement the PRD security baseline and make privileged/financial operations reconstructable.

**Prerequisites:** Phase 14; core workflows.

**Dependencies:** Secret/config system, auth, audit table, provider boundaries.

**Tasks**

- [ ] Add configurable rate limiting for webhook, mutation, auth-sensitive, and simulator endpoints.
- [ ] Add secret redaction, environment validation, rotation/revocation hooks, TLS/deployment checks, and encrypted managed storage assumptions.
- [ ] Minimize PII, redact logs, and enforce role-based customer-context access.
- [ ] Audit policy/config/integration changes, approvals, manual actions, simulator runs, reconciliations, security events, and state changes.
- [ ] Add dependency/security scanning and safe error responses.

**Files / Modules Affected:** API middleware/config, audit service, auth, logging/redaction, CI security checks.

**Tests:** Rate limits, invalid signature no mutation, secret non-leakage, PII redaction, audit completeness, unauthorized operations, dependency check.

**Sprint Exit Criteria:** Security controls are enforced and tested; audit can reconstruct every material financial/policy/action event.

### Sprint 15.2 — Structured observability and health

**Sprint Objective:** Make system health and workflow failures visible to operators.

**Prerequisites:** Sprint 15.1; worker/API/provider paths.

**Dependencies:** Structured logging, metrics backend/adapter, health endpoints.

**Tasks**

- [ ] Implement structured logs with correlation and entity IDs; redact secrets/PII.
- [ ] Implement webhook, case, policy, job, worker, provider, AI, incident, action, and recovery metrics.
- [ ] Implement liveness/readiness and dependency health states.
- [ ] Add error tracking hooks, stuck-job alerts, queue/backlog metrics, AI fallback metrics, and provider failure visibility.
- [ ] Add optional trace spans behind configuration without sensitive payloads.

**Files / Modules Affected:** Logging/metrics/health/tracing modules, API/worker/adapters, dashboard health data.

**Tests:** Correlation propagation, redaction, health state, metric increments, worker absence, provider outage, AI fallback spike, trace disabled/enabled.

**Sprint Exit Criteria:** An operator can distinguish healthy, degraded, unavailable, stale, and failed subsystems with correlation IDs.

**Phase 15 Exit Criteria:** Security, audit, health, metrics, structured logging, and operational visibility meet PRD/NFR expectations.

## Phase 16 — Testing, Reliability & Failure Scenarios

### Sprint 16.1 — Integrated test matrix

**Sprint Objective:** Consolidate layered tests and ensure every financial/safety invariant is automated.

**Prerequisites:** All implemented modules through Phase 15.

**Dependencies:** Test database, provider fakes, seeded fixtures, browser E2E runtime.

**Tasks**

- [ ] Add unit tests for money, identity, state, scoring, policy, incident, attribution, and configuration.
- [ ] Add integration tests for migrations, repositories, webhook-to-case, success reconciliation, jobs, adapters, auth, and tenant isolation.
- [ ] Add API contract and frontend route tests.
- [ ] Add worker/concurrency tests with injectable clock and controlled provider doubles.
- [ ] Add E2E harness for the first vertical slice.

**Files / Modules Affected:** `apps/api/tests`, `apps/web` tests, shared fixtures/scripts, CI.

**Tests:** All mandatory scenarios listed in Section 12 of this plan, including concurrent case creation and worker/payment races.

**Sprint Exit Criteria:** Required test matrix runs reproducibly in CI; failures identify the owning module and correlation context.

### Sprint 16.2 — Resilience, replay, and failure injection

**Sprint Objective:** Validate behavior under component failure rather than only happy paths.

**Prerequisites:** Sprint 16.1.

**Dependencies:** Provider failure injection, job DLQ/replay, health/observability.

**Tasks**

- [ ] Inject webhook processing, database, AI, payment, messaging, rate-limit, and worker failures.
- [ ] Verify bounded retries/backoff, stale-job handling, expired lease recovery, dead-letter status, and safe replay.
- [ ] Verify no duplicate financial/outbound effects after retries or restarts.
- [ ] Verify degraded UI states and operator-visible remediation hints.

**Files / Modules Affected:** Failure test harness, adapters, worker, API/frontend error states, observability.

**Tests:** Invalid AI output, provider outage, database unavailable, worker restart, dead-letter replay, stale recommendation, payment verification unavailable, partial dashboard.

**Sprint Exit Criteria:** Failure scenarios are deterministic, safe, observable, and recoverable according to policy.

**Phase 16 Exit Criteria:** Unit, integration, API, E2E, concurrency, AI evaluation, and resilience suites pass with no critical financial/safety defect.

## Phase 17 — End-to-End Integration

### Sprint 17.1 — First vertical slice integration

**Sprint Objective:** Execute the complete failed-UPI journey from event to dashboard recovery.

**Prerequisites:** Phases 1–16 required core paths complete.

**Dependencies:** Ingestion, case, scoring, AI/fallback, policy, worker, provider, reconciliation, audit, attribution, API, web.

**Tasks**

- [ ] Run failed UPI event through signature/idempotency and one Recovery Case.
- [ ] Produce root cause, deterministic probability, expected recoverable amount, priority, and recommendation.
- [ ] Apply policy and schedule a permitted action.
- [ ] Trigger payment success before execution and verify last-moment cancellation, reconciliation, attribution, audit, and dashboard update.
- [ ] Repeat with action execution followed by success and verify assisted recovery.

**Files / Modules Affected:** Cross-cutting application path, simulator, E2E fixtures, API/web.

**Tests:** Full vertical slice, payment race, duplicate webhook, duplicate action, AI fallback, policy conflict, natural/assisted outcome.

**Sprint Exit Criteria:** The exact PRD first vertical slice passes from a clean environment without manual database edits or fixed dashboard totals.

### Sprint 17.2 — Batch integration and operational workflow

**Sprint Objective:** Prove the multi-case Buildathon story and operator workflows.

**Prerequisites:** Sprint 17.1; simulator controls; incident/attribution.

**Dependencies:** Seeded dataset, dashboard, approvals, health, audit, runbook.

**Tasks**

- [ ] Run a batch containing one-time failures, abandonments, subscriptions, invoices, duplicates, opt-outs, incidents, approvals, natural recoveries, assisted recoveries, and unrecovered cases.
- [ ] Verify incident suppression, post-incident targeted actions, approval path, provider failure retry, and worker restart.
- [ ] Verify dashboard totals reconcile to database facts and attribution.
- [ ] Verify operator runbook actions are possible through supported APIs/UI and audited.

**Files / Modules Affected:** Simulator, metrics, dashboard, incident/approval/worker operations.

**Tests:** Batch invariants, cross-source identity, incident totals, metric reconciliation, operator permission/error states.

**Sprint Exit Criteria:** The full batch is reproducible and produces derived, labeled metrics with no critical discrepancy.

**Phase 17 Exit Criteria:** End-to-end MVP workflow, batch processing, and operational recovery are integrated.

## Phase 18 — Final MVP Validation & Buildathon Demo

### Sprint 18.1 — Final MVP validation and release hardening

**Sprint Objective:** Validate every PRD acceptance criterion and prepare a clean reproducible release candidate.

**Prerequisites:** Phase 17 complete.

**Dependencies:** Full CI, deployment environment, seeded data, security/test/observability docs.

**Tasks**

- [ ] Run clean install, migrations, seed, API, worker, web, full tests, build, lint, typecheck, and E2E from documented commands.
- [ ] Execute the final MVP acceptance checklist in Section 12.
- [ ] Review configuration for magic values, secrets, fixed demo totals, duplicate rules, and provider labels.
- [ ] Review tenant isolation, audit completeness, error states, rate limits, backups/recovery assumptions, and dependency findings.
- [ ] Resolve or explicitly record any remaining blocker; do not silently waive financial/safety defects.

**Files / Modules Affected:** Release configuration, CI/deployment scripts, all relevant modules.

**Tests:** Full test suite, smoke tests, security checks, performance targets, restart/recovery, and seeded metric reconciliation.

**Sprint Exit Criteria:** Clean environment passes all required checks; no unresolved critical issue; release configuration is reproducible and documented.

### Sprint 18.2 — Demo stabilization and five-minute walkthrough

**Sprint Objective:** Deliver an honest, polished, repeatable Buildathon demonstration.

**Prerequisites:** Sprint 18.1; stable UI and derived metrics.

**Dependencies:** Simulator, incident flow, case detail, audit, attribution, fallback, demo environment.

**Tasks**

- [ ] Create a demo seed/configuration that derives outcomes from actual workflow execution.
- [ ] Demonstrate baseline/current UPI degradation and outreach suppression.
- [ ] Demonstrate natural recovery, targeted assisted recovery, approval, policy conflict, and payment race.
- [ ] Demonstrate AI recommendation reasoning and deterministic fallback.
- [ ] Confirm every synthetic/simulated/sandbox label and remove any misleading claim.
- [ ] Capture final dashboard/case/incident/audit views and recovery metrics.

**Files / Modules Affected:** Demo configuration/scripts, dashboard content, simulator, final release docs.

**Tests:** Full demo rehearsal from clean state; reset/re-run same seed; verify expected relationships rather than fixed totals.

**Sprint Exit Criteria:** Five-minute demo completes without manual data edits, shows measurable derived recovery, and handles at least one failure/race scenario visibly.

**Phase 18 Exit Criteria:** MVP acceptance, release hardening, reproducibility, and Buildathon demo are complete.

## 9. Global dependencies

```text
Phase 0 Foundation
    ↓
Phase 1 Database/Persistence
    ↓
Phase 2 Events/Idempotency
    ↓
Phase 3 Recovery Case Engine
    ↓
Phase 4 Root Cause/Scoring
    ↓
Phase 5 AI  ─────┐
Phase 6 Policy ──┼─> Phase 7 Jobs/Worker ─> Phase 8 Adapters/Simulator
                 │                                  ↓
                 └────────────────────────────> Phase 9 Reconciliation/Races
                                                   ↓
                                      Phase 10 Incidents ─┐
                                      Phase 11 Attribution ─┼─> Phase 12 API
                                                           └─> Phase 13 Web
                                                                  ↓
                                                             Phase 14 Auth/RBAC
                                                                  ↓
                                                Phase 15 Security/Observability
                                                                  ↓
                                                Phase 16 Testing/Reliability
                                                                  ↓
                                                Phase 17 E2E Integration
                                                                  ↓
                                                Phase 18 MVP/Demo
```

Safe parallel work:

- Pure scoring functions and fixtures can proceed alongside repository work after the domain contract is stable.
- UI component primitives can proceed after the shared package boundary is fixed, while API implementation continues.
- Provider adapter contract tests can proceed alongside worker implementation.
- Incident detector tests can proceed alongside API/frontend work once event facts are available.
- CI/security tooling and documentation updates can proceed throughout without changing domain order.

Blocking dependencies are database identity constraints before case creation, case/state services before policy/jobs, policy before execution, reconciliation before attribution, and API contracts before full frontend integration.

## 10. Critical path

The shortest path to a functioning RecoveryOS vertical slice is:

1. Phase 0.1–0.2: workspace and quality gates.
2. Phase 1.1–1.2: schema and transaction repositories.
3. Phase 2.1–2.2: signed normalized event and idempotency.
4. Phase 3.1–3.2: obligation/case identity and state machine.
5. Phase 4.1–4.2: diagnosis and deterministic economics.
6. Phase 5.1–5.2: structured recommendation and fallback.
7. Phase 6.1–6.2: policy precedence and approval.
8. Phase 7.1–7.2: durable schedule/worker with recheck.
9. Phase 8.1–8.2: payment/messaging simulator adapters.
10. Phase 9.1–9.2: success reconciliation and race safety.
11. Phase 12.1–12.2: API contract.
12. Phase 13.1–13.2: dashboard/case UI.
13. Phase 14.1–14.2: auth and tenant scope.
14. Phase 15–17: hardening, tests, integrated demo.

The largest technical risks on this path are obligation uniqueness under concurrency, authoritative payment reconciliation, last-mile action cancellation, durable worker leases, policy precedence, and keeping AI from becoming financial truth. Incident detection and attribution are essential to the complete Buildathon story but can be integrated after the first single-case flow is proven.

## 11. Risk areas and validation

| Risk | Impact | Mitigation | Validation method |
|---|---|---|---|
| Financial arithmetic error | Incorrect revenue claims | Integer smallest-unit types and pure calculations | Money/property/unit tests and source reconciliation |
| Duplicate webhook/event | Duplicate case or amount | Unique provider event identity and transactional idempotency | Sequential/concurrent duplicate tests |
| Concurrent case creation | Multiple obligations counted | Unique obligation/case constraints and reload path | Parallel insertion test |
| Duplicate action execution | Customer contacted twice | Action/job idempotency reservation and provider reference | Worker retry/race test |
| Payment race | Message after payment | Last-mile authoritative recheck and cancellation | Payment-before/during-worker E2E tests |
| Payment provider ambiguity | False recovery or unsafe action | Typed provider errors and fail-closed verification | Timeout/unknown-status tests |
| AI hallucination | Unsafe/invalid action | Allow-list, schema validation, policy authority, fallback | Malformed/unsafe AI contract tests |
| AI outage/drift | Workflow blocked or inconsistent | Versioned prompts/models, deterministic fallback, evaluation set | Outage/fallback/regression tests |
| Policy bypass | Unauthorized contact/action | One policy service and server-side checks | Conflict, role, terminal, opt-out tests |
| Worker loss/stale lease | Missed or repeated recovery | Durable jobs, leases, startup reconciliation, DLQ | Restart/lease/replay tests |
| Incident misclassification | Message flood or lost opportunity | Configurable thresholds, confidence, cooldown | Detector boundary/flapping tests |
| Tenant isolation failure | Data/privacy breach | Scope every query/mutation/job/audit | Cross-tenant negative tests |
| Webhook spoof/replay | Unauthorized domain mutation | Signature and replay checks | Invalid signature/replay tests |
| PII/secret leakage | Security/compliance incident | Redaction, secret manager, minimal fields | Log/API/security scan |
| Attribution error | Misleading lift/ROI | Immutable assignment, case-level rules, deduplication | Attribution fixture reconciliation |
| Provider differences | Inconsistent workflows | Normalized events and adapters | Contract tests across simulator/provider fakes |
| Overengineering | Delayed MVP | Modular monolith and no unapproved infrastructure | Architecture review at phase gates |
| Fixed demo outcome | Misleading Buildathon claim | Seeded event execution and derived totals | Re-run seed and reconcile database totals |

## 12. Final MVP acceptance checklist

Each item maps to PRD requirements and must have an implementation/test path before release.

- [ ] Ingest a valid Razorpay-style payment-risk event.
- [ ] Reject invalid signatures without domain mutation.
- [ ] Validate and normalize event payloads.
- [ ] Deduplicate duplicate webhooks/events, including concurrent delivery.
- [ ] Identify one obligation and one Recovery Case across multiple attempts.
- [ ] Enforce legal state transitions and audit them.
- [ ] Verify payment truth server-side.
- [ ] Use integer smallest-unit currency arithmetic.
- [ ] Prevent duplicate payment effects, action effects, cases, and recovered revenue.
- [ ] Classify root cause with confidence/evidence.
- [ ] Calculate deterministic recovery probability and priority.
- [ ] Calculate Expected Recoverable Revenue and preserve score versions.
- [ ] Detect configurable systemic degradation and associate cases without adding obligations.
- [ ] Produce validated AI or deterministic fallback recommendations.
- [ ] Explain recommendation evidence, confidence, scoring factors, and policy result.
- [ ] Enforce policy precedence, contact limits, intervals, quiet hours, channels, incidents, opt-out, approval, and stopping rules.
- [ ] Persist policy versions and decisions.
- [ ] Schedule durable work with retries, leases, cancellation, DLQ status, and replay.
- [ ] Re-check payment/order/case/policy/opt-out/incident state immediately before action.
- [ ] Execute provider actions idempotently.
- [ ] Reconcile payment success and cancel future work.
- [ ] Handle refunds/reversals through explicit adjustments.
- [ ] Support Viewer/Operator/Admin authorization and merchant isolation.
- [ ] Show dashboard, case detail, incident, policies, measurement, and system health.
- [ ] Show loading, empty, degraded, stale, unavailable, and error states.
- [ ] Record audit timeline and structured operational telemetry.
- [ ] Classify natural, assisted, suppressed, control, treatment, and unrecovered outcomes.
- [ ] Demonstrate failure, race, fallback, and restart scenarios.

## 13. Final demo checklist

- [ ] Start the system from documented clean setup.
- [ ] Run the seeded simulator without manual database edits.
- [ ] Show clearly labeled synthetic/simulated/Test Mode behavior.
- [ ] Show baseline and current UPI health during degradation.
- [ ] Show probable incident diagnosis and outreach suppression.
- [ ] Show affected Recovery Cases and expected recoverable value.
- [ ] Show natural recovery after incident recovery.
- [ ] Show segmented targeted recovery for unresolved cases.
- [ ] Show AI recommendation, evidence, confidence, and structured action.
- [ ] Show deterministic fallback after AI failure or malformed output.
- [ ] Show policy decision and AI/policy conflict behavior.
- [ ] Show high-value approval path.
- [ ] Show durable schedule and worker status.
- [ ] Show payment race: payment succeeds before scheduled outreach, action cancels, no message sends.
- [ ] Show action execution followed by success reconciliation.
- [ ] Show audit timeline and policy/model/scoring versions.
- [ ] Show natural versus assisted recovery and attribution limitations.
- [ ] Show dashboard metrics derived from persisted workflow outcomes.
- [ ] Re-run the seed and confirm reproducible relationships/totals.
- [ ] Confirm no secrets, raw card data, unnecessary PII, or proprietary Razorpay claims are exposed.

## 14. Coding agent execution model

For each phase and sprint, the coding agent MUST:

1. Read `PRD.md`.
2. Read the relevant sections of `ARCHITECTURE.md`, `DATA_MODEL.md`, and `DECISIONS.md`, plus any existing implementation contract that is already present.
3. Inspect the current implementation, Git status, and existing tests.
4. Confirm the sprint prerequisites and identify the next unchecked task.
5. Implement only the sprint scope.
6. Add/update unit, integration, API, worker, frontend, E2E, concurrency, or failure tests as relevant.
7. Run the relevant lint, typecheck, build, migration, and test checks.
8. Update an existing source document only if implementation materially changes its owned behavior or contract; do not create phase-specific documentation as a sprint requirement.
9. Verify every sprint exit criterion.
10. Commit the coherent sprint change and push it to `origin/main`.
11. Proceed only when implementation, tests, integration, E2E validation, and exit criteria pass.

After all sprints in a phase, the agent MUST run phase-level tests, review PRD/architecture/data/decision consistency, record unresolved issues, and only then begin the next phase. Code compiling is never sufficient completion evidence.

If an implementation conflict appears:

1. Stop at the affected task.
2. Identify the conflicting PRD, architecture, data-model, or decision statement.
3. Evaluate alternatives and impact.
4. Update `DECISIONS.md`.
5. Update `ARCHITECTURE.md` and/or `DATA_MODEL.md` if necessary.
6. Update this plan if order, scope, or tests change.
7. Continue only after the decision is resolved.

## 15. Final plan quality check

Before implementation starts, confirm:

- [ ] The plan reflects the actual repository: documentation-only, no source/stack/database/tests/CI/deployment yet.
- [ ] No future implementation task incorrectly claims existing code is complete.
- [ ] PRD remains the product source of truth.
- [ ] Architecture, data model, and decisions remain separate responsibilities.
- [ ] Recovery Case identity and existing state machine are preserved.
- [ ] No phase introduces Redis/microservices without a decision update.
- [ ] Financial truth is never sourced from AI, messaging, simulator counters, or duplicate events.
- [ ] All sprints contain objective prerequisites, tasks, tests, E2E validation expectations, and exit criteria.
- [ ] No sprint or phase requires creation of additional Markdown files.
- [ ] Existing source documents are updated only when a material change requires it.
- [ ] The first vertical slice is executable before secondary breadth is treated as complete.
- [ ] Global dependencies and safe parallel work are explicit.
- [ ] Critical path and risk validation are explicit.
- [ ] Final MVP and demo checklists map to PRD behavior.
