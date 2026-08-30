# RecoveryOS Product Requirements Document

**Product:** RecoveryOS — AI Revenue Recovery Decision & Orchestration Engine  
**Track:** Razorpay Buildathon, Track 3 — AI Revenue Recovery  
**Status:** Product Approved — Architecture Pending  
**Version:** 1.0  
**Date:** 2026-08-30

## 1. Executive summary

RecoveryOS is a revenue recovery control plane for merchants. It converts failed payments, checkout abandonments, recurring-payment failures, overdue invoices, and payment-system degradation signals into a common **Recovery Case**. It diagnoses the likely cause, estimates recoverability and Expected Recoverable Revenue, prioritizes cases, selects a bounded next-best action, applies deterministic policies, executes or schedules the action, observes the result, and proves how much money was recovered.

The product is not a chatbot, a notification sender, a subscription-retry clone, or a payment-routing replacement. Its differentiation is a unified intelligence and orchestration layer across revenue-risk surfaces, with explicit restraint, financial correctness, auditability, and measurable incremental recovery.

Tagline: **Detect revenue at risk. Decide the next-best recovery action. Recover money safely. Prove the result.**

## 2. Product vision and thesis

Businesses lose revenue through fragmented failure modes: a temporary UPI timeout, a card decline, an abandoned checkout, a failed subscription mandate, an overdue invoice, or a broad payment incident. Each can be handled by a different tool, but the merchant needs one answer: what revenue is at risk, what is likely to help, and what happened afterward?

RecoveryOS treats these as one problem: **Revenue at Risk**. Every risk signal becomes a Recovery Case and passes through a shared loop:

```text
Revenue event
  -> normalize and deduplicate
  -> Recovery Case
  -> root-cause diagnosis
  -> recovery probability
  -> Expected Recoverable Revenue
  -> priority
  -> next-best action
  -> policy check
  -> execute, schedule, wait, suppress, or escalate
  -> observe payment and intervention outcomes
  -> recovered revenue and attribution
```

The system optimizes recovered revenue while minimizing customer annoyance, intervention cost, operational burden, and compliance risk. Sometimes the best action is no action.

## 3. Buildathon context and positioning

The Buildathon challenge requires a system that detects at-risk revenue, understands why it is slipping away, chooses an intervention, executes a bounded workflow, stops or escalates safely, maintains an audit trail, and demonstrates measurable money recovered across a batch.

Revenue recovery is an established category. Razorpay, Stripe, Paddle, Chargebee, Recurly, Tesorio, HighRadius, Upflow, Hyperswitch, Kill Bill, and Lago represent adjacent capabilities in payments, retries, dunning, collections, routing, or orchestration. Razorpay already provides capabilities related to recurring retries, payment links, checkout abandonment, Optimizer, AI agents, subscriptions, cart conversion, and analytics.

RecoveryOS therefore must not claim to be the first recovery system. The differentiated proposition is:

- cross-surface revenue-risk detection;
- a universal Recovery Case abstraction;
- root-cause and incident correlation;
- recovery probability and Expected Recoverable Revenue;
- priority based on economic value, not just failure count;
- policy-governed bounded autonomy;
- stopping rules and intelligent restraint;
- control/treatment measurement and incremental attribution;
- an auditable decision and action timeline.

RecoveryOS complements Razorpay infrastructure. Optimizer primarily reduces avoidable failures before or during payment routing; RecoveryOS handles unresolved revenue risk after or around a failure.

## 4. Problem statement

Merchants lack a unified, economically prioritized way to answer:

1. How much money is currently at risk?
2. Which failures are customer-specific versus systemic?
3. Which cases are worth intervention?
4. What should happen next, and when?
5. Is the action permitted and safe?
6. Did the customer pay naturally or because of the intervention?
7. How much incremental revenue and ROI did the recovery program produce?

Naive automation sends the same reminder to every failed payment. That creates duplicate messages, contacts customers who already paid, wastes money on low-value cases, worsens customer experience during incidents, and cannot prove causal impact.

## 5. Objectives and success criteria

### 5.1 Primary objective

Increase **incremental revenue recovered**: money successfully collected that would likely have remained unrecovered without the treatment.

### 5.2 MVP objectives

The MVP must be able to:

- ingest Razorpay-style revenue-risk events;
- normalize events into Recovery Cases;
- prevent duplicate cases through idempotency;
- classify likely root cause;
- estimate recovery probability and Expected Recoverable Revenue;
- prioritize cases in a merchant operations view;
- detect probable systemic payment degradation;
- recommend only registered interventions;
- enforce deterministic policies over AI recommendations;
- schedule and execute bounded actions;
- re-check payment state immediately before action;
- cancel unnecessary outreach after payment success or opt-out;
- keep a complete audit timeline;
- process a synthetic batch and show recovered revenue;
- separate natural recovery from assisted recovery;
- demonstrate safe failure handling and AI fallback.

### 5.3 Primary business metrics

- total revenue at risk;
- estimated recoverable revenue;
- revenue actually recovered;
- incremental revenue recovered;
- recovery rate;
- natural recovery rate;
- treatment recovery rate;
- recovery lift;
- intervention cost and net recovery;
- recovered revenue per intervention cost;
- median time to recovery;
- active cases;
- cases requiring human approval;
- suppressed cases;
- false intervention rate;
- intervention success rate by method, failure type, strategy, and channel.

## 6. Non-objectives and out of scope

The Buildathon MVP will not:

- become a generic conversational assistant;
- execute arbitrary financial actions generated by an LLM;
- store raw card data, CVV, or payment credentials;
- claim access to Razorpay proprietary network-wide data;
- claim production ML accuracy from synthetic data;
- present simulated outreach or degradation as real provider behavior;
- build a full accounts-receivable suite;
- build a full CRM, call-center, or voice recovery system;
- replace payment routing, checkout, or Razorpay Optimizer;
- build dozens of microservices or a large multi-agent framework;
- implement real WhatsApp/voice delivery unless explicitly integrated and labeled;
- provide causal certainty when only observational or synthetic data exists;
- support every payment provider or every country in the MVP.

## 7. Users and personas

### Merchant Operations Manager

Monitors money at risk, causes, active interventions, incidents, and cases requiring attention.

### Founder or Business Owner

Needs a fast view of recovered money, ROI, recovery lift, and whether the system creates measurable value.

### Payments / Fintech Operations

Investigates failure patterns, payment-method health, route degradation, retry outcomes, and webhook health.

### Finance / Accounts Receivable

Manages overdue invoices, promise-to-pay commitments, prioritization, and escalation.

### Customer Support / Account Manager

Needs a concise customer context, case history, recommended next action, and safe contact guidance.

### Technical Administrator

Manages integrations, webhook processing, policy configuration, audit logs, failures, and observability.

## 8. User stories

- As a merchant operator, I can see current revenue at risk, recoverable value, recovered value, and active incidents within five seconds.
- As an operator, I can open a Recovery Case and understand its source, amount, cause, confidence, probability, recommendation, policy result, and full timeline.
- As a payments operator, I can see when many failures form a probable systemic incident and verify that outreach was suppressed.
- As a finance user, I can prioritize overdue invoices by expected value and urgency rather than age alone.
- As a support user, I can see what has already been attempted and avoid contacting a customer who has paid or opted out.
- As an administrator, I can configure limits, quiet hours, approval thresholds, channels, and opt-out behavior.
- As a business owner, I can compare natural recovery with treatment recovery and see an honest, labeled attribution result.
- As a reviewer, I can inspect what data informed an AI recommendation and which deterministic rule allowed or blocked it.

## 9. Product principles

1. **Recovered revenue is the north star.** Activity is not value.
2. **Financial truth is deterministic.** Client state and AI text never establish payment success.
3. **AI is bounded.** It recommends from registered actions; policy code has final authority.
4. **State is explicit.** Recovery Cases use an auditable state machine.
5. **Every action is reversible where possible.** Scheduled outreach can be cancelled before execution.
6. **Check before acting.** Old state is never enough for financial or customer-contact actions.
7. **Restraint is intelligence.** Natural recovery, opt-out, and systemic degradation should suppress unnecessary intervention.
8. **Synthetic data is labeled.** Demonstration results are not represented as live Razorpay results.
9. **Explainability is part of the feature.** Recommendations include reasons, evidence, confidence, and policy results.
10. **Simple architecture first.** The prototype should be compact but production-minded.

## 10. Core domain model: Recovery Case

The primary domain object is `RecoveryCase`, not `Payment`. A case may originate from a payment failure, checkout abandonment, recurring-payment failure, overdue invoice, or an incident-correlated risk event.

Representative fields:

```json
{
  "id": "rc_001",
  "source_type": "payment_failure",
  "source_id": "pay_xyz",
  "merchant_id": "merchant_001",
  "customer_id": "customer_123",
  "amount_at_risk": 249900,
  "currency": "INR",
  "payment_method": "upi",
  "failure_code": "UPI_TIMEOUT",
  "root_cause": "temporary_payment_failure",
  "root_cause_confidence": 0.88,
  "recovery_probability": 0.82,
  "expected_recoverable_amount": 204918,
  "priority_score": 0.89,
  "recommended_action": "send_retry_link",
  "status": "WAITING",
  "attempt_count": 1,
  "max_attempts": 3,
  "recovered_amount": 0,
  "created_at": "...",
  "updated_at": "..."
}
```

All monetary values are integer smallest units. For INR, ₹2,499 is `249900` paise. Currency, amount, and recovered totals must be calculated by deterministic code.

### 10.1 Recovery sources

1. **Failed one-time payment:** e.g. a ₹2,499 UPI timeout.
2. **Checkout abandonment:** checkout started but no successful payment within a configured window.
3. **Subscription or recurring-payment failure:** expired card, insufficient funds, mandate failure, or temporary bank issue.
4. **Overdue B2B invoice:** invoice remains unpaid beyond its due date.
5. **Systemic payment degradation:** a correlated cluster of failures creates shared revenue risk and changes the appropriate action.

### 10.2 Related entities

- `Merchant`: tenant, policies, integration settings, experiments.
- `Customer`: minimal identity and payment-history metadata.
- `RevenueEvent`: normalized incoming event.
- `PaymentSnapshot`: provider state used for deterministic verification.
- `RecoveryCase`: current risk and workflow state.
- `CaseEvidence`: features, source events, incident links, and scoring inputs.
- `Recommendation`: structured AI or deterministic recommendation.
- `PolicyDecision`: allow, block, require approval, schedule, suppress, or stop.
- `RecoveryAction`: attempted communication, retry, link generation, escalation, or wait.
- `Incident`: correlated degradation window and evidence.
- `ExperimentAssignment`: control/treatment assignment and experiment metadata.
- `AttributionRecord`: natural versus assisted recovery classification.
- `AuditEvent`: append-only record of meaningful state and decision changes.
- `ProcessedEvent`: idempotency record for external events.
- `ScheduledJob`: durable future action with deduplication key.

## 11. Lifecycle and state machine

### 11.1 States

