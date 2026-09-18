import { randomUUID } from 'node:crypto';
import type pg from 'pg';

export type PaymentStatus = 'pending' | 'succeeded' | 'failed' | 'cancelled';
export type Payment = {
  id: string; idempotencyKey: string; amount: number; currency: string; description: string;
  status: PaymentStatus; provider: string; providerPaymentId: string | null; payerName: string; payerEmail: string;
  receiverName: string; maskedPaymentMethod: string | null; createdAt: string; updatedAt: string;
};

type Row = Record<string, unknown>;
function mapPayment(row: Row): Payment {
  return {
    id: row.id as string, idempotencyKey: row.idempotency_key as string, amount: row.amount as number,
    currency: row.currency as string, description: row.description as string, status: row.status as PaymentStatus,
    provider: row.provider as string, providerPaymentId: (row.provider_payment_id as string | null),
    payerName: row.payer_name as string, payerEmail: row.payer_email as string, receiverName: row.receiver_name as string,
    maskedPaymentMethod: row.masked_payment_method as string | null,
    createdAt: (row.created_at as Date).toISOString(), updatedAt: (row.updated_at as Date).toISOString()
  };
}

export class PaymentRepository {
  constructor(private readonly pool: pg.Pool) {}

  async findById(id: string): Promise<Payment | null> {
    const result = await this.pool.query('SELECT * FROM payments WHERE id = $1', [id]);
    return result.rows[0] ? mapPayment(result.rows[0]) : null;
  }

  async findByIdempotencyKey(key: string): Promise<Payment | null> {
    const result = await this.pool.query('SELECT * FROM payments WHERE idempotency_key = $1', [key]);
    return result.rows[0] ? mapPayment(result.rows[0]) : null;
  }

  async create(input: { id?: string; idempotencyKey: string; amount: number; currency: string; description: string; provider: string; providerPaymentId?: string | null; payerName: string; payerEmail: string; receiverName: string; maskedPaymentMethod?: string | null }): Promise<Payment> {
    const result = await this.pool.query(
      `INSERT INTO payments (id, idempotency_key, amount, currency, description, status, provider, provider_payment_id, payer_name, payer_email, receiver_name, masked_payment_method)
       VALUES ($1, $2, $3, $4, $5, 'pending', $6, $7, $8, $9, $10, $11) RETURNING *`,
      [input.id ?? randomUUID(), input.idempotencyKey, input.amount, input.currency, input.description, input.provider, input.providerPaymentId ?? null, input.payerName, input.payerEmail, input.receiverName, input.maskedPaymentMethod ?? null]
    );
    return mapPayment(result.rows[0]);
  }

  async updateStatus(id: string, status: PaymentStatus, providerPaymentId?: string | null): Promise<Payment | null> {
    const result = await this.pool.query(
      `UPDATE payments SET status = $2, provider_payment_id = COALESCE($3, provider_payment_id), updated_at = NOW()
       WHERE id = $1 RETURNING *`, [id, status, providerPaymentId ?? null]
    );
    return result.rows[0] ? mapPayment(result.rows[0]) : null;
  }

  async recordWebhook(providerEventId: string, eventType: string): Promise<boolean> {
    const result = await this.pool.query(
      `INSERT INTO webhook_events (id, provider_event_id, event_type) VALUES ($1, $2, $3)
       ON CONFLICT (provider_event_id) DO NOTHING`, [randomUUID(), providerEventId, eventType]
    );
    return result.rowCount === 1;
  }
}
