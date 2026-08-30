# RecoveryOS Architecture Decisions

This is the single decision record for meaningful product-architecture and engineering choices. It is not a changelog. Product requirements remain in `PRD.md`; implementation contracts belong in the phase-specific documents created when those systems are implemented.

## Decision template

Each decision records:

- **Decision**
- **Context**
- **Options considered**
- **Chosen option**
- **Reason**
- **Trade-offs**
- **Consequences**
- **Status**

## ADR-001 — Modular monolith as the initial architecture

**Decision**  
Build RecoveryOS as one modular API/application with separate web and worker runtimes, backed by PostgreSQL.

**Context**  
The repository is greenfield, the Buildathon requires a coherent end-to-end vertical slice, and the PRD explicitly rejects complexity for appearance.

**Options considered**

1. Modular monolith with a separate worker process.
2. Multiple microservices for ingestion, intelligence, policy, execution, and analytics.
3. Single process containing web, API, and worker.

**Chosen option**  
Option 1.

**Reason**  
It provides clear domain boundaries, independent worker execution, transactional financial workflows, and simple local/deployment operations without network calls between every business step.

**Trade-offs**  
The API codebase must maintain disciplined module boundaries and may require later extraction if scale or team ownership demands it.

**Consequences**  
All new modules must point through explicit interfaces. Microservice extraction is a future decision based on measured need, not an initial convention.

**Status**  
Proposed — pending architecture approval.

## ADR-002 — pnpm workspace and Turborepo

**Decision**  
Use a pnpm workspace orchestrated by Turborepo for the greenfield repository.

**Context**  
RecoveryOS needs a web app, shared UI package, API boundary, scripts, and later potentially shared contract packages. The reference repository demonstrates a similar structure, but is inspiration only.

**Options considered**

1. pnpm + Turborepo monorepo.
2. Single application repository with copied UI components.
3. Separate repositories for web, API, and UI.

**Chosen option**  
Option 1.

**Reason**  
It supports shared UI and typed contracts, consistent quality gates, task caching, and one reviewable source tree while keeping apps independently runnable.

**Trade-offs**  
Monorepo task configuration and package boundaries add initial setup. Turborepo must not become a reason to create packages without distinct ownership.

**Consequences**  
The architecture must define workspace package names, dependency direction, lockfile policy, and CI commands before implementation.

**Status**  
Proposed — pending architecture approval.

## ADR-003 — Next.js web application and shared UI package

**Decision**  
Use a TypeScript Next.js application in `apps/web` and a shared Tailwind/shadcn-style UI package in `packages/ui/src`.

**Context**  
The PRD requires a responsive merchant dashboard, reusable components in the shared package, centralized global CSS/design tokens, and no reusable components under `apps/web/app/components`.

**Options considered**

1. Next.js + shared UI package.
2. A standalone SPA with local component folders.
3. Server-rendered templates without a typed shared component system.

**Chosen option**  
Option 1.

**Reason**  
It supports typed interactive screens, accessible component composition, responsive dashboard UX, and an explicit package boundary for design consistency.

**Trade-offs**  
The team must manage client/server boundaries and ensure domain logic does not leak into components.

**Consequences**  
`packages/ui/src/global.css` owns shared tokens/styles; route composition stays in the web app; financial and policy logic stays in the API.

**Status**  
Proposed — pending architecture approval.

## ADR-004 — FastAPI modular API

**Decision**  
Use FastAPI with Python for `apps/api`, organized as domain, application, API, persistence, worker, integration, AI, policy, scoring, incident, audit, and simulator modules.

**Context**  
The product requires webhook processing, typed validation, background workflows, financial domain logic, provider adapters, and future model/scoring integration.

**Options considered**

1. FastAPI modular monolith.
2. Node.js API matching the web language.
3. Separate services for each workflow boundary.

**Chosen option**  
Option 1.

**Reason**  
FastAPI/Pydantic provide strong request/schema validation and a mature Python ecosystem for deterministic scoring and AI adapters, while the modular boundary limits coupling to the frontend.

**Trade-offs**  
The repository uses TypeScript and Python, so tooling and contract generation must be explicit. This is a deliberate two-runtime choice, not multiple backend stacks.

**Consequences**  
The web consumes generated/explicit OpenAPI client types; shared business logic is not duplicated in TypeScript.

**Status**  
Proposed — pending architecture approval.

## ADR-005 — PostgreSQL with SQLAlchemy and Alembic

**Decision**  
Use PostgreSQL as the source of truth, SQLAlchemy for persistence, and Alembic for versioned migrations.

**Context**  
RecoveryOS needs transactions, unique constraints, row locking, audit history, durable jobs, monetary correctness, and tenant-scoped queries.

**Options considered**

1. PostgreSQL + SQLAlchemy/Alembic.
2. Document database.
3. In-memory/demo-only storage.
4. Managed workflow database plus separate analytics store from day one.

**Chosen option**  
Option 1, with a deterministic simulator adapter for isolated tests.

**Reason**  
Relational constraints and transactions directly support obligation identity, idempotency, reconciliation, and auditability. It remains credible for production evolution without requiring multiple stores in the Buildathon.

**Trade-offs**  
Schema migrations and query/index discipline are required. Analytics may need read models later.

**Consequences**  
Financial/workflow writes are transactional; schema changes are explicit migrations and never startup side effects.

**Status**  
Proposed — pending architecture approval.

## ADR-006 — PostgreSQL-backed durable scheduler for MVP

**Decision**  
Use a PostgreSQL `scheduled_jobs` table and a dedicated worker process for durable jobs. Add a separate queue only if measured workload or operational requirements justify it.

