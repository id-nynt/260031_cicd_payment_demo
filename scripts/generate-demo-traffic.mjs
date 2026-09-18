import { randomUUID } from 'node:crypto';

const baseUrl = process.env.PAYMENT_BASE_URL ?? 'http://localhost:3000';
const count = Number(process.argv[2] ?? 3);
if (!Number.isInteger(count) || count < 1 || count > 100) {
  throw new Error('Pass a repeat count between 1 and 100, for example: npm run traffic:demo -- 5');
}

async function createPayment(card, expectedStatus) {
  const response = await fetch(baseUrl + '/payments', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': randomUUID()
    },
    body: JSON.stringify({
      amount: 5000,
      currency: 'AUD',
      payerName: 'Demo Customer',
      payerEmail: 'demo@example.com',
      description: 'Telemetry demonstration',
      provider: 'fake',
      demoCardNumber: card
    })
  });
  const payment = await response.json();
  if (response.status !== 201 || payment.status !== expectedStatus) {
    throw new Error(`Expected HTTP 201 and ${expectedStatus}; got HTTP ${response.status} and ${JSON.stringify(payment)}`);
  }
  console.log(`POST /payments: HTTP ${response.status}, payment ${payment.status}, id ${payment.id}`);
}

const ready = await fetch(baseUrl + '/ready');
if (!ready.ok) throw new Error(`Service not ready: HTTP ${ready.status}`);
console.log(`GET /ready: HTTP ${ready.status}`);

for (let index = 0; index < count; index++) {
  await createPayment('4242424242424242', 'succeeded');
  await createPayment('4000000000000002', 'failed');
}

const invalid = await fetch(baseUrl + '/payments', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ amount: 5000 })
});
if (invalid.status !== 400) throw new Error(`Expected HTTP 400 for invalid request; got ${invalid.status}`);
console.log('POST /payments: HTTP 400, missing idempotency key');
console.log('Metrics are exported every 5 seconds. Inspect the collector /metrics endpoint after a short wait.');

