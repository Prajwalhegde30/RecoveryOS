import type { Metadata } from 'next';
import '@recoveryos/ui/global.css';

export const metadata: Metadata = {
  title: 'RecoveryOS',
  description: 'AI revenue recovery decision and orchestration engine',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
