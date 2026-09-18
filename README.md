# Payment Service

A small payment-service demonstration that can run locally, in Docker, on a VM, or through a GitHub Actions CI/CD pipeline.

The default deployment mode is `fake`. It simulates approval and rejection, stores payment records in PostgreSQL, and does not move real money. Stripe is an optional integration for test-mode payment instruments.

## Application introduction

The application provides:

- A three-step checkout flow:
  1. Customer and payment amount
  2. Payment method and provider
  3. Receipt and processing result
- Provider selection between `Fake / Demo` and `Stripe`.
- Fake payment approval and rejection using test card numbers.
- PostgreSQL persistence for payment records, payer/receiver information, status, and masked card details.
- Configurable merchant/receiver name.
- Health and readiness endpoints for deployment checks.
- REST endpoints for creating, viewing, and processing payments.
- Docker Compose packaging for repeatable local and server deployment.
- CI/CD stages for validation, tests, build, security scanning, image publishing, staging deployment, production deployment, and health checks.

The fake provider is the recommended starting point because it is usable without a Stripe account, API key, webhook, or external network dependency.

### User flow

1. Open `/checkout`.
2. Enter payer name, email, amount, currency, description, and provider.
3. Continue to `/payment`.
4. For the fake provider, enter any future expiry and CVC plus a supported demo card number.
5. Submit the payment.
6. View the receipt at `/receipt`.

Demo card outcomes:

- `4242 4242 4242 4242` approves the payment.
- `4000 0000 0000 0002` rejects the payment.
- Other valid-looking numbers use the configured `FAKE_PAYMENT_OUTCOME` value.

The application never stores the full card number. It stores only the masked last four digits for the fake flow. Do not use real card details with this demo.

### Important endpoints

| Endpoint | Purpose |
|---|---|
| `GET /checkout` | Checkout form |
| `GET /payment` | Payment-method form |
| `GET /receipt` | Payment result page |
| `GET /health` | Liveness check |
| `GET /ready` | Database/readiness check |
| `GET /config` | Available providers and Stripe readiness |
| `POST /payments` | Create and process a payment |
| `GET /payments/:id` | Read a payment |
| `POST /payments/intent` | Create a Stripe PaymentIntent |
| `POST /webhooks/stripe` | Receive signed Stripe webhook events |

## Prerequisites

For the simplest path, install:

- Docker Desktop on Windows or macOS, or Docker Engine and Compose on Linux.
- Git, if cloning the repository.
- A browser.

Node.js is only required when running the application directly or running the quality checks outside Docker.

## Run locally with Docker

### Actions

1. Open a terminal in the project directory.
2. Make sure Docker Desktop or Docker Engine is running.
3. Use the fake provider. No Stripe credentials are required.
4. Build and start the application and PostgreSQL database.
5. Open the checkout page in a browser.
6. Submit a demo payment using one of the demo cards above.

### Commands

PowerShell:

```powershell
docker compose up -d --build
docker compose ps
```

Open:

```text
http://localhost:3000/checkout
```

Check the service:

```powershell
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/ready
Invoke-RestMethod http://localhost:3000/config
```

### What you should see in the browser

#### Step 1: Checkout

Open `http://localhost:3000/checkout`. The page should show:

- A payment amount, normally pre-filled with `50.00`.
- Currency, normally `AUD`.
- Payer name and email.
- A description.
- A provider selector. Choose `Demo card simulation`.
- A receiver/merchant name, normally `Demo Merchant`.

Click `Continue to payment`. The browser should move to `/payment`. This is correct: the first page collects the transaction information, and the second page collects the payment method.

#### Step 2: Payment details

The payment page should show:

- A summary such as `50.00 AUD - Alex Customer - fake`.
- Cardholder name.
- Demo card number.
- Expiry.
- CVC.
- A blue `Pay now` button.
- A note saying that demo cards are simulated and never stored.

Enter the following values:

| Field | Value |
|---|---|
| Cardholder name | `Alex Customer` or any name |
| Demo card number | `4242 4242 4242 4242` |
| Expiry | `12/34` or another `MM/YY` value with month `01` to `12` |
| CVC | `123` or any 3/4 digit value |

Click `Pay now`. You should briefly see `Payment is being processed...`, then the browser should move to `/receipt?id=...`.

#### Step 3: Receipt

For card `4242 4242 4242 4242`, the receipt should show a green success result:

