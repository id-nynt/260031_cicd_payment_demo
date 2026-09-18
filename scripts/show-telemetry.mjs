const metricsUrl = process.env.METRICS_URL ?? 'http://127.0.0.1:9464/metrics';
const response = await fetch(metricsUrl);
if (!response.ok) throw new Error(`Collector returned HTTP ${response.status}`);
const text = await response.text();

function samples(name) {
  return text.split('\n')
    .filter((line) => line.startsWith(name + '{') || line.startsWith(name + ' '))
    .map((line) => {
      const match = line.match(/^([^\s{]+)(?:\{([^}]*)\})?\s+([\d.eE+-]+)$/);
      return match ? { labels: match[2] ?? '', value: Number(match[3]) } : null;
    })
    .filter((sample) => sample !== null);
}
const total = (name, labelFragment = '') => samples(name)
  .filter((sample) => sample.labels.includes(labelFragment))
  .reduce((sum, sample) => sum + sample.value, 0);

const requests = total('payment_http_requests_total');
const errors = total('payment_http_errors_total');
const paymentRequests = total('payment_http_requests_total', 'route="/payments"');
const durationSum = total('payment_http_request_duration_milliseconds_sum');
const durationCount = total('payment_http_request_duration_milliseconds_count');
const ready = total('payment_service_ready');
const succeeded = total('payment_transactions_total', 'status="succeeded"');
const failed = total('payment_transactions_total', 'status="failed"');

if (!samples('payment_service_ready').length) {
  throw new Error('No payment-service metrics yet. Start the app, make requests, and wait about 5 seconds.');
}
console.log(`Collector: ${metricsUrl}`);
console.log(`HTTP requests: ${requests} total, ${paymentRequests} to /payments`);
console.log(`HTTP errors: ${errors} (${requests ? (100 * errors / requests).toFixed(1) : '0.0'}% of all requests since app start)`);
console.log(`Average HTTP latency: ${durationCount ? (durationSum / durationCount).toFixed(2) : 'n/a'} ms`);
console.log(`Database readiness: ${ready ? 'ready (1)' : 'not ready (0)'}`);
console.log(`Fake/Stripe payment outcomes: ${succeeded} succeeded, ${failed} failed`);
console.log('HTTP 4xx/5xx are errors; a rejected demo payment is a recorded business failure with HTTP 201.');
