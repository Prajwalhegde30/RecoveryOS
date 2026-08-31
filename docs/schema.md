# RecoveryOS Proposed Database Schema

**Status:** PROPOSED SCHEMA — the canonical conceptual model is implemented through SQLAlchemy metadata and versioned Alembic migrations; production rollout remains environment-dependent  
**Conceptual source:** [DATA_MODEL.md](./DATA_MODEL.md)  
**Runtime direction:** [ARCHITECTURE.md](./ARCHITECTURE.md)  
**Persistence access:** [data_API.md](./data_API.md)

## 1. Purpose

This is the implementation-oriented schema reference for the canonical conceptual data model. It describes proposed PostgreSQL tables, columns, relationships, constraints, indexes, lifecycle, tenant scope, retention, and financial invariants. It is not evidence that these tables already exist; implementation begins in Phase 1 through versioned migrations.

Unless implementation proves a necessary change, table and column intent must remain aligned with `DATA_MODEL.md`.

## 2. Conventions

- Primary keys use opaque UUID/ULID-style identifiers; exact generator is implementation-defined.
- Timestamps use timezone-aware timestamps in UTC; merchant timezone is policy/configuration context.
- Monetary values use non-negative integer smallest units plus ISO currency code.
- JSON fields are typed/validated at application boundaries and are not a substitute for indexed identity fields.
- Tenant-owned tables include `merchant_id` directly or through a constrained parent.
- `created_at`/`updated_at` are required for mutable records; append-only records use `created_at`.
- Proposed indexes must be verified with query plans after implementation.

## 3. Proposed tables

### merchants

**Purpose:** Tenant/business account.  
**Columns:** `id` UUID PK NOT NULL; `external_key` text NOT NULL; `name` text NOT NULL; `default_currency` char(3) NOT NULL; `timezone` text NOT NULL; `environment_mode` enum/text NOT NULL; `status` enum/text NOT NULL; `created_at` timestamptz NOT NULL; `updated_at` timestamptz NOT NULL.  
**Constraints:** Unique `external_key`; valid currency/timezone/status checks.  
**Indexes:** external key unique; status.  
**Relationships:** Parent of all merchant-owned records.  
**Lifecycle/retention:** Created before merchant data; archival/status, not destructive cascade.  
**Tenant/audit:** Root tenant; administrative changes audited.

### users

**Purpose:** Authenticated human identity reference.  
**Columns:** `id` UUID PK; `issuer` text NOT NULL; `subject` text NOT NULL; optional `email_or_label` text; `status`; `created_at`; `updated_at`.  
**Constraints:** Unique `(issuer, subject)`.  
**Indexes:** issuer/subject unique.  
**Relationships:** Linked through `merchant_memberships`.  
**Lifecycle/retention:** Identity lifecycle follows auth/security policy.  
**Tenant/audit:** Membership changes and privileged actor use audited.

### merchant_memberships

**Purpose:** User-to-merchant role.  
**Columns:** `merchant_id` FK NOT NULL; `user_id` FK NOT NULL; `role` enum (`VIEWER`,`OPERATOR`,`ADMIN`) NOT NULL; `created_at`; `updated_at`.  
**Primary key:** `(merchant_id,user_id)`.  
**Indexes:** user, merchant/role.  
**Lifecycle:** Role changes are updates with audit; membership deletion must be authorized.

### customers

**Purpose:** Minimal merchant-scoped customer identity/context.  
**Columns:** `id` UUID PK; `merchant_id` FK; `external_customer_id` text NOT NULL; optional minimized `name`, `email`, `phone`; `status`; `opted_out_at`; `created_at`; `updated_at`.  
**Constraints:** Unique `(merchant_id,external_customer_id)`; PII length/format checks.  
**Indexes:** merchant/external ID; merchant/opted-out.  
**Lifecycle/retention:** Status/archive and configured retention; no raw payment credentials.  
**Tenant/audit:** Merchant-scoped and access-controlled.

### obligations

