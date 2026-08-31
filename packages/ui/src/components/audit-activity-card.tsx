import { Card, CardHeader, CardTitle } from './card';
import { EmptyState } from './feedback';

export type AuditActivity = {
  id: string;
  eventType: string;
  entityType: string;
  entityId: string;
  correlationId: string;
};

export function AuditActivityCard({ events }: { events: AuditActivity[] | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent audit activity</CardTitle>
      </CardHeader>
      {events?.length ? (
        <div className="data-list">
          {events.map((event) => (
            <div className="data-row" key={event.id}>
              <div>
                <p>{event.eventType.replaceAll('_', ' ')}</p>
                <small>
                  {event.entityType.replaceAll('_', ' ')} · {event.entityId.slice(0, 8)}
                </small>
              </div>
              <small>{event.correlationId.slice(0, 16)}</small>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState>
          {events === null
            ? 'Audit activity is unavailable for this role.'
            : 'No audit activity yet.'}
        </EmptyState>
      )}
    </Card>
  );
}
