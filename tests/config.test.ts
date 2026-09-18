import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config.js';

describe('configuration', () => {
  it('loads safe fake-provider configuration', () => {
    const config = loadConfig({ DATABASE_URL: 'postgres://localhost/payment', PAYMENT_PROVIDER: 'fake' });
    expect(config.PAYMENT_PROVIDER).toBe('fake');
    expect(config.PORT).toBe(3000);
    expect(config.EXPERIMENT_MODE).toBe('normal');
    expect(config.CI_RUN_ID).toBe('local');
  });

  it('requires Stripe credentials when Stripe is enabled', () => {
    expect(() => loadConfig({ DATABASE_URL: 'postgres://localhost/payment', PAYMENT_PROVIDER: 'stripe' })).toThrow();
  });

  it('rejects unknown experiment modes', () => {
    expect(() => loadConfig({ DATABASE_URL: 'postgres://localhost/payment', EXPERIMENT_MODE: 'random' })).toThrow();
  });

  it('accepts safe CI run labels and rejects label injection', () => {
    expect(loadConfig({ DATABASE_URL: 'postgres://localhost/payment', CI_RUN_ID: '12345-2' }).CI_RUN_ID).toBe('12345-2');
    expect(() => loadConfig({ DATABASE_URL: 'postgres://localhost/payment', CI_RUN_ID: 'bad"label' })).toThrow();
  });
});
