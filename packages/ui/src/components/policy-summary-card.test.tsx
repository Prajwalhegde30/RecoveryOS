import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { PolicySummaryCard } from './policy-summary-card';

describe('PolicySummaryCard', () => {
  it('renders versioned policy controls and safe empty state', () => {
    const markup = renderToStaticMarkup(
      <PolicySummaryCard
        policy={{
          version: 4,
          status: 'ACTIVE',
          policy: {
            enabled_channels: ['email', 'sms'],
            max_contacts_per_case: 3,
            max_contacts_per_customer: 5,
            approval_threshold_minor_units: 100000,
          },
        }}
      />,
    );
    expect(markup).toContain('v4');
    expect(markup).toContain('email, sms');
    expect(markup).toContain('100000 minor units');
    expect(renderToStaticMarkup(<PolicySummaryCard policy={null} />)).toContain(
      'No active policy is available.',
    );
  });
});