`Payment successful`

It should also show a transaction ID, amount, payer, receiver, provider `fake`, and a masked payment method ending in `4242`.

To test rejection, repeat the flow with `4000 0000 0000 0002`. The receipt should show a red result:

`Payment rejected`

#### If you remain on Payment details

The yellow box says `Payment is being processed...` while the request runs. A red box shows a validation or server error. Read the red text and correct the indicated field. Common causes are:

- The card number is not exactly 16 digits after spaces are removed.
- Expiry is not written as `MM/YY`, or the month is outside `01` to `12`.
- CVC is not 3 or 4 digits.
- The page was loaded from an old Docker image after a code change.

If the summary says `Loading payment summary...` indefinitely or the fields clear when you click Pay Now, the payment page's JavaScript did not start. The current version has a regression test for this and was rebuilt successfully; first make sure your browser is using the current container image.

After updating the project, rebuild the container and refresh the page:

```powershell
docker compose up -d --build
```

Then use `Ctrl+F5` in the browser, open `/checkout` again, select `Demo card simulation`, and repeat the three steps. Do not select Stripe unless `/config` reports `stripeReady: true`.

If the message still does not explain the problem, inspect the application log in another terminal while clicking `Pay now`:

```powershell
docker compose logs -f app
```

For a successful fake payment, the request to `POST /payments` should return a payment ID and the browser should immediately navigate to the receipt page.

View logs:

```powershell
docker compose logs -f app
```

Stop the application while keeping database data:

```powershell
docker compose down
```

Stop the application and remove the local database volume:

```powershell
docker compose down -v
```

The last command deletes local demo transaction data and should only be used when that is intended.

## Run quality checks locally

### Actions

Use this when changing application code or before pushing to GitHub.

1. Install dependencies.
2. Run linting, type checking, and tests.
3. Build the production TypeScript output.

### Commands

```powershell
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

To run the Node application directly, first start PostgreSQL and copy `.env.example` to `.env`, then run:

```powershell
npm run dev
```

Docker Compose is recommended because it starts both the application and its database consistently.

## Optional Stripe test mode

Stripe is not required for the fake deployment. You need Stripe test credentials only if you select `Stripe` in the UI or call the Stripe PaymentIntent endpoint.

Required values are:

- `STRIPE_SECRET_KEY`: Stripe test secret key beginning with `sk_test_`.
- `STRIPE_PUBLISHABLE_KEY`: Stripe test publishable key beginning with `pk_test_`.
- `STRIPE_WEBHOOK_SECRET`: signing secret beginning with `whsec_`.

### Actions

1. Create or access a Stripe test-mode account.
2. Copy the three test values into `.env`.
3. Set `PAYMENT_PROVIDER=both`.
4. Start a Stripe CLI webhook forwarder during local testing, or configure a public HTTPS webhook URL when deployed.
5. Restart the application.
6. Select Stripe in the checkout and use Stripe test card details.

### Commands

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build
```

Stripe must remain in test mode until the integration, webhook handling, refunds, reconciliation, and operational controls have been reviewed. The fake mode remains the dependable option for CI/CD and traffic testing.

## Deploy with Docker on a VM or server

This deployment is usable with fake transactions and does not require Stripe keys.

### Actions

1. Provision a Linux VM or another machine that can run Docker.
2. Install Docker Engine, Docker Compose, and Git.
3. Allow inbound traffic only to the application port or, preferably, to an HTTPS reverse proxy.
4. Do not expose PostgreSQL port `5432` to the public internet.
5. Clone the repository.
6. Create a server `.env` file using fake mode.
7. Start the stack and verify health.
8. Put Nginx, Caddy, or another reverse proxy in front of the app for HTTPS.
9. Configure database backups and monitoring.

### Commands

```bash
git clone <repository-url> payment-service
cd payment-service
cp .env.example .env
```

Edit `.env` and use values similar to:

```text
NODE_ENV=production
PORT=3000
DATABASE_URL=postgres://payment:change-this-password@db:5432/payment
PAYMENT_PROVIDER=fake
FAKE_PAYMENT_OUTCOME=succeeded
MERCHANT_NAME=Demo Merchant
```

Start and verify the service:

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:3000/health
curl --fail http://127.0.0.1:3000/ready
```

The service is then available at `http://SERVER_IP:3000` if that port is allowed through the firewall. For a real public URL, route HTTPS traffic from a domain to the container and keep port `5432` private.

