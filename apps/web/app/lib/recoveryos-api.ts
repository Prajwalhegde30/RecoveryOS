export type Metrics = Record<string, number | null>;
export type Dashboard = { metrics: Metrics; freshness: string };
export type CaseSummary = {
  id: string;
  source_type: string;
  status: string;
  amount_at_risk_minor_units: number;
  recovered_amount_minor_units: number;
  priority_score: number | null;
};
export type CaseDetail = CaseSummary & {
  customer_id: string | null;
  root_cause: string | null;
  root_cause_confidence: number | null;
  recovery_probability: number | null;
  recovery_attempt_count: number;
  max_attempts: number;
  recommendations: Array<{ action_type?: string; rationale?: string; confidence?: number }>;
  policy_decisions: Array<{ result?: string; decisive_rule?: string; reason?: string }>;
  actions: Array<{ action_type?: string; status?: string; failure_detail_safe?: string | null }>;
  timeline: Array<{ event_type: string; reason: string; created_at: string }>;
};
export type Incident = { id: string; dimension_key: string; status: string; confidence: number };
export type OperationalHealth = {
  components: Record<
    string,
    { status: string; detail: string; pending_jobs?: number; stale_claims?: number }
  >;
};
export type CurrentPolicy = { version: number; status: string; policy: Record<string, unknown> };
export type ActionResult = { status?: string; reason?: string; detail?: string };

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

  cases(): Promise<CaseSummary[]> {
    return this.get('/api/v1/cases?limit=8');
  }

  incidents(): Promise<Incident[]> {
    return this.get('/api/v1/incidents?active_only=true');
  }

  operationalHealth(): Promise<OperationalHealth> {
    return this.get('/api/v1/health/operational');
  }

  currentPolicy(): Promise<CurrentPolicy> {
    return this.get('/api/v1/policies/current');
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
