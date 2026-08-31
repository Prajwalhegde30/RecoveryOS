import { describe, expect, it, vi } from 'vitest';

import { RecoveryOsApiClient, RecoveryOsApiError } from './recoveryos-api';

describe('RecoveryOsApiClient', () => {
  it('uses the authenticated typed boundary for reads and action requests', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ metrics: {}, freshness: 'live' }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'SCHEDULED' }), { status: 200 }),
      );
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.dashboard()).resolves.toEqual({ metrics: {}, freshness: 'live' });
    await expect(client.requestEmailAction('case/1')).resolves.toEqual({ status: 'SCHEDULED' });
    expect(fetcher).toHaveBeenLastCalledWith(
      'http://api.test/api/v1/cases/case%2F1/actions',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetcher.mock.calls[0]?.[1]).toEqual({
      headers: { Authorization: 'Bearer token' },
    });
  });

  it('reads the tenant-scoped approval queue', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.approvals()).resolves.toEqual([]);
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/v1/approvals',
      expect.objectContaining({ headers: { Authorization: 'Bearer token' } }),
    );
  });

  it('encodes status and source filters through the typed cases boundary', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.cases('WAITING', 'checkout.abandoned')).resolves.toEqual([]);
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/v1/cases?limit=50&status=WAITING&source=checkout.abandoned',
      expect.objectContaining({ headers: { Authorization: 'Bearer token' } }),
    );
  });

  it('encodes root-cause filtering through the typed cases boundary', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.cases(undefined, undefined, 'temporary_payment_failure')).resolves.toEqual(
      [],
    );
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/v1/cases?limit=50&root_cause=temporary_payment_failure',
      expect.objectContaining({ headers: { Authorization: 'Bearer token' } }),
    );
  });

  it('reads durable operational metrics through the typed boundary', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(JSON.stringify({ merchant_id: 'merchant-1', metrics: {} }), { status: 200 }),
      );
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.operationalMetrics()).resolves.toEqual({
      merchant_id: 'merchant-1',
      metrics: {},
    });
  });

  it('reads recent audit events through the typed boundary', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.audit(10)).resolves.toEqual([]);
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/v1/audit?limit=10',
      expect.objectContaining({ headers: { Authorization: 'Bearer token' } }),
    );
  });

  it('posts approval decisions through the authenticated case boundary', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ status: 'ALLOW' }), { status: 200 }));
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.resolveApproval('case/1', 'policy/1', true)).resolves.toEqual({
      status: 'ALLOW',
    });
    expect(fetcher).toHaveBeenCalledWith(
      'http://api.test/api/v1/cases/case%2F1/approvals',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('normalizes safe API errors with status', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: 'case not found' }), { status: 404 }),
      );
    const client = new RecoveryOsApiClient('http://api.test', 'token', fetcher);

    await expect(client.caseDetail('case-1')).rejects.toEqual(
      new RecoveryOsApiError('case not found', 404),
    );
  });
});
