import type { ButtonHTMLAttributes } from 'react';

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`button ${className}`.trim()}
      style={{
        border: 0,
        borderRadius: 'var(--radius-md)',
        background: 'var(--color-primary)',
        color: 'var(--color-primary-foreground)',
        cursor: 'pointer',
        padding: '0.7rem 1rem',
      }}
      {...props}
    />
  );
}
