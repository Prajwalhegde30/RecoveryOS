import { Badge } from './badge';
import { Button } from './button';
import { Card, CardHeader, CardTitle } from './card';
import { EmptyState } from './feedback';

export type ApprovalQueueItem = {
  case_id: string;
  amount_at_risk_minor_units: number;
  reason: string;
};

export function ApprovalQueueCard({
  approvals,
  onSelect,
  formatAmount,
}: {
  approvals: ApprovalQueueItem[] | null;
  onSelect: (caseId: string) => void;
  formatAmount: (minorUnits: number) => string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Approval queue</CardTitle>
        <Badge>{approvals == null ? 'Unavailable' : `${approvals.length} pending`}</Badge>
      </CardHeader>
      {approvals?.length ? (
        <div className="data-list">
          {approvals.map((approval) => (
            <div className="data-row" key={approval.case_id}>
              <div>
                <p>Case {approval.case_id.slice(0, 8)}</p>
                <small>{approval.reason}</small>
              </div>
              <Button type="button" onClick={() => onSelect(approval.case_id)}>
                Review {formatAmount(approval.amount_at_risk_minor_units)}
              </Button>
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
  );
}
