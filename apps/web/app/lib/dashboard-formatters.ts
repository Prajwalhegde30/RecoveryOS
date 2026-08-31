export function formatMoney(value: number | null | undefined) {
  return value == null
    ? '—'
    : new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
      }).format(value / 100);
}

export function formatWindow(window: Record<string, unknown>) {
  const rate = window.failure_rate_percent;
  return typeof rate === 'number' ? `${rate}% failure rate` : 'not available';
}

export function formatEvidence(evidence: Record<string, unknown>) {
  const source = evidence.source;
  return typeof source === 'string' ? source : 'detector evidence recorded';
}

export function formatInteger(value: number | null | undefined) {
  return value == null ? '—' : new Intl.NumberFormat('en-IN').format(value);
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

export function formatTimestamp(value: string) {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime())
    ? 'unavailable'
    : new Intl.DateTimeFormat('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(timestamp);
}
