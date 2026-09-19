# Payment Service

A small payment-service demonstration that can run locally, in Docker, on a VM, or through a GitHub Actions CI/CD pipeline. Its research controller can generate a Jason BDI agent from pipeline, goal, and project configuration; that agent selects each CI/CD entity while GitHub Actions executes the selected work.

See [the BDI controller guide](bdi-cicd-framework/README.md), [manual execution guide](docs/BDI_MANUAL_EXECUTION_GUIDE.md), [architecture audit](docs/BDI_ARCHITECTURE_AUDIT_AND_PLAN.md), and [experiment results](docs/BDI_CONTROLLER_EXPERIMENT_RESULTS.md).

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
- OpenTelemetry measurements for HTTP traffic, latency, errors, database readiness, and payment outcomes.
- Prometheus server with a query UI and seven-day local metric retention.
- Optional v2 fault modes for repeatable CI/CD and telemetry experiments; normal behaviour remains the default.
- REST endpoints for creating, viewing, and processing payments.
- Docker Compose packaging for repeatable local and server deployment.
- CI/CD entity jobs for build, tests, advisory dependency audit, staging, and production, selected by a persistent Jason/BDI controller; the earlier gate chain remains available only as an explicitly enabled legacy workflow.

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
4. Build and start the application, PostgreSQL, OpenTelemetry Collector, and Prometheus.
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

Stop the stack while keeping database and Prometheus data:

```powershell
docker compose down
```

Stop the stack and remove the local database and Prometheus volumes:

```powershell
docker compose down -v
```

The last command deletes local demo transaction data and metric history; use it only when that is intended.

## Observe real telemetry

The Docker stack starts an OpenTelemetry Collector and a real Prometheus server. The app sends metrics to the collector over OTLP/HTTP every 5 seconds. Prometheus scrapes the collector every 5 seconds and keeps seven days of history in a Docker volume. The collector also writes debug summaries to its Docker logs:

```text
Browser or traffic script -> Payment Service -> OpenTelemetry SDK
                   -> OTLP/HTTP -> Collector -> Prometheus -> query UI/history
                                             -> collector logs
```

The collector's raw metrics endpoint is bound to `127.0.0.1:9464` and the Prometheus UI to `127.0.0.1:9090` by default. Both are accessible only on the Docker host. The OTLP receiver is available only inside the Compose network.

### Actions: local verification

1. Start the Docker stack. Wait until `/ready` responds with `{"status":"ready"}`.
2. Open `http://localhost:3000/checkout`. Select `Demo card simulation` and make a successful payment with `4242 4242 4242 4242`.
3. Start another checkout and make a rejected payment with `4000 0000 0000 0002`. Both payment attempts should reach a receipt.
4. Optionally run the traffic helper to repeat these two outcomes three times and add one deliberately invalid HTTP request.
5. Wait about 5–10 seconds for the app to export metrics.
6. Open Prometheus and confirm that its collector target is UP. Run the queries below to inspect request counts, errors, latency, and health. You can also inspect raw measurements and collector logs.

### Commands: local verification (PowerShell)

```powershell
docker compose up -d --build
Invoke-RestMethod http://localhost:3000/ready
npm run traffic:demo -- 3
Start-Sleep -Seconds 10
npm run telemetry:show
```

Open `http://localhost:9090` in a browser. Under **Status > Target health** (or `/targets`), `payment-collector` should be **UP**. In the Prometheus query page, paste one expression at a time and click **Execute**. Use the **Table** view for current values or **Graph** for history. Wait 10–20 seconds after generating traffic for the app to export and Prometheus to scrape it.

| Question | PromQL expression |
|---|---|
| Is scraping working? | `up{job="payment-collector"}` — expect `1`. |
| How many payment API requests? | `sum(payment_http_requests_total{route="/payments"})` |
| HTTP error percentage across all routes since app start? | `100 * sum(payment_http_errors_total) / clamp_min(sum(payment_http_requests_total), 1)` |
| Mean HTTP latency across all routes, in milliseconds since app start? | `sum(payment_http_request_duration_milliseconds_sum) / clamp_min(sum(payment_http_request_duration_milliseconds_count), 1)` |
| Is the database reachable? | `payment_service_ready` — expect `1`. |
| How many fake payments succeeded or failed? | `sum by (status) (payment_transactions_total{provider="fake"})` |