**Purpose:** One payable business obligation behind a Recovery Case.  
**Columns:** `id` UUID PK; `merchant_id` FK; `obligation_type` enum/text NOT NULL; `external_obligation_id` text NOT NULL; optional source IDs (`order_id`, `checkout_intent_id`, `subscription_id`, `billing_cycle_id`, `invoice_id`); `amount_at_risk` bigint NOT NULL; `currency` char(3) NOT NULL; `status`; `authoritative_status`; `due_at`; `paid_at`; `created_at`; `updated_at`.  
**Constraints:** Amount non-negative; valid currency; unique `(merchant_id,obligation_type,external_obligation_id)`.  
**Indexes:** merchant/type/external ID; merchant/status/due time.  
**Lifecycle:** Open, paid, cancelled, expired, or reconciled according to case workflow.  
**Financial:** Identity, not every attempt, controls revenue-at-risk counting.

### recovery_cases

**Purpose:** One recoverable obligation's workflow.  
**Columns:** `id` UUID PK; `merchant_id` FK; `obligation_id` FK NOT NULL; optional `customer_id` FK; `source_type`; `status` enum; `root_cause`; `root_cause_confidence` numeric/decimal; `recovery_probability` numeric/decimal; `probability_version`; `expected_recoverable_amount` bigint; `priority_score` numeric/decimal; `priority_version`; `attempt_count`; `max_attempts_snapshot`; `recovered_amount` bigint; `currency`; `attribution_status`; `incident_suppressed`; timestamps; `closed_at`.  
**Constraints:** Unique `obligation_id`; probability/score ranges; amount non-negative; valid status/currency.  
**Indexes:** merchant/status/priority; merchant/created; obligation; customer/open status.  
**Lifecycle:** Follows PRD state machine; terminal records retained for reporting/audit.  
**Financial:** Recovered amount changes only through reconciliation/correction.

### payment_attempts

**Purpose:** Provider payment attempt associated with a case.  
**Columns:** `id` UUID PK; `merchant_id` FK; `recovery_case_id` FK; `external_payment_id` text NOT NULL; `provider`; `payment_method`; `amount` bigint; `currency`; `status`; `failure_code`; provider/received timestamps; `created_at`; `updated_at`.  
**Constraints:** Unique `(merchant_id,provider,external_payment_id)`; amount/currency checks.  
**Indexes:** case/time; merchant/provider/external payment; status/method.  
**Lifecycle:** Append attempt facts; corrections/reversals are explicit updates/events.

### revenue_events

**Purpose:** Canonical normalized event facts.  
**Columns:** `id` UUID PK; `merchant_id` FK; `provider`; `external_event_id`; `event_type`; `source_object_id`; optional obligation/case FKs; normalized payload JSON; provider/received/processed timestamps; `processing_status`; `correlation_id`.  
**Constraints:** Unique `(merchant_id,provider,external_event_id)`; supported event/status checks.  
**Indexes:** merchant/status/received; provider/external ID; case/time.  
**Lifecycle:** Processing status changes; raw payload retention is minimized.

### processed_events

**Purpose:** Idempotency result for external events.  
**Columns:** `id` UUID PK; `merchant_id` FK; `provider`; `idempotency_key`; `event_type`; `first_seen_at`; `result`; `correlation_id`.  
**Constraints:** Unique `(merchant_id,provider,idempotency_key)`.  
**Indexes:** unique identity; first-seen/status as needed.  
**Lifecycle:** Retention must cover provider replay window and audit needs.

### recommendations

**Purpose:** AI/rule proposal, not authority.  
**Columns:** `id` PK; `merchant_id`; `recovery_case_id`; `source`; `action_type`; validated `parameters_json`; `reason_code`; `rationale`; `evidence_json`; `confidence`; `prompt_version`; `model_version`; `scoring_version`; `created_at`.  
**Constraints:** Known source/action; confidence range; schema validation before insert.  
**Indexes:** case/time; source/action; low-confidence review.  
**Lifecycle:** Append-only; superseded recommendations remain for explanation.