`DETECTED`, `ANALYZING`, `ACTION_PENDING`, `POLICY_CHECK`, `SCHEDULED`, `ACTION_EXECUTED`, `WAITING`, `RECOVERED`, `ESCALATED`, `EXHAUSTED`, `CANCELLED`, `OPTED_OUT`, and `SUPPRESSED`.

### 11.2 Typical flow

```text
DETECTED -> ANALYZING -> ACTION_PENDING -> POLICY_CHECK
  -> SCHEDULED -> ACTION_EXECUTED -> WAITING -> RECOVERED
```

Permitted terminal or alternate exits include `ESCALATED`, `EXHAUSTED`, `CANCELLED`, `OPTED_OUT`, and `SUPPRESSED`.

### 11.3 Transition requirements

- Every transition is validated against an explicit transition table.
- Every transition records actor, reason, timestamp, correlation IDs, and prior/new state.
- Payment success can transition an active case to `RECOVERED` from any state where the case is still open, subject to deterministic reconciliation.
- Opt-out can transition an open case to `OPTED_OUT` and must cancel future contact jobs.
- A policy block does not silently discard a case; it records the decision and moves to the appropriate waiting, suppressed, escalated, or exhausted outcome.
- Terminal states must not accept new interventions except an auditable correction/reconciliation flow.

## 12. End-to-end behavioral requirements

For a failed UPI payment, the system should:

1. receive a signed provider-style event;
2. verify its signature;
3. perform idempotency checks;
4. confirm no successful payment for the same order exists;
5. create one Recovery Case;
6. classify the failure and estimate confidence;
7. calculate probability, Expected Recoverable Revenue, and priority;
8. obtain a structured next-best action;
9. pass it through policy evaluation;
10. schedule or execute only the permitted action;
11. re-check current payment/order/case state before contact or retry;
12. observe later success or failure events;
13. cancel future actions after success;
14. mark the case recovered with the correct amount;
15. show the complete timeline and attribution.

The critical race condition is mandatory: if a customer manually retries and pays after a reminder is scheduled but before it executes, the worker must re-check and cancel the reminder. Never send “please complete payment” to a customer who has already paid.

## 13. Root-cause and incident intelligence

### 13.1 Root-cause categories

- temporary UPI or network failure;
- issuing-bank issue;
- insufficient funds;
- expired card;
- authentication or OTP failure;
- mandate failure;
- customer cancellation;
- checkout abandonment;
- systemic payment degradation;
- invalid payment instrument;
- merchant configuration problem;
- unknown or insufficient evidence.

The system must distinguish symptoms from causes. For example, “payment failed” is a symptom; “temporary UPI timeout” or “expired card” guides the strategy.

### 13.2 Systemic degradation detection

The detector correlates event volume and success-rate deviations over configurable windows using payment method, bank, gateway, issuer, error code, merchant, and region where available. A simple MVP detector can use baseline success rate, current rolling success rate, minimum failure count, and confidence thresholds.

Example signal: normal UPI success 94%, current success 49%, 57 correlated failures in five minutes. The result should be a probable incident, not a claim of certainty.

When an incident is active, RecoveryOS should default to `WAIT` or `SUPPRESS_OUTREACH` for affected cases, monitor the window, allow natural retry, and process remaining cases after recovery. Mass outreach during an infrastructure incident is a harmful false intervention.

## 14. Recoverability, priority, and economics

### 14.1 Recovery probability

The MVP may use a transparent deterministic score or a replaceable model adapter using features such as amount, payment method, failure reason, customer history, attempt count, time since failure, checkout engagement, subscription tenure, invoice aging, historical recovery rate, incident status, message opens/clicks, segment, and time of day.

Scores must expose their features and confidence. Synthetic scoring must be labeled as a prototype estimate, not production accuracy.

### 14.2 Expected Recoverable Revenue

```text
Expected Recoverable Revenue = Amount at Risk × Probability of Recovery
Expected Net Recovery = Expected Recoverable Revenue − Expected Intervention Cost
```

Example: ₹10,000 at risk at 60% probability gives ₹6,000 expected recoverable revenue. A ₹50,000 case at 30% can outrank a ₹500 case at 90% because its expected value is ₹15,000 versus ₹450.

### 14.3 Priority

The baseline priority model is:

```text
Priority = Expected Recoverable Revenue
         × Urgency Factor
         × Customer Value Factor
         × Confidence Factor
         − Intervention Cost and Risk Penalties
```

The implementation must normalize factors, preserve calculation inputs, and avoid double-counting money. Priority ranks work; it does not alter financial truth.

## 15. Interventions and bounded autonomy

### 15.1 Registered actions

The initial action registry may include:

`NO_ACTION`, `WAIT`, `RETRY`, `GENERATE_PAYMENT_LINK`, `SEND_EMAIL`, `SEND_SMS`, `SEND_WHATSAPP`, `SUGGEST_ALTERNATE_PAYMENT_METHOD`, `REQUEST_PAYMENT_METHOD_UPDATE`, `SCHEDULE_RETRY`, `NOTIFY_ACCOUNT_MANAGER`, `ESCALATE_TO_HUMAN`, `STOP`, and `CLOSE_CASE`.

AI may select only from this registry and must provide structured parameters validated by schema. It cannot invent tools, payment amounts, recipients, or authorization.

### 15.2 Policy engine

Policy code has final authority. Default MVP policy controls include:

- maximum recovery attempts: 3;
- minimum interval between contacts: 4 hours;
- quiet hours: 21:00–08:00 in merchant timezone;
- stop after verified successful payment;
- stop after customer opt-out;
- human approval for high-value transactions, default threshold ₹50,000;
- explicit consent and policy for voice outreach;
- maximum active sequence duration;
- fallback and rate limits per channel;
- merchant-level and customer-level contact caps;
- no action while a systemic incident suppresses outreach.

Example: the AI recommends WhatsApp, but the policy engine blocks it because the customer was contacted 30 minutes ago. The blocked action and reason remain visible in the timeline.

### 15.3 Human approval

High-value, unusual, low-confidence, or policy-sensitive cases can move to `ESCALATED` or an approval queue. Approval records approver identity, timestamp, decision, reason, and policy version. No silent auto-approval is permitted.

### 15.4 Stopping rules

Stop future actions when payment succeeds, the case is cancelled, the customer opts out, limits are exceeded, the maximum sequence duration expires, or a human resolves the case. Repeated failure eventually produces `EXHAUSTED`.

## 16. AI responsibilities and contracts

### 16.1 AI may assist with

- interpreting root cause from structured evidence;
- selecting a registered strategy;
- generating a concise case summary;
- explaining a recommendation;
- identifying relevant evidence;
- proposing timing or channel within supplied policy bounds.

### 16.2 Deterministic software owns

Payment and order status, webhook verification, idempotency, amounts, currency arithmetic, database mutations, authorization, scheduling, retry limits, quiet hours, opt-outs, state transitions, audit persistence, intervention permissions, totals, reporting, and API success/failure.

### 16.3 Structured recommendation

The AI contract should validate an object similar to:

```json
{
  "action": "WAIT",
  "delay_minutes": 10,
  "reason_code": "TRANSIENT_FAILURE",
  "rationale": "Signals resemble a temporary UPI timeout.",
  "evidence": ["UPI_TIMEOUT", "incident_score_low", "customer_history_positive"],
  "confidence": 0.84,
  "requires_human_approval": false,
  "fallback_action": "GENERATE_PAYMENT_LINK"
}
```

The schema must reject unknown actions, invalid ranges, missing reasons, unsafe free-form financial parameters, and malformed output.

### 16.4 Fallback behavior

If the LLM is unavailable, times out, violates schema, or returns low confidence, the workflow continues with deterministic rules or safely waits/escalates. The product must show that fallback occurred. An AI failure must never bypass policy or create financial truth.

## 17. Data, events, and integrations

### 17.1 Event model

Normalized events should include provider event ID, event type, source object ID, merchant, customer/order references, amount and currency where applicable, payment method, failure code, provider timestamp, received timestamp, signature metadata, and raw payload reference subject to privacy rules.

Core event types include `payment.failed`, `payment.succeeded`, `checkout.started`, `checkout.abandoned`, `subscription.payment_failed`, `invoice.overdue`, `invoice.paid`, `customer.opted_out`, `message.delivered`, `message.opened`, `message.clicked`, `action.failed`, and `incident.detected`/`incident.resolved`.

### 17.2 Razorpay integration posture

Razorpay Test Mode and test webhooks may be real when implemented. Webhook signatures must be verified and events deduplicated. Provider status is authoritative only after server-side verification. Secrets live in environment variables and are never committed.

### 17.3 Integration matrix

| Capability | MVP posture |
|---|---|
| Razorpay test payments | Real where configured |
| Razorpay-style webhook ingestion | Real or local provider-compatible simulator |
| Email | Sandbox/provider abstraction |
| SMS | Simulated or sandbox |
| WhatsApp | Simulated unless an approved sandbox is integrated |
| Voice | Out of scope unless explicitly added |
| Network-wide bank-health telemetry | Synthetic simulator |
| ML trained on Razorpay-wide data | Not available; use transparent synthetic features |

Every demo view must label simulated data and actions clearly.

### 17.4 Idempotency

The ingestion layer stores a unique processed-event key, preferably the provider event ID, with a safe composite fallback. Duplicate `payment.failed` events are no-ops after the first successful processing. Action execution also needs idempotency keys so worker retries do not send duplicate messages or create duplicate payment links.

## 18. Architecture requirements at product level

The PRD intentionally does not prescribe a final framework. The architecture must support these boundaries:

- event ingestion and signature verification;
- normalization and idempotency;
- Recovery Case service and state machine;
- deterministic scoring and economic calculations;
- AI recommendation adapter with schema validation and fallback;
- policy engine;
- durable scheduler/worker;
- provider abstractions for payment, messaging, and links;
- incident detector;
- attribution and metrics service;
- merchant dashboard and case detail APIs;
- append-only audit timeline;
- structured logs and health metrics.

The Buildathon version may be a modular monolith with a durable relational database and background worker. Separate services are justified only when they improve reliability or clarity.

## 19. Required screens and UX

The visual language should be serious fintech operations software: high signal, low clutter, data-rich, readable, and professional. Avoid a generic chatbot layout, excessive gradients, childish illustrations, or decorative AI animation.

### 19.1 Dashboard

Within roughly five seconds, show:

- revenue at risk;
- Expected Recoverable Revenue;
- recovered revenue;
- recovery rate and lift;
- natural versus assisted recovery;
- active cases and cases needing humans;
- current payment incidents;
- intervention cost and net recovery;
- top causes, methods, strategies, and channels.

### 19.2 Recovery Cases list

Filter and sort by status, source, amount, priority, expected value, method, root cause, incident, action, approval requirement, and date. Show why a case is high priority.

### 19.3 Case detail

Show amount and payment truth, source, customer context, root cause and confidence, score inputs, Expected Recoverable Revenue, recommendation, policy decision, scheduled actions, attempts, delivery outcomes, state history, payment events, recovered amount, attribution, and audit timeline.

### 19.4 Incident view