For recent traffic rather than cumulative values, try `sum(rate(payment_http_requests_total[1m]))` or a one-minute average latency: `sum(rate(payment_http_request_duration_milliseconds_sum[1m])) / sum(rate(payment_http_request_duration_milliseconds_count[1m]))`. A graph needs at least two samples in the selected time window. Choose a time range that includes your test traffic.

You can also check the Prometheus API from PowerShell:

```powershell
Invoke-RestMethod 'http://localhost:9090/-/ready'
Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22payment-collector%22%7D'
```

Inspect the raw measurements and collector log:

```powershell
curl.exe -s http://127.0.0.1:9464/metrics | Select-String 'payment_http_requests_total|payment_http_errors_total|payment_http_request_duration_milliseconds_(sum|count)|payment_service_ready|payment_transactions_total'
docker compose logs --tail=80 otel-collector
docker compose logs --tail=80 app
```

The traffic helper requires Node.js 22 on the computer running it. The browser flow needs only Docker and a browser.

### What the measurements mean

| Measurement | What to look for |
|---|---|
| `payment_http_requests_total` | Completed requests grouped by method, route, and HTTP status. |
| `payment_http_errors_total` | Requests with HTTP 4xx or 5xx responses. Divide by total requests for the cumulative HTTP error percentage since app start. |
| `payment_http_request_duration_milliseconds_sum` and `_count` | Divide sum by count for average latency in milliseconds; `_bucket` lines show the distribution. |
| `payment_service_ready` | `1` when the service is ready and PostgreSQL is reachable; `0` when either check fails. Also check `/health` for process liveness. |
| `payment_transactions_total` | Recorded payment outcomes grouped by provider and `succeeded` or `failed` status. |

For example, the traffic helper with a count of `3` should add three successful and three rejected payments, plus one HTTP 400. A rejected demo payment returns HTTP 201 because it was recorded as a transaction; its business failure appears in `payment_transactions_total{status="failed"}`, not the HTTP error counter. Exact totals and latency vary with other traffic and service restarts.

### Alternate local ports

If ports `3000`, `5432`, `9464`, or `9090` are already occupied, use free host ports. For example:

```powershell
$env:APP_PORT='3300'
$env:POSTGRES_PORT='55432'
$env:METRICS_PORT='19464'
$env:PROMETHEUS_PORT='19090'
docker compose up -d --build
$env:PAYMENT_BASE_URL='http://127.0.0.1:3300'
$env:METRICS_URL='http://127.0.0.1:19464/metrics'
npm run traffic:demo -- 3
Start-Sleep -Seconds 10
npm run telemetry:show
```

With those overrides, open `http://localhost:19090` for Prometheus. Set the same port variables whenever you run `docker compose` commands for that stack.

### On the GitHub Actions runner

Staging uses app port `3001`, collector port `9465`, and Prometheus port `9091`; production uses app port `3000`, collector port `9464`, and Prometheus port `9090`. The deployment workflow verifies `/health`, `/ready`, collector request metrics, and that Prometheus reports its scrape target as UP. After deployment, use the payment UI repeatedly or run the traffic helper from your development computer with `PAYMENT_BASE_URL` set to the runner's reachable app URL.

Run these commands on the runner itself to inspect its local collector:

```bash
curl -fsS http://127.0.0.1:9465/metrics | grep '^payment_'   # staging
curl -fsS http://127.0.0.1:9464/metrics | grep '^payment_'   # production
curl -fsS http://127.0.0.1:9091/-/ready                  # staging Prometheus
curl -fsS http://127.0.0.1:9090/-/ready                  # production Prometheus
COMPOSE_PROJECT_NAME=payment-staging docker compose logs --tail=80 otel-collector
```

