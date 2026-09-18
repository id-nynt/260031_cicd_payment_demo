import { randomUUID } from 'node:crypto';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import type { Pool } from 'pg';
import type { Config } from './config.js';
import type { PaymentStatus } from './payments.js';

export type Telemetry = {
  recordPayment: (provider: string, status: PaymentStatus) => void;
  shutdown: () => Promise<void>;
};

export function createTelemetry(app: FastifyInstance, pool: Pool, config: Config): Telemetry {
  const endpoint = config.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT;
  if (!endpoint) {
    return { recordPayment: () => {}, shutdown: async () => {} };
  }

  const provider = new MeterProvider({
    resource: resourceFromAttributes({
      'service.name': config.OTEL_SERVICE_NAME,
      'service.instance.id': randomUUID(),
      'deployment.environment.name': config.OTEL_DEPLOYMENT_ENVIRONMENT
    }),
    readers: [new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({ url: endpoint }),
      exportIntervalMillis: 5000
    })]
  });
  const meter = provider.getMeter('payment-service');
  const requests = meter.createCounter('payment.http.requests', {
    description: 'Completed HTTP requests'
  });
  const errors = meter.createCounter('payment.http.errors', {
    description: 'Completed HTTP requests with 4xx or 5xx responses'
  });
  const duration = meter.createHistogram('payment.http.request.duration', {
    description: 'HTTP response time',
    unit: 'ms'
  });
  const paymentOutcomes = meter.createCounter('payment.transactions', {
    description: 'Recorded payment outcomes by provider and status'
  });
  const readiness = meter.createObservableGauge('payment.service.ready', {
    description: '1 when PostgreSQL is reachable, otherwise 0'
  });
  readiness.addCallback(async (result) => {
    try {
      await pool.query('SELECT 1');
      result.observe(1);
    } catch {
      result.observe(0);
    }
  });

  const started = new WeakMap<FastifyRequest, bigint>();
  app.addHook('onRequest', async (request) => {
    started.set(request, process.hrtime.bigint());
  });
  app.addHook('onResponse', async (request, reply) => {
    const start = started.get(request);
    const attributes = {
      method: request.method,
      route: request.routeOptions.url ?? 'unmatched',
      status_code: String(reply.statusCode)
    };
    requests.add(1, attributes);
    if (reply.statusCode >= 400) errors.add(1, attributes);
    if (start !== undefined) {
      duration.record(Number(process.hrtime.bigint() - start) / 1_000_000, attributes);
    }
  });

  return {
    recordPayment: (paymentProvider, status) => {
      if (status === 'succeeded' || status === 'failed') {
        try {
          paymentOutcomes.add(1, { provider: paymentProvider, status });
        } catch (error) {
          app.log.warn({ error }, 'payment telemetry could not be recorded');
        }
      }
    },
    shutdown: () => provider.shutdown()
  };
}
