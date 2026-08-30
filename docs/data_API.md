# RecoveryOS Data Access API

**Status:** Proposed implementation contract  
**Scope:** Application/domain interaction with persistence  
**Not:** The public HTTP API specification  
**Canonical model:** [DATA_MODEL.md](./DATA_MODEL.md)  
**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)

## 1. Purpose and scope

This document defines the data-access boundary between RecoveryOS application/domain services and PostgreSQL persistence. It describes repositories, transactions, concurrency, idempotency, errors, tenant scoping, and query behavior. It does not define HTTP routes, UI payloads, or provider SDKs.

No implementation currently exists. Names and signatures below are conceptual interfaces to be confirmed during implementation without weakening the stated invariants.

## 2. Data ownership

| Data | Owning application service | Persistence responsibility |
|---|---|---|
| Recovery Cases | Case lifecycle service | Store current state and immutable references |
| Obligations | Obligation identity/reconciliation service | Enforce one logical payable obligation |
| Payment attempts | Payment/case service | Attach attempts to one case and external payment identity |
| Revenue events | Event ingestion service | Store normalized facts and provider identity |
| Recommendations | Analysis/AI service | Store versioned proposal/evidence, never authority |
| Policy decisions | Policy service | Append policy result, rule, inputs, and version |
| Actions | Action service | Reserve/record external effect and idempotency |
| Jobs | Scheduler/worker service | Durable due work, leases, retries, cancellation |
| Incidents | Incident service | Correlation context only; no financial obligation |
| Experiments | Experiment service | Immutable case assignment and configuration |
| Attribution | Attribution service | One case-level outcome and explicit adjustments |
| Audit events | Audit service | Append-only reconstruction record |
| Merchant policy | Configuration/policy service | Typed, versioned, tenant-scoped rules |

Domain services own invariants and orchestration. Repositories own persistence mechanics and must not silently add product behavior.

## 3. Repository boundaries

Conceptual repository interfaces:

```text
ObligationRepository
RecoveryCaseRepository
PaymentAttemptRepository
RevenueEventRepository
ProcessedEventRepository
RecommendationRepository
PolicyRepository
PolicyDecisionRepository
RecoveryActionRepository
ScheduledJobRepository
IncidentRepository
ExperimentRepository
AttributionRepository
AuditEventRepository
MerchantRepository
CustomerRepository
```

Repositories MUST:

- require merchant scope for tenant-owned reads/writes;
- accept typed domain values rather than provider payloads;
- expose explicit transaction/session boundaries;
- preserve unique-constraint and foreign-key errors for application mapping;
- avoid returning raw database rows to the web layer;
- support pagination and deterministic ordering;
- distinguish not-found from authorization-safe not-found behavior;
- avoid hidden writes during reads.

The application layer composes repositories through a unit-of-work or explicit transaction. The domain layer depends on interfaces, not SQLAlchemy.

## 4. Core operations

### Merchant, customer, and membership

- Create/update merchant and membership through authorized Admin workflows.
- Read only within authenticated merchant scope.
- Customer contact fields are minimized, access-controlled, and never used as obligation identity.
- Membership role changes are audited.
- Delete/retention uses status or archival; financial/audit parents are not cascaded away.

### Obligations and cases

- `find_by_identity(merchant, obligation_identity)` resolves the one logical obligation.
- `create_if_absent` must handle concurrent unique conflicts by returning the existing record.
- `get_case_for_obligation` enforces one case per obligation.
- `associate_attempt` appends an attempt without creating a second case.
- `transition_case` requires current state, expected version/lock, next state, actor, reason, and correlation ID.
- `reconcile_success` atomically binds verified payment success, recovered amount, terminal state, future-job cancellation, and audit.
- Case reads provide current facts plus ordered history; they do not recalculate financial truth in the UI.

### Events and processed events

- `reserve_event_idempotency` inserts the merchant/provider/event key atomically.
- `get_processing_result` returns the prior safe result for a duplicate.
- `append_normalized_event` stores canonical event facts and status.
- Event payloads are minimized/redacted according to retention policy.
- Replay preserves original identity and enters the same application path.

### Recommendations and policy decisions

- Recommendations are append-only proposals with source/version/evidence.
- Policy decisions are append-only and include policy version, decisive rule, result, and input snapshot.
- Re-evaluation creates a new record; it does not overwrite history.

### Actions and jobs

- `reserve_action` uses a merchant-scoped idempotency key.
- `create_job` is transactional with the action/policy decision.
- `claim_due_job` uses lease/lock semantics and returns one claimable job.
- `cancel_jobs_for_case` is idempotent and records the reason.
- `record_action_result` is safe if a worker retries after an ambiguous provider response.
- `dead_letter_job` preserves original identity and failure details safe for operators.

### Incidents and experiments

- Incident upsert is unique by merchant, dimension set, and incident window.
- Case association is unique and does not change obligation totals.
- Experiment assignment is immutable per experiment/case.
- Attribution is one current case-level record with explicit adjustment history.

### Audit

Audit writes are append-only. Every material state, policy, action, reconciliation, approval, configuration, simulator, and security event must be written in the same transaction as the operation where atomicity is required.

## 5. Transaction boundaries

The following operations MUST be atomic:

1. Reserve processed-event identity and persist the accepted normalized event.
2. Resolve/create obligation and case, attach the attempt, and record case creation/association audit.
3. Transition case state and append the state audit event.
4. Persist recommendation/policy snapshot when the decision is part of the case transition.
5. Persist policy decision and durable job/action creation.
6. Claim a job and write its lease before a worker acts.
7. Reserve action idempotency before an external effect.
8. Reconcile payment success, update case amount/state, cancel future jobs, and append audit.
9. Assign experiment variant before any treatment action.

External provider calls cannot share a database transaction. They use an idempotency key, a durable action record, and reconciliation for ambiguous responses.

## 6. Concurrency

### Concurrent case creation

The database unique obligation/case constraint is authoritative. Application pre-checks improve performance but cannot replace the constraint. On conflict, the transaction reloads the existing case and associates the new attempt.

### Job claiming

Workers claim due jobs using row locking/lease semantics. A lease has a configured expiry. An expired lease can be reclaimed only after checking the prior attempt and action idempotency record.

### Action reservation

The action idempotency key is reserved before an external effect. A concurrent worker sees the existing reservation/result and does not invoke the provider twice.

### Payment reconciliation

Success reconciliation takes precedence over outreach. Worker preflight and success handling must coordinate through authoritative lookup plus transaction/locking/idempotency strategy. If status is temporarily unavailable, the worker waits/retries/escalates.

### Optimistic versioning

Case/job/action updates SHOULD use expected version or lease ownership to reject stale writers. Exact implementation is pending architecture finalization.

## 7. Idempotency matrix

| Effect | Identity | Persistence mechanism | Duplicate result |
|---|---|---|---|
| External event | merchant + provider + event ID | `processed_events` unique | Prior processing result |
| Business obligation | merchant + source type + external obligation ID | `obligations` unique | Existing obligation |
| Recovery Case | one obligation ID | `recovery_cases.obligation_id` unique | Existing case |
| Payment attempt | merchant + provider + payment ID | `payment_attempts` unique | Existing attempt |
| Action | merchant + action idempotency key | `recovery_actions` unique | Prior provider/result |
| Scheduled job | merchant + job idempotency key | `scheduled_jobs` unique | Existing job |
| Recovered amount | obligation + verified payment identity | reconciliation/attribution constraints | No increment |
| Experiment assignment | experiment + case | assignment unique | Existing variant |

Retries, replay, and concurrency must use the same identity rules. No caller may create a second effect by changing only a local request ID.

## 8. Error behavior

Persistence errors are mapped to application categories:

- `ValidationError`: malformed domain values or constraints known before persistence.
- `AuthorizationError`: scope/role failure; do not reveal another tenant's existence.
- `NotFoundError`: requested scoped entity is absent.
- `ConflictError`: uniqueness, stale version, or lease conflict; caller may reload/retry safely.
- `StateTransitionError`: illegal case/job/action transition.
- `RetryablePersistenceError`: transient database/connection/deadlock condition.
- `ConfigurationError`: invalid required policy/provider/runtime configuration.
- `DataIntegrityError`: unexpected invariant/foreign-key failure requiring alert and investigation.

Repositories must rollback failed transactions, never swallow uniqueness/integrity failures, and never convert an uncertain financial write into success. User-facing API errors are safe summaries; internal logs include correlation IDs and redacted details.

## 9. Tenant scoping

Every tenant-owned repository method requires `merchant_id` from validated authentication/application context. It must not accept merchant scope solely from an untrusted request body. Query builders apply merchant scope before filters and joins. Job claims, audit reads, metrics, simulator runs, provider configuration, and customer information are all merchant-scoped.

Cross-tenant access tests are required for every aggregate. Identical external IDs in two merchants must remain separate. Background workers carry merchant scope from the durable job and revalidate it before acting.

## 10. Financial persistence rules

- Store amount as non-negative integer smallest units plus ISO currency.
- Validate currency consistently at event, obligation, payment, action-cost, attribution, and reporting boundaries.
- Never use floating-point values for persisted or aggregated monetary amounts.
- Expected values are estimates and must remain distinct from recovered amounts.
- Recovered amount changes only from authoritative success reconciliation or auditable adjustment.
- Message delivery/clicks, AI recommendations, incident volume, and simulator counters cannot update financial totals.
- Refunds/reversals append explicit adjustments; original success history remains intact.

## 11. Query and index considerations

Required access patterns:

- open cases by merchant/status/priority;
- cases by obligation/customer/source/date;
- due jobs by merchant/status/due time;
- unprocessed events by merchant/status/received time;
- incidents by merchant/status/dimension;
- audit timeline by entity/time;
- experiments by experiment/variant;
- reconciliation by provider/payment/obligation identity.

Indexes are defined canonically in `DATA_MODEL.md` and concretely in `schema.md` once implementation exists. New queries must include a query plan review for the seeded batch and must not remove tenant predicates for performance.

## 12. Retention and deletion

Retention periods are `OPEN` pending security/deployment decisions. Application code must use archival/status workflows rather than cascading deletion of financial obligations, cases, reconciliations, or audit records. PII deletion must be reconciled with legal/audit retention and recorded as an auditable operation.

## 13. Verification checklist

- [ ] All repository methods require tenant scope where applicable.
- [ ] Unique constraints are tested under concurrency.
- [ ] Every material multi-write operation has a defined transaction boundary.
- [ ] External effects have action/job idempotency.
- [ ] Reconciliation cannot double-count a success.
- [ ] Audit records are atomic or explicitly reconciled.
- [ ] Persistence errors map to safe application errors.
- [ ] No financial value originates in a read-model or UI calculation.