On the runner, open `http://localhost:9091` for staging or `http://localhost:9090` for production. From another computer, use an SSH tunnel, for example `ssh -L 9091:127.0.0.1:9091 user@RUNNER_IP`, then open `http://localhost:9091`. Do not expose the unauthenticated Prometheus UI publicly. The collector exporter supplies live cumulative measurements; Prometheus stores samples for seven days, even across app restarts. After a restart, allow a new export/scrape cycle before evaluating queries. `docker compose down -v` deletes the history.

## V2 controlled experiments

The `experiment-v2` branch adds `EXPERIMENT_MODE`. It defaults to `normal` and changes only the fake-payment path, except for the `unhealthy` readiness check. These are deliberate test faults, not real payment-provider failures. Do not use the fault modes with real card details or on a public service.

| Mode | Observable behaviour |
|---|---|
| `normal` | Existing fake checkout and receipt flow; `/health` and `/ready` return 200. |
| `high_latency` | Each new valid fake `POST /payments` waits 800 ms before processing. |
| `high_error_rate` | Every third new valid fake `POST /payments` returns HTTP 503 before a transaction is created. The per-instance counter resets when the app restarts. Other requests do not count. |
| `unhealthy` | `/health` remains 200, `/ready` returns 503, and `payment_service_ready` reports `0`. This is an intentional readiness failure; direct payment requests are not disabled. |

An ordinary rejected demo card remains HTTP 201 with payment status `failed`; it is **not** an injected HTTP error. The Stripe path is not delayed or failed by these modes. Reusing an existing idempotency key returns the existing payment and does not advance the error counter.

### Actions: test v2 without touching the baseline

1. Use the `experiment-v2` branch. Give its Compose stack a separate project name and host ports so existing staging/production containers and data stay untouched.
2. Start in `normal`, run the experiment traffic helper, then switch the app container through the other modes. Keep the same port and project variables in the PowerShell session.
3. Wait 10–20 seconds after traffic and inspect the Prometheus UI at `http://localhost:19091`.
4. Restore `normal` or stop only this isolated stack when finished.

### Commands: isolated PowerShell session

```powershell
$env:COMPOSE_PROJECT_NAME='payment-v2-check'
$env:APP_PORT='3301'
$env:POSTGRES_PORT='55433'
$env:METRICS_PORT='19465'
$env:PROMETHEUS_PORT='19091'
$env:PAYMENT_BASE_URL='http://127.0.0.1:3301'

$env:EXPERIMENT_MODE='normal'
docker compose up -d --build
npm run traffic:experiment -- normal 3

$env:EXPERIMENT_MODE='high_latency'
docker compose up -d --no-deps app
npm run traffic:experiment -- high_latency 3

$env:EXPERIMENT_MODE='high_error_rate'
docker compose up -d --no-deps app
npm run traffic:experiment -- high_error_rate 6

$env:EXPERIMENT_MODE='unhealthy'
docker compose up -d --no-deps app
npm run traffic:experiment -- unhealthy 3

# Restore normal operation after the experiment:
$env:EXPERIMENT_MODE='normal'
docker compose up -d --no-deps app
```

The helper checks expected responses and prints each request's duration. For `high_error_rate`, six sequential requests should include two HTTP 503s on a fresh app instance. For `high_latency`, each measured request should take at least 700 ms. For `unhealthy`, expect `/health` 200 and `/ready` 503. The helper needs Node.js 22; the checkout UI itself still needs only Docker and a browser.

Useful Prometheus queries after the export/scrape delay:

```promql
sum(payment_http_errors_total{route="/payments",status_code="503"})
sum(payment_http_requests_total{route="/payments",status_code="503"})
sum(payment_http_request_duration_milliseconds_sum{route="/payments"}) / sum(payment_http_request_duration_milliseconds_count{route="/payments"})
payment_service_ready
```

Prometheus keeps earlier samples, but instant queries show the current app instance. Use the Graph view and a time range covering the experiment to compare modes across restarts. To stop only the isolated stack while keeping its data, run `docker compose down` with the project and port variables still set. Do not use `down -v` unless you intend to delete this stack's payment records and metric history.

