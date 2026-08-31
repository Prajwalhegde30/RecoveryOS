import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { MetricBarChart } from './metric-bar-chart';

describe('MetricBarChart', () => {
  it('renders persisted metric comparisons with proportional bars', () => {
    const markup = renderToStaticMarkup(
      <MetricBarChart
        title="Recovery value comparison"
        bars={[
          { label: 'At risk', value: '₹100', numericValue: 100 },
          { label: 'Recovered', value: '₹40', numericValue: 40 },
        ]}
      />,
    );

    expect(markup).toContain('Recovery value comparison');
    expect(markup).toContain('width:40%');
  });

  it('renders an honest empty state when no value exists', () => {
    expect(
      renderToStaticMarkup(<MetricBarChart title="Recovery value comparison" bars={[]} />),
    ).toContain('No persisted recovery value is available yet.');
  });
});
