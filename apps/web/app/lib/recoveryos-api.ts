export type Metrics = Record<string, number | null>;
export type Dashboard = { metrics: Metrics; freshness: string; last_updated_at: string };
export type CaseSummary = {
  id: string;
  obligation_id: string;
  source_type: string;
  status: string;
  currency: string;
  amount_at_risk_minor_units: number;
  expected_recoverable_amount_minor_units: number | null;
  recovered_amount_minor_units: number;
  attribution_status: string;
  incident_suppressed: boolean;
  created_at: string;
  priority_score: number | null;
};
export type CaseDetail = CaseSummary & {
  customer_id: string | null;
  root_cause: string | null;
  root_cause_confidence: number | null;
  recovery_probability: number | null;
  recovery_attempt_count: number;
  max_attempts: number;
  attempts: Array<{ status?: string; provider?: string; provider_reference?: string | null }>;
  recommendations: Array<{
    action_type?: string;
    rationale?: string;
    confidence?: number;
    source?: string;
  }>;
  policy_decisions: Array<{
    result?: string;
    decisive_rule?: string;
    reason?: string;
    policy_version_id?: string;
  }>;
  actions: Array<{
    action_type?: string;
    status?: string;
    failure_detail_safe?: string | null;
    idempotency_key?: string;
  }>;
  timeline: Array<{
    event_type: string;
    reason: string;
    actor_type: string;
    correlation_id: string;
    created_at: string;
  }>;
};
export type Incident = {
  id: string;
  dimension_key: string;
  status: string;
  confidence: number;
  baseline_window: Record<string, unknown>;
  current_window: Record<string, unknown>;
  evidence: Record<string, unknown>;
  affected_case_ids: string[];
};
export type OperationalHealth = {
  components: Record<
    string,
    { status: string; detail: string; pending_jobs?: number; stale_claims?: number }
  >;
};
export type OperationalMetrics = { merchant_id: string; metrics: Record<string, number> };
export type AuditEvent = {
  id: string;
  entity_type: string;
  entity_id: string;
  event_type: string;
  actor_type: string;
  reason: string;
  metadata: Record<string, unknown>;
  correlation_id: string;
  created_at: string;
};
export type CurrentPolicy = { version: number; status: string; policy: Record<string, unknown> };
export type ApprovalQueueItem = {
  case_id: string;
  decision_id: string;
  policy_version_id: string;
  amount_at_risk_minor_units: number;
  currency: string;
  reason: string;
  created_at: string;
};
export type ActionResult = { status?: string; reason?: string; detail?: string };
export type ApprovalResult = { status?: string; reason?: string; decision_id?: string };

export class RecoveryOsApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'RecoveryOsApiError';
  }
}

export class RecoveryOsApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  dashboard(): Promise<Dashboard> {
    return this.get('/api/v1/dashboard');
  }

  cases(status?: string, source?: string): Promise<CaseSummary[]> {
    const query = new URLSearchParams({ limit: '50' });
    if (status) query.set('status', status);
    if (source) query.set('source', source);
    return this.get(`/api/v1/cases?${query.toString()}`);
  }

  incidents(): Promise<Incident[]> {
    return this.get('/api/v1/incidents?active_only=true');
  }

  operationalHealth(): Promise<OperationalHealth> {
    return this.get('/api/v1/health/operational');
  }

  operationalMetrics(): Promise<OperationalMetrics> {
    return this.get('/api/v1/health/metrics');
  }

  audit(limit = 50): Promise<AuditEvent[]> {
    return this.get(`/api/v1/audit?limit=${limit}`);
  }

  currentPolicy(): Promise<CurrentPolicy> {
    return this.get('/api/v1/policies/current');
  }

  approvals(): Promise<ApprovalQueueItem[]> {
    return this.get('/api/v1/approvals');
  }

  caseDetail(caseId: string): Promise<CaseDetail> {
    return this.get(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  }

  requestEmailAction(caseId: string): Promise<ActionResult> {
    return this.post(`/api/v1/cases/${encodeURIComponent(caseId)}/actions`, {
      action_type: 'SEND_EMAIL',
      idempotency_key: `dashboard-${caseId}-${crypto.randomUUID()}`,
      due_at: new Date().toISOString(),
      channel: 'email',
    });
  }

  resolveApproval(
    caseId: string,
    policyVersionId: string,
    approved: boolean,
  ): Promise<ApprovalResult> {
    return this.post(`/api/v1/cases/${encodeURIComponent(caseId)}/approvals`, {
      policy_version_id: policyVersionId,
      approved,
      reason: approved
        ? 'Approved from the merchant dashboard.'
        : 'Rejected from the merchant dashboard.',
    });
  }

  private async get<T>(path: string): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    return this.parse<T>(response);
  }

  private async post<T>(path: string, body: object): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    return this.parse<T>(response);
  }

  private async parse<T>(response: Response): Promise<T> {
    const payload = (await response.json()) as T & { detail?: string };
    if (!response.ok) {
      throw new RecoveryOsApiError(
        payload.detail ?? 'The RecoveryOS API returned an error.',
        response.status,
      );
    }
    return payload;
  }
}
