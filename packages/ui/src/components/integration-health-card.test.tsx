import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { IntegrationHealthCard } from './integration-health-card';

describe('IntegrationHealthCard', () => {
  it('renders safe provider health and unavailable state', () => {
    const markup = renderToStaticMarkup(
      <IntegrationHealthCard
        health={{
          simulated_payment: { status: 'healthy', detail: 'synthetic provider' },
          simulated_messaging: { status: 'degraded', detail: 'provider unavailable' },
        }}
      />,
    );
    expect(markup).toContain('simulated payment');
    expect(markup).toContain('provider unavailable');
    expect(renderToStaticMarkup(<IntegrationHealthCard health={null} />)).toContain(
      'Integration health is unavailable.',
    );
  });
});
