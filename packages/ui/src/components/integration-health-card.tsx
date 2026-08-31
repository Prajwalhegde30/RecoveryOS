import { Badge } from './badge';
import { Card, CardHeader, CardTitle } from './card';
import { EmptyState } from './feedback';

export type IntegrationHealth = Record<string, { status: string; detail: string }>;

export function IntegrationHealthCard({ health }: { health: IntegrationHealth | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Integration health</CardTitle>
        <Badge>{health ? 'Live checks' : 'Unavailable'}</Badge>
      </CardHeader>
      {health ? (
        <div className="data-list">
          {Object.entries(health).map(([name, component]) => (
            <div className="data-row" key={name}>
              <div>
                <p>{name.replaceAll('_', ' ')}</p>
                <small>{component.detail}</small>
              </div>
              <Badge tone={component.status === 'healthy' ? 'success' : 'warning'}>
                {component.status}
              </Badge>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState>Integration health is unavailable.</EmptyState>
      )}
    </Card>
  );
}
