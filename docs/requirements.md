# RecoveryOS Engineering Requirements Catalogue

**Status:** Proposed, traceable implementation catalogue  
**Source:** [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DATA_MODEL.md](./DATA_MODEL.md), [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Implementation status:** No application code exists yet

## 1. Purpose

This catalogue translates the approved product behavior into engineering-verifiable requirements. It is not a replacement for PRD scope or the implementation roadmap. Requirement IDs are stable references for tests, reviews, and sprint exit checks.

Priority values: `MUST` is required for MVP correctness; `SHOULD` is expected unless a decision records an exception; `MAY` is optional/stretch.

## 2. Product and case requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-PROD-001 | RecoveryOS MUST optimize incremental recovered revenue while minimizing customer annoyance, intervention cost, operational burden, and risk. | MUST | PRD north star | Measurement | Metrics/E2E review | 11,17,18 |
| REQ-CASE-001 | One recoverable business obligation MUST map to at most one Recovery Case. | MUST | Prevents double counting | Obligation identity, DB uniqueness | Concurrent identity tests | 1–3 |
| REQ-CASE-002 | Multiple payment attempts for one order/cycle/invoice MUST remain attached to one case. | MUST | Case semantics | Obligation identity | Multi-attempt integration test | 3 |
| REQ-CASE-003 | Cases MUST use the explicit PRD state machine and reject illegal transitions. | MUST | Financial workflow safety | Domain service | Transition test matrix | 3 |
| REQ-CASE-004 | Verified payment success MUST be able to close any still-open recoverable case. | MUST | Reconciliation priority | Payment provider | Reconciliation E2E | 9 |
| REQ-CASE-005 | Terminal cases MUST reject customer-facing actions except authorized correction flow. | MUST | Stop rules | State/policy | Terminal action test | 3,6,9 |

## 3. Event and idempotency requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-EVENT-001 | The ingestion boundary MUST validate supported event type, required fields, timestamps, merchant scope, and amount/currency where applicable. | MUST | Trust boundary | Schemas/config | Invalid payload tests | 2 |
| REQ-EVENT-002 | Signed provider webhooks MUST be signature-verified before domain mutation. | MUST | Webhook security | Provider secret config | Invalid signature test | 2 |
| REQ-EVENT-003 | Provider events MUST be normalized into a canonical event model. | MUST | Adapter isolation | Event contract | Mapping tests | 2 |
| REQ-EVENT-004 | Accepted events MUST carry provider identity, source identity, merchant, timestamps, and correlation ID. | MUST | Traceability | Event persistence | Schema/integration test | 2 |
| REQ-IDEM-001 | External event identity MUST be unique per merchant/provider/event ID. | MUST | Duplicate prevention | `processed_events` | Constraint/concurrency test | 1,2 |
| REQ-IDEM-002 | Duplicate events MUST be safe no-ops and MUST NOT create cases, attempts, actions, or financial effects. | MUST | Financial correctness | Event transaction | Duplicate E2E | 2 |
| REQ-IDEM-003 | Obligation, payment, case, action, job, assignment, and recovered payment identities MUST each have explicit uniqueness rules. | MUST | Cross-cutting idempotency | Data model | Constraint tests | 1–9 |
| REQ-IDEM-004 | Replays MUST preserve original identity and use the same idempotent application path. | MUST | Safe recovery | Event/job services | Replay test | 2,7 |
| REQ-IDEM-005 | Correlation IDs MUST propagate from event through case, recommendation, job, provider action, reconciliation, audit, and logs. | MUST | Observability | Runtime context | Propagation test | 2,15 |

## 4. Financial requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-FIN-001 | All monetary values MUST be integer smallest currency units with validated ISO currency. | MUST | Prevents rounding errors | Schema/domain | Unit/DB tests | 1,4 |
| REQ-FIN-002 | Payment/order truth MUST come from authoritative server-side provider or verified simulator status. | MUST | Browser/AI cannot establish payment | Provider adapter | Reconciliation test | 8,9 |
| REQ-FIN-003 | Expected Recoverable Revenue MUST be amount at risk × probability using deterministic arithmetic. | MUST | Economic prioritization | Scoring config | Arithmetic tests | 4 |
| REQ-FIN-004 | Recovered amount MUST be updated only by authoritative reconciliation or auditable correction. | MUST | Prevents false revenue | Payment identity | Source reconciliation | 9,11 |
| REQ-FIN-005 | Messages, clicks, recommendations, incidents, simulator counters, and duplicate events MUST NOT create recovered revenue. | MUST | Financial truth | Attribution | Negative tests | 9,11 |
| REQ-FIN-006 | Refunds/reversals MUST be represented as explicit adjustments without deleting original success history. | MUST | Net correctness | Reconciliation | Adjustment tests | 9,11 |
| REQ-FIN-007 | Recovery reports MUST prevent duplicate aggregation by obligation/payment identity. | MUST | Dashboard integrity | Read models | Metric reconciliation | 11,13 |

## 5. Analysis and scoring requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-SCORE-001 | Root cause MUST be classified from supported categories or returned as unknown/insufficient evidence. | MUST | Strategy depends on cause | Normalized facts | Fixture tests | 4 |
| REQ-SCORE-002 | Recovery probability v1 MUST be deterministic, configurable, versioned, explainable, and behind a replaceable interface. | MUST | No invented production ML | Evidence/config | Score tests | 4 |
| REQ-SCORE-003 | Probability MUST be clamped to `[0,1]`; missing data MUST follow documented neutral/low-confidence behavior. | MUST | Safe scoring | Scoring config | Boundary tests | 4 |
| REQ-SCORE-004 | Priority MUST use configured factors/penalties and determine ordering only, never financial totals. | MUST | Economic prioritization | Expected value | Ordering tests | 4 |
| REQ-SCORE-005 | Score outputs MUST contain input evidence, confidence, version, and explanation. | MUST | Explainability | Persistence | Snapshot tests | 4,5 |
| REQ-INCIDENT-001 | Incident detection MUST compare configurable baseline/current windows with sample, failure, degradation, correlation, and confidence thresholds. | MUST | Systemic restraint | Event/payment facts | Detector tests | 10 |
| REQ-INCIDENT-002 | Incidents MUST be operational context only and MUST NOT create financial obligations or totals. | MUST | Prevents double count | Case association | Aggregate negative test | 10 |
| REQ-INCIDENT-003 | Incidents MUST support resolution threshold, recovery window, cooldown, and affected-case association. | MUST | Avoids flapping | Jobs/policy | Lifecycle tests | 10 |

## 6. AI requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-AI-001 | AI MUST receive minimized, tenant-scoped evidence and may recommend only registered actions. | MUST | Bounded autonomy | Action registry | Contract/security tests | 5 |
| REQ-AI-002 | AI output MUST validate against a typed schema with action, parameters, reason, evidence, confidence, fallback, and version metadata. | MUST | Prevents arbitrary actions | Provider adapter | Malformed output tests | 5 |
| REQ-AI-003 | AI MUST NOT determine payment truth, mutate financial state, bypass policy, alter authorization, or execute arbitrary tools. | MUST | Deterministic boundary | Policy/service layers | Negative/security tests | 5,6 |
| REQ-AI-004 | Prompt, model, schema, and configuration versions MUST be traceable on each recommendation. | MUST | Reproducibility | Config/persistence | Metadata test | 5 |
| REQ-AI-005 | Timeout, outage, malformed output, invalid action, low confidence, or contradictory evidence MUST use deterministic fallback, wait, suppression, or approval. | MUST | Safe degradation | Fallback rules | Failure tests | 5 |
| REQ-AI-006 | Recommendation explanations MUST show evidence, confidence, scoring factors, source, and downstream policy result. | MUST | Decision transparency | UI/API | Case E2E | 5,12,13 |

## 7. Policy and action requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-POLICY-001 | Every proposed action MUST pass deterministic policy evaluation. | MUST | AI is advisory | Policy service | Policy integration tests | 6 |
| REQ-POLICY-002 | Precedence MUST be success, opt-out, terminal, stale/invalid, incident, limits, interval, quiet hours, approval, channel, allow. | MUST | Safety ordering | Policy context | Branch matrix | 6 |
| REQ-POLICY-003 | Policy MUST enforce attempts, contact limits, minimum interval, quiet hours, channel availability, incident suppression, and sequence duration. | MUST | Customer safety | Typed policy | Config tests | 6 |
| REQ-POLICY-004 | Policy versions MUST be immutable/reconstructable and stored on decisions/jobs/actions. | MUST | Auditability | Policy persistence | Version tests | 6,7 |
| REQ-POLICY-005 | Opt-out MUST stop applicable future customer contact. | MUST | Consent/safety | Customer state/jobs | Opt-out E2E | 6,7,9 |
| REQ-POLICY-006 | High-value or configured cases MUST require authorized human approval. | MUST | Bounded autonomy | RBAC | Approval tests | 6,14 |
| REQ-ACTION-001 | Actions MUST use provider adapters and action idempotency keys. | MUST | External-effect safety | Adapter/job | Duplicate action test | 7,8 |
| REQ-ACTION-002 | Provider failure MUST be classified as retryable or terminal and handled with bounded retry/backoff and a safe fallback. Repeated failure MUST reach an explicit terminal failure state; a dedicated DLQ is optional Stretch infrastructure. | MUST | Resilience | Worker | Failure injection | 7,16 |

## 8. Job and worker requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-JOB-001 | Scheduled work MUST be durable or reconstructable after restart. | MUST | No lost recovery | PostgreSQL jobs | Restart test | 7 |
| REQ-JOB-002 | Job claiming MUST use lease/lock ownership and reject stale writers. | MUST | Concurrency | DB locks | Concurrent worker test | 7 |
| REQ-JOB-003 | Worker MUST recheck payment/order/case/opt-out/incident/policy/action state immediately before effects. | MUST | Race safety | Provider/policy | Preflight E2E | 7,9 |
| REQ-JOB-004 | If dedicated DLQ capability is implemented, repeatedly failing jobs SHOULD enter dead-letter status with controlled replay preserving identity. This optional Stretch capability must not be required for the MVP workflow. | MAY (STRETCH) | Operations | Job persistence | Optional DLQ/replay test | 7,16 |
| REQ-JOB-005 | Success, opt-out, cancellation, suppression, and exhaustion MUST cancel applicable future jobs idempotently. | MUST | Stop rules | Case/job service | Cancellation tests | 6,7,9 |

## 9. Attribution and measurement requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-ATTR-001 | When an approved experiment is active and a case is eligible, the case MAY receive an immutable control/treatment assignment before treatment. This is Stretch and is not required for normal MVP attribution. | MAY (STRETCH) | Optional lift measurement | Experiment service | Assignment tests when enabled | 11 |
| REQ-ATTR-002 | MVP case outcomes MUST classify natural, assisted, suppressed, and unrecovered consistently at case level, with recovery cost, net recovery, and applicable refund/reversal adjustments. | MUST | Revenue measurement | Reconciliation/actions | Outcome and adjustment tests | 9,11 |
| REQ-ATTR-003 | Attribution MUST use configured case-level window and deterministic event ordering. | MUST | Avoids false credit | Event timestamps | Window tests | 11 |
| REQ-ATTR-004 | MVP reports MUST show recovery cost, net recovery, recovery rates, and measurement limitations. If an approved experiment is active, experiment-specific lift and sample information MAY also be shown. | MUST | Honest ROI | Metrics | MVP metric/E2E tests | 11,13 |
| REQ-ATTR-005 | Experiment-specific control/treatment analytics and treatment lift MAY be provided for approved experiments, but MUST NOT block core case-level attribution or MVP completion. | MAY (STRETCH) | Optional experimentation | Experiment service/metrics | Optional experiment analytics tests | 11,13 |

## 10. API, UI, auth, and tenancy requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-API-001 | API schemas MUST be typed and provide a stable contract for dashboard, cases, incidents, policies, actions, metrics, simulator, and health. | MUST | Web/API separation | OpenAPI | Contract tests | 12 |
| REQ-API-002 | API errors MUST be safe, categorized, correlated, and free of raw provider/secrets/PII. | MUST | Operability/security | Error mapping | API tests | 12,15 |
| REQ-UI-001 | Dashboard MUST show risk, expected/recovered value, incidents, active cases, approvals, attribution, and system health. | MUST | Five-second story | Metrics/API | Browser E2E | 13 |
| REQ-UI-002 | Case detail MUST show financial truth, evidence, diagnosis, score, recommendation, policy, actions, reconciliation, attribution, and audit. | MUST | Explainability | Case API | Browser E2E | 13 |
| REQ-UI-003 | Shared/reusable UI MUST live in `packages/ui/src`; global styles/tokens MUST come from the shared package. | MUST | Maintainability | Monorepo | Architecture check | 0,13 |
| REQ-AUTH-001 | API MUST validate JWT/JWKS identity and enforce Viewer/Operator/Admin permissions server-side. | MUST | Trust boundary | Auth config | Auth matrix | 14 |
| REQ-TENANT-001 | Every tenant-owned query, mutation, job, metric, provider context, and audit read MUST enforce merchant scope. | MUST | Data isolation | Memberships | Cross-tenant tests | 14 |

## 11. Security, observability, and performance requirements

| ID | Requirement | Priority | Source/rationale | Dependencies | Verification | Phase |
|---|---|---|---|---|---|---|
| REQ-SEC-001 | Secrets MUST come from secure environment/secret management and never source control, client bundles, logs, or responses. | MUST | Secret safety | Config | Secret scan/log test | 0,15 |
| REQ-SEC-002 | Deployed traffic/storage MUST use configured TLS/encryption capabilities; PII MUST be minimized/redacted. | MUST | Data protection | Deployment | Security review/test | 15 |
| REQ-SEC-003 | Webhook, mutation, auth-sensitive, and simulator endpoints MUST have configurable rate limits. | MUST | Abuse prevention | Middleware | Rate-limit tests | 15 |
| REQ-AUDIT-001 | Material state, policy, action, approval, reconciliation, configuration, security, and simulator events MUST be append-only/auditable. | MUST | Reconstruction | Audit service | Audit completeness | 3,6,9,15 |
| REQ-OBS-001 | Logs MUST be structured, correlated, and redacted; metrics MUST cover webhook, case, job, provider, AI, incident, and recovery health. | MUST | Operations | Observability | Log/metric tests | 15 |
| REQ-OBS-002 | API and worker MUST expose safe liveness/readiness/dependency health and stale/backlog signals. | MUST | Failure visibility | Health checks | Health tests | 12,15 |
| REQ-PERF-001 | Valid webhook acknowledgement SHOULD meet p95 ≤ 2 seconds after validation, with heavy processing asynchronous. | SHOULD | Provider reliability | API/runtime | Load test | 2,12 |
| REQ-PERF-002 | Common read API p95 SHOULD be ≤ 500 ms and initial dashboard p95 ≤ 2 seconds for seeded demo data. | SHOULD | Usable dashboard | Indexes/API | Performance test | 12,13 |
| REQ-PERF-003 | Due jobs SHOULD be picked up within the configured demo target. | SHOULD | Timely bounded work | Worker | Worker/load test | 7 |
| REQ-PERF-004 | AI calls MUST have a configured timeout and safe failure behavior. | MUST | Bounded AI dependency | AI adapter | AI timeout/fallback test | 5 |

## 12. Testing requirements

| ID | Requirement | Priority | Verification |
|---|---|---|---|
| REQ-TEST-001 | Financial calculations, identity, state, policy, scoring, incident, attribution, and configuration MUST have unit tests. | MUST | Unit suite |
| REQ-TEST-002 | Database migrations, repositories, webhook-to-case, reconciliation, jobs, adapters, auth, and tenant boundaries MUST have integration tests. | MUST | Integration suite |
| REQ-TEST-003 | The first vertical slice MUST have browser/API E2E coverage. | MUST | E2E suite |
| REQ-TEST-004 | Every completed phase MUST run relevant unit/integration tests, functionality E2E, regression E2E, and phase exit checks before completion. | MUST | CI/phase gate |
| REQ-TEST-005 | Failure injection MUST cover AI/provider/database/worker failures, stale jobs, leases, bounded retries, safe replay/idempotency, terminal failure, and duplicate effects. Dedicated DLQ/replay infrastructure MAY be tested when the Stretch capability is enabled. | MUST | Resilience suite |
