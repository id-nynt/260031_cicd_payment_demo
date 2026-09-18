import { setTimeout as delay } from 'node:timers/promises';
import type { Config } from './config.js';

// The counter is scoped to one app instance and resets when that instance restarts.
export function createExperiment(mode: Config['EXPERIMENT_MODE']) {
  let fakePaymentAttempts = 0;

  return {
    isReady: mode !== 'unhealthy',
    async beforeFakePayment(): Promise<boolean> {
      if (mode === 'high_latency') await delay(800);
      if (mode === 'high_error_rate') return ++fakePaymentAttempts % 3 === 0;
      return false;
    }
  };
}