Show baseline versus current payment health, affected volume and amount, correlated dimensions, confidence, suppressed outreach, monitoring status, and resolution.

### 19.5 Experiments and measurement

Show control/treatment counts, assignment, natural recovery, assisted recovery, lift, confidence/limitations, cost, and synthetic-data labeling.

### 19.6 Policies and integrations

Show current policy version, limits, quiet hours, approval thresholds, channel settings, webhook health, worker health, simulator status, and audit history for changes.

## 20. Simulator and demo requirements

The simulator is a first-class Buildathon capability, not a fake claim of production connectivity. It should generate a labeled batch containing successful payments, temporary UPI failures, card failures, abandonments, recurring failures, overdue invoices, opt-outs, duplicates, natural recoveries, treatment recoveries, and a correlated degradation episode.

Preferred five-minute story:

1. Start with a merchant batch.
2. Trigger UPI degradation: baseline 94%, current 49%, affected cases and amount visible.
3. Show diagnosis: probable systemic degradation.
4. Show `WAIT/SUPPRESS_OUTREACH` instead of mass messaging.
5. Resolve the incident and allow natural retries.
6. Process unresolved cases with segmented strategies: fresh UPI retry, alternate method, WhatsApp simulation, and human review.
7. Open one case and demonstrate recommendation, policy check, race-condition recheck, success event, cancellation, recovered status, and audit log.
8. End with batch totals and natural versus agent-assisted recovery.

Example labeled final screen:

```text
Revenue at risk:        ₹3,42,800
Natural recovery:       ₹1,62,400
Agent-assisted recovery:₹1,09,700
Unrecovered:            ₹70,700
```

The exact result is synthetic and must be labeled as such.

## 21. Measurement and attribution

The product must distinguish:

- **natural recovery:** payment completed without an eligible treatment intervention;
- **assisted recovery:** payment completed after a treatment action and within the attribution window;
- **unrecovered:** no qualifying success within the case window;
- **suppressed:** intervention intentionally withheld, often because of incident or opt-out;
- **control/treatment lift:** difference in recovery rate between comparable assigned groups.

Attribution requires deterministic event ordering, a configurable attribution window, experiment assignment before treatment, deduplication, and an audit record. Observational results must be described as measured association; synthetic control/treatment results must be labeled demonstration data.

## 22. Security, privacy, and compliance posture

- Verify webhook signatures.
- Never trust client-provided payment state.
- Validate and sanitize all payloads.
- Use environment variables or a secret manager for credentials.
- Use least-privilege credentials.
- Never store CVV or raw card data.
- Minimize customer PII and redact sensitive fields from logs.
- Authenticate dashboard APIs and enforce merchant-level authorization.
- Protect policy and integration changes with role checks and audit history.
- Ensure messages do not expose hidden payment data.
- Define retention and deletion behavior for customer and event data.

This is fintech-adjacent software; security review is part of Definition of Done even for a prototype.

## 23. Auditability and observability

The system must answer what happened, when, with what inputs, what AI recommended, why, what policy allowed or blocked, what executed, whether it succeeded, whether the customer paid, and how much was recovered.

Structured logs should include `case_id`, `payment_id`, `event_id`, `merchant_id`, and `action_id` when relevant. Track webhook latency/failures, duplicates, case creation, AI latency/errors/fallbacks, worker queue depth, scheduled jobs, execution failures, delivery rates, recovery rates, incident detections, database errors, and API errors.

## 24. Failure handling and resilience

Required behaviors:

- Duplicate webhook: idempotency lookup, safe no-op.
- Customer pays during recovery: success event cancels future work and closes case.
- Worker restart: scheduled jobs survive restart or are reconciled from durable state.
- LLM timeout or invalid output: deterministic fallback, safe wait, or escalation.
- Messaging failure: bounded retry with backoff, optional fallback channel, audit record.
- API rate limit: retry with provider-appropriate backoff and idempotency.
- Database unavailability: fail visibly, avoid silent data loss, preserve retryability.
- Stale job: re-check case, payment, opt-out, policy, and incident state before acting.

## 25. Testing requirements

### Unit tests

State transitions, amount arithmetic, Expected Recoverable Revenue, priority, policy rules, quiet hours, limits, stopping rules, idempotency keys, attribution, and incident thresholds.

### Integration tests

Webhook to case, success to recovered, duplicate webhook, scheduled intervention, policy block, AI fallback, message failure, payment race, opt-out, and worker restart/reconciliation.

### End-to-end scenarios

- failed payment -> wait/retry -> success -> recovered;
- checkout abandonment -> recovery action -> success;
- subscription failure -> update/retry -> success;
- overdue invoice -> promise -> paid;
- degradation -> outreach suppression -> incident resolution -> targeted recovery.

### AI evaluation

Use a fixed synthetic dataset to evaluate root-cause labels, action appropriateness, unsafe recommendations, structured-output validity, confidence calibration, and fallback behavior. Do not present this as production model validation.

## 26. Rollout and implementation roadmap

### Phase 0 — Product and architecture

Complete PRD, architecture, data model, decision records, state machine, event model, API boundaries, AI contracts, policy model, and real/simulated integration matrix.

### Phase 1 — Core recovery engine

Implement database, ingestion, normalization, cases, state machine, idempotency, audit timeline, deterministic rules, and simulator. No dependency on fancy AI.

### Phase 2 — Intelligence layer

Add root-cause analysis, probability, Expected Recoverable Revenue, priority, structured recommendations, explanations, and fallbacks.

### Phase 3 — Recovery execution

Add policy evaluation, durable scheduled actions, payment links/retry paths, communications abstraction, approval queue, stopping rules, and success handling.

### Phase 4 — Incident and measurement

Add degradation detection, experiments, control/treatment assignment, attribution, recovery metrics, and dashboard views.

### Phase 5 — Hardening and demo

Complete resilience, observability, security review, tests, UX polish, deployment, README, architecture diagram, demo dataset, and five-minute demo flow.

If time is limited, protect: event ingestion, Recovery Case, state machine, idempotency, root cause, scoring, Expected Recoverable Revenue, recommendation, policy engine, scheduling, success cancellation, audit trail, batch simulator, recovered revenue dashboard, and degradation demo.

## 27. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Duplicate events create duplicate cases | Provider event idempotency and unique constraints |
| Reminder sent after payment | Last-mile server-side state recheck and cancellation |
| AI suggests unsafe action | Registered action schema plus deterministic policy engine |
| System incident causes message flood | Correlation detector and suppression state |
| Synthetic scores look falsely authoritative | Feature transparency, confidence, and explicit labels |
| Recovery counted twice | Provider payment identity, reconciliation, and immutable attribution rules |
| Messaging provider failure | Bounded retries, fallback, and visible delivery state |
| Worker crash loses scheduled work | Durable jobs and startup reconciliation |
| PII or secrets leak | Minimal storage, redaction, environment secrets, access control |
| Architecture becomes overbuilt | Modular monolith first; justify infrastructure additions |
| Dashboard shows activity but not value | Lead with recovered revenue, lift, cost, and case outcomes |

## 28. Open questions for architecture review

1. What application stack and database should the implementation use?
2. Will Razorpay Test Mode be integrated in the first demo or will the simulator be the primary source?
3. Which communication channels are simulated versus sandbox-integrated?
4. What merchant timezone and default policy values should be used?
5. What attribution window and control/treatment assignment rules are appropriate for the demo?
6. What minimum authentication and tenant model is required for the Buildathon deployment?
7. Which AI provider/model and structured-output mechanism will be used?
8. What is the smallest durable scheduling mechanism that survives restart?
9. Which screens are required for the first vertical slice?
10. What exact synthetic dataset and expected final totals will be used for judging?

## 29. Definition of Done

### Product

Clear problem, differentiated solution, visible value, understandable case decisions, and honest synthetic-data labeling.

### Backend

Reliable event handling, explicit case state machine, idempotency, scheduling, policies, audit, reconciliation, and failure handling.

### AI

Justified use, constrained actions, structured outputs, explanations, confidence, deterministic fallback, and evaluation.

### Financial correctness

Server-verified payment state, integer monetary arithmetic, duplicate prevention, correct recovered totals, and natural/assisted separation.

### Frontend

Polished dashboard, case detail, incident display, policy display, and experiment/measurement views.

### Testing and resilience

Core unit/integration/end-to-end tests pass; duplicate webhook, AI failure, message failure, worker restart, incident suppression, opt-out, and payment-race scenarios work safely.

### Documentation and Buildathon

PRD, architecture, setup, README, assumptions, architecture diagram, demo instructions, a reproducible batch result, and a clear five-minute story exist.

## 30. Future roadmap

After the MVP, RecoveryOS can add real provider adapters, merchant-configurable strategy experimentation, richer invoice and promise-to-pay workflows, calibrated production models, multi-currency support, improved causal measurement, provider health feeds, role-based approvals, regional compliance controls, and deeper integration with Razorpay payments, checkout, links, subscriptions, messaging, analytics, and Optimizer.

## 31. Glossary

- **Revenue at Risk:** money associated with an event that may remain uncollected.
- **Recovery Case:** unified workflow object representing one revenue-risk situation.
- **Expected Recoverable Revenue:** amount at risk multiplied by recovery probability.
- **Recovery Probability:** estimated likelihood of successful recovery under the available evidence and strategy.
- **Next-Best Action:** approved registered intervention selected for a case.
- **Policy Engine:** deterministic authority that allows, blocks, schedules, suppresses, or escalates actions.
- **Natural Recovery:** payment recovered without an eligible treatment intervention.
- **Assisted Recovery:** payment recovered after a qualifying intervention.
- **Incident:** correlated systemic degradation affecting payment outcomes.
- **Idempotency:** safe handling of duplicate events or retries without duplicate financial effects.
- **Treatment / Control:** intervention group and comparison group used to estimate recovery lift.
- **Incremental Revenue Recovered:** recovery attributable to treatment above the expected counterfactual baseline.

## 32. Product statement

Everything implemented in RecoveryOS should support this sentence:

> RecoveryOS finds revenue that is slipping away, understands why it is at risk, determines whether and how it should be recovered, executes the safest permitted intervention, adapts to the result, and proves how much incremental money it brought back.

## 33. MVP / Stretch / Future capability matrix

This matrix is the scope boundary for v1.0. A capability classified as Stretch or Future must not block the first vertical slice. Out-of-scope capabilities must not be implied by UI copy or demo claims.

