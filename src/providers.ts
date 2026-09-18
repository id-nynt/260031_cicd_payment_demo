import Stripe from 'stripe';
import { hasStripeTestConfig, type Config } from './config.js';
import type { PaymentStatus } from './payments.js';

export type CreatePaymentInput = { amount: number; currency: string; description: string; payerEmail?: string; paymentId?: string };
export type ProviderPayment = { id: string; status: PaymentStatus };
export type PaymentIntentResult = { id: string; clientSecret: string; status: PaymentStatus };
export interface PaymentProvider {
  readonly name: string;
  createPayment(input: CreatePaymentInput): Promise<ProviderPayment>;
}

export class FakePaymentProvider implements PaymentProvider {
  readonly name = 'fake';
  constructor(private readonly outcome: PaymentStatus = 'succeeded') {}
  async createPayment(input: CreatePaymentInput & { demoCardNumber?: string }): Promise<ProviderPayment> {
    const card = input.demoCardNumber?.replace(/\s/g, '');
    const status = card?.endsWith('0002') ? 'failed' : card?.endsWith('9995') ? 'failed' : card?.endsWith('4242') ? 'succeeded' : this.outcome;
    return { id: `fake_${crypto.randomUUID()}`, status };
  }
}

export class StripePaymentProvider implements PaymentProvider {
  readonly name = 'stripe';
  private readonly stripe: Stripe;
  constructor(config: Config) { this.stripe = new Stripe(config.STRIPE_SECRET_KEY!); }
  async createPayment(input: CreatePaymentInput): Promise<ProviderPayment> {
    const intent = await this.stripe.paymentIntents.create({
      amount: input.amount, currency: input.currency.toLowerCase(), description: input.description,
      automatic_payment_methods: { enabled: true }, metadata: input.paymentId ? { paymentId: input.paymentId } : undefined
    });
    const status: PaymentStatus = intent.status === 'succeeded' ? 'succeeded' : 'pending';
    return { id: intent.id, status };
  }
  async createPaymentIntent(input: CreatePaymentInput): Promise<PaymentIntentResult> {
    const intent = await this.stripe.paymentIntents.create({
      amount: input.amount, currency: input.currency.toLowerCase(), description: input.description,
      receipt_email: input.payerEmail, metadata: input.paymentId ? { paymentId: input.paymentId } : undefined,
      automatic_payment_methods: { enabled: true }
    });
    return { id: intent.id, clientSecret: intent.client_secret!, status: intent.status === 'succeeded' ? 'succeeded' : 'pending' };
  }
  constructEvent(rawBody: Buffer, signature: string, secret: string): Stripe.Event {
    return this.stripe.webhooks.constructEvent(rawBody, signature, secret);
  }
}

export function createProviders(config: Config): { fake: FakePaymentProvider; stripe: StripePaymentProvider | null } {
  return { fake: new FakePaymentProvider(config.FAKE_PAYMENT_OUTCOME), stripe: hasStripeTestConfig(config) ? new StripePaymentProvider(config) : null };
}
