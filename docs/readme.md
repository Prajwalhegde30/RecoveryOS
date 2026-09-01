# RecoveryOS

**RecoveryOS — AI Revenue Recovery Decision & Orchestration Engine**

> Detect revenue at risk. Decide the next-best recovery action. Recover money safely. Prove the result.

## RecoveryOS overview

RecoveryOS is a planned merchant operations platform for revenue recovery. It turns failed payments, checkout abandonment, recurring-payment failures, overdue invoices, and correlated payment degradation into prioritized Recovery Cases. It diagnoses likely causes, estimates recoverability, selects a bounded action, applies deterministic policy, executes or schedules work, reconciles payment truth, and measures natural versus assisted recovery.

The repository contains the implemented RecoveryOS modular monolith: a FastAPI API and worker, PostgreSQL persistence and migrations, provider/simulator workflows, deterministic scoring and fallback, policy enforcement, reconciliation, attribution, tenant-scoped APIs, and a Next.js operations dashboard.

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

The current repository contains documentation, the Phase 0 scaffold, and `LICENSE`. The implementation structure is:

```text
apps/web/              Next.js merchant dashboard and route composition
apps/api/              FastAPI API, domain, application, persistence, worker, adapters
packages/ui/src/       Shared accessible components, tokens, global.css, utilities
docs/                  Product, architecture, data, decisions, and implementation contracts
scripts/               Seed, validation, smoke E2E, and repository tooling
```

Reusable components must not be placed in `apps/web/app/components`. Business logic must not live in route handlers or UI components.

## Documentation map

| File                          | Purpose                                                           |
| ----------------------------- | ----------------------------------------------------------------- |
| `docs/PRD.md`                 | What/why: product scope, MVP, business rules, acceptance criteria |
| `docs/ARCHITECTURE.md`        | How the system is structured and deployed                         |
| `docs/DATA_MODEL.md`          | Conceptual entities, constraints, identities, and transactions    |
| `docs/DECISIONS.md`           | Why major technical/engineering choices were made                 |
| `docs/IMPLEMENTATION_PLAN.md` | Phase → sprint → task → subtask execution roadmap                 |
| `docs/appflow.md`             | End-to-end behavior and alternate flows                           |
| `docs/data_API.md`            | Application-to-persistence data access contract                   |
| `docs/phase_scope.md`         | Business/technical boundary and acceptance of each phase          |
| `docs/requirements.md`        | Traceable engineering requirement catalogue                       |
| `docs/schema.md`              | Proposed concrete database schema reference                       |
| `docs/supabase-setup.md`      | Not created: Supabase is not part of the approved architecture    |

Additional implementation-contract documents should be created only when a later implementation decision explicitly requires them.

## Prerequisites

The Phase 0 development baseline requires:

- Git;
- Node.js 22.14.x and pnpm 11.19.x;
- Python 3.12.x;
- Docker/Compose for local PostgreSQL, unless the approved local runtime changes;
- access to a PostgreSQL database for local/test/demo environments;
- optional provider credentials only when a real/test adapter is enabled;
- optional AI provider credentials only when an AI adapter is enabled.

The current repository provides package manifests, a lockfile, runtime scripts, an environment template, quality tooling, SQLAlchemy persistence, the complete Alembic migration chain, a Docker Compose PostgreSQL service on host port 5433, simulator lifecycle APIs, and worker-backed recovery workflows.

## Installation and environment configuration

The Phase 0 onboarding shape is:

```powershell
pnpm install --frozen-lockfile
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[test]"
```

The exact commands, package-manager version, and environment file names are implementation-defined in the approved architecture and README update. Never commit real values.

The current environment template defines these variable names; values remain local/configuration inputs:

```text
APP_ENV
API_HOST
API_PORT
WEB_ORIGIN
DATABASE_URL
AUTH_ISSUER
AUTH_AUDIENCE
AUTH_MODE                  # local or jwks
AUTH_JWKS_URL              # required in jwks mode
AUTH_HMAC_SECRET           # local/demo only; never commit
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET         # server-only
RAZORPAY_WEBHOOK_SECRET     # server-only
AI_PROVIDER
AI_MODEL
GROQ_API_KEY                # required only for groq; server-only
AI_TIMEOUT_MS               # provider timeout in milliseconds
LOG_LEVEL
SIMULATOR_SEED
```

