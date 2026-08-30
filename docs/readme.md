# RecoveryOS

**RecoveryOS — AI Revenue Recovery Decision & Orchestration Engine**

> Detect revenue at risk. Decide the next-best recovery action. Recover money safely. Prove the result.

## RecoveryOS overview

RecoveryOS is a planned merchant operations platform for revenue recovery. It turns failed payments, checkout abandonment, recurring-payment failures, overdue invoices, and correlated payment degradation into prioritized Recovery Cases. It diagnoses likely causes, estimates recoverability, selects a bounded action, applies deterministic policy, executes or schedules work, reconciles payment truth, and measures natural versus assisted recovery.

The repository currently contains the product and engineering documentation baseline only. The implementation stack and runtime shape are approved as a proposed architecture but application code has not yet been created.

## Problem

Merchants often manage payment retries, abandoned checkouts, subscription failures, and overdue invoices in separate systems. Generic reminders do not understand root cause, customer history, system incidents, contact limits, or whether the customer already paid. RecoveryOS unifies the risk and action loop so the merchant can see value at risk, choose safe interventions, suppress unnecessary outreach, and measure incremental recovery.

## Core concept: Recovery Case

A Recovery Case represents one recoverable business obligation, not one webhook or one payment attempt. Multiple attempts for one order normally belong to the same case. A subscription billing cycle and a B2B invoice each represent their own obligation. An incident can be associated with many cases but is never itself a financial obligation.

Payment status and recovered money come only from authoritative server-side reconciliation. AI recommendations, messages, clicks, simulator counters, or duplicate events cannot establish payment success.

## Key capabilities

- **Event ingestion:** Validate signatures and payloads, normalize provider events, attach correlation IDs, and handle duplicates safely.
- **Recovery analysis:** Classify root cause from structured evidence and identify customer-specific versus systemic risk.
- **Scoring:** Calculate deterministic recovery probability, Expected Recoverable Revenue, and priority from configurable inputs.
- **AI recommendations:** Interpret evidence and recommend a registered action with rationale, evidence, confidence, and fallback.
- **Policy enforcement:** Apply contact limits, intervals, quiet hours, incident suppression, approvals, channel availability, and stopping rules.
- **Scheduling:** Persist durable jobs, claim them with leases, classify retryable/terminal failures, retry safely, cancel stale work, and optionally dead-letter repeated failures as Stretch.
- **Reconciliation:** Re-check payment state before action and close cases only from verified provider/simulator success.
- **Incident suppression:** Detect configurable systemic degradation and delay mass outreach until the system recovers.
- **Attribution:** MVP separates natural recovery, assisted recovery, suppressed, and unrecovered outcomes at case level, including cost/net recovery and adjustments. Control/treatment and experiment lift are optional Stretch.
- **Audit:** Preserve state, policy, recommendation, action, reconciliation, approval, and configuration history.
- **Dashboard:** Show revenue at risk, expected/recovered value, incidents, cases, approvals, attribution, and system health.

## Architecture overview

The proposed baseline is a pnpm/Turborepo modular monolith with a Next.js TypeScript web app, a FastAPI Python API, PostgreSQL persistence, a dedicated PostgreSQL-backed worker, provider adapters, and a shared UI package. Reusable UI is owned by `packages/ui/src`, including `global.css`, design tokens, and shadcn/Tailwind-style components. The API owns domain/application rules; the dashboard is not a source of financial truth.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for module boundaries, runtime flow, adapters, authentication, deployment, and dependency direction.

## Repository structure

The current repository contains documentation and `LICENSE`. The planned implementation structure is:

```text
apps/web/              Next.js merchant dashboard and route composition
apps/api/              FastAPI API, domain, application, persistence, worker, adapters
packages/ui/src/       Shared accessible components, tokens, global.css, utilities
docs/                  Product, architecture, data, decisions, and implementation contracts
scripts/               Seed, validation, and repository tooling
```

Reusable components must not be placed in `apps/web/app/components`. Business logic must not live in route handlers or UI components.

## Documentation map

| File | Purpose |
|---|---|
| `docs/PRD.md` | What/why: product scope, MVP, business rules, acceptance criteria |
| `docs/ARCHITECTURE.md` | How the system is structured and deployed |
| `docs/DATA_MODEL.md` | Conceptual entities, constraints, identities, and transactions |
| `docs/DECISIONS.md` | Why major technical/engineering choices were made |
| `docs/IMPLEMENTATION_PLAN.md` | Phase → sprint → task → subtask execution roadmap |
| `docs/appflow.md` | End-to-end behavior and alternate flows |
| `docs/data_API.md` | Application-to-persistence data access contract |
| `docs/phase_scope.md` | Business/technical boundary and acceptance of each phase |
| `docs/requirements.md` | Traceable engineering requirement catalogue |
| `docs/schema.md` | Proposed concrete database schema reference |
| `docs/supabase-setup.md` | Not created: Supabase is not part of the approved architecture |

