import React from 'react';

import { Button } from '@recoveryos/ui';

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">RecoveryOS</p>
        <h1 id="page-title">Revenue recovery control plane</h1>
        <p className="lede">
          The merchant dashboard foundation is ready. Recovery workflows will be added through the
          phased implementation plan.
        </p>
        <Button type="button">View implementation status</Button>
      </section>
    </main>
  );
}
