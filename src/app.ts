import Fastify from 'fastify';
import { randomUUID } from 'node:crypto';
import rawBody from 'fastify-raw-body';
import { z } from 'zod';
import type Stripe from 'stripe';
import type { Config } from './config.js';
import { createPool } from './db/pool.js';
import { PaymentRepository } from './payments.js';
import { createProviders, StripePaymentProvider } from './providers.js';
import { checkoutPage, receiptPage } from './ui.js';
import { paymentPage } from './payment-page.js';
import { createTelemetry } from './telemetry.js';
import { createExperiment } from './experiment.js';

const paymentInput = z.object({
  amount: z.number().int().positive(),
  currency: z.string().length(3).transform((value) => value.toUpperCase()),
  description: z.string().trim().min(1).max(500),
  payerName: z.string().trim().min(2).max(120),
  payerEmail: z.string().email().max(255),
  provider: z.enum(['fake', 'stripe']).default('fake'),
  demoCardNumber: z.string().optional()
});
const idSchema = z.string().uuid();

export function buildApp(config: Config) {
  const app = Fastify({ logger: true, bodyLimit: 1024 * 1024 });
  const pool = createPool(config);
  const repository = new PaymentRepository(pool);
  const experiment = createExperiment(config.EXPERIMENT_MODE);
  const telemetry = createTelemetry(app, pool, config);
  const providers = createProviders(config);
  const allowedProviders = config.PAYMENT_PROVIDER === 'both' ? ['fake', 'stripe'] : [config.PAYMENT_PROVIDER];
  const providerFor = (name: 'fake' | 'stripe') => name === 'stripe' ? providers.stripe : providers.fake;

  app.register(rawBody, { field: 'rawBody', global: false, encoding: false, runFirst: true });
  app.get('/', async (_request, reply) => reply.redirect('/checkout'));
  app.get('/checkout', async (_request, reply) => reply.type('text/html').send(checkoutPage));
  app.get('/payment', async (_request, reply) => reply.type('text/html').header('cache-control', 'no-store').send(paymentPage));
  app.get('/receipt', async (_request, reply) => reply.type('text/html').send(receiptPage));
  app.get('/config', async () => ({ providers: allowedProviders.filter((name) => name !== 'stripe' || Boolean(providers.stripe)), stripeReady: Boolean(providers.stripe), publishableKey: providers.stripe ? config.STRIPE_PUBLISHABLE_KEY : null, merchantName: config.MERCHANT_NAME }));
  app.get('/legacy', async (_request, reply) => reply.type('text/html').send(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Service</title><style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:760px;margin:48px auto;padding:0 24px;color:#172033;background:#f7f9fc}
main{background:white;border:1px solid #e3e8f0;border-radius:16px;padding:32px;box-shadow:0 8px 30px #17203312}h1{margin-top:0}code{background:#eef2f7;padding:3px 6px;border-radius:5px}a{color:#155eef;text-decoration:none}a:hover{text-decoration:underline}.badge{display:inline-block;background:#e8f7ee;color:#137333;border-radius:999px;padding:5px 10px;font-size:14px}
</style></head><body><main><span class="badge">Payment API online</span><h1>Payment Service</h1>
<p>A small payment API running with a safe test provider. Use the API endpoints below to create and inspect payments.</p>
<h2>Checks</h2><ul><li><a href="/health"><code>/health</code></a> — process health</li><li><a href="/ready"><code>/ready</code></a> — database readiness</li></ul>
<h2>API</h2><p><code>POST /payments</code> creates a payment. It requires an <code>Idempotency-Key</code> header.</p>
<p>Amounts are expressed in the smallest currency unit. For example, <code>2500 AUD</code> means AUD 25.00.</p>
</main></body></html>`));
  app.get('/health', async () => ({ status: 'ok' }));
  app.get('/ready', async (_request, reply) => {
    if (!experiment.isReady) return reply.code(503).send({ error: 'experiment_unhealthy', message: 'Service is intentionally not ready' });
    try { await pool.query('SELECT 1'); return { status: 'ready' }; }
    catch { return reply.code(503).send({ error: 'database_unavailable', message: 'Database is not ready' }); }
  });

  app.post<{ Body: unknown }>('/payments', async (request, reply) => {
    const key = request.headers['idempotency-key'];
    if (typeof key !== 'string' || key.length < 8 || key.length > 255) return reply.code(400).send({ error: 'invalid_idempotency_key', message: 'Idempotency-Key must be 8-255 characters' });
    const parsed = paymentInput.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'validation_error', message: parsed.error.issues[0]?.message ?? 'Invalid request' });
    const existing = await repository.findByIdempotencyKey(key);
    if (existing) return reply.send(existing);
    try {
      const paymentId = randomUUID();
      if (!allowedProviders.includes(parsed.data.provider)) return reply.code(400).send({ error: 'provider_not_available', message: 'Selected provider is not enabled' });
      if (parsed.data.provider === 'fake' && (!parsed.data.demoCardNumber || !/^\d{16}$/.test(parsed.data.demoCardNumber.replace(/\s/g, '')))) return reply.code(400).send({ error: 'invalid_demo_card', message: 'Enter a 16-digit demo card number' });
      const selectedProvider = providerFor(parsed.data.provider);
      if (!selectedProvider) return reply.code(400).send({ error: 'provider_not_available', message: 'Selected provider is not configured' });
      if (parsed.data.provider === 'fake' && await experiment.beforeFakePayment()) {
        return reply.code(503).send({ error: 'experiment_injected_failure', message: 'Demo payment temporarily unavailable' });
      }
      const external = await selectedProvider.createPayment({ ...parsed.data, paymentId });
      const card = parsed.data.demoCardNumber?.replace(/\s/g, '');
      const payment = await repository.create({ ...parsed.data, id: paymentId, idempotencyKey: key, provider: selectedProvider.name, providerPaymentId: external.id, receiverName: config.MERCHANT_NAME, maskedPaymentMethod: card ? `•••• ${card.slice(-4)}` : null });
      const updated = external.status === 'pending' ? payment : await repository.updateStatus(payment.id, external.status, external.id);
      telemetry.recordPayment(selectedProvider.name, (updated ?? payment).status);
      return reply.code(201).send(updated ?? payment);
    } catch (error) {
      request.log.error(error, 'payment creation failed');
      return reply.code(500).send({ error: 'payment_creation_failed', message: 'Payment could not be created' });
    }
  });

  app.post<{ Body: unknown }>('/payments/intent', async (request, reply) => {
    if (!(providers.stripe instanceof StripePaymentProvider)) return reply.code(404).send({ error: 'stripe_not_enabled', message: 'Stripe provider is not enabled' });
    const key = request.headers['idempotency-key'];
    if (typeof key !== 'string' || key.length < 8 || key.length > 255) return reply.code(400).send({ error: 'invalid_idempotency_key', message: 'Idempotency-Key must be 8-255 characters' });
    const parsed = paymentInput.safeParse({ ...(request.body as object), provider: 'stripe' });
    if (!parsed.success) return reply.code(400).send({ error: 'validation_error', message: parsed.error.issues[0]?.message ?? 'Invalid request' });
    const existing = await repository.findByIdempotencyKey(key);
    if (existing) return reply.send({ payment: existing, clientSecret: null });
    const paymentId = randomUUID();
    try {
      const payment = await repository.create({ ...parsed.data, id: paymentId, idempotencyKey: key, provider: 'stripe', receiverName: config.MERCHANT_NAME });
      const intent = await providers.stripe.createPaymentIntent({ ...parsed.data, paymentId });
      const updated = await repository.updateStatus(payment.id, intent.status, intent.id);
      telemetry.recordPayment('stripe', (updated ?? payment).status);
      return reply.code(201).send({ payment: updated ?? payment, clientSecret: intent.clientSecret });
    } catch (error) {
      request.log.error(error, 'Stripe payment intent creation failed');
      return reply.code(500).send({ error: 'payment_intent_creation_failed', message: 'Payment could not be started' });
    }
  });

  app.get<{ Params: { id: string } }>('/payments/:id', async (request, reply) => {
    if (!idSchema.safeParse(request.params.id).success) return reply.code(400).send({ error: 'invalid_payment_id', message: 'Payment ID must be a UUID' });
    const payment = await repository.findById(request.params.id);
    return payment ? reply.send(payment) : reply.code(404).send({ error: 'payment_not_found', message: 'Payment not found' });
  });

  app.post<{ Headers: { 'stripe-signature'?: string } }>('/webhooks/stripe', { config: { rawBody: true } }, async (request, reply) => {
    if (!(providers.stripe instanceof StripePaymentProvider)) return reply.code(404).send({ error: 'stripe_not_enabled', message: 'Stripe provider is not enabled' });
    const signature = request.headers['stripe-signature'];
    if (!signature || !request.rawBody) return reply.code(400).send({ error: 'invalid_webhook', message: 'Missing webhook signature' });
    let event: Stripe.Event;
    const raw = Buffer.isBuffer(request.rawBody) ? request.rawBody : Buffer.from(request.rawBody);
    try { event = providers.stripe.constructEvent(raw, signature, config.STRIPE_WEBHOOK_SECRET!); }
    catch { return reply.code(400).send({ error: 'invalid_webhook', message: 'Invalid webhook signature' }); }
    if (!(await repository.recordWebhook(event.id, event.type))) return reply.send({ received: true, duplicate: true });
    const object = event.data.object as { metadata?: { paymentId?: string }; id?: string };
    const paymentId = object.metadata?.paymentId;
    if (paymentId && event.type === 'payment_intent.succeeded') {
      if (await repository.updateStatus(paymentId, 'succeeded', object.id)) telemetry.recordPayment('stripe', 'succeeded');
    }
    if (paymentId && event.type === 'payment_intent.payment_failed') {
      if (await repository.updateStatus(paymentId, 'failed', object.id)) telemetry.recordPayment('stripe', 'failed');
    }
    return reply.send({ received: true });
  });

  app.addHook('onClose', async () => { await telemetry.shutdown(); await pool.end(); });
  return app;
}
