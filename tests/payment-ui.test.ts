import { describe, expect, it } from 'vitest';
import { Script } from 'node:vm';
import { paymentPage } from '../src/payment-page.js';

const inlineScript = paymentPage.split('<script>').at(-1)?.split('</script>')[0] ?? '';

describe('payment page', () => {
  it('has parseable browser JavaScript and shows the checkout summary', () => {
    const elements = new Map<string, Record<string, unknown>>();
    const getElementById = (id: string) => {
      if (!elements.has(id)) elements.set(id, { value: '', hidden: false, disabled: false, textContent: '' });
      return elements.get(id);
    };
    let submit: ((event: { preventDefault: () => void }) => Promise<void>) | undefined;
    getElementById('payment-form')!.addEventListener = (_name: string, handler: typeof submit) => { submit = handler; };
    getElementById('card-number')!.value = '4242 4242 4242 4242';
    getElementById('expiry')!.value = '12/34';
    getElementById('cvc')!.value = '123';
    const location = { href: '', origin: 'http://localhost:3000' };
    let requestBody: Record<string, unknown> | undefined;
    const checkout = {
      amount: 5000, currency: 'AUD', payerName: 'Alex Customer',
      payerEmail: 'alex@example.com', description: 'Demo payment', provider: 'fake'
    };
    new Script(inlineScript).runInNewContext({
      document: { getElementById },
      localStorage: { getItem: () => JSON.stringify(checkout) },
      location,
      crypto: { randomUUID: () => '12345678-1234-1234-1234-123456789abc' },
      fetch: async (_url: string, options: { body: string }) => {
        requestBody = JSON.parse(options.body);
        return { ok: true, json: async () => ({ id: '12345678-1234-1234-1234-123456789abc' }) };
      }
    });

    expect(getElementById('summary')!.textContent).toBe('50.00 AUD - Alex Customer - fake');
    expect(submit).toBeTypeOf('function');
    return submit!({ preventDefault: () => {} }).then(() => {
      expect(requestBody?.demoCardNumber).toBe('4242424242424242');
      expect(location.href).toBe('/receipt?id=12345678-1234-1234-1234-123456789abc');
      expect(getElementById('card-number')!.value).toBe('4242 4242 4242 4242');
    });
  });
});

