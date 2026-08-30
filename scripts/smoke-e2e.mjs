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

await assertResponse(`${apiBaseUrl}/health/live`, '"status":"ok"');
await assertResponse(`${apiBaseUrl}/health/ready`, '"status":"ok"');
await assertResponse(webBaseUrl, 'Revenue recovery control plane');
console.log(
  'RecoveryOS smoke E2E passed: API liveness/readiness and web shell responded correctly.',
);
