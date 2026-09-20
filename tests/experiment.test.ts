import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildApp } from '../src/app.js';
import { loadConfig } from '../src/config.js';
import { createExperiment } from '../src/experiment.js';
import { PaymentRepository } from '../src/payments.js';

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('controlled experiment modes', () => {
  it('returns an injected HTTP 503 for a valid fake payment in request fault mode', async () => {
    vi.spyOn(PaymentRepository.prototype, 'findByIdempotencyKey').mockResolvedValue(null);
    const app = buildApp(loadConfig({ DATABASE_URL: 'postgres://localhost/payment', EXPERIMENT_MODE: 'request_faults' }));
    try {
      const response = await app.inject({ method: 'POST', url: '/payments',
        headers: { 'idempotency-key': 'request-fault-test', 'x-experiment-fault': 'error' },
        payload: { amount: 100, currency: 'AUD', description: 'Fault test', payerName: 'Demo User',
          payerEmail: 'demo@example.com', provider: 'fake', demoCardNumber: '4242424242424242' } });
      expect(response.statusCode).toBe(503);
      expect(response.json().error).toBe('experiment_injected_failure');
    } finally { await app.close(); }
  });
  it('enables request faults only in the explicit experiment mode and clears with normal traffic', async () => {
    const experiment = createExperiment('request_faults');
    expect(experiment.isReady).toBe(true);
    expect(await experiment.beforeFakePayment(true)).toBe(true);
    expect(await experiment.beforeFakePayment(false)).toBe(false);
    expect(await createExperiment('normal').beforeFakePayment(true)).toBe(false);
  });
  it('keeps normal mode ready without injected failures', async () => {
    const experiment = createExperiment('normal');
    expect(experiment.isReady).toBe(true);
    expect(await experiment.beforeFakePayment()).toBe(false);
  });

  it('delays a fake payment by 800 ms in high_latency mode', async () => {
    vi.useFakeTimers();
    const experiment = createExperiment('high_latency');
    let finished = false;
    const payment = experiment.beforeFakePayment().then((failed) => {
      finished = true;
      return failed;
    });
    await vi.advanceTimersByTimeAsync(799);
    expect(finished).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(await payment).toBe(false);
  });

  it('fails exactly every third eligible fake payment', async () => {
    const experiment = createExperiment('high_error_rate');
    const outcomes = [];
    for (let index = 0; index < 6; index++) outcomes.push(await experiment.beforeFakePayment());
    expect(outcomes).toEqual([false, false, true, false, false, true]);
  });

  it('reports unhealthy readiness while liveness remains available', async () => {
    const config = loadConfig({ DATABASE_URL: 'postgres://localhost/payment', EXPERIMENT_MODE: 'unhealthy' });
    const app = buildApp(config);
    try {
      const health = await app.inject('/health');
      const ready = await app.inject('/ready');
      expect(health.statusCode).toBe(200);
      expect(health.json()).toMatchObject({ deploymentRunId: 'local', experimentMode: 'unhealthy' });
      expect(ready.statusCode).toBe(503);
      expect(ready.json()).toMatchObject({ error: 'experiment_unhealthy' });
    } finally {
      await app.close();
    }
  });
});