### merchant_policies

**Purpose:** Current policy pointer per merchant.  
**Columns:** `id` PK; `merchant_id` unique FK; `current_version_id` FK; `updated_at`.  
**Constraints:** One current policy per merchant; current version belongs to same merchant.

### policy_versions

**Purpose:** Immutable typed policy configuration.  
**Columns:** `id` PK; `merchant_id`; `version`; typed `policy_json`; `created_by`; `status`; `created_at`.  
**Constraints:** Unique `(merchant_id,version)`; schema-valid policy; valid status.  
**Indexes:** merchant/current status.  
**Lifecycle:** Immutable historical versions; activation is audited.

### policy_decisions

**Purpose:** Result of deterministic policy evaluation.  
**Columns:** `id` PK; `merchant_id`; `recovery_case_id`; optional recommendation; `policy_version_id`; result enum; decisive rule; reason; input snapshot JSON; actor type; correlation ID; `created_at`.  
**Constraints:** Valid result and referenced policy/case tenant.  
**Indexes:** case/time; result/time; policy version.  
**Lifecycle:** Append-only.

### recovery_actions

**Purpose:** Intended/executed external or human action.  
**Columns:** `id` PK; `merchant_id`; `recovery_case_id`; optional recommendation; action/channel; status; `idempotency_key`; attempt number; provider reference; cost bigint; requested/executed/cancelled timestamps; failure category/safe detail; correlation ID.  
**Constraints:** Unique `(merchant_id,idempotency_key)`; known action/channel/status; cost non-negative.  
**Indexes:** case/status/time; due/action status; provider reference.

### scheduled_jobs

**Purpose:** Durable future work.  
**Columns:** `id` PK; `merchant_id`; optional case/action; job type/status; `due_at`; attempt count/max; `lease_until`; `next_retry_at`; `idempotency_key`; last error category/safe detail; timestamps; correlation ID.  
**Constraints:** Unique `(merchant_id,idempotency_key)`; valid lease/status; non-negative attempts.  
**Indexes:** status/due/lease; merchant/case; retry time.  
**Lifecycle:** Pending, claimed, succeeded, cancelled, retrying, or terminally failed. A dedicated `dead-lettered` state/workflow is optional Stretch capability and must not block MVP completion.

### incidents

**Purpose:** Correlated systemic payment condition.  
**Columns:** `id` PK; `merchant_id`; dimension key; status; baseline/current windows; opened/resolved/cooldown timestamps; confidence; evidence JSON; detector version.  
**Constraints:** Unique merchant/dimension/window identity; valid thresholds/status.  
**Indexes:** merchant/status/dimension; active incidents.  
**Financial:** Never an obligation or revenue total.

### case_incidents

**Purpose:** Case-to-incident association.  
**Columns:** `incident_id` FK; `recovery_case_id` FK; association reason; `created_at`.  
**Primary key:** `(incident_id,recovery_case_id)`.  
**Lifecycle:** Association remains for audit even after resolution.

### simulator_runs

