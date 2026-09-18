import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config.js';

describe('configuration', () => {
  it('loads safe fake-provider configuration', () => {
    const config = loadConfig({ DATABASE_URL: 'postgres://localhost/payment', PAYMENT_PROVIDER: 'fake' });
    expect(config.PAYMENT_PROVIDER).toBe('fake');
    expect(config.PORT).toBe(3000);
  });

  it('requires Stripe credentials when Stripe is enabled', () => {
    expect(() => loadConfig({ DATABASE_URL: 'postgres://localhost/payment', PAYMENT_PROVIDER: 'stripe' })).toThrow();
  });
});
