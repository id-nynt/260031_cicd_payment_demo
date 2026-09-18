import { z } from 'zod';

const schema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().min(1),
  PAYMENT_PROVIDER: z.enum(['fake', 'stripe', 'both']).default('fake'),
  FAKE_PAYMENT_OUTCOME: z.enum(['succeeded', 'failed', 'pending']).default('succeeded'),
  MERCHANT_NAME: z.string().min(1).default('Demo Merchant'),
  OTEL_SERVICE_NAME: z.string().min(1).default('payment-service'),
  OTEL_DEPLOYMENT_ENVIRONMENT: z.string().min(1).default('local'),
  OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: z.string().url().optional(),
  STRIPE_SECRET_KEY: z.string().optional(),
  STRIPE_PUBLISHABLE_KEY: z.string().optional(),
  STRIPE_WEBHOOK_SECRET: z.string().optional()
});

export type Config = z.infer<typeof schema>;

export function hasStripeTestConfig(config: Pick<Config, 'STRIPE_SECRET_KEY' | 'STRIPE_PUBLISHABLE_KEY' | 'STRIPE_WEBHOOK_SECRET'>): boolean {
  const secret = config.STRIPE_SECRET_KEY;
  const publishable = config.STRIPE_PUBLISHABLE_KEY;
  const webhook = config.STRIPE_WEBHOOK_SECRET;
  return Boolean(
    secret?.startsWith('sk_test_') && !secret.includes('...') && !secret.endsWith('replace_me') &&
    publishable?.startsWith('pk_test_') && !publishable.includes('...') && !publishable.endsWith('replace_me') &&
    webhook?.startsWith('whsec_') && !webhook.includes('...') && !webhook.endsWith('replace_me')
  );
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const config = schema.parse(env);
  if (config.PAYMENT_PROVIDER === 'stripe' && !hasStripeTestConfig(config)) {
    throw new Error('STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, and STRIPE_WEBHOOK_SECRET are required when PAYMENT_PROVIDER=stripe');
  }
  return config;
}
