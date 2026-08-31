import { Badge } from './badge';
import { Button } from './button';
import { Card, CardHeader, CardTitle } from './card';
import { EmptyState, ErrorState } from './feedback';

export type CaseListItem = {
  id: string;
  source_type: string;
  root_cause: string | null;
  status: string;
  amount_at_risk_minor_units: number;
  priority_score: number | null;
};

export function CaseListCard({
  cases,
  casesError,
  sortByPriority,
  status,
  source,
  rootCause,
  formatAmount,
  onRetry,
  onSelect,
  onStatusChange,
  onSourceChange,
  onRootCauseChange,
  onSortChange,
}: {
  cases: CaseListItem[];
  casesError: string | null;
  sortByPriority: boolean;
  status: string;
  source: string;
  rootCause: string;
  formatAmount: (value: number) => string;
  onRetry: () => void;
  onSelect: (caseId: string) => void;
  onStatusChange: (value: string) => void;
  onSourceChange: (value: string) => void;
  onRootCauseChange: (value: string) => void;
  onSortChange: () => void;
}) {
  const visibleCases = [...cases].sort((left, right) => {
    if (!sortByPriority) return 0;
    return (right.priority_score ?? -1) - (left.priority_score ?? -1);
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Priority recovery cases</CardTitle>
        <div className="card-actions">
          <label className="sr-only" htmlFor="case-status">
            Filter cases by status
          </label>
          <select
            id="case-status"
            value={status}
            onChange={(event) => onStatusChange(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="WAITING">Waiting</option>
            <option value="RECOVERED">Recovered</option>
            <option value="SUPPRESSED">Suppressed</option>
            <option value="UNRECOVERED">Unrecovered</option>
          </select>
          <label className="sr-only" htmlFor="case-source">
            Filter cases by source
          </label>
          <select
            id="case-source"
            value={source}
            onChange={(event) => onSourceChange(event.target.value)}
          >
            <option value="">All sources</option>
            <option value="payment.failed">Payment failure</option>
            <option value="checkout.abandoned">Checkout abandonment</option>
            <option value="subscription.payment_failed">Subscription failure</option>
            <option value="invoice.overdue">Overdue invoice</option>
          </select>
          <label className="sr-only" htmlFor="case-root-cause">
            Filter cases by root cause
          </label>
          <select
            id="case-root-cause"
            value={rootCause}
            onChange={(event) => onRootCauseChange(event.target.value)}
          >
            <option value="">All root causes</option>
            <option value="temporary_payment_failure">Temporary payment failure</option>
            <option value="issuing_bank_issue">Issuing bank issue</option>
            <option value="insufficient_funds">Insufficient funds</option>
            <option value="expired_card">Expired card</option>
            <option value="checkout_abandonment">Checkout abandonment</option>
            <option value="systemic_payment_degradation">Systemic payment degradation</option>
            <option value="unknown">Unknown</option>
          </select>
          <Button type="button" onClick={onSortChange}>
            {sortByPriority ? 'Priority order' : 'Newest order'}
          </Button>
          <Badge>{visibleCases.length} shown</Badge>
        </div>
      </CardHeader>
      {casesError ? (
        <ErrorState message={casesError} onRetry={onRetry} />
      ) : visibleCases.length ? (
        <div className="data-list">
          {visibleCases.map((item) => (
            <button
              className="data-row data-row-button"
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
            >
              <div>
                <p>
                  {item.id.slice(0, 8)} · {item.source_type.replaceAll('_', ' ')}
                </p>
                <small>
                  {formatAmount(item.amount_at_risk_minor_units)} at risk · priority{' '}
                  {item.priority_score ?? '—'} · {item.root_cause ?? 'root cause pending'}
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
  );
}
