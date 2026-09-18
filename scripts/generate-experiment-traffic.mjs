import { randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';

const baseUrl = process.env.PAYMENT_BASE_URL ?? 'http://localhost:3000';
const mode = process.argv[2] ?? 'normal';
const count = Number(process.argv[3] ?? 6);
const modes = ['normal', 'high_latency', 'high_error_rate', 'unhealthy'];
if (!modes.includes(mode)) throw new Error(`Mode must be one of: ${modes.join(', ')}`);
if (!Number.isInteger(count) || count < 3 || count > 100) throw new Error('Pass a request count between 3 and 100');

const health = await fetch(`${baseUrl}/health`);
if (health.status !== 200) throw new Error(`Expected /health HTTP 200, got ${health.status}`);
const ready = await fetch(`${baseUrl}/ready`);
if (mode === 'unhealthy') {
  if (ready.status !== 503) throw new Error(`Expected /ready HTTP 503, got ${ready.status}`);
  console.log('GET /health: HTTP 200; GET /ready: HTTP 503 (intentional unhealthy mode)');
} else {
  if (ready.status !== 200) throw new Error(`Expected /ready HTTP 200, got ${ready.status}`);
  console.log('GET /health: HTTP 200; GET /ready: HTTP 200');
  let succeeded = 0;
  let injectedFailures = 0;
  for (let index = 0; index < count; index++) {
    const started = performance.now();
    const response = await fetch(`${baseUrl}/payments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
      body: JSON.stringify({
        amount: 5000,
        currency: 'AUD',
        description: 'V2 controlled experiment',
        payerName: 'Demo Customer',
        payerEmail: 'demo@example.com',
        provider: 'fake',
        demoCardNumber: '4242424242424242'
      })
    });
    const durationMs = Math.round(performance.now() - started);
    const body = await response.json();
    if (response.status === 201 && body.status === 'succeeded') succeeded++;
    else if (mode === 'high_error_rate' && response.status === 503 && body.error === 'experiment_injected_failure') injectedFailures++;
    else throw new Error(`Unexpected HTTP ${response.status}: ${JSON.stringify(body)}`);
    if (mode === 'high_latency' && durationMs < 700) throw new Error(`Expected at least 700 ms, got ${durationMs} ms`);
    console.log(`POST /payments: HTTP ${response.status}, ${durationMs} ms`);
  }
  if (mode === 'high_error_rate' && injectedFailures === 0) throw new Error('Expected at least one injected HTTP 503');
  if (mode !== 'high_error_rate' && injectedFailures > 0) throw new Error('Unexpected injected HTTP 503');
  console.log(`Summary: ${succeeded} succeeded, ${injectedFailures} injected HTTP 503`);
}
console.log('Wait 10-20 seconds for OpenTelemetry export and Prometheus scrape.');
