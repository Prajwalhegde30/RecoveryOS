const apiBaseUrl = process.env.API_BASE_URL ?? 'http://127.0.0.1:8000';
const token = process.env.DEMO_AUTH_TOKEN;
const seed = Number(process.env.DEMO_SEED ?? 20260901);
const runKey = process.env.DEMO_RUN_KEY ?? `seed:${seed}`;

if (!token || !Number.isInteger(seed)) {
  throw new Error('DEMO_AUTH_TOKEN and an integer DEMO_SEED are required');
}

const configuration = {
  seed,
  run_key: runKey,
  transaction_count: 6,
  amounts_minor_units: [249900, 1999000],
  payment_methods: ['upi', 'card'],
  failure_codes: ['UPI_TIMEOUT', 'CARD_DECLINED'],
  duplicate_event_indices: [1],
  opt_out_indices: [2],
  incident_indices: [3],
  natural_recovery_indices: [0],
  assisted_recovery_indices: [5],
  provider_failure_indices: [4],
};

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(`${path} returned ${response.status}: ${body.detail ?? 'error'}`);
  return body;
}

const run = await request('/api/v1/simulator/runs', {
  method: 'POST',
  body: JSON.stringify(configuration),
});
if (
  run.label !== 'synthetic_simulator_data' ||
  run.case_count !== configuration.transaction_count
) {
  throw new Error('demo simulator did not produce the configured persisted case batch');
}
if (run.recommendation_count !== run.case_count || run.duplicate_event_count < 1) {
  throw new Error('demo simulator did not exercise normal recommendation/idempotency paths');
}
const stored = await request(`/api/v1/simulator/runs/${encodeURIComponent(run.run_id)}`);
const dashboard = await request('/api/v1/dashboard');
if (
  stored.status !== 'COMPLETED' ||
  !dashboard.metrics ||
  typeof dashboard.metrics.revenue_at_risk_minor_units !== 'number'
) {
  throw new Error('demo workflow did not persist a completed run and derived dashboard metrics');
}
console.log(
  JSON.stringify({
    run_id: run.run_id,
    seed: run.seed,
    label: run.label,
    cases: run.case_count,
    recommendations: run.recommendation_count,
    duplicate_events: run.duplicate_event_count,
    success_events: run.success_event_count,
    revenue_at_risk_minor_units: dashboard.metrics.revenue_at_risk_minor_units,
    recovered_minor_units: dashboard.metrics.recovered_minor_units,
  }),
);
