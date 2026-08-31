import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import { CaseListCard } from './case-list-card';

describe('CaseListCard', () => {
  it('renders diagnosis, priority ordering, and filter controls', () => {
    const markup = renderToStaticMarkup(
      <CaseListCard
        cases={[
          {
            id: 'case-high',
            source_type: 'payment.failed',
            root_cause: 'temporary_payment_failure',
            status: 'WAITING',
            amount_at_risk_minor_units: 2500,
            priority_score: 0.9,
          },
        ]}
        casesError={null}
        sortByPriority
        status=""
        source=""
        rootCause=""
        formatAmount={(value) => `₹${value}`}
        onRetry={vi.fn()}
        onSelect={vi.fn()}
        onStatusChange={vi.fn()}
        onSourceChange={vi.fn()}
        onRootCauseChange={vi.fn()}
        onSortChange={vi.fn()}
      />,
    );

    expect(markup).toContain('temporary_payment_failure');
    expect(markup).toContain('Priority order');
    expect(markup).toContain('Filter cases by root cause');
  });

  it('renders a retryable error state without case rows', () => {
    const markup = renderToStaticMarkup(
      <CaseListCard
        cases={[]}
        casesError="Recovery cases are temporarily unavailable."
        sortByPriority
        status=""
        source=""
        rootCause=""
        formatAmount={(value) => `₹${value}`}
        onRetry={vi.fn()}
        onSelect={vi.fn()}
        onStatusChange={vi.fn()}
        onSourceChange={vi.fn()}
        onRootCauseChange={vi.fn()}
        onSortChange={vi.fn()}
      />,
    );

    expect(markup).toContain('Recovery cases are temporarily unavailable.');
    expect(markup).not.toContain('No recovery cases yet.');
  });
});
