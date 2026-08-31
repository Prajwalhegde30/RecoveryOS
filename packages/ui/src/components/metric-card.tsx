import { Card } from './card';

export function MetricCard({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'success';
}) {
  return (
    <Card className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className={tone === 'success' ? 'metric-success' : ''}>{value}</strong>
    </Card>
  );
}
