import { setTimeout as delay } from 'node:timers/promises';
import type { Config } from './config.js';

// The counter is scoped to one app instance and resets when that instance restarts.
export function createExperiment(mode: Config['EXPERIMENT_MODE']) {
  let fakePaymentAttempts = 0;

  return {
    isReady: mode !== 'unhealthy',
    async beforeFakePayment(requestFault = false): Promise<boolean> {
      if (mode === 'request_faults' && requestFault) return true;
      if (mode === 'high_latency') await delay(800);
      if (mode === 'high_error_rate') return ++fakePaymentAttempts % 3 === 0;
      return false;
    }
  };
}
