# Payment Service

## Project goal

Build a small, production-shaped payment service that can run locally with Docker Compose and be validated/deployed through a simple GitHub Actions pipeline. The first release must use Stripe test mode only and must never handle raw card details.

## Delivery plan

The project is delivered in two deliberately small stages:

### Stage 1: working demo transaction flow (implemented first)

- Provide a browser UI at `/` with amount, currency, description, and a Pay button.
- Call the existing `POST /payments` API from the UI.
- Store every transaction in PostgreSQL.
- Show `Payment successful`, `Payment rejected`, or `Payment is being processed`.
- Use the fake provider so the application works locally without payment credentials.
- Select the demo result with `FAKE_PAYMENT_OUTCOME=succeeded|failed|pending`.
- Clearly label the UI as demo mode; do not collect card details or claim that money moved.

### Stage 2: real Stripe test-mode flow (implemented)

- The UI switches to Stripe Payment Element when `PAYMENT_PROVIDER=stripe`.
- The backend creates a local pending transaction and a Stripe PaymentIntent.
- The browser confirms the payment using Stripe.js.
- Signed Stripe webhooks are used as the source of truth for final status.
- Approval and rejection can be tested with Stripe test cards.
- Keep raw card number, expiry, and CVV data outside this application.

The UI is intentionally simple in both stages. Demo mode proves the application, database, deployment, and user experience; Stripe test mode adds real payment-instrument handling without redesigning the core transaction model.

## Technology recommendation