The authentication variables above map to the API settings names. `AUTH_MODE=jwks` requires `AUTH_JWKS_URL` and validates asymmetric provider-issued JWTs; it never falls back to HMAC. `AUTH_MODE=local` requires `AUTH_HMAC_SECRET` for the deterministic demo path. `AI_PROVIDER=groq` requires the server-side `GROQ_API_KEY`; it is never read by the web app or exposed in browser configuration. Keep secrets out of browser bundles and logs.

For a real Groq-backed run, set `AI_PROVIDER=groq`, `GROQ_API_KEY`, `AI_MODEL` (the default is `openai/gpt-oss-20b`), and `AI_TIMEOUT_MS` on the API process only. Start the API with those variables, then run the authenticated simulator workflow with `AI_PROVIDER=groq` in the shell running `pnpm demo:e2e`. The output must contain `provider":"groq"` and `recommendation_sources":["AI"]`; `DETERMINISTIC_FALLBACK` indicates fallback instead. Never put `GROQ_API_KEY` in `NEXT_PUBLIC_*` variables.

## Database and migrations

The approved proposed database is PostgreSQL with SQLAlchemy persistence and Alembic migrations. The current local migration workflow is:

1. Start PostgreSQL with `docker compose up -d postgres`.
2. Copy `.env.example` to `.env` and configure `DATABASE_URL` if the local connection differs.
3. Apply the baseline with `pnpm db:upgrade`.
4. Run tests against an isolated test database.

Application startup must not silently mutate schemas. Repository operations and product workflow migrations remain planned. See [DATA_MODEL.md](./DATA_MODEL.md), [schema.md](./schema.md), and [data_API.md](./data_API.md).

## Running the system

The Phase 0 runtime commands are:

```text
pnpm dev:web         Start the web shell
pnpm dev:api         Start the API health boundary (activate .venv first)
python -m app.workers --merchant-id <merchant-id>
                      Start the durable action worker (run from apps/api)
pnpm e2e:smoke       Verify running API and web processes
pnpm demo:reset      Recreate the dedicated recoveryos_demo database and run migrations
pnpm demo:e2e        Run the deterministic authenticated simulator batch and verify derived dashboard metrics
pnpm test            Run the current workspace tests
pnpm build           Build the current workspace artifacts
```

The API simulator lifecycle is available through authenticated Admin routes. The worker runner uses the existing durable job, simulated payment, and simulated messaging boundaries; it does not create a schema or queue as a startup side effect. The database migration command is available now.

## Testing

The project will require unit, integration, API, database, worker, provider-adapter, concurrency, AI-contract, resilience, and browser E2E tests. MVP scenarios include duplicate webhooks/events, concurrent case creation, payment-before/during-worker races, AI failure/malformed output, policy blocks, opt-out, incident suppression, worker restart/lease expiry, provider retry/exhaustion with terminal failure, safe replay, duplicate actions, refunds/reversals, unauthorized operations, tenant isolation, and money correctness. Dedicated dead-letter replay and experiment/control-treatment tests are optional Stretch coverage.

Current checks are:

```text
pnpm validate
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm e2e:smoke       # requires API and web running
pnpm demo:reset      # requires Docker and the RecoveryOS PostgreSQL container
pnpm demo:e2e        # requires API, PostgreSQL, an authenticated admin token, and a configured merchant policy
```

### Clean-state demo workflow

With the RecoveryOS PostgreSQL container running on host port 5433, use the dedicated demo database:

```powershell
$env:DEMO_AUTH_SECRET = 'local-demo-only'
pnpm demo:reset
$env:DATABASE_URL = 'postgresql+psycopg://recoveryos:recoveryos@127.0.0.1:5433/recoveryos_demo'
$env:DEMO_AUTH_TOKEN = (node scripts/run-python.mjs apps/api/scripts/seed_demo.py)
pnpm demo:e2e
```

Start the API with the same `DATABASE_URL` and `DEMO_AUTH_SECRET`, then start the worker for `demo-merchant`; the simulator batch exercises ingestion, case creation, diagnosis, fallback recommendation, policy evaluation, recovery action, reconciliation, attribution, and dashboard metrics. Re-running `pnpm demo:reset` drops only `recoveryos_demo`, recreates it, and reruns migrations, so no prior demo facts remain. The reset command refuses any database name other than `recoveryos_demo`.

The API test/typecheck commands require the repository virtual environment to be active or its Python directory on PATH.

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

The next implementation step is Phase 1 repository and unit-of-work work after the schema baseline. Supabase setup is intentionally not documented because the approved architecture selects PostgreSQL directly, not Supabase.