The CI/CD workflow uses `normal` for pushes and production. A manual `workflow_dispatch` run on `main` can select `high_error_rate` **for staging only**. Staging generates payments and waits for run-specific Prometheus samples; the BDI gate then blocks production on excessive HTTP errors or latency. A pull request runs build/test checks only. The existing production stack is left untouched when the gate blocks; this is pre-deployment avoidance, not an automatic rollback.

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

1. `build`: install dependencies, lint, compile TypeScript, and build the Docker image on a GitHub-hosted Ubuntu runner.
2. `test`: start PostgreSQL, apply migrations, and run tests in a separate GitHub-hosted job.
3. `security`: report high and critical production dependency findings with `npm audit`. This is advisory for the demo; findings appear in the job log but do not prevent deployment.
4. `deploy-staging`: build and deploy the fake provider, collector, and Prometheus on ports `3001`, `9465`, and `9091`; generate payments and wait for run-specific request rate, p95 latency, and readiness samples.
5. `bdi-gate`: on the self-hosted runner, read this Actions run and staging Prometheus, give the observations to Jason, and succeed only if the agent decides `allow`. `block` or unresolved `unknown` fails the job.
6. `deploy-production`: runs only after `bdi-gate` succeeds; deploys normal mode on ports `3000`, `9464`, and `9090` and checks the deployed run ID.

The deployment jobs build from the checked-out repository with Docker Compose. This simple pipeline does not require a container registry or a Trivy action. Both the build and test jobs must pass before deployment.

`build`, `test`, and `security` run on GitHub-hosted Ubuntu runners. Staging, the BDI gate, and production use your self-hosted runner. It needs Bash, Docker Compose, `curl`, network access to GitHub's API and Gradle/Maven downloads, and access to staging at `127.0.0.1:3001` and Prometheus at `127.0.0.1:9091`. The workflow installs Node 22 and Java 21 through official setup actions; the checked-in Gradle wrapper installs the pinned Gradle version. On Windows, install Git for Windows so Bash is available and keep Docker Desktop running for the runner account. On Linux, the runner account must be able to run `docker info` without `sudo`. The workflow does not use PowerShell.

### Actions

1. Push this repository to GitHub.
2. On the target machine, install Docker, the Docker Compose plugin, Git, Bash, and curl. Verify `docker info` works as the account running the runner service.
3. In GitHub, open `Settings > Actions > Runners > New self-hosted runner`.
4. Follow GitHub's displayed commands to download, configure, and start the runner.
5. Ensure the runner service remains online, has the `self-hosted` label, and has permission to run Docker commands.
6. Create GitHub Environments named `staging` and `production`.
7. Add a required reviewer to `production` if production deployment must be approved manually.
8. Push to `main` and watch the Actions run. A normal push can proceed all the way to production; use a protected production environment if you need human approval.

For the controlled experiment, use the [BDI experiment guide](docs/BDI_EXPERIMENT.md). It gives the exact normal/high-error dispatch commands, expected job outcomes, Prometheus checks, and limits of local versus live verification.

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

If Actions reports that it cannot resolve `aquasecurity/trivy-action` or `aquasecurity/setup-trivy`, GitHub is running an older workflow. This simplified workflow does not use those actions. Push the updated workflow to `main` and inspect the new run; rerunning an old commit uses the old workflow.

Before deployment on a local runner, check that ports `3000`, `3001`, `5432`, `5433`, `9464`, `9465`, `9090`, and `9091` are free on that machine. An already running local Compose stack may occupy production ports and prevent it from starting. The collector and Prometheus ports listen only on loopback.

On the runner, check the required tools and Docker access before triggering Actions:

```bash
docker info
docker compose version
curl --version
```

The staging checkout is at `http://RUNNER_IP:3001/checkout` and production is at `http://RUNNER_IP:3000/checkout` if those ports are reachable through the host firewall. `localhost` in the Actions smoke test means the runner machine itself, so it is not a public URL. Use a domain and HTTPS reverse proxy when making the app available online.

If Actions reports `pwsh: command not found`, GitHub is running an older workflow. Push the current workflow, which uses Bash for both deployment jobs, and inspect the new run.

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