| Capability | Classification | v1.0 boundary |
|---|---|---|
| Failed one-time payment recovery | MVP | End-to-end first vertical slice |
| Checkout abandonment | MVP | Ingest, case, simulate bounded recovery |
| Subscription failure | MVP | Billing-cycle case and retry/update strategy |
| Overdue invoice recovery | MVP | Case, aging, escalation, simulated payment |
| Systemic payment degradation | MVP | Configurable detector and outreach suppression |
| Recovery Case lifecycle | MVP | Explicit state machine and audit |
| Root-cause analysis | MVP | Explainable rules with AI adapter |
| Recovery probability | MVP | Deterministic v1 scorer behind replaceable interface |
| Expected Recoverable Revenue | MVP | Deterministic integer arithmetic |
| Priority scoring | MVP | Configurable v1 formula |
| AI recommendation | MVP | Structured, registered actions only |
| Policy engine | MVP | Deterministic precedence and audit |
| Scheduled interventions | MVP | Durable/reconstructable jobs and recheck |
| Payment links | MVP | Provider abstraction; sandbox/simulator acceptable |
| Email | MVP | Provider abstraction; simulated delivery acceptable |
| SMS | Stretch | Adapter and simulation if time permits |
| WhatsApp | Stretch | Simulated channel unless approved sandbox exists |
| Voice | Out of Scope | No voice workflow in MVP |
| Human approval | MVP | Queue for high-value or policy-sensitive actions |
| Audit timeline | MVP | Append-only business-event history |
| Experiments | Stretch | Basic assignment and reporting |
| Control/treatment | Stretch | Required if experiments are demonstrated |
| Attribution | MVP | Case-level natural/assisted classification |
| Multi-provider payments | Future | Razorpay-style provider plus simulator first |
| ML-based recovery scoring | Future | Replaceable interface only; no production model claim |
| Role-based access | MVP | Viewer, Operator, Admin lightweight roles |
| Merchant-configurable policies | MVP | Typed persisted policy with safe defaults |
| Production provider-health feeds | Future | Synthetic health signals for Buildathon |

## 34. Formal functional requirements

The following requirements are normative. `MUST` is required for MVP correctness; `SHOULD` is expected unless an approved trade-off is recorded; `MAY` is optional.

### Event ingestion and normalization

- **FR-001:** The system MUST accept provider-style revenue-risk events through a validated ingestion boundary.
- **FR-002:** The system MUST verify webhook signatures before creating or mutating domain records.
- **FR-003:** The system MUST reject malformed, incomplete, unsupported, or unauthorized events without a domain mutation.
- **FR-004:** The system MUST normalize provider-specific payloads into a canonical event model.
- **FR-005:** The system MUST persist an idempotency key for each accepted external event.
- **FR-006:** Duplicate external events MUST produce no duplicate domain effect.
- **FR-007:** Each event and downstream operation MUST retain correlation identifiers where available.
- **FR-008:** The system SHOULD expose receipt, validation, processing, and failure status for operational diagnosis.

### Recovery Cases and financial obligations

- **FR-009:** The system MUST create or associate a Recovery Case for each eligible recoverable business obligation.
- **FR-010:** A Recovery Case MUST represent one obligation, not one webhook or one payment attempt.
- **FR-011:** Multiple payment attempts for the same order or invoice MUST be associated with one case unless an explicit business rule creates a new obligation.
- **FR-012:** Each case MUST retain source type, source identity, merchant, customer, amount, currency, and source-event references.
- **FR-013:** Cases MUST use the explicit state machine and reject illegal transitions.
- **FR-014:** Terminal cases MUST not receive customer-facing actions except through documented reconciliation/correction flows.
- **FR-015:** A verified payment success event MUST reconcile all relevant open cases and close the applicable case as recovered.
- **FR-016:** The system MUST preserve a history of attempts, actions, state changes, and payment outcomes.

### Financial truth

- **FR-017:** Payment and order status MUST be established from an authoritative server-side provider or verified simulator source.
- **FR-018:** Monetary values MUST be stored and calculated as integer smallest currency units.
- **FR-019:** The system MUST prevent the same obligation or success event from being counted twice.
- **FR-020:** Recovered amount MUST be reconciled to authoritative payment success and MUST NOT be inferred from message delivery.
- **FR-021:** Financial reporting MUST distinguish revenue at risk, recovered revenue, natural recovery, assisted recovery, and unrecovered amounts.

### Intelligence and incident detection

- **FR-022:** The system MUST classify a probable root cause or explicitly return unknown/insufficient evidence.
- **FR-023:** The system MUST calculate recovery probability using a versioned, explainable v1 scoring engine.
- **FR-024:** The system MUST calculate Expected Recoverable Revenue as amount at risk multiplied by probability, using deterministic arithmetic.
- **FR-025:** The system MUST calculate a versioned priority score from expected value, urgency, customer value, confidence, cost, and risk inputs.
- **FR-026:** Score outputs MUST include the score version, input features, confidence, and explanation.
- **FR-027:** The system MUST detect probable systemic degradation from configurable rolling-window signals.
- **FR-028:** Cases MAY reference an Incident, but an Incident MUST NOT create an additional revenue obligation or duplicate financial total.
- **FR-029:** AI recommendations MUST use schema-validated structured output and registered action types only.
- **FR-030:** AI failure, timeout, invalid output, or low confidence MUST invoke a deterministic fallback or safe wait/escalation.

### Policies and bounded autonomy

- **FR-031:** Every proposed intervention MUST pass through the deterministic policy engine before execution.
- **FR-032:** Policy evaluation MUST use the documented precedence order and MUST override AI recommendations.
- **FR-033:** The policy engine MUST enforce contact caps, minimum intervals, quiet hours, channel availability, incident suppression, approval thresholds, and stopping rules.
- **FR-034:** Customer opt-out MUST prevent future applicable customer contact and be auditable.
- **FR-035:** High-value or otherwise configured cases MUST require human approval before execution.
- **FR-036:** Policy decisions MUST record result, rule, policy version, inputs, actor, and reason.

### Execution and scheduling

- **FR-037:** Scheduled actions MUST be durable or reconstructable after worker restart.
- **FR-038:** A worker MUST re-check authoritative payment, order, case, opt-out, incident, and policy state immediately before executing a customer-facing action.
- **FR-039:** Action execution MUST use an idempotency key and prevent duplicate external effects during worker retries.
- **FR-040:** Provider failures MUST be classified as retryable or terminal and handled with bounded retry/backoff behavior.
- **FR-041:** The system MUST support cancelling scheduled actions after payment success, opt-out, terminal state, suppression, or human resolution.
- **FR-042:** Every action attempt MUST expose execution, delivery, failure, cancellation, and retry status.

### Measurement and attribution

- **FR-043:** The system MUST assign each eligible case to control or treatment before treatment execution when an experiment is active.
- **FR-044:** The system MUST classify case outcomes as `NATURAL_RECOVERY`, `ASSISTED_RECOVERY`, `UNRECOVERED`, or `SUPPRESSED` where applicable.
- **FR-045:** Attribution MUST use a configured case-level attribution window and deterministic event ordering.
- **FR-046:** Duplicate success events MUST not change attribution or recovered totals after reconciliation.
- **FR-047:** Refunds or reversals, where supported, MUST be represented as a subsequent financial adjustment rather than silently ignored.
- **FR-048:** Reporting MUST expose intervention cost, recovery rate, treatment/control recovery, and measured lift with limitations.

### UX, access, and operations

- **FR-049:** The dashboard MUST show revenue at risk, Expected Recoverable Revenue, recovered revenue, natural/assisted recovery, incidents, and human actions required.
- **FR-050:** Case detail MUST show source, financial truth, diagnosis, scoring evidence, recommendation, policy decision, actions, outcomes, and timeline.
- **FR-051:** The product MUST provide incident, experiments/measurement, policies, integrations, and system-health views or equivalent operational surfaces.
- **FR-052:** The product MUST show understandable loading, empty, degraded, unavailable, stale, and error states.
- **FR-053:** Viewer, Operator, and Admin roles MUST be enforced at the API boundary for their documented permissions.
- **FR-054:** The system MUST audit manual retries, approvals, policy changes, integration changes, simulator runs, and access-sensitive operations.

## 35. Testable MVP acceptance criteria

These scenarios are intended to become automated tests.

### Duplicate webhook

**GIVEN** the same external payment-failure event arrives multiple times  
**WHEN** events are processed  
**THEN** only one logical case/attempt effect occurs  
**AND** only one recoverable obligation is counted  
**AND** duplicate handling is visible in logs or audit data.

### Payment race

**GIVEN** a customer-facing recovery action is scheduled  
**AND** the customer pays before execution  
**WHEN** the worker begins processing the job  
**THEN** authoritative payment state is re-checked  
**AND** the action is cancelled  
**AND** no recovery message is sent  
**AND** the case becomes `RECOVERED`.

### AI policy conflict

**GIVEN** AI recommends an action  
**AND** deterministic policy forbids it  
**WHEN** policy evaluation occurs  
**THEN** the action is not executed  
**AND** the policy decision and reason are audited  
**AND** the case follows the configured block, schedule, suppress, or escalation outcome.

### Opt-out

**GIVEN** a customer opts out  
**WHEN** an active case has future customer-contact jobs  
**THEN** all applicable future outreach is cancelled  
**AND** the case enters the correct terminal or suppressed state  
**AND** future workers cannot send customer contact.

### Incident suppression

**GIVEN** correlated failures exceed configured incident thresholds  
**WHEN** degradation is detected  
**THEN** affected cases are suppressed or delayed  
**AND** suppression is visible in the case timeline and incident view  
**AND** the incident itself is not added to revenue totals.

### AI failure

**GIVEN** the LLM times out or returns invalid output  
**WHEN** a decision is required  
**THEN** deterministic fallback executes or the case safely waits/escalates  
**AND** no policy is bypassed  
**AND** the fallback is observable.

### Duplicate action execution

**GIVEN** a worker retries the same action job  
**WHEN** the action has already succeeded  
**THEN** the external customer-facing effect occurs only once  
**AND** the retry is recorded as an idempotent no-op.

### Financial arithmetic

**GIVEN** amount at risk is stored in smallest units and probability is within 0–1  
**WHEN** expected recovery is calculated  
**THEN** deterministic integer-safe arithmetic is used  
**AND** rounding behavior is documented  
**AND** priority calculation cannot change financial totals.

### Natural versus assisted recovery

**GIVEN** an eligible case is assigned to control or treatment  
**WHEN** a verified success arrives inside or outside the configured attribution window  
**THEN** the outcome is classified according to case-level attribution rules  
**AND** duplicate success events do not alter the result.

## 36. Recovery Case Identity & Deduplication Rules

> A Recovery Case represents one recoverable business obligation, not one webhook or one payment attempt.

### Order payment

The conceptual identity is `(merchant_id, order_id, obligation_scope)`. Multiple attempts for an unpaid order normally belong to one case. For example, an order with failed UPI, failed card, and successful UPI attempts has one Recovery Case with three attempts and one recovered obligation. A new independent order or explicitly split obligation creates a new identity.

### Checkout abandonment

The conceptual identity is `(merchant_id, checkout_intent_id)` or a stable order/session intent identity. Repeated events for one abandoned checkout are one case. A new independent checkout intent or order may create a new case.

### Subscription

The conceptual identity is `(merchant_id, subscription_id, billing_cycle_or_invoice_id)`. Each billing cycle/invoice is one recoverable obligation. A later cycle is a new case even if the previous cycle was exhausted.

### B2B invoice

The conceptual identity is `(merchant_id, invoice_id)`. One invoice is one case unless a documented business rule explicitly splits the invoice into independent obligations.

### Incident association