**Purpose:** Persist the lifecycle and reproducibility identity of a synthetic simulator request.
**Status:** IMPLEMENTED in ORM metadata and the next Alembic migration; deployment rollout remains environment-dependent.
**Columns:** `id` PK; `merchant_id` FK; `run_key`; `seed`; `status`; `label`; `configuration_json`; optional `result_json`; optional `started_at`, `completed_at`, and `error_safe`; `created_at`; `updated_at`.
**Constraints:** Unique `(merchant_id,run_key)`; run status is `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, or `RESET`.
**Indexes:** `(merchant_id,status)` supports tenant-scoped lifecycle operations.
**Lifecycle:** Repeated starts reuse a completed run. Reset is non-destructive and clears only the stored result/lifecycle state; generated events, obligations, cases, payment facts, actions, and attribution are preserved.
**Financial:** Synthetic run metadata and counters never establish financial truth.

### experiments

**Purpose:** Optional Stretch control/treatment configuration; not required for MVP case-level attribution.
**Columns:** `id` PK; `merchant_id`; name; status; control/treatment ratios; attribution window; eligibility JSON; timestamps.  
**Constraints:** Ratios valid/non-negative and total configured appropriately; valid status/window.

### experiment_assignments

**Purpose:** Optional Stretch immutable case variant for an approved experiment. It is not a prerequisite for normal recovery.
**Columns:** `id` PK; `experiment_id`; `recovery_case_id`; variant; assigned_at; assignment version.  
**Constraints:** Unique `(experiment_id,recovery_case_id)`; valid variant and same merchant scope.  
**Lifecycle:** Immutable after assignment.

### attribution_records

**Purpose:** One case-level measurement outcome.  
**Columns:** `id` PK; `merchant_id`; `recovery_case_id` unique; optional assignment/action/payment references; outcome; window start/end; recovered amount; adjustment amount; confidence; limitations; timestamps.  
**Constraints:** One record per case; valid outcome/window; amounts non-negative/adjustment rules.  
**Indexes:** merchant/outcome/time. Experiment/variant indexes through assignments are optional Stretch indexes and must not be required by MVP reporting.

### audit_events

**Purpose:** Append-only reconstruction trail.  
**Columns:** `id` PK; `merchant_id`; entity type/id; event type; actor type/id; optional from/to state; reason; safe metadata JSON; correlation ID; `created_at`.  
**Constraints:** Valid event/actor/state enums; metadata size/redaction rules.  
**Indexes:** entity/time; merchant/time; event type/time; correlation ID.  
**Lifecycle/retention:** Append-only and retained per approved policy; archival/deletion must be auditable.

## 4. Index strategy

Indexes prioritize merchant-scoped operational queries: open cases by status/priority, cases by obligation/customer/source/time, unprocessed events, due/leased jobs, active incidents, audit timelines, and provider/payment reconciliation. Experiment-variant indexes are optional Stretch support. Every index must be justified by a real access pattern and checked against the demo dataset; indexes must not remove tenant predicates.

## 5. Idempotency constraints

The schema must enforce uniqueness for external events, payment IDs, obligations, case-to-obligation, action keys, job keys, and case attribution. Experiment-assignment uniqueness applies when the optional Stretch capability is enabled. Financial recovery totals use obligation/payment identity and explicit adjustments, never row count or event count.

## 6. Concurrency constraints

Concurrent case creation relies on obligation/case uniqueness and reload-on-conflict. Worker claiming relies on leases/row locks. Action reservation precedes provider effects. Payment reconciliation and preflight must coordinate through transaction/locking/idempotency behavior. Exact isolation/locking settings are implementation-defined but must satisfy the tests in `IMPLEMENTATION_PLAN.md`.

## 7. Migration strategy

The schema is created by versioned Alembic migrations. Migrations must be reproducible, additive where possible, constraint-aware, and explicitly run in local/test/deployment workflows. Application startup must not mutate schema. Backfills and corrections must be idempotent and auditable.

## 8. Retention strategy

Retention periods are `OPEN` pending security/deployment decisions. Financial obligations, reconciliations, and audit history must not be silently cascaded away. PII retention and deletion must respect approved security/legal rules and record the operation.

## 9. Data integrity and tenant isolation

All foreign keys must reference same-merchant parents where applicable. Repository queries require validated `merchant_id`; external IDs are never globally trusted. Cross-tenant access is a test failure. Delete behavior uses status/archive for material financial records.

## 10. Financial integrity

No table may represent message delivery, AI output, incident count, or simulator counter as recovered money. Only authoritative payment reconciliation or an explicitly audited correction changes recovered amount. Refunds/reversals append adjustments. Dashboard queries aggregate reconciled case/attribution facts once.

## 11. Implementation status audit

The conceptual schema remains the canonical reference. Concrete tables through simulator lifecycle are implemented in `apps/api/app/persistence/models.py` and versioned migrations; any table or constraint not represented there remains `PROPOSED SCHEMA` until implemented.