- Node.js 22 LTS
- TypeScript
- Fastify
- PostgreSQL 16
- Drizzle ORM and SQL migrations
- Zod for request validation
- Vitest for tests
- Pino for structured logging
- Docker and Docker Compose
- GitHub Actions, runnable locally with [`act`](https://github.com/nektos/act)

Keep the code modular so the Stripe provider can later be replaced by another provider or a test fake.

## Functional scope

### Required endpoints

`GET /health`

Returns HTTP 200 when the process is alive.

`GET /ready`

Returns HTTP 200 only when the database is reachable.

`POST /payments`

Creates a payment using a provider adapter.

Request:

```json
{
  "amount": 2500,
  "currency": "AUD",
  "description": "Order #123"
}
```

Headers:

- `Idempotency-Key`: required; repeated requests with the same key must not create duplicate payments.

Response fields:

- `id`
- `amount`
- `currency`
- `description`
- `status`
- `providerPaymentId`
- `createdAt`
- `updatedAt`

`GET /payments/:id`

Returns a payment by internal ID.

`POST /webhooks/stripe`

Accepts Stripe webhook events. Verify the Stripe signature before processing an event. Webhook processing must be idempotent.

### Payment states

```text
pending -> succeeded
pending -> failed
pending -> cancelled
```

Do not allow arbitrary state transitions.

## Data model

Create a `payments` table containing at least:

- `id` UUID primary key
- `idempotency_key` unique text
- `amount` positive integer in the smallest currency unit
- `currency` three-character uppercase text
- `description` text
- `status` text or enum
- `provider` text
- `provider_payment_id` nullable text
- `created_at`
- `updated_at`

Create a `webhook_events` table containing at least:

- `id` UUID primary key
- `provider_event_id` unique text
- `event_type`
- `processed_at`
- `created_at`

Store no card number, CVV, full payment method details, or other sensitive payment data.

## Provider design

Define a `PaymentProvider` interface with operations for creating a payment and retrieving a payment. Implement:

1. `StripePaymentProvider` for Stripe test mode.
2. `FakePaymentProvider` for unit and integration tests.

Provider credentials must be loaded from environment variables and must never be committed.

## Error handling and security

- Validate all request bodies, parameters, and environment variables.
- Return consistent JSON errors with a stable error code.
- Use appropriate HTTP status codes: 400 for validation, 404 for missing resources, 409 for idempotency conflicts, and 500 for unexpected failures.
- Verify webhook signatures using the raw request body.
- Add request IDs and structured logs.
- Apply a basic request body size limit.
- Add CORS configuration only if required; default to restrictive behavior.
- Do not log secrets, webhook signatures, or sensitive payment data.

## Local development

Required tools:

- Node.js 22+
- Docker Desktop
- `act` for local GitHub Actions execution (optional but recommended)

Expected commands:

```bash
npm install
docker compose up -d postgres
npm run db:migrate
npm run dev
```

The service should be available at `http://localhost:3000`.

The repository should include `.env.example` with safe placeholder values:

```env
NODE_ENV=development
PORT=3000
DATABASE_URL=postgres://payment:payment@localhost:5432/payment
STRIPE_SECRET_KEY=sk_test_replace_me
STRIPE_WEBHOOK_SECRET=whsec_replace_me
```

`docker compose up` should start the application and PostgreSQL together for a simple local deployment. Add a persistent named volume for PostgreSQL.

## Scripts

Add these package scripts:

```text
dev         Start the development server
build       Compile TypeScript
start       Start the compiled server
lint        Run linting
typecheck   Run TypeScript checks
test        Run the test suite
test:watch  Run tests in watch mode
db:migrate  Apply database migrations
db:generate Generate ORM migration files
```

## GitHub Actions CI/CD

Create `.github/workflows/ci-cd.yml` with these jobs:

### `build`

Run on pull requests and pushes to `main`:

1. Checkout the repository.
2. Set up Node.js 22 with npm caching.
3. Install dependencies with `npm ci`.
4. Run `npm run lint`.
5. Build the application and Docker image.

### `test`

Run separately from `build` on pull requests and pushes to `main`:

1. Start a PostgreSQL service container.
2. Install dependencies and apply migrations.
3. Run `npm test`.

### `security`

Run after build and test:

- Audit production dependencies with `npm audit --omit=dev --audit-level=high`.
- Treat this scan as advisory for the demo. Record findings in the Actions log while keeping the build, lint, migrations, and tests as required deployment gates.

### `deploy-staging`

Run after `build`, `test`, and `security` on `main` using a self-hosted runner with Bash and Docker Compose:

1. Deploy the Compose stack as `payment-staging` on port 3001.
2. Use Bash to poll `/health` and `/ready` as smoke tests.

### `deploy-production`

Run after staging succeeds using the `production` GitHub Environment. Configure required reviewers so production requires approval. Deploy the production Compose stack on port 3000 and use Bash to poll `/health` and `/ready`.

The included workflow is designed for a project/demo VM or local self-hosted runner. For separate online staging and production VMs, replace the Compose deploy steps with SSH or cloud-provider deployment actions and keep separate environment secrets.

## Running Actions locally

Document the following workflow in `README.md`:

```bash
act -j ci
```

If service containers are unavailable in the local `act` setup, start PostgreSQL first with Docker Compose and provide `DATABASE_URL` through an `.env` file or `act` secret file. The workflow must still be valid on GitHub-hosted runners.

## Testing requirements

Include tests for:

- Health and readiness endpoints.
- Valid and invalid payment requests.
- Idempotent payment creation.
- Payment lookup and not-found behavior.
- Valid, duplicate, and invalid Stripe webhook events.
- Provider failure handling.
- Database persistence.

Tests must use the fake provider and test database fixtures; never call live Stripe APIs.

## Definition of done

- `docker compose up --build` starts the service and database locally.
- A payment can be created and retrieved using the documented API.
- Duplicate idempotency keys do not create duplicate payments.
- Webhook signatures are verified and duplicate events are ignored.
- No sensitive payment data is stored or logged.
- `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` pass.
- The GitHub Actions workflow passes on a clean repository.
- The CI job can be run locally with `act -j ci` when Docker is available.
- README documentation explains setup, environment variables, API usage, tests, and local Actions execution.

## Implementation order

1. Scaffold TypeScript, Fastify, configuration, logging, and Docker files.
2. Add PostgreSQL schema, migrations, and repository layer.
3. Add the provider interface and fake provider.
4. Implement payment endpoints and idempotency.
5. Add Stripe provider and signed webhook handling.
6. Add tests, OpenAPI documentation, and README instructions.
7. Add and locally validate the GitHub Actions workflow.