An Incident has its own identity, such as `(merchant_id, detector_dimension_set, incident_window)`. Cases reference an Incident through an association table or equivalent. The Incident is never itself a payment obligation and is never included in revenue-at-risk totals.

### Uniqueness and double-count prevention

The persistence design MUST enforce uniqueness for provider event identity and logical obligation identity. Case creation must be transactionally safe under concurrent events. Attempts and events are child records of the case. Reconciliation must resolve cases against provider payment/order identity, not message count, AI recommendation count, or incident count.

## 37. State transition matrix

The following matrix is the product-level contract. Side effects and audit events are mandatory unless marked optional. `Illegal` means the transition must be rejected without a domain mutation.

| Current state | Trigger/event | Guard conditions | Next state | Side effects | Audit event | Legal / illegal |
|---|---|---|---|---|---|---|
| none | eligible normalized event | obligation identity is new | DETECTED | create case and evidence | `CASE_CREATED` | Legal |
| DETECTED | analysis begins | case is open | ANALYZING | load evidence | `ANALYSIS_STARTED` | Legal |
| ANALYZING | scoring/recommendation ready | valid result or fallback | ACTION_PENDING | persist score and recommendation | `RECOMMENDATION_READY` | Legal |
| ACTION_PENDING | policy evaluation begins | case still open | POLICY_CHECK | snapshot policy context | `POLICY_CHECK_STARTED` | Legal |
| POLICY_CHECK | policy allows future action | no stop guard; schedule valid | SCHEDULED | persist idempotent job | `ACTION_SCHEDULED` | Legal |
| POLICY_CHECK | policy allows immediate action | no stop guard | ACTION_EXECUTED | execute once | `ACTION_EXECUTION_STARTED` | Legal |
| POLICY_CHECK | policy requires approval | approval configured | ESCALATED | create approval task | `APPROVAL_REQUIRED` | Legal |
| POLICY_CHECK | incident suppression | active incident applies | SUPPRESSED or WAITING | cancel/delay outreach | `OUTREACH_SUPPRESSED` | Legal |
| POLICY_CHECK | policy blocks | block is explainable | WAITING, ESCALATED, or EXHAUSTED | no customer effect | `ACTION_BLOCKED` | Legal |
| SCHEDULED | job becomes due | recheck passes | ACTION_EXECUTED | perform idempotent action | `ACTION_EXECUTED` | Legal |
| SCHEDULED | job becomes due | payment succeeded or case terminal | RECOVERED or terminal state | cancel job; no outreach | `STALE_ACTION_CANCELLED` | Legal |
| ACTION_EXECUTED | provider succeeds | effect recorded once | WAITING | schedule observation/recheck | `ACTION_SUCCEEDED` | Legal |
| ACTION_EXECUTED | provider fails | retryable failure and attempts remain | WAITING or SCHEDULED | bounded retry/backoff | `ACTION_FAILED_RETRYABLE` | Legal |
| ACTION_EXECUTED | provider fails | terminal failure or limit reached | EXHAUSTED or ESCALATED | stop or escalate | `ACTION_FAILED_TERMINAL` | Legal |
| WAITING | verified payment success | payment reconciles to obligation | RECOVERED | cancel future jobs; record amount | `CASE_RECOVERED` | Legal |
| any open state | verified payment success | obligation still open | RECOVERED | reconcile and stop | `CASE_RECOVERED` | Legal, high priority |
| any open state | customer opt-out | opt-out is valid | OPTED_OUT | cancel customer contact | `CUSTOMER_OPTED_OUT` | Legal |
| any open state | merchant cancellation | authorized actor | CANCELLED | cancel jobs | `CASE_CANCELLED` | Legal |
| any open state | incident detector | suppression configured | SUPPRESSED | cancel/delay outreach | `CASE_SUPPRESSED` | Legal |
| any open state | maximum attempts/window reached | exhaustion rule applies | EXHAUSTED | stop actions | `CASE_EXHAUSTED` | Legal |
| RECOVERED / OPTED_OUT / CANCELLED / EXHAUSTED | customer-facing action | no reconciliation correction | none | no effect | `ILLEGAL_ACTION_REJECTED` | Illegal |
| terminal state | new failure event | new independent obligation proven | new case | create separate case | `NEW_CASE_CREATED` | Legal only as new case |
| any state | arbitrary transition | guard not satisfied | unchanged | no effect | `ILLEGAL_TRANSITION_REJECTED` | Illegal |

Payment success is a high-priority reconciliation event. Customer-facing actions are forbidden from `RECOVERED`, `OPTED_OUT`, `CANCELLED`, and `EXHAUSTED` unless a separately authorized, documented correction flow is used.

## 38. Deterministic policy precedence

Policy evaluation MUST apply the following order and stop at the first decisive result:

1. Authoritatively successful payment → `STOP`.
2. Customer opted out → `STOP`.
3. Case is terminal → `STOP`.
4. Duplicate, invalid, or stale case/action → `STOP`.
5. Systemic incident suppression → `SUPPRESS` or `WAIT`.
6. Merchant/customer contact limit → `BLOCK` or `SCHEDULE`.
7. Minimum contact interval → `SCHEDULE`.
8. Quiet hours → `SCHEDULE`.
9. Human approval threshold → `REQUIRE_APPROVAL`.
10. Channel unavailable → configured `FALLBACK`/`BLOCK`.
11. Normal policy conditions → `ALLOW`.

The externally visible policy result enum is `ALLOW`, `BLOCK`, `SCHEDULE`, `SUPPRESS`, `REQUIRE_APPROVAL`, or `STOP`. AI never overrides policy precedence. Every result includes the first decisive rule and the policy version.

## 39. Recovery Probability v1

The MVP MUST implement a deterministic scorer behind a `RecoveryProbabilityProvider`-style interface. An ML model may replace it later without changing the case or policy contract. The LLM must not invent the probability.

The following are illustrative Buildathon defaults and MUST be typed configuration, not scattered source constants. The final values belong in architecture/configuration documentation and seeded demo settings.

| Component | Configurable v1 behavior |
|---|---|
| Base probability | Configured per source type or global default |
| Temporary timeout | Positive adjustment when recent and no active incident |
| Previous customer success | Positive adjustment based on configured history band |
| Recent activity/link click | Positive adjustment when evidence exists |
| Repeated failures | Negative adjustment per configured attempt band |
| Insufficient funds | Negative adjustment; may favor alternate timing/method |
| Expired card | Negative adjustment; favors payment-method update |
| Active systemic incident | Negative adjustment and may suppress action |
| Subscription tenure | Configured segment adjustment |
| Invoice aging | Configured urgency/recoverability adjustment |

Each feature has a documented range, adjustment, and missing-data behavior. Missing data uses a neutral adjustment unless policy says the case requires review. The final score is clamped to `[0,1]`, confidence is separately calculated from evidence completeness, and the result includes `scoring_version`, features, adjustments, final probability, confidence, and explanation. These are synthetic Buildathon coefficients, not Razorpay-derived statistics.

## 40. Priority Score v1

Priority is a work-ordering score only; it MUST never modify amount at risk, recovered amount, or any financial total.

```text
priority_raw = expected_recoverable_revenue
             × urgency_factor
             × customer_value_factor
             × confidence_factor
             − cost_penalty
             − risk_penalty
```

Factors are normalized to configured non-negative ranges, with score weights, penalties, and clamp maximum supplied by typed configuration. Missing non-financial features use neutral configured values and reduce confidence where appropriate. The result includes `priority_version`, factor inputs, weights, penalties, and final clamped score. Ties are broken deterministically by expected recoverable amount, then case creation time, then case ID.

## 41. Systemic Incident Detection v1

The Buildathon detector compares a configurable current rolling window with a configurable baseline window. A reasonable seeded demo may use a current five-minute window and previous sixty-minute baseline, but these values MUST come from configuration.

Required configurable inputs:

- baseline window and current rolling window;
- minimum payment-attempt count;
- minimum failure count;
- minimum success-rate degradation;
- correlation dimensions such as method, bank, gateway, issuer, error code, merchant, and region;
- incident-open confidence threshold;
- incident-resolved success threshold;
- cooldown/recovery window.

An incident opens only when sample and degradation thresholds are met for a correlation group. Confidence combines sample sufficiency and signal strength. It resolves when success returns above the configured resolution threshold for the configured recovery window, then enters cooldown to avoid flapping. Cases retain their individual financial identity while referencing the incident. Exact thresholds are configuration, not source-code constants.

## 42. Attribution v1

MVP attribution is case-level and uses the following outcome vocabulary:

- `NATURAL_RECOVERY`: verified success without a qualifying treatment action;
- `ASSISTED_RECOVERY`: verified success after a qualifying treatment action within the configured window;
- `UNRECOVERED`: no qualifying success by case expiry;
- `SUPPRESSED`: intervention intentionally withheld or delayed under policy/incident rules;
- `CONTROL`: eligible case assigned to comparison experience;
- `TREATMENT`: eligible case assigned to intervention experience.

Assignment occurs before treatment execution and is persisted immutably for the case. The attribution window is configurable. A qualifying treatment is an executed, non-blocked action with a recorded idempotency key. Event ordering uses provider event time with received-time tie-breaking and reconciliation rules. Multiple interventions remain one case outcome; the timeline records all interventions but MVP does not attempt multi-touch credit allocation. Duplicate success events are no-ops. Refunds or reversals create an adjustment and can change net recovered reporting according to documented reconciliation rules.

Attribution is a measured product metric and does not automatically establish rigorous causal proof. Control/treatment lift must be reported with sample size and limitations.

## 43. Lightweight roles and permissions

| Permission | Viewer | Operator | Admin |
|---|---:|---:|---:|
| View dashboards, cases, incidents, analytics | Yes | Yes | Yes |
| View permitted customer information | Yes | Yes | Yes |
| Manually retry or schedule permitted action | No | Yes | Yes |
| Execute intervention outside normal automation | No | Configured | Yes |
| Approve high-value action/escalation | No | No | Yes |
| Modify merchant policy | No | No | Yes |
| Manage integrations/secrets configuration | No | No | Yes |
| Run simulator/demo batch | No | Configured | Yes |
| View audit logs | Limited | Yes | Yes |

Authorization is enforced server-side and is merchant-scoped. MVP does not require an enterprise permission-builder; the three roles and explicit operation checks are sufficient.

## 44. Non-functional requirements