**Context**  
RecoveryOS needs restart-safe scheduling, leases, retries, cancellation, action idempotency, and payment preflight checks. A second queue increases operational surface area.

**Options considered**

1. PostgreSQL-backed jobs and worker.
2. Redis-backed queue.
3. Hosted queue service.
4. In-process timers.

**Chosen option**  
Option 1.

**Reason**  
It keeps job state close to financial state, supports transactional case/job changes, and is sufficient for the demo-scale batch.

**Trade-offs**  
Very high throughput or complex scheduling may later justify a queue. Polling and locking must be implemented carefully.

**Consequences**  
Job leases, startup reconciliation, bounded retry, terminal failure status, and idempotent replay are required in the MVP worker contract. A dedicated dead-letter queue/workflow is a Stretch extension and must not block MVP completion.

**Status**  
Proposed — pending architecture approval.

## ADR-007 — Provider-neutral adapters

**Decision**  
Place Razorpay, simulator, messaging, AI, and scheduler implementations behind application-facing interfaces.

**Context**  
The PRD requires honest real/simulated integration labeling and future provider flexibility without provider-specific logic leaking into the domain.

**Options considered**

1. Provider adapters with normalized events.
2. Provider SDK calls directly from route handlers and services.
3. A generic integration gateway service.

**Chosen option**  
Option 1.

**Reason**  
It preserves the same workflow for test, simulator, and provider paths and makes failures injectable in tests.

**Trade-offs**  
Interfaces need careful scope and can be over-abstracted. Only stable external boundaries receive adapters.

**Consequences**  
`PaymentProvider`, `MessagingProvider`, `AIProvider`, `JobScheduler`, and `Clock` contracts are architecture-level seams.

**Status**  
Proposed — pending architecture approval.

## ADR-008 — Typed OpenAPI contract between API and web

**Decision**  
Expose API schemas through FastAPI/OpenAPI and generate or validate a TypeScript client for `apps/web`.

**Context**  
The web and API use different languages, and duplicated hand-written types would risk contract drift.

**Options considered**

1. OpenAPI-generated TypeScript client.
2. Manually duplicated TypeScript/Python types.
3. Shared runtime schema package across Python and TypeScript.

**Chosen option**  
Option 1 initially.

**Reason**  
It keeps the API authoritative while providing typed frontend usage without forcing a cross-language runtime package.

**Trade-offs**  
Generation must be part of CI and the client output must not be manually edited.

**Consequences**  
API contract changes require synchronized generated output, tests, and documentation updates when the relevant implementation phase begins.

**Status**  
Proposed — pending architecture approval.

## ADR-009 — API-validated JWT/JWKS with lightweight RBAC

**Decision**  
Validate bearer claims at the API boundary and authorize Viewer, Operator, and Admin roles against merchant membership. Local demo mode uses a clearly separated signed token mechanism.

**Context**  
The PRD requires tenant isolation, three roles, and server-side enforcement without enterprise RBAC overbuild.

**Options considered**

1. API-validated JWT/JWKS with persisted merchant memberships.
2. Frontend-only role flags.
3. Full enterprise policy/permission builder.
4. Session-only authentication with no tenant membership model.

**Chosen option**  
Option 1.

**Reason**  
It keeps authorization at the trust boundary, supports production identity providers, and is small enough for MVP.

**Trade-offs**  
Identity provider integration and local token handling require careful environment separation. Fine-grained permissions remain limited.

**Consequences**  
Every mutation and tenant query receives an authenticated scope; UI hiding is never security.

**Status**  
Proposed — pending security architecture review.

## ADR-010 — Deterministic scoring with replaceable AI recommendation

**Decision**  
Recovery probability, Expected Recoverable Revenue, priority, payment truth, and policy decisions are deterministic. AI is an adapter for interpretation and registered action recommendation only.

**Context**  
The PRD explicitly separates AI assistance from financial truth and prohibits fake or unconstrained AI behavior.

**Options considered**

1. Deterministic scorer plus structured AI recommendation adapter.
2. LLM-generated probability and action.
3. Production ML model before sufficient data exists.

**Chosen option**  
Option 1.

**Reason**  
It is explainable, testable with seeded data, safe during provider outage, and replaceable by calibrated ML later.

**Trade-offs**  
The v1 score is not production-calibrated and needs explicit synthetic labeling.

**Consequences**  
Scoring/model/prompt versions and evidence are persisted; AI output passes schema validation and policy precedence.

**Status**  
Proposed — pending AI contract review.

## ADR-011 — Documentation hierarchy and progressive creation

**Decision**  
Maintain one `PRD.md`, one `ARCHITECTURE.md`, one `DATA_MODEL.md`, and one `DECISIONS.md` at the current stage. Create event, state, API, AI, policy, security, testing, observability, attribution, runbook, and demo documents only when their implementation phase begins.

**Context**  
Documentation must remain small, non-duplicated, and useful to the current engineering stage.

**Options considered**

1. Progressive documentation by implementation phase.
2. Create every planned document before implementation.
3. Keep all technical detail in the PRD.

**Chosen option**  
Option 1.

**Reason**  
It preserves clear ownership: PRD is what/why, architecture is how structure, data model is data, decisions are why technical choices, README is onboarding, and later contracts appear when relevant.

**Trade-offs**  
Some later work cannot be fully specified until implementation exposes concrete behavior.

**Consequences**  
Material changes update the owning document in the same step; no duplicate ADR files are created.

**Status**  
Accepted.
