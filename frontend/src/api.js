const BASE = '/api';

async function requestJson(path, options) {
  const response = await fetch(`${BASE}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = typeof payload === 'object' && payload !== null
      ? payload.detail || payload.message
      : payload;
    throw new Error(message || `${response.status} ${response.statusText}`);
  }

  return payload;
}

export async function getConfig() {
  return requestJson('/config');
}

export async function getHealth() {
  return requestJson('/health');
}

export async function startWarmup() {
  return requestJson('/warmup/start', { method: 'POST' });
}

export async function getWarmupStatus() {
  return requestJson('/warmup/status');
}

export async function runDetect() {
  return requestJson('/detect/run', { method: 'POST' });
}

export async function recoverService(serviceName) {
  return requestJson(`/recover?service_name=${encodeURIComponent(serviceName)}`, {
    method: 'POST',
  });
}

export async function getIncidents() {
  return requestJson('/incidents');
}

export async function getLatestIncident() {
  return requestJson('/latest');
}

export async function injectChaos(service, scenario) {
  return requestJson(
    `/chaos/inject?service=${encodeURIComponent(service)}&scenario=${encodeURIComponent(scenario)}`,
    { method: 'POST' },
  );
}

export async function cleanupChaos() {
  return requestJson('/chaos/cleanup', { method: 'POST' });
}