Useful server operations:

```bash
docker compose logs -f app
docker compose restart app
docker compose pull
docker compose up -d --build
docker compose down
```

Before using a VM for important data, add encrypted PostgreSQL backups, log retention, TLS certificates, firewall rules, OS updates, and a secret-management process.

## Deploy with the local GitHub Actions runner

The workflow is `.github/workflows/ci-cd.yml`.

### Pipeline stages

1. `validate`: install dependencies, lint, migrate a PostgreSQL service, run tests, build, and build the Docker image.
2. `security`: run npm audit and Trivy filesystem vulnerability/secret scans.
3. `publish`: publish an image to GitHub Container Registry on pushes to `main`.
4. `deploy-staging`: deploy the fake provider to the self-hosted runner on port `3001`, then check `/health` and `/ready`.
5. `deploy-production`: deploy the fake provider on port `3000`, then check `/health` and `/ready`.

The current deployment jobs build from the checked-out repository with Docker Compose. The image publishing stage is included for registry use and future immutable-image deployment.

`validate`, `security`, and `publish` run on GitHub-hosted Ubuntu runners. Only the two deploy jobs run on your self-hosted runner. The deploy jobs use PowerShell (`pwsh`), so the runner machine must have PowerShell and Docker Compose available. On a Windows runner, Docker Desktop must be running for the runner account.

### Actions

1. Push this repository to GitHub.
2. On the target machine, install Docker and Git.
3. In GitHub, open `Settings > Actions > Runners > New self-hosted runner`.
4. Follow GitHub's displayed commands to download, configure, and start the runner.
5. Ensure the runner service remains online and has permission to run Docker commands.
6. Create GitHub Environments named `staging` and `production`.
7. Add a required reviewer to `production` if production deployment must be approved manually.
8. Push to `main` and watch the Actions run.

The included workflow uses fake transactions, so no Stripe secret is needed for the pipeline. If Stripe is later enabled, provide secrets through GitHub Environments and update the deployment job to create the server `.env` from those secrets. Never commit Stripe keys to the repository.

### Commands to push the project

Run these only if the repository has not already been connected to GitHub:

```powershell
git add .
git commit -m "Prepare payment service deployment"
git branch -M main
git remote add origin https://github.com/<owner>/<repository>.git
git push -u origin main
```

After the runner and GitHub Environments are configured, normal deployment is:

```powershell
git add .
git commit -m "Deploy application update"
git push origin main
```

If Actions reports `Unable to resolve action aquasecurity/trivy-action@0.28.0`, the workflow in GitHub is an older copy. The published release tag is `v0.28.0`, and this repository's workflow now uses `aquasecurity/trivy-action@v0.28.0`. Push the corrected workflow to `main` from your Git checkout, then inspect the new Actions run. Rerunning the old commit does not apply the corrected file.

Before deployment on a local runner, check that ports `3000`, `3001`, `5432`, and `5433` are free on that machine. An already running local Compose stack may occupy ports `3000` and `5432` and prevent production from starting.

## Monitoring and troubleshooting

Use these checks from the server:

```bash
curl --fail http://127.0.0.1:3000/health
curl --fail http://127.0.0.1:3000/ready
docker compose ps
docker compose logs --tail=200 app
```

An uptime monitor such as Uptime Kuma or UptimeRobot can check `/health`. Alert on a non-200 response, container restarts, high disk usage, failed backups, and database readiness failures.

Common issues:

- `Route GET:/ not found`: open `/checkout`; the application root redirects there in the current version.
- Payment appears stuck: check the browser developer console and `docker compose logs -f app`; fake payments should return immediately.
- Stripe is unavailable: confirm that real `sk_test_`, `pk_test_`, and `whsec_` values are configured. Placeholder values intentionally report `stripeReady: false`.
- Database is not ready: inspect `docker compose logs db`, then check `/ready` after PostgreSQL finishes starting.

## Current scope

This is a deployable payment-flow simulation and CI/CD test application. It is suitable for demonstrating checkout UX, API traffic, database persistence, health checks, Docker deployment, and pipeline promotion.

It is not a production payment processor. Production use would require a real provider account, secure secret storage, HTTPS, webhook verification, idempotency, refunds, reconciliation, audit logging, access control, rate limiting, alerting, backup recovery testing, and a compliance review.
