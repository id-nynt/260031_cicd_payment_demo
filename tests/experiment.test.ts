import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildApp } from '../src/app.js';
import { loadConfig } from '../src/config.js';
import { createExperiment } from '../src/experiment.js';

afterEach(() => vi.useRealTimers());

describe('controlled experiment modes', () => {
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
