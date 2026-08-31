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
}

console.log(
  'RecoveryOS smoke E2E passed: API liveness/readiness and web shell responded correctly.',
);