Additional implementation-contract documents should be created only when a later implementation decision explicitly requires them.

## Prerequisites

The planned development baseline requires:

- Git;
- Node.js and pnpm versions finalized in the architecture implementation step;
- Python version finalized in the architecture implementation step;
- Docker/Compose for local PostgreSQL, unless the approved local runtime changes;
- access to a PostgreSQL database for local/test/demo environments;
- optional provider credentials only when a real/test adapter is enabled;
- optional AI provider credentials only when an AI adapter is enabled.

The current repository does not yet provide package manifests, lockfiles, runtime scripts, Docker files, or environment templates. Installation commands below are planned and must not be treated as currently available commands.

## Installation and environment configuration

Once Phase 0 is implemented, the expected onboarding shape is:

```text
pnpm install
copy .env.example .env.local
```

The exact commands, package-manager version, and environment file names are implementation-defined in the approved architecture and README update. Never commit real values.

Expected variable categories, names to be finalized during implementation, include:

```text
APP_ENV
API_HOST
API_PORT
WEB_ORIGIN
DATABASE_URL
JWT_ISSUER
JWT_AUDIENCE
JWT_JWKS_URL
JWT_SIGNING_SECRET          # local/demo only; never commit
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET         # server-only
RAZORPAY_WEBHOOK_SECRET     # server-only
AI_PROVIDER
AI_MODEL
AI_API_KEY                  # server-only
AI_TIMEOUT_MS
LOG_LEVEL
SIMULATOR_SEED
```

These are variable categories, not currently implemented configuration names. The implementation must validate required variables and keep secrets out of browser bundles/logs.

## Database and migrations

The approved proposed database is PostgreSQL with SQLAlchemy persistence and Alembic migrations. The migration workflow will be:

1. Start the local PostgreSQL runtime.
2. Validate environment configuration.
3. Apply versioned migrations explicitly.
4. Run deterministic seed/simulator commands where required.
5. Run tests against an isolated test database.

The current repository has no migration files or database runtime. Application startup must not silently mutate schemas. See [DATA_MODEL.md](./DATA_MODEL.md), [schema.md](./schema.md), and [data_API.md](./data_API.md).

## Running the system

No runtime commands are currently available because implementation has not started. After Phase 0, README must document exact commands for:

```text
pnpm dev             Start development runtimes
pnpm dev:web         Start the web app, if provided
pnpm dev:api         Start the API, if provided
pnpm worker          Start the durable worker
pnpm simulator       Run a seeded synthetic batch
pnpm test            Run the relevant test suite
pnpm build           Build deployable artifacts
```

The final command names must match the actual package scripts; this README must be updated when implementation begins.

## Testing

The project will require unit, integration, API, database, worker, provider-adapter, concurrency, AI-contract, resilience, and browser E2E tests. MVP scenarios include duplicate webhooks/events, concurrent case creation, payment-before/during-worker races, AI failure/malformed output, policy blocks, opt-out, incident suppression, worker restart/lease expiry, provider retry/exhaustion with terminal failure, safe replay, duplicate actions, refunds/reversals, unauthorized operations, tenant isolation, and money correctness. Dedicated dead-letter replay and experiment/control-treatment tests are optional Stretch coverage.

Exact test commands are not currently available. They must be added to the README when the test framework is installed and must run in CI.

## Development workflow

For each implementation sprint:

1. Read the PRD and relevant architecture/data/decision sections.
2. Inspect the current implementation and Git status.
3. Implement only the sprint scope.
4. Add tests with the behavior.
5. Run lint, typecheck, build, migration, unit/integration, and relevant E2E checks.
6. Update existing source documentation only if a material contract changes.
7. Verify sprint and phase exit criteria.
8. Commit and push the coherent change to `origin/main`.

Do not introduce unapproved microservices, Redis, provider behavior, fixed demo totals, or frontend-only authorization.

## Common problems

The following are planned troubleshooting categories; exact commands will be added after implementation:

- **Database unavailable:** check `DATABASE_URL`, PostgreSQL readiness, migrations, and API readiness.
- **Webhook rejected:** verify configured signature secret, payload shape, timestamp/replay rules, and provider mode.
- **Worker unhealthy:** inspect job leases, worker process, database readiness, terminal failure status, and optional dead-letter status.
- **AI unavailable:** confirm provider configuration; deterministic fallback should keep the workflow safe.
- **Razorpay disconnected:** use the explicitly labeled simulator/test adapter; do not claim live provider results.
- **Stale action:** inspect payment reconciliation, opt-out, incident, policy, and job state; never manually bypass preflight.
- **Wrong recovery total:** stop reporting, reconcile provider/payment identity and adjustments, and use an auditable correction path.

## Status and next step

The next implementation step is Phase 0 repository bootstrap. Before code is written, the architecture and decisions must be reviewed for the exact package/runtime versions and local commands. Supabase setup is intentionally not documented because the approved architecture selects PostgreSQL directly, not Supabase.
