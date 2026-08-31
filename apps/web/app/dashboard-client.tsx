'use client';

import React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  Badge,
  Button,
  Card,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
} from '@recoveryos/ui';
import {
  CaseDetail,
  CaseSummary,
  CurrentPolicy,
  Dashboard,
  Incident,
  OperationalHealth,
  RecoveryOsApiClient,
} from './lib/recoveryos-api';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const merchantId = process.env.NEXT_PUBLIC_MERCHANT_ID ?? '';
const authToken = process.env.NEXT_PUBLIC_AUTH_TOKEN ?? '';

export function DashboardClient() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [health, setHealth] = useState<OperationalHealth | null>(null);
  const [policy, setPolicy] = useState<CurrentPolicy | null>(null);
  const [selectedCase, setSelectedCase] = useState<CaseDetail | null>(null);
  const [caseStatus, setCaseStatus] = useState('');
  const [sortByPriority, setSortByPriority] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const api = useMemo(() => new RecoveryOsApiClient(apiBaseUrl, authToken), []);

  const load = useCallback(async () => {
    if (!merchantId || !authToken) {
      setError(
        'Configure NEXT_PUBLIC_MERCHANT_ID and NEXT_PUBLIC_AUTH_TOKEN to connect the merchant dashboard.',
      );
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [dashboardResult, casesResult, incidentsResult] = await Promise.all([
        api.dashboard(),
        api.cases(caseStatus || undefined),
        api.incidents(),
      ]);
      setDashboard(dashboardResult);
      setCases(casesResult);
      setIncidents(incidentsResult);
      const [healthResult, policyResult] = await Promise.allSettled([
        api.operationalHealth(),
        api.currentPolicy(),
      ]);
      setHealth(healthResult.status === 'fulfilled' ? healthResult.value : null);
      setPolicy(policyResult.status === 'fulfilled' ? policyResult.value : null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load RecoveryOS data.');
    } finally {
      setLoading(false);
    }
  }, [api, caseStatus]);

  const loadCaseDetail = useCallback(
    async (caseId: string) => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        setSelectedCase(await api.caseDetail(caseId));
      } catch (cause) {
        setDetailError(cause instanceof Error ? cause.message : 'Unable to load case details.');
      } finally {
        setDetailLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = dashboard?.metrics;
  const visibleCases = [...cases].sort((left, right) => {
    if (!sortByPriority) return 0;
    return (right.priority_score ?? -1) - (left.priority_score ?? -1);
  });
  const money = (value: number | null | undefined) =>
    value == null
      ? '—'
      : new Intl.NumberFormat('en-IN', {
          style: 'currency',
          currency: 'INR',
          maximumFractionDigits: 0,
        }).format(value / 100);

  return (
    <main className="dashboard-shell">
      <div className="dashboard-container">
        <header className="dashboard-header">
          <div>
            <p className="eyebrow">RecoveryOS</p>
            <h1>Revenue recovery control plane</h1>
            <p>Detect revenue at risk, decide safely, and prove what came back.</p>
          </div>
          <Button type="button" onClick={() => void load()} disabled={loading}>
            Refresh data
          </Button>
        </header>

        {loading ? <LoadingState /> : null}
        {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
        {!loading && !error && dashboard ? (
          <>
            <div className="metric-grid" aria-label="Recovery metrics">
              <Metric label="Revenue at risk" value={money(metrics?.revenue_at_risk_minor_units)} />
              <Metric
                label="Expected recoverable"
                value={money(metrics?.expected_recoverable_minor_units)}
              />
              <Metric
                label="Recovered"
                value={money(metrics?.recovered_minor_units)}
                tone="success"
              />
              <Metric
                label="Net recovery"
                value={money(metrics?.net_recovery_minor_units)}
                tone="success"
              />
              <Metric
                label="Natural recovery"
                value={money(metrics?.natural_recovered_minor_units)}
              />
              <Metric
                label="Assisted recovery"
                value={money(metrics?.assisted_recovered_minor_units)}
              />
              <Metric label="Recovery cost" value={money(metrics?.recovery_cost_minor_units)} />
              <Metric
                label="Recovery rate"
                value={
                  metrics?.recovery_rate_percent == null ? '—' : `${metrics.recovery_rate_percent}%`
                }
              />
            </div>
            <div className="section-heading">
              <div>
                <h2>Operational view</h2>
                <p>Freshness: {dashboard.freshness}</p>
              </div>
              <Badge tone={incidents.length ? 'warning' : 'success'}>
                {incidents.length
                  ? `${incidents.length} active incident${incidents.length === 1 ? '' : 's'}`
                  : 'Systems nominal'}
              </Badge>
            </div>
            <div className="content-grid">
              <Card>
                <CardHeader>
                  <CardTitle>Priority recovery cases</CardTitle>
                  <div className="card-actions">
                    <label className="sr-only" htmlFor="case-status">
                      Filter cases by status
                    </label>
                    <select
                      id="case-status"
                      value={caseStatus}
                      onChange={(event) => setCaseStatus(event.target.value)}
                    >
                      <option value="">All statuses</option>
                      <option value="WAITING">Waiting</option>
                      <option value="RECOVERED">Recovered</option>
                      <option value="SUPPRESSED">Suppressed</option>
                      <option value="UNRECOVERED">Unrecovered</option>
                    </select>
                    <Button type="button" onClick={() => setSortByPriority((current) => !current)}>
                      {sortByPriority ? 'Priority order' : 'Newest order'}
                    </Button>
                    <Badge>{visibleCases.length} shown</Badge>
                  </div>
                </CardHeader>
                {visibleCases.length ? (
                  <div className="data-list">
                    {visibleCases.map((item) => (
                      <button
                        className="data-row data-row-button"
                        key={item.id}
                        type="button"
                        onClick={() => void loadCaseDetail(item.id)}
                      >
                        <div>
                          <p>
                            {item.id.slice(0, 8)} · {item.source_type.replaceAll('_', ' ')}
                          </p>
                          <small>
                            {money(item.amount_at_risk_minor_units)} at risk · priority{' '}
                            {item.priority_score ?? '—'}
                          </small>
                        </div>
                        <Badge tone={item.status === 'RECOVERED' ? 'success' : 'warning'}>
                          {item.status}
                        </Badge>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState>
                    No recovery cases yet. Run a labeled simulator batch or ingest a payment event.
                  </EmptyState>
                )}
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Systemic degradation</CardTitle>
                </CardHeader>
                {incidents.length ? (
                  <div className="data-list">
                    {incidents.map((item) => (
                      <div className="data-row" key={item.id}>
                        <div>
                          <p>{item.dimension_key}</p>
                          <small>
                            Detector confidence {item.confidence}% · {item.affected_case_ids.length}{' '}
                            affected case{item.affected_case_ids.length === 1 ? '' : 's'}
                          </small>
                          <small>
                            Current window: {formatWindow(item.current_window)} · baseline:{' '}
                            {formatWindow(item.baseline_window)}
                          </small>
                          <small>Evidence: {formatEvidence(item.evidence)}</small>
                        </div>
                        <Badge tone="warning">SUPPRESSING</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>No active incidents. Outreach guardrails are clear.</EmptyState>
                )}
              </Card>
            </div>
            <div className="content-grid">
              <Card>
                <CardHeader>
                  <CardTitle>System health</CardTitle>
                  <Badge
                    tone={
                      health &&
                      Object.values(health.components).some((item) => item.status === 'degraded')
                        ? 'warning'
                        : 'success'
                    }
                  >
                    {health ? 'Live checks' : 'Unavailable'}
                  </Badge>
                </CardHeader>
                {health ? (
                  <div className="data-list">
                    {Object.entries(health.components).map(([name, component]) => (
                      <div className="data-row" key={name}>
                        <div>
                          <p>{name.replaceAll('_', ' ')}</p>
                          <small>{component.detail}</small>
                        </div>
                        <Badge tone={component.status === 'healthy' ? 'success' : 'warning'}>
                          {component.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>Operational health is unavailable.</EmptyState>
                )}
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Active policy</CardTitle>
                  <Badge>{policy ? `v${policy.version}` : 'Unavailable'}</Badge>
                </CardHeader>
                {policy ? (
                  <div className="data-list">
                    <div className="data-row">
                      <div>
                        <p>Policy status</p>
                        <small>Server-evaluated policy controls action eligibility.</small>
                      </div>
                      <Badge tone={policy.status === 'ACTIVE' ? 'success' : 'warning'}>
                        {policy.status}
                      </Badge>
                    </div>
                    <div className="data-row">
                      <div>
                        <p>Configured channels</p>
                        <small>
                          {Array.isArray(policy.policy.enabled_channels)
                            ? policy.policy.enabled_channels.join(', ')
                            : 'Not exposed'}
                        </small>
                      </div>
                    </div>
                  </div>
                ) : (
                  <EmptyState>No active policy is available.</EmptyState>
                )}
              </Card>
            </div>
            {detailLoading ? <LoadingState label="Loading case details…" /> : null}
            {detailError ? <ErrorState message={detailError} /> : null}
            {selectedCase ? (
              <CaseDetailPanel
                item={selectedCase}
                actionMessage={actionMessage}
                onRequestAction={async () => {
                  setActionMessage(null);
                  try {
                    const result = await api.requestEmailAction(selectedCase.id);
                    setActionMessage(
                      `${result.status ?? 'Processed'}: ${result.reason ?? 'policy evaluated'}`,
                    );
                    await loadCaseDetail(selectedCase.id);
                  } catch (cause) {
                    setActionMessage(
                      cause instanceof Error
                        ? cause.message
                        : 'The recovery action could not be requested.',
                    );
                  }
                }}
              />
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}

function CaseDetailPanel({
  item,
  actionMessage,
  onRequestAction,
}: {
  item: CaseDetail;
  actionMessage: string | null;
  onRequestAction: () => Promise<void>;
}) {
  return (
    <Card className="case-detail-card">
      <CardHeader>
        <div>
          <CardTitle>Case {item.id.slice(0, 8)}</CardTitle>
          <p>
            {item.root_cause ?? 'Root cause pending'} · {item.status}
          </p>
        </div>
        <Badge tone={item.status === 'RECOVERED' ? 'success' : 'warning'}>
          {item.recovery_probability == null
            ? 'Probability pending'
            : `${item.recovery_probability}% likely`}
        </Badge>
      </CardHeader>
      <div className="case-detail-grid">
        <div>
          <span className="metric-label">Attempts</span>
          <strong>
            {item.recovery_attempt_count}/{item.max_attempts}
          </strong>
        </div>
        <div>
          <span className="metric-label">Policy decisions</span>
          <strong>{item.policy_decisions.length}</strong>
        </div>
        <div>
          <span className="metric-label">Actions</span>
          <strong>{item.actions.length}</strong>
        </div>
        <div>
          <span className="metric-label">Audit events</span>
          <strong>{item.timeline.length}</strong>
        </div>
        <div>
          <span className="metric-label">Payment status</span>
          <strong>{item.attempts.at(-1)?.status ?? 'unknown'}</strong>
        </div>
      </div>
      <p className="case-detail-note">
        {item.policy_decisions.at(-1)?.reason ?? 'No policy decision recorded yet.'}
      </p>
      <div className="case-detail-sections">
        <section>
          <h3>Recommendation</h3>
          <p>
            {item.recommendations.at(-1)?.action_type ?? 'No action recommended'} ·{' '}
            {item.recommendations.at(-1)?.source ?? 'pending'} · confidence{' '}
            {item.recommendations.at(-1)?.confidence ?? '—'}
          </p>
          <small>{item.recommendations.at(-1)?.rationale ?? 'No rationale recorded.'}</small>
        </section>
        <section>
          <h3>Policy and execution</h3>
          <p>
            Decision: {item.policy_decisions.at(-1)?.result ?? 'pending'} · action:{' '}
            {item.actions.at(-1)?.status ?? 'not scheduled'}
          </p>
          <small>
            {item.actions.at(-1)?.failure_detail_safe ?? 'No safe failure detail.'} · provider:{' '}
            {item.attempts.at(-1)?.provider_reference ?? 'not reconciled'}
          </small>
        </section>
        <section>
          <h3>Audit timeline</h3>
          {item.timeline.length ? (
            <ol className="timeline-list">
              {item.timeline.slice(-5).map((event) => (
                <li key={`${event.correlation_id}-${event.created_at}`}>
                  <strong>{event.event_type}</strong> — {event.reason}
                  <small>
                    {event.actor_type} · {new Date(event.created_at).toLocaleString()}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <small>No audit events recorded.</small>
          )}
        </section>
      </div>
      <div className="case-detail-actions">
        <Button
          type="button"
          onClick={() => void onRequestAction()}
          disabled={['RECOVERED', 'CANCELLED', 'OPTED_OUT', 'EXHAUSTED'].includes(item.status)}
        >
          Request email recovery
        </Button>
        {actionMessage ? <p className="case-detail-note">{actionMessage}</p> : null}
      </div>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'success';
}) {
  return (
    <Card className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className={tone === 'success' ? 'metric-success' : ''}>{value}</strong>
    </Card>
  );
}

function formatWindow(window: Record<string, unknown>) {
  const rate = window.failure_rate_percent;
  return typeof rate === 'number' ? `${rate}% failure rate` : 'not available';
}

function formatEvidence(evidence: Record<string, unknown>) {
  const source = evidence.source;
  return typeof source === 'string' ? source : 'detector evidence recorded';
}
