import { Card } from './card';

export type MetricBar = {
  label: string;
  value: string;
  numericValue: number;
};

export function MetricBarChart({ title, bars }: { title: string; bars: MetricBar[] }) {
  const maximum = Math.max(...bars.map((bar) => Math.max(0, bar.numericValue)), 0);

  return (
    <Card className="metric-chart" aria-label={title}>
      <h2 className="ui-card-title">{title}</h2>
      {bars.length && maximum > 0 ? (
        <div className="metric-chart-list">
          {bars.map((bar) => {
            const percentage = Math.round((Math.max(0, bar.numericValue) / maximum) * 100);
            return (
              <div className="metric-chart-row" key={bar.label}>
                <div className="metric-chart-heading">
                  <span>{bar.label}</span>
                  <strong>{bar.value}</strong>
                </div>
                <div className="metric-chart-track" aria-hidden="true">
                  <span className="metric-chart-bar" style={{ width: `${percentage}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="ui-feedback">No persisted recovery value is available yet.</p>
      )}
    </Card>
  );
}
