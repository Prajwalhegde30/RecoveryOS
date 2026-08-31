import type { HTMLAttributes, PropsWithChildren } from 'react';

export function Badge({
  tone = 'neutral',
  children,
  className = '',
  ...props
}: PropsWithChildren<
  HTMLAttributes<HTMLSpanElement> & { tone?: 'neutral' | 'success' | 'warning' | 'danger' }
>) {
  return (
    <span className={`ui-badge ui-badge-${tone} ${className}`.trim()} {...props}>
      {children}
    </span>
  );
}
