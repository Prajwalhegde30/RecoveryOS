import { Badge } from './badge';
import { Button } from './button';
import { Card, CardHeader, CardTitle } from './card';

export type CaseDetailCardModel = {
  id: string;
  status: string;
  root_cause: string | null;
  recovery_probability: number | null;
  recovery_attempt_count: number;
  max_attempts: number;
  attempts: Array<{ status?: string; provider_reference?: string | null }>;
  recommendations: Array<{
    action_type?: string;
    rationale?: string;
    confidence?: number;
    source?: string;
  }>;
  policy_decisions: Array<{
    result?: string;
    reason?: string;
    policy_version_id?: string;
  }>;
  actions: Array<{ status?: string; failure_detail_safe?: string | null }>;
  timeline: Array<{
    event_type: string;
    reason: string;
    actor_type: string;
    correlation_id: string;
    created_at: string;
  }>;
};

export function CaseDetailCard({
  item,
  actionMessage,
  approvalMessage,
  onRequestAction,
  onResolveApproval,
}: {
  item: CaseDetailCardModel;
  actionMessage: string | null;
  approvalMessage: string | null;
  onRequestAction: () => Promise<void>;
  onResolveApproval: (approved: boolean) => Promise<void>;
}) {
  const latestPolicy = item.policy_decisions.at(-1);
  const pendingApproval = latestPolicy?.result === 'REQUIRE_APPROVAL';
  const canResolve = pendingApproval && latestPolicy.policy_version_id;

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
        {latestPolicy?.reason ?? 'No policy decision recorded yet.'}
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
            Decision: {latestPolicy?.result ?? 'pending'} · action:{' '}
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
        {canResolve ? (
          <>
            <Button type="button" onClick={() => void onResolveApproval(true)}>
              Approve action
            </Button>
            <Button type="button" onClick={() => void onResolveApproval(false)}>
              Reject action
            </Button>
            {approvalMessage ? <p className="case-detail-note">{approvalMessage}</p> : null}
          </>
        ) : null}
      </div>
    </Card>
  );
}
