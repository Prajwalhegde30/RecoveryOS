const apiBaseUrl = process.env.API_BASE_URL ?? 'http://127.0.0.1:8000';
const webBaseUrl = process.env.WEB_BASE_URL ?? 'http://127.0.0.1:3000';

async function assertResponse(url, expectedText) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
  const body = await response.text();
  if (expectedText && !body.includes(expectedText)) {
    throw new Error(`${url} did not contain expected smoke text: ${expectedText}`);
  }
  return response;
}

async function assertAuthenticatedRead(url, token, expectedStatus = 200) {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status !== expectedStatus) {
    throw new Error(`${url} returned HTTP ${response.status}; expected ${expectedStatus}`);
  }
  return response;
}

async function assertAuthenticatedJson(url, token, options = {}, expectedStatus = 200) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
  if (response.status !== expectedStatus) {
    throw new Error(`${url} returned HTTP ${response.status}; expected ${expectedStatus}`);
  }
  return response.json();
}

await assertResponse(`${apiBaseUrl}/health/live`, '"status":"ok"');
await assertResponse(`${apiBaseUrl}/health/ready`, '"status":"ok"');
await assertResponse(webBaseUrl, 'Revenue recovery control plane');

const authToken = process.env.E2E_AUTH_TOKEN;
if (authToken) {
  const routes = ['/api/v1/dashboard', '/api/v1/cases', '/api/v1/health/operational'];
  for (const route of routes) {
    await assertAuthenticatedRead(`${apiBaseUrl}${route}`, authToken);
  }
  const metrics = await assertAuthenticatedRead(`${apiBaseUrl}/api/v1/health/metrics`, authToken);
  const payload = await metrics.json();
  if (!payload || typeof payload.metrics !== 'object') {
    throw new Error('authenticated operational metrics response was not a typed object');
  }
  console.log('Authenticated RecoveryOS read E2E passed: dashboard, cases, health, and metrics.');

  const simulatorPayload = process.env.E2E_SIMULATOR_PAYLOAD;
  if (simulatorPayload) {
    let configuration;
    try {
      configuration = JSON.parse(simulatorPayload);
    } catch {
      throw new Error('E2E_SIMULATOR_PAYLOAD must be valid JSON');
    }
    const run = await assertAuthenticatedJson(`${apiBaseUrl}/api/v1/simulator/runs`, authToken, {
      method: 'POST',
      body: JSON.stringify(configuration),
    });
    if (run.label !== 'synthetic_simulator_data' || typeof run.run_id !== 'string') {
      throw new Error('simulator E2E did not return a labeled persisted run');
    }
    if (!Array.isArray(run.case_ids) || typeof run.case_count !== 'number') {
      throw new Error('simulator E2E did not return typed case facts');
    }
    if (
      Array.isArray(configuration.duplicate_event_indices) &&
      configuration.duplicate_event_indices.length > 0 &&
      (typeof run.duplicate_event_count !== 'number' || run.duplicate_event_count < 1)
    ) {
      throw new Error('simulator E2E did not persist duplicate-event facts');
    }
    if (
      Array.isArray(configuration.assisted_recovery_indices) &&
      configuration.assisted_recovery_indices.length > 0 &&
      run.scenario_counts?.assisted_recovery !== configuration.assisted_recovery_indices.length
    ) {
      throw new Error('simulator E2E did not produce the requested assisted-recovery outcomes');
    }
    const storedRun = await assertAuthenticatedJson(
      `${apiBaseUrl}/api/v1/simulator/runs/${encodeURIComponent(run.run_id)}`,
      authToken,
    );
    if (storedRun.run_id !== run.run_id || storedRun.status !== 'COMPLETED') {
      throw new Error('simulator E2E run status was not durably completed');
    }
    const cases = await assertAuthenticatedJson(`${apiBaseUrl}/api/v1/cases?limit=50`, authToken);
    if (
      !Array.isArray(cases) ||
      !run.case_ids.every((caseId) => cases.some((item) => item.id === caseId))
    ) {
      throw new Error('simulator E2E cases were not visible through the tenant-scoped API');
    }
    const dashboard = await assertAuthenticatedJson(`${apiBaseUrl}/api/v1/dashboard`, authToken);
    if (!dashboard.metrics || typeof dashboard.metrics !== 'object') {
      throw new Error('simulator E2E dashboard metrics were not typed persisted facts');
    }
    if (
      Array.isArray(configuration.assisted_recovery_indices) &&
      configuration.assisted_recovery_indices.length > 0 &&
      typeof dashboard.metrics.assisted_recovered_minor_units !== 'number'
    ) {
      throw new Error('simulator E2E dashboard did not expose assisted recovery metrics');
    }
    console.log('Authenticated RecoveryOS simulator vertical-slice E2E passed.');
  }
}

console.log(
  'RecoveryOS smoke E2E passed: API liveness/readiness and web shell responded correctly.',
);