- **NFR-001:** Currency arithmetic MUST avoid floating point and use integer smallest units.
- **NFR-002:** Duplicate external events MUST NOT duplicate business effects or recovered revenue.
- **NFR-003:** Duplicate worker execution MUST NOT duplicate outbound customer effects.
- **NFR-004:** Scheduled work MUST survive restart or be reconstructable from durable state.
- **NFR-005:** Every state transition, policy decision, action, and financial reconciliation MUST be auditable.
- **NFR-006:** Validated webhook requests SHOULD be acknowledged quickly enough to avoid provider retry storms; processing MAY be asynchronous.
- **NFR-007:** Common dashboard queries MUST remain responsive for the seeded demo dataset; target p95 is configurable and must be recorded by implementation.
- **NFR-008:** AI calls MUST have a configured timeout, schema validation, retry policy, and fallback.
- **NFR-009:** Invalid signatures MUST cause no domain mutation.
- **NFR-010:** Secrets MUST never enter source control or structured logs.
- **NFR-011:** Sensitive fields MUST be minimized and redacted from logs.
- **NFR-012:** Every request, job, event, and action SHOULD carry correlation IDs.
- **NFR-013:** Merchant authorization MUST be enforced at the API/application boundary.
- **NFR-014:** Modules MUST have typed interfaces, consistent errors, and no duplicated business rules.
- **NFR-015:** Worker health, webhook health, integration health, AI fallback, and action failures MUST be observable.
- **NFR-016:** The application MUST fail fast on invalid mandatory configuration.
- **NFR-017:** Provider-specific errors MUST be mapped to safe user-facing error categories.
- **NFR-018:** Simulator outputs MUST be reproducible from a configured seed and MUST be labeled synthetic.

## 45. Engineering Standards & Company-Style Development Constraints

RecoveryOS must be implemented as if reviewed by a serious fintech engineering organization. These are product constraints on implementation quality and are intentionally stack-neutral until `ARCHITECTURE.md` is approved.

### Existing-code-first rule

Before implementation, the agent MUST inspect the complete repository, current stack, package manager, lint/format rules, test framework, naming conventions, environment/configuration approach, CI/CD, deployment, README, and existing architecture. Coherent repository standards take precedence. If greenfield, the standards and final tree MUST be defined in `ARCHITECTURE.md` before large-scale implementation.

### Coherent stack rule

Use one coherent backend approach, one primary persistence approach, one queue/scheduler approach, and one frontend state approach unless a documented technical reason justifies otherwise. Do not mix Python and Node backends, multiple ORMs, multiple queue systems, framework switches, duplicate libraries, or microservices solely for appearance. Optimize for maintainability, type safety, testing, Razorpay integration, async jobs, structured validation, and deployment simplicity.

### Domain-oriented repository rule

The approved implementation tree must separate configuration, domain models, application services, integrations, API/controllers, persistence, workers/jobs, AI adapters, policy, incident detection, scoring, experiments, audit, simulator, shared utilities, and tests as appropriate. No giant utility dumping ground, giant route/controller, UI-owned payment logic, webhook-owned business logic, duplicated policy, or scattered prompts.

### Zero business-critical hardcoding rule

Business-critical and environment-specific values MUST come from typed configuration, environment variables, persisted merchant policy, or explicit experiment overrides. This includes maximum attempts, contact intervals, quiet hours, approval thresholds, contact caps, sequence duration, channels, retry/backoff, incident windows and thresholds, scoring coefficients and weights, attribution windows and ratios, provider IDs and URLs, secrets, ports, database/queue URLs, model names, AI timeouts, logging/environment settings, merchant timezone, feature flags, simulator seed, distributions, and incident parameters.

Structural enums such as `RECOVERED`, `WAIT`, `ALLOW`, and event types may be source-defined. Mutable rules may not be duplicated as magic numbers or strings in business logic. Deterministic behavior is required; hidden hardcoding is not.

### Configuration hierarchy and validation

Conceptual precedence is: safe structural defaults, environment configuration, merchant database policy, explicit experiment override, and per-case computed context. Secrets come only from secure environment/secret-management mechanisms. Configuration is typed and validated at startup: durations are positive, timezones valid, probabilities in `[0,1]`, amounts non-negative, actions/channels known, and mandatory values present. Invalid mandatory configuration fails fast.

### Demo integrity

Demo totals MUST be computed from seeded synthetic events and actual workflow results. Fixed values such as `recoveredRevenue = 109700` are prohibited. Demo-only behavior must be explicit through configuration/feature flags and visibly labeled as synthetic, simulated, sandbox, or Razorpay Test Mode. AI recommendations and deterministic fallback must use the same schema and policy path; cases must not be mapped directly to predetermined UI text.

### Engineering quality

Use small focused modules, typed domain models, explicit interfaces, pure functions for calculations, dependency injection where useful, centralized configuration, clear naming, minimal side effects, versioned migrations, structured logging, and consistent error categories such as validation, authorization, integration, retryable integration, policy, state-transition, and configuration errors. Do not expose raw provider errors to users.

### Provider adapters

External systems MUST sit behind interfaces such as `PaymentProvider`, `MessagingProvider`, `AIProvider`, and `JobScheduler`. Razorpay-specific behavior belongs primarily in its adapter. The domain consumes normalized events. Simulator and test providers must implement the same contracts without masquerading as Razorpay.

### Database, testing, and documentation discipline

Schema changes MUST use versioned migrations with constraints and indexes supporting identity/idempotency. Business logic changes require deterministic tests around money, case identity, transitions, idempotency, policy precedence, scheduling, race conditions, scoring, incidents, attribution, and fallback. Major decisions belong in `ARCHITECTURE.md`, `DATA_MODEL.md`, `DECISIONS.md`/ADRs, or the README according to their purpose.

## 46. Assumptions and constraints

| Assumption | Status / constraint |
|---|---|
| Buildathon timeline | OPEN: confirm schedule; scope protects first vertical slice |
| Primary currency | INR; multi-currency is Future |
| Default merchant timezone | OPEN: configure per merchant; provide a documented demo default |
| Demo tenants | OPEN: expected one primary demo tenant unless architecture review chooses otherwise |
| Demo transaction volume | OPEN: seeded, demo-scale, and configurable |
| Razorpay integration | Razorpay Test Mode where configured; simulator remains reproducible |
| Provider-health signals | Synthetic for Buildathon; no proprietary network data |
| Messaging | Simulated/sandbox unless a real approved adapter exists |
| Voice | Out of Scope |
| Browser support | OPEN: current mainstream desktop browser for demo |
| Deployment | OPEN: choose after repository/stack inspection and architecture review |
| ML claims | No production accuracy claim; v1 scorer is transparent synthetic logic |
| Secrets and PII | Never committed; minimal storage and redacted logs |

## 47. First vertical slice

The first implementation slice is fixed as:

```text
Failed UPI payment
 -> signed event ingestion
 -> validation and idempotency
 -> one Recovery Case with one/more attempts
 -> root cause
 -> deterministic probability
 -> Expected Recoverable Revenue
 -> priority
 -> structured recommendation
 -> policy evaluation
 -> durable scheduled action
 -> authoritative pre-action recheck
 -> payment success
 -> action cancellation
 -> RECOVERED
 -> audit timeline
 -> dashboard update
```

Invoices, advanced subscriptions, experiments, and decorative dashboard features must not block this vertical slice.

## 48. Deterministic demo dataset specification

The simulator MUST accept a configured seed and generate outputs by running the same event, policy, worker, and reconciliation paths as the application. The dataset specification MUST include:

- seed;
- merchant count;
- transaction/case count;
- success and at-risk counts;
- failure distribution;
- payment-method distribution;
- incident period and correlation dimensions;
- duplicate events;
- opt-outs;
- high-value approval cases;
- natural recoveries;
- treatment recoveries;
- unrecoverable cases;
- simulated delivery/provider failures.

Exact final dashboard totals are intentionally not specified here. They must be derived from execution and displayed with a synthetic-data label.

## 49. UX loading, empty, degraded, and error states

The product MUST provide understandable states for:

- initial loading;
- no cases/data;
- simulator never run;
- Razorpay disconnected;
- invalid webhook configuration;
- worker unhealthy or stale;
- AI unavailable or fallback active;
- messaging unavailable;
- no active incidents;
- no approvals pending;
- case not found;
- payment verification temporarily unavailable;
- failed action and retry status;
- stale recommendation requiring re-analysis;
- partial dashboard data or reporting delay.

Errors must explain what the operator can do next without exposing raw provider errors or secrets.

## 50. Architecture Handoff Checklist

Before `ARCHITECTURE.md` begins, confirm:

- [ ] MVP feature matrix frozen
- [ ] Functional requirements frozen
- [ ] Acceptance criteria reviewed
- [ ] Recovery Case identity frozen
- [ ] State transition matrix frozen
- [ ] Policy precedence frozen
- [ ] Recovery Probability v1 frozen
- [ ] Priority v1 frozen
- [ ] Incident Detection v1 frozen
- [ ] Attribution v1 frozen
- [ ] Role model frozen
- [ ] NFRs accepted
- [ ] Hardcoding/configuration rules accepted
- [ ] Engineering standards accepted
- [ ] Real vs simulated integrations frozen
- [ ] Demo dataset design frozen
- [ ] First vertical slice frozen
- [ ] Open assumptions clearly marked

## 51. Greenfield repository and monorepo direction

RecoveryOS is currently a greenfield repository. The approved default direction is a pnpm workspace orchestrated by Turborepo. This is a repository and development constraint, while exact framework versions, package dependencies, database, queue, deployment, and API wire contracts remain architecture decisions for `docs/ARCHITECTURE.md`.

The initial application boundary is:

```text
RecoveryOS/
├── apps/
│   ├── web/              # Merchant dashboard and product experience
│   └── api/              # Modular backend/service boundary
├── packages/
│   └── ui/               # Shared UI package and design system
├── docs/                 # Product and engineering source of truth
└── scripts/              # Repository tooling and validation
```

The exact tree may evolve only through an architecture decision. The project SHOULD begin as one web app and one modular API, avoiding premature microservices. New apps MAY be added only when they represent a clearly justified product or deployment boundary.

### 51.1 Shared UI ownership

`packages/ui/src` is the canonical home for reusable UI. It MUST contain shared components, shadcn-style primitives, design tokens, utilities, and global styles as appropriate. The package MUST expose a stable public entrypoint for consuming applications.

`packages/ui/src/global.css` MUST be the canonical shared stylesheet for CSS variables and design tokens, including colors, typography, spacing, radii, shadows, responsive conventions, light/dark theme variables where supported, and accessible state styles. Tailwind configuration/preset and shadcn-style component conventions belong to the shared UI system.

Reusable components MUST NOT be created in `apps/web/app/components` or duplicated across applications. Route-specific composition may remain near a route, but reusable cards, tables, forms, dialogs, badges, navigation, data-display patterns, loading states, and feedback components belong in `packages/ui/src`.

Applications MUST consume the shared UI package and global styles. UI components MUST remain presentation-oriented and MUST NOT own payment truth, policy evaluation, scoring, attribution, or other domain rules.

### 51.2 Frontend quality constraints

The web experience MUST use Tailwind CSS and shadcn-style accessible primitives, support responsive layouts, provide keyboard/focus states, and expose clear loading, empty, degraded, and error states. Pages and route modules SHOULD remain below approximately 400–500 lines; larger screens MUST be decomposed into domain sections and shared components unless a documented exception exists.

The user experience should feel like serious fintech operations software: high signal, low clutter, interactive, readable, and production-minded. Decorative AI effects or generic chatbot patterns must not replace useful case reasoning and operational controls.

## 52. Modular backend direction

The backend MUST be organized by domain and responsibility rather than by an undifferentiated route or utility layer. The architecture handoff MUST define the concrete tree and dependency direction for:

- configuration and typed startup validation;
- domain models, invariants, and state transitions;
- application services and use cases;
- persistence and repositories;
- normalized event ingestion and webhook controllers;
- Razorpay and simulator provider adapters;
- workers, jobs, and scheduling;
- AI provider adapters and structured-output validation;
- deterministic policy engine;
- scoring and recovery economics;
- incident detection;
- experiments and attribution;
- audit and observability;
- simulator and seeded fixtures;
- shared errors, types, and contract validation.

Route handlers/controllers MUST translate transport input and delegate to application services. They MUST NOT contain payment truth, policy precedence, scoring formulas, persistence orchestration, or provider-specific recovery logic. Provider-specific behavior MUST remain behind adapters/interfaces such as `PaymentProvider`, `MessagingProvider`, `AIProvider`, and `JobScheduler`.

The dependency direction MUST keep domain logic independent from UI, HTTP, provider SDKs, and infrastructure details. Business rules MUST have one authoritative implementation.

## 53. Lightweight RBAC and authorization

RecoveryOS will use lightweight MVP RBAC because policy changes, approvals, integrations, customer context, and simulator controls have different risk levels. RBAC is not intended to become an enterprise permission-builder in the Buildathon.

### Roles

- **Viewer:** may view dashboards, cases, incidents, analytics, audit summaries, and permitted customer context.
- **Operator:** includes Viewer permissions and may review cases, perform permitted manual operations, and execute configured low-risk interventions.
- **Admin:** includes Operator permissions and may approve high-value actions, modify merchant policies, manage integrations, manage simulator settings, and access full operational audit data.

Authorization MUST be enforced at the API/application boundary and scoped to the merchant/tenant. UI hiding is presentation only and is never a security control. The permission model MUST cover viewing cases, viewing customer information, manual retry, intervention execution, approval, policy modification, integration management, simulator execution, and audit-log access.

Every privileged operation MUST record actor, role, merchant, action, target, decision, timestamp, and correlation ID. A future permission-builder or complex organization hierarchy is out of scope unless separately approved.

## 54. Documentation synchronization and development workflow

Documentation is part of the product change. Any material change to behavior, scope, state transitions, policy, data shape, API contract, integration posture, UI surface, security control, test strategy, or deployment assumptions MUST update the relevant document under `docs/` in the same change.

The documentation map is:

| Document | Responsibility |
|---|---|
| `docs/PRD.md` | Product scope, requirements, principles, acceptance criteria, and source of truth |
| `docs/ARCHITECTURE.md` | Stack, repository tree, module boundaries, dependencies, runtime, and deployment |
| `docs/DATA_MODEL.md` | Canonical entities, fields, constraints, indexes, and relationships |
| `docs/DECISIONS.md` or ADR directory | Material architecture and product decisions with rationale |
| `README.md` | Developer setup, commands, usage, and contribution entrypoint |

The implementation agent MUST check existing documentation before changing architecture or behavior. If a decision changes an earlier document, the change MUST be made in place or recorded as a superseding decision; competing undocumented sources of truth are not permitted.

## 55. Repository quality gates and end-to-end verification

The repository MUST define and run coherent quality gates appropriate to the selected stack:

- formatting;
- linting;
- type checking;
- unit tests;
- integration tests;
- build validation;
- end-to-end tests for the first vertical slice;
- UI architecture checks ensuring reusable components remain in `packages/ui/src`;
- configuration and secret checks where tooling supports them.

After each implementation step, the agent MUST run the relevant checks and report failures clearly. Before calling a feature complete, the agent MUST run the full applicable suite and manually or automatically verify the end-to-end behavior, including the payment race, duplicate webhook, policy block, opt-out, AI fallback, and incident suppression scenarios.

Commits and changes SHOULD follow consistent naming, reviewable scope, clear error handling, and conventional repository practices. Quality gates must be documented in the architecture and README rather than assumed.

## 56. Skills and agent tooling constraint

Agent skills, skills.sh resources, and development tools are optional engineering aids. They are not product dependencies, must not introduce runtime behavior, and must not bypass tests, policies, security controls, documentation updates, or review gates. A skill MAY be used when it materially improves the current task, and its output MUST still be reviewed against this PRD and the repository standards.

The implementation agent MUST NOT install or add an external skill solely to justify a dependency or change the product architecture. Missing tooling is an explicit development constraint, not permission to invent a substitute product feature.

## 57. Updated architecture handoff defaults

The next artifact, `docs/ARCHITECTURE.md`, MUST make these defaults concrete without re-litigating the product scope:

- pnpm workspace and Turborepo orchestration;
- one `apps/web` merchant dashboard and one `apps/api` modular backend initially;
- `packages/ui/src` as the sole home of reusable UI and shared design tokens;
- `packages/ui/src/global.css` as the canonical global CSS/token source;
- Tailwind CSS and shadcn-style accessible primitives;
- typed API contracts through an explicit shared or generated boundary;
- lightweight Viewer/Operator/Admin RBAC enforced server-side;
- business logic outside route handlers and UI components;
- validated configuration or persisted merchant settings for all mutable business values;
- provider adapters isolating Razorpay, messaging, AI, and scheduling implementations;
- no duplicated domain logic or undocumented architecture shortcuts.

The architecture document MUST then decide the exact framework versions, package manager version, package names, folder tree, dependency boundaries, database and migrations, queue/scheduler, API contracts, authentication mechanism, local development, deployment, CI/CD, and implementation order for the first vertical slice.

## 58. Core business rules

These rules define product behavior independently of the implementation stack. They refine the existing Recovery Case state machine and identity rules; they do not add new case semantics.

### Eligibility and case creation

- A revenue event is eligible only when it represents an unpaid, recoverable business obligation and contains a valid merchant, obligation identity, amount, currency, and source reference.
- A verified payment success is never eligible for recovery outreach.
- One recoverable business obligation creates at most one logical Recovery Case. Multiple attempts, webhooks, messages, or incident associations do not create additional obligations.
- Cases must be merchant-scoped and must not be visible across tenants.
- Unknown, malformed, or ambiguous obligations are recorded for investigation or rejected; they are not silently counted as revenue at risk.
- Case creation and event idempotency must be safe under concurrent delivery.

### Recovery attempts and action eligibility

- A recovery attempt is an actual provider/payment attempt or customer-facing intervention recorded against the case, not an AI recommendation or scheduled-job retry by itself.
- A case may proceed only while it is open, unpaid, within its configured recovery window, not opted out, and within configured attempt/contact limits.
- Before every payment or customer-facing action, the system must re-check authoritative payment/order state, case state, opt-out, incident, policy, and action idempotency.
- A successful payment cancels future work and records the verified recovered amount exactly once.
- AI recommendations are proposals; only registered actions that pass policy may execute.

### Escalation and closure

- Cases require human review when the configured approval threshold, low-confidence rule, unusual risk, or explicit policy requires it.
- A case is `EXHAUSTED` when configured attempts or sequence duration are consumed without recovery and no further permitted action remains.
- A case is `OPTED_OUT` after a valid customer opt-out and all applicable future customer contact is cancelled.
- A case is `SUPPRESSED` or `WAITING` during a qualifying systemic incident according to configured incident policy.
- A case is `CANCELLED` only through an authorized merchant/system cancellation or a documented reconciliation flow.
- A case is `RECOVERED` only after authoritative payment reconciliation; message delivery, link clicks, promises, or AI confidence cannot close it.

## 59. Failure-handling principles

RecoveryOS must fail closed for financial truth and customer contact, fail visibly for operations, and remain retryable where the failure may resolve. No component failure may bypass policy, create a false recovery, or silently discard an obligation.

| Failure | Required behavior |
|---|---|
| Invalid webhook signature | Reject without domain mutation; record safe security/health telemetry |
| Webhook validation or processing failure | Return a safe provider response, persist/retry when appropriate, expose failed status, and preserve idempotency |
| Duplicate webhook | Safe no-op after idempotency check; never duplicate case or financial effect |
| Worker crash/restart | Reconstruct due work from durable job/case state; use action idempotency before effects |
| Stuck or overdue job | Mark stale, alert/health-report it, re-evaluate or dead-letter according to configured retry policy |
| AI timeout/invalid output | Validate, record failure, use deterministic fallback or safe wait/escalation |
| Messaging/payment provider failure | Classify retryable versus terminal, use bounded backoff, optional configured fallback, and audit each attempt |
| Database outage | Do not claim success; fail safely, preserve retryability, expose degraded health, and reconcile after restoration |
| Stale recommendation | Re-check current context; discard and re-score when material inputs changed |
| Payment verification unavailable | Do not send a customer-facing action; retry or escalate with visible degraded state |
| Rate limit | Honor provider limits, retry with configured backoff, and prevent duplicate outbound effects |

## 60. Performance targets

The following are initial Buildathon acceptance targets, not hidden source-code constants. They MUST be represented as environment-validated operational configuration where applicable and measured in the target deployment.

| Operation | Initial target |
|---|---|
| Valid webhook acknowledgement | p95 ≤ 2 seconds after validation; heavy processing asynchronous |
| Webhook-to-case persistence | p95 ≤ 5 seconds in demo environment |
| Read API common query | p95 ≤ 500 ms for seeded demo dataset |
| Mutating API request | p95 ≤ 1 second excluding external provider latency |
| Initial dashboard data load | p95 ≤ 2 seconds after API availability |
| Case detail load | p95 ≤ 1 second for normal case history |
| Decision timeout | Configured; default demo budget ≤ 5 seconds for AI and deterministic fallback immediately available |
| Due-job pickup | p95 ≤ 30 seconds from configured due time in demo worker |
| Action preflight recheck | p95 ≤ 1 second excluding provider outage |
| Dashboard freshness | Show last-updated timestamp; stale threshold is configured |

Load, timeout, and error measurements must be reported with environment and dataset size. A slower external provider must not be misrepresented as RecoveryOS computation latency.

## 61. Observability requirements

### Structured logs

All application logs MUST be structured and include severity, timestamp, environment, service/module, operation, duration where relevant, outcome, and applicable `merchant_id`, `case_id`, `event_id`, `payment_id`, `action_id`, `job_id`, `incident_id`, and `correlation_id`. Secrets, credentials, CVV, raw card data, and unnecessary PII must never be logged.

### Metrics

The system MUST expose or record counters, gauges, and latency measurements for webhook received/accepted/rejected/duplicate/failed, cases created and transitioned, policy allows/blocks/suppression/approval, jobs queued/started/succeeded/retried/dead-lettered, provider calls and failures, AI requests/timeouts/fallbacks/invalid outputs, messages attempted/delivered/failed, incidents opened/resolved, and natural/assisted recovery and recovered amount.

### Health checks

Provide separate liveness and readiness signals where the runtime supports them. Readiness must reflect required database, queue/scheduler, provider configuration, and migration state. Health output must not leak credentials. The dashboard must distinguish healthy, degraded, unavailable, and stale dependencies.

### Error tracking and alerting

Unexpected exceptions, repeated provider failures, signature failures, stuck jobs, queue growth, worker absence, AI fallback spikes, and database degradation must be captured with correlation IDs and safe context. Alert thresholds are typed configuration. The operator view must link an error condition to affected cases or operational actions where possible.

