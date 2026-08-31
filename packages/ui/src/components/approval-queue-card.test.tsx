import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { ApprovalQueueCard } from './approval-queue-card';

describe('ApprovalQueueCard', () => {
  it('renders review affordances and safe unavailable state', () => {
    const markup = renderToStaticMarkup(
      <ApprovalQueueCard
        approvals={[{ case_id: 'case-123456', amount_at_risk_minor_units: 2500, reason: 'review' }]}
        onSelect={() => undefined}
        formatAmount={(amount) => `₹${amount}`}
      />,
    );
    expect(markup).toContain('Case case-123');
    expect(markup).toContain('Review ₹2500');
    expect(
      renderToStaticMarkup(
        <ApprovalQueueCard approvals={null} onSelect={() => undefined} formatAmount={() => ''} />,
      ),
    ).toContain('Approval visibility is unavailable for this role.');
  });
});
