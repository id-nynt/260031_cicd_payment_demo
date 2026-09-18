// One-shot scrape check. Staging retries this after generating new payment traffic.
const runId = process.env.CI_RUN_ID ?? 'local';
const prometheusUrl = process.env.PROMETHEUS_URL ?? 'http://127.0.0.1:9091';
if (!/^[A-Za-z0-9_.-]+$/.test(runId)) throw new Error('Invalid CI_RUN_ID');

async function value(query) {
  const url = new URL('/api/v1/query', prometheusUrl);
  url.searchParams.set('query', query);
  const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Prometheus HTTP ${response.status}`);
  const body = await response.json();
  if (body.status !== 'success' || !body.data?.result?.length) throw new Error('No Prometheus sample');
  const number = Number(body.data.result[0]?.value?.[1]);
  if (!Number.isFinite(number)) throw new Error('Non-finite Prometheus sample');
  return number;
}

try {
  const selector = `ci_run_id="${runId}",route="/payments"`;
  const rate = await value(`sum(rate(payment_http_requests_total{${selector}}[2m]))`);
  const p95 = await value(`histogram_quantile(0.95, sum by (le) (rate(payment_http_request_duration_milliseconds_bucket{${selector}}[2m])))`);
  const ready = await value(`min(payment_service_ready{ci_run_id="${runId}"})`);
  if (rate <= 0 || ready < 1) throw new Error(`Not ready: request rate=${rate}, readiness=${ready}`);
  if (process.env.EXPERIMENT_MODE === 'high_error_rate') {
    const failureRate = await value(`sum(rate(payment_http_errors_total{ci_run_id="${runId}",route="/payments",status_code="503"}[2m]))`);
    if (failureRate <= 0) throw new Error('Injected HTTP 503s are not visible in Prometheus yet');
  }
  console.log(`Fresh gate telemetry: run=${runId}, request_rate=${rate}, p95_ms=${p95}, readiness=${ready}`);
} catch (error) {
  console.error(`Gate telemetry not ready: ${error.message}`);
  process.exitCode = 1;
}
