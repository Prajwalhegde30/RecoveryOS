'use client';

import React from 'react';
import { useCallback, useEffect, useState } from 'react';

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

type Metrics = Record<string, number | null>;
type Dashboard = { metrics: Metrics; freshness: string };
type CaseSummary = {
  id: string;
  source_type: string;
  status: string;
  amount_at_risk_minor_units: number;
  recovered_amount_minor_units: number;
  priority_score: number | null;
};
type CaseDetail = CaseSummary & {
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
type Incident = { id: string; dimension_key: string; status: string; confidence: number };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const merchantId = process.env.NEXT_PUBLIC_MERCHANT_ID ?? '';
const authToken = process.env.NEXT_PUBLIC_AUTH_TOKEN ?? '';

export function DashboardClient() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      const headers = { Authorization: `Bearer ${authToken}` };
      const [dashboardResponse, casesResponse, incidentsResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/api/v1/dashboard`, { headers }),
        fetch(`${apiBaseUrl}/api/v1/cases?limit=8`, { headers }),
        fetch(`${apiBaseUrl}/api/v1/incidents?active_only=true`, { headers }),
      ]);
      if (!dashboardResponse.ok || !casesResponse.ok || !incidentsResponse.ok) {
        throw new Error('The RecoveryOS API returned a degraded response.');
      }
      setDashboard((await dashboardResponse.json()) as Dashboard);
      setCases((await casesResponse.json()) as CaseSummary[]);
      setIncidents((await incidentsResponse.json()) as Incident[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load RecoveryOS data.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCaseDetail = useCallback(async (caseId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/cases/${caseId}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!response.ok) throw new Error('Unable to load the selected recovery case.');
      setSelectedCase((await response.json()) as CaseDetail);
    } catch (cause) {
      setDetailError(cause instanceof Error ? cause.message : 'Unable to load case details.');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = dashboard?.metrics;
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
                  <Badge>{cases.length} shown</Badge>
                </CardHeader>
                {cases.length ? (
                  <div className="data-list">
                    {cases.map((item) => (
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
                          <small>Detector confidence {item.confidence}%</small>
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
            {detailLoading ? <LoadingState label="Loading case details…" /> : null}
            {detailError ? <ErrorState message={detailError} /> : null}
            {selectedCase ? <CaseDetailPanel item={selectedCase} /> : null}
          </>
        ) : null}
      </div>
    </main>
  );
}

function CaseDetailPanel({ item }: { item: CaseDetail }) {
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
      </div>
      <p className="case-detail-note">
        {item.policy_decisions.at(-1)?.reason ?? 'No policy decision recorded yet.'}
      </p>
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
