'use client';

import React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  AuditActivityCard,
  Badge,
  Button,
  CaseListCard,
  CaseDetailCard,
  Card,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricBarChart,
  MetricCard,
  IntegrationHealthCard,
  PolicySummaryCard,
} from '@recoveryos/ui';
import {
  CaseDetail,
  CaseSummary,
  CurrentPolicy,
  Dashboard,
  Incident,
  OperationalHealth,
  ApprovalQueueItem,
  AuditEvent,
  OperationalMetrics,
  RecoveryOsApiClient,
} from './lib/recoveryos-api';
import {
  formatDuration,
  formatEvidence,
  formatInteger,
  formatMoney,
  formatTimestamp,
  formatWindow,
} from './lib/dashboard-formatters';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const merchantId = process.env.NEXT_PUBLIC_MERCHANT_ID ?? '';
const authToken = process.env.NEXT_PUBLIC_AUTH_TOKEN ?? '';

export function DashboardClient() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [health, setHealth] = useState<OperationalHealth | null>(null);
  const [operationalMetrics, setOperationalMetrics] = useState<OperationalMetrics | null>(null);
  const [policy, setPolicy] = useState<CurrentPolicy | null>(null);
  const [approvals, setApprovals] = useState<ApprovalQueueItem[] | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[] | null>(null);
  const [casesError, setCasesError] = useState<string | null>(null);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<CaseDetail | null>(null);
  const [caseStatus, setCaseStatus] = useState('');
  const [caseSource, setCaseSource] = useState('');
  const [caseRootCause, setCaseRootCause] = useState('');
  const [sortByPriority, setSortByPriority] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [approvalMessage, setApprovalMessage] = useState<string | null>(null);
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
      const [dashboardResult, casesResult, incidentsResult] = await Promise.allSettled([
        api.dashboard(),
        api.cases(caseStatus || undefined, caseSource || undefined, caseRootCause || undefined),
        api.incidents(),
      ]);
      if (dashboardResult.status === 'rejected') {
        throw dashboardResult.reason;
      }
      setDashboard(dashboardResult.value);
      setCasesError(
        casesResult.status === 'rejected'
          ? casesResult.reason instanceof Error
            ? casesResult.reason.message
            : 'Recovery cases are temporarily unavailable.'
          : null,
      );
      setCases(casesResult.status === 'fulfilled' ? casesResult.value : []);
      setIncidentsError(
        incidentsResult.status === 'rejected'
          ? incidentsResult.reason instanceof Error
            ? incidentsResult.reason.message
            : 'Incident data is temporarily unavailable.'
          : null,
      );
      setIncidents(incidentsResult.status === 'fulfilled' ? incidentsResult.value : []);
      const [healthResult, metricsResult, policyResult, approvalsResult, auditResult] =
        await Promise.allSettled([
          api.operationalHealth(),
          api.operationalMetrics(),
          api.currentPolicy(),
          api.approvals(),
          api.audit(),
        ]);
      setHealth(healthResult.status === 'fulfilled' ? healthResult.value : null);
      setOperationalMetrics(metricsResult.status === 'fulfilled' ? metricsResult.value : null);
      setPolicy(policyResult.status === 'fulfilled' ? policyResult.value : null);
      setApprovals(approvalsResult.status === 'fulfilled' ? approvalsResult.value : null);
      setAuditEvents(auditResult.status === 'fulfilled' ? auditResult.value : null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load RecoveryOS data.');
    } finally {
      setLoading(false);
    }
  }, [api, caseRootCause, caseSource, caseStatus]);

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
              <MetricCard
                label="Revenue at risk"
                value={formatMoney(metrics?.revenue_at_risk_minor_units)}
              />
              <MetricCard
                label="Expected recoverable"
                value={formatMoney(metrics?.expected_recoverable_minor_units)}
              />
              <MetricCard
                label="Recovered"
                value={formatMoney(metrics?.recovered_minor_units)}
                tone="success"
              />
              <MetricCard
                label="Net recovery"
                value={formatMoney(metrics?.net_recovery_minor_units)}
                tone="success"
              />
              <MetricCard
                label="Natural recovery"
                value={formatMoney(metrics?.natural_recovered_minor_units)}
              />
              <MetricCard
                label="Assisted recovery"
                value={formatMoney(metrics?.assisted_recovered_minor_units)}
              />
              <MetricCard
                label="Recovery cost"
                value={formatMoney(metrics?.recovery_cost_minor_units)}
              />
              <MetricCard
                label="Recovery rate"
                value={
                  metrics?.recovery_rate_percent == null ? '—' : `${metrics.recovery_rate_percent}%`
                }
              />
              <MetricCard label="Suppressed" value={formatMoney(metrics?.suppressed_minor_units)} />
              <MetricCard
                label="Unrecovered"
                value={formatMoney(metrics?.unrecovered_minor_units)}
              />
              <MetricCard
                label="Recovered cases"
                value={formatInteger(metrics?.recovered_case_count)}
                tone="success"
              />
              <MetricCard
                label="Median time to recovery"
                value={formatDuration(metrics?.median_time_to_recovery_seconds)}
              />
            </div>
            <MetricBarChart
              title="Recovery value comparison"
              bars={[
                {
                  label: 'At risk',
                  value: formatMoney(metrics?.revenue_at_risk_minor_units),
                  numericValue: metrics?.revenue_at_risk_minor_units ?? 0,
                },
                {
                  label: 'Expected recoverable',
                  value: formatMoney(metrics?.expected_recoverable_minor_units),
                  numericValue: metrics?.expected_recoverable_minor_units ?? 0,
                },
                {
                  label: 'Recovered',
                  value: formatMoney(metrics?.recovered_minor_units),
                  numericValue: metrics?.recovered_minor_units ?? 0,
                },
                {
                  label: 'Net recovery',
                  value: formatMoney(metrics?.net_recovery_minor_units),
                  numericValue: metrics?.net_recovery_minor_units ?? 0,
                },
              ]}
            />
            <div className="section-heading">
              <div>
                <h2>Operational view</h2>
                <p>
                  Freshness: {dashboard.freshness} · Last updated{' '}
                  {formatTimestamp(dashboard.last_updated_at)}
                </p>
              </div>
              <Badge tone={incidents.length ? 'warning' : 'success'}>
                {incidents.length
                  ? `${incidents.length} active incident${incidents.length === 1 ? '' : 's'}`
                  : 'Systems nominal'}
              </Badge>
            </div>
            <div className="content-grid">
              <CaseListCard
                cases={cases}
                casesError={casesError}
                sortByPriority={sortByPriority}
                status={caseStatus}
                source={caseSource}
                rootCause={caseRootCause}
                formatAmount={formatMoney}
                onRetry={() => void load()}
                onSelect={(caseId) => void loadCaseDetail(caseId)}
                onStatusChange={setCaseStatus}
                onSourceChange={setCaseSource}
                onRootCauseChange={setCaseRootCause}
                onSortChange={() => setSortByPriority((current) => !current)}
              />
              <Card>
                <CardHeader>
                  <CardTitle>Systemic degradation</CardTitle>
                </CardHeader>
                {incidentsError ? (
                  <ErrorState message={incidentsError} onRetry={() => void load()} />
                ) : incidents.length ? (
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
            <Card>
              <CardHeader>
                <CardTitle>Approval queue</CardTitle>
                <Badge>{approvals == null ? 'Unavailable' : `${approvals.length} pending`}</Badge>
              </CardHeader>
              {approvals?.length ? (
                <div className="data-list">
                  {approvals.map((approval) => (
                    <div className="data-row" key={approval.decision_id}>
                      <div>
                        <p>Case {approval.case_id.slice(0, 8)}</p>
                        <small>{approval.reason}</small>
                      </div>
                      <Badge tone="warning">
                        {formatMoney(approval.amount_at_risk_minor_units)}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState>
                  {approvals == null
                    ? 'Approval visibility is unavailable for this role.'
                    : 'No pending approvals.'}
                </EmptyState>
              )}
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Workflow telemetry</CardTitle>
                <Badge>{operationalMetrics ? 'Persisted' : 'Unavailable'}</Badge>
              </CardHeader>
              {operationalMetrics ? (
                <div className="data-list">
                  {Object.entries(operationalMetrics.metrics)
                    .filter(([, value]) => value > 0)
                    .slice(0, 8)
                    .map(([name, value]) => (
                      <div className="data-row" key={name}>
                        <p>{name.replaceAll('_', ' ')}</p>
                        <strong>{formatInteger(value)}</strong>
                      </div>
                    ))}
                  {!Object.values(operationalMetrics.metrics).some((value) => value > 0) ? (
                    <EmptyState>No persisted workflow activity yet.</EmptyState>
                  ) : null}
                </div>
              ) : (
                <EmptyState>Workflow telemetry is unavailable.</EmptyState>
              )}
            </Card>
            <AuditActivityCard
              events={
                auditEvents?.map((event) => ({
                  id: event.id,
                  eventType: event.event_type,
                  entityType: event.entity_type,
                  entityId: event.entity_id,
                  correlationId: event.correlation_id,
                })) ?? null
              }
            />
            <div className="content-grid">
              <IntegrationHealthCard health={health?.components ?? null} />
              <PolicySummaryCard policy={policy} />
            </div>
            {detailLoading ? <LoadingState label="Loading case details…" /> : null}
            {detailError ? <ErrorState message={detailError} /> : null}
            {selectedCase ? (
              <CaseDetailCard
                item={selectedCase}
                actionMessage={actionMessage}
                approvalMessage={approvalMessage}
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
                onResolveApproval={async (approved) => {
                  const policyDecision = selectedCase.policy_decisions.at(-1);
                  if (!policyDecision?.policy_version_id) return;
                  setApprovalMessage(null);
                  try {
                    const result = await api.resolveApproval(
                      selectedCase.id,
                      policyDecision.policy_version_id,
                      approved,
                    );
                    setApprovalMessage(
                      `${result.status ?? 'Processed'}: ${result.reason ?? 'approval recorded'}`,
                    );
                    await loadCaseDetail(selectedCase.id);
                  } catch (cause) {
                    setApprovalMessage(
                      cause instanceof Error
                        ? cause.message
                        : 'The approval decision could not be recorded.',
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
