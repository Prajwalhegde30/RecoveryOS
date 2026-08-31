import { Badge } from './badge';
import { Card, CardHeader, CardTitle } from './card';
import { EmptyState } from './feedback';

export type PolicySummary = {
  version: number;
  status: string;
  policy: Record<string, unknown>;
};

function display(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ');
  if (value === null || value === undefined || value === '') return 'Not exposed';
  return String(value);
}

export function PolicySummaryCard({ policy }: { policy: PolicySummary | null }) {
  return (
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
            <Badge tone={policy.status === 'ACTIVE' ? 'success' : 'warning'}>{policy.status}</Badge>
          </div>
          <div className="data-row">
            <div>
              <p>Configured channels</p>
              <small>{display(policy.policy.enabled_channels)}</small>
            </div>
          </div>
          <div className="data-row">
            <div>
              <p>Contact limits</p>
              <small>
                Per case: {display(policy.policy.max_contacts_per_case)} · Per customer:{' '}
                {display(policy.policy.max_contacts_per_customer)}
              </small>
            </div>
          </div>
          <div className="data-row">
            <div>
              <p>Approval threshold</p>
              <small>{display(policy.policy.approval_threshold_minor_units)} minor units</small>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState>No active policy is available.</EmptyState>
      )}
    </Card>
  );
}
