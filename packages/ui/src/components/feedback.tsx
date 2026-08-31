import type { PropsWithChildren } from 'react';

export function LoadingState({ label = 'Loading recovery data…' }: { label?: string }) {
  return (
    <p className="ui-feedback" role="status">
      {label}
    </p>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="ui-feedback ui-feedback-error" role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button className="ui-link-button" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ children }: PropsWithChildren) {
  return <div className="ui-feedback">{children}</div>;
}