### Tracing

Distributed tracing is `Stretch` for the MVP. When enabled, spans SHOULD cover webhook receipt, normalization, case creation, diagnosis/scoring, recommendation, policy evaluation, scheduling, worker execution, provider call, reconciliation, and dashboard query. Trace IDs must correlate with structured logs without carrying sensitive payloads.

## 62. Expanded security requirements

- All API endpoints MUST enforce authenticated, merchant-scoped authorization; UI visibility alone is insufficient.
- Webhook endpoints MUST verify signatures, reject replayed/expired events where provider metadata supports it, and record safe security telemetry.
- Public and mutation endpoints MUST have configurable rate limits appropriate to operation risk. Webhook limits must not break legitimate provider retries.
- Secrets MUST be provided through environment/secret-management mechanisms, never committed, logged, returned by APIs, or stored in client bundles.
- Integration secrets SHOULD support rotation without code changes or downtime where the provider permits it. Rotation and revocation events must be audited.
- Data in transit MUST use TLS in deployed environments. Sensitive data at rest MUST use the database/platform encryption capability; application-level field encryption is required where threat modeling identifies a need.
- Tenant identifiers MUST be applied to every case, event, job, audit, analytics, and customer query. Cross-tenant access tests are mandatory.
- Customer PII MUST be minimized, access-controlled, redacted from logs, and retained only for a configured period. Raw card data and CVV are prohibited.
- Audit logs MUST be append-only to application actors, include policy/configuration changes, and use a configured retention period. Deletion or archival must preserve required compliance evidence and be auditable.
- High-risk operations such as policy changes, integration changes, approvals, manual retries, and simulator execution require role checks and audit events.
- Error responses MUST avoid provider secrets, internal stack traces, sensitive payment details, and cross-tenant identifiers.

## 63. AI governance and decision explanation

### Prompt and model governance

Prompts, system instructions, schemas, model/provider identifiers, and generation settings MUST be versioned configuration or versioned source artifacts with an immutable reference stored on each recommendation. Prompt or model changes require a reviewable change and regression evaluation. Model names, endpoints, API keys, and timeouts are environment configuration.

### Evidence and explanation

Every recommendation MUST expose the action, reason code, relevant evidence, score inputs, confidence, scoring/model version, policy result, and fallback action. The UI should distinguish evidence from generated prose and clearly show when a deterministic rule—not an LLM—made the decision.

### Safeguards

AI input must be minimized and tenant-scoped. Untrusted event fields must not be treated as instructions. Output must be schema-validated, allow-listed, range-checked, and rejected when it contains unsupported actions, financial truth, credentials, or arbitrary tool instructions. AI cannot establish payment status, change amount, override authorization, bypass policy, or execute an unregistered tool.

### Confidence and failure

Low confidence, missing evidence, contradictory evidence, schema failure, timeout, provider outage, or prompt/model version mismatch must result in deterministic fallback, safe wait, suppression, or human review according to policy. AI fallback rate, invalid-output rate, and low-confidence rate must be observable.

## 64. Operational runbook expectations

The eventual `docs/OPERATIONS.md` or equivalent operations section MUST provide step-by-step response guidance. The PRD requires these playbooks:

### Stuck jobs

Inspect job age, case state, payment state, retry count, provider response, and worker health. Re-run only through an idempotent recovery path, cancel stale work when payment/opt-out/terminal state applies, and dead-letter after configured attempts. Record the operator action.

### Webhook failures

Check signature/configuration errors, provider delivery status, ingestion health, duplicate rates, and database readiness. Correct configuration through Admin controls, replay only with provider event identity and idempotency, and reconcile cases after recovery.

### Provider degradation

Confirm incident dimensions, baseline/current success rates, affected amount, and confidence. Keep outreach suppressed or delayed while policy applies, monitor resolution/cooldown, and review unresolved cases after recovery. Do not manually broadcast customer contact during a suspected incident.

### AI outage

Confirm provider health, timeout/error/fallback metrics, and recommendation backlog. Keep deterministic scoring and fallback active, route low-confidence/high-value cases to approval, and restore AI only after structured-output and policy-path checks pass.

### Database or queue issue

Mark the dependency degraded, stop claiming financial/action success, protect inbound retry/idempotency behavior, restore or fail over through the deployment procedure, reconcile unprocessed events and jobs, and verify audit continuity.

### Suspected incorrect recovery total

Freeze reporting changes, reconcile provider success identities and case obligations, inspect duplicate events/actions and refund/reversal adjustments, correct only through an auditable reconciliation flow, and document the incident.

## 65. Expanded risk register

| Category | Risk | Mitigation |
|---|---|---|
| Financial | Success or recovered amount counted twice | Obligation identity, unique constraints, authoritative reconciliation, immutable attribution |
| Financial | Outreach sent after payment | Last-mile payment recheck and cancellation |
| Financial | Incorrect smallest-unit/currency arithmetic | Integer amounts, currency validation, unit tests |
| Technical | Duplicate webhook or worker delivery | Idempotency keys and transactional uniqueness |
| Technical | Stuck or lost scheduled work | Durable/reconstructable jobs, health metrics, DLQ, reconciliation |
| Technical | Database outage causes silent loss | Fail-safe writes, retryability, readiness checks, restore reconciliation |
| Security | Cross-tenant data access | Merchant-scoped authorization and isolation tests |
| Security | Secret or PII leakage | Secret management, redaction, TLS/encryption, minimal retention |
| Security | Webhook spoofing or replay | Signature verification, replay protections where supported, audit telemetry |
| Operational | Provider incident triggers mass outreach | Configurable incident detection and suppression |
| Operational | Message provider outage creates noisy retries | Bounded backoff, channel caps, fallback policy, DLQ |
| AI | Hallucinated action or financial fact | Allow-listed schema, evidence contract, policy authority, deterministic fallback |
| AI | Prompt/model drift changes behavior | Versioning, regression set, recommendation audit, rollout control |
| AI | Low confidence treated as certainty | Separate probability/confidence, approval and safe-wait rules |
| Product | Customers annoyed by over-contact | Contact caps, interval, quiet hours, opt-out, suppression metrics |
| Product | Dashboard optimizes activity over value | Lead with recovered/incremental revenue, cost, and lift |
| Scalability | Large case/event volume slows prioritization | Indexed queries, async processing, bounded batch jobs, measured targets |
| Scalability | One merchant overwhelms shared workers | Tenant-aware limits, queue fairness, and observable backlog |
| Compliance | Audit history altered or retained incorrectly | Append-only audit storage, retention policy, access controls, archival record |
| Demo credibility | Synthetic result presented as real | Explicit simulator labels, reproducible seed, derived totals, no fake fixed metrics |

## 66. Configuration management contract

Configuration has four categories:

1. **Environment configuration:** deployment, database/queue URLs, secrets, provider endpoints, model settings, logging, rate limits, and runtime timeouts.
2. **Merchant policy:** attempts, intervals, quiet hours, approval thresholds, channel enablement, contact caps, sequence duration, fallback, and timezone.
3. **Feature flags:** controlled enablement of simulator behavior, channels, experiments, incident suppression, tracing, and staged capabilities.
4. **Experiment overrides:** explicitly scoped and time-bound variations that cannot override safety or financial invariants.

Safe defaults may exist for structural behavior and local development, but every mutable business value must have a typed source and effective-value display/audit path. Configuration precedence remains environment → merchant policy → approved experiment override → per-case computed context, subject to safety guardrails. Secrets are never database defaults or source-code values. Startup validation must reject malformed mandatory configuration.

Policy and configuration changes MUST be versioned. A policy version is captured on each policy decision, scheduled job, action, and relevant audit event so an operator can reconstruct exactly which rules were applied.

## 67. Architecture diagram requirement

`docs/ARCHITECTURE.md` MUST include a high-level diagram showing:

```text
Provider/Webhook/Simulator
          -> validation + idempotency
          -> event normalization
          -> Recovery Case identity and state machine
          -> diagnosis + scoring + incident correlation
          -> AI recommendation / deterministic fallback
          -> policy precedence and RBAC
          -> durable scheduler/worker
          -> provider/action adapters
          -> payment reconciliation and attribution
          -> audit, metrics, and merchant dashboard
```

The diagram is an architecture handoff requirement, not permission to move architecture decisions into this PRD.

## 68. Operational resilience extensions

### Dead-letter handling

DLQ support is `Stretch` for the MVP but the execution design MUST define how repeatedly failing events/actions/jobs are isolated, inspected, replayed safely, or permanently closed. Replay requires original identity and idempotency checks.

### Disaster recovery

The production-readiness plan MUST document backup frequency, retention, restore verification, database durability, job reconstruction, secret recovery/rotation, and reconciliation after outage. Exact RPO/RTO values are `OPEN` until deployment architecture is selected. The Buildathon must at minimum demonstrate restart-safe or reconstructable scheduled work.

### Distributed tracing

Tracing is `Stretch`; structured correlation IDs and reliable audit events are MVP requirements. Tracing may be added without changing domain behavior and must avoid sensitive payloads.

## 69. Expanded glossary additions

- **Business obligation:** The single payable order, checkout intent, billing cycle, or invoice that can be recovered.
- **Attempt:** A payment or recovery intervention recorded against a case; not a duplicate webhook or AI proposal.
- **Policy version:** Immutable identifier of the merchant/environment rules used for a decision.
- **Correlation ID:** Identifier connecting one request/event/workflow across logs, jobs, provider calls, and audit records.
- **Liveness:** Whether a process is running; it does not imply dependencies are usable.
- **Readiness:** Whether required dependencies and configuration permit safe traffic.
- **DLQ:** Dead-letter queue for repeatedly failing work requiring inspection or controlled replay.
- **Feature flag:** Explicit runtime control for staged or demo behavior.
- **RPO/RTO:** Recovery Point Objective and Recovery Time Objective for disaster recovery planning.
- **Prompt version:** Immutable identifier of the AI instructions/schema/configuration used for a recommendation.

## 70. Finalization review

The PRD revision must be considered consistent only if:

- existing MVP capability classifications, Recovery Case identity, and state machine remain unchanged;
- every new threshold, timeout, target, retention value, or policy value is described as configurable or explicitly marked OPEN;
- financial truth remains deterministic and server-authoritative;
- AI remains advisory, structured, explainable, and policy-constrained;
- RBAC remains lightweight and server-enforced;
- the reference repository is treated as inspiration only;
- `ARCHITECTURE.md` remains the separate owner of stack and implementation decisions;
- no fixed demo output is used in place of simulator-derived results;
- operational, security, reliability, and failure states are visible and auditable.

## Changelog

### v1.0

- implementation-readiness requirements added;
- acceptance criteria added;
- Recovery Case identity formalized;
- state and policy rules formalized;
- scoring, incident, and attribution v1 defined;
- NFRs added;
- engineering governance added;
- zero-hardcoding policy added;
- configuration hierarchy added;
- demo dataset requirements added;
- architecture handoff gate added.
