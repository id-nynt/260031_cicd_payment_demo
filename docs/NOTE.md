# Payment service

## 1. Local run

Actions:

- Start Docker Desktop.
- Build and start app + PostgreSQL.
- Open the checkout UI.
- Make a fake payment.
- Check /health and /ready.
- Run the existing quality checks.

Commands:

    ```
    docker compose up -d --build
    docker compose ps

    # Then:
    npm ci
    npm run lint
    npm run typecheck
    npm test
    npm run build
    ```

## 2. Setup GitHub Actions self-hosted runner

### 2.1. Create GitHub repo

- Create GitHub repo for this project
- Connect to local project

  ```
  git init
  git add .
  git commit -m "Initial payment service"
  git branch -M main
  git remote add origin https://github.com/YOUR_USERNAME/payment-service.git
  git push -u origin main
  ```

- Check tab Actions: if there is the workflow

### 2.2. Install the self-hosted runner

- Go to GitHub repository → Settings → Actions → Runners → New self-hosted runner.
- Select Linux → x64.

- Open PowerShell and start Ubuntu:
  ```
  wsl -d Ubuntu
  cd ~/actions-runner-payment
  ```
- Follow GitHub's provided commands to download and configure the runner.
- Start it with:

  ```
  ./run.sh
  ```

- Check GitHub → Settings → Actions → Runners → runner should show Idle/Online.

Checkpoint: ✅ Self-hosted runner is online and waiting for GitHub Actions jobs.

### 2.3. Create GitHub environments

- Repository → Settings → Environments → New environment

- Create:
  ```
      staging
      production
  ```

### 2.4. Trigger the CI/CD

- Create some harmless update, then

  ```
  git add .
  git commit -m "Test CI/CD deployment"
  git push origin main
  ```

- GitHub → Repository → Actions
- Check if the workflow run successfully

### 2.5. Verify CI/CD

- Check the apps in each environment:
  ```
  Staging    -> http://localhost:3001/checkout
  Production -> http://localhost:3000/checkout
  ```
- Confirms containers really exist
  ```
  docker ps
  ```
- Heathchek
  ```
  Invoke-RestMethod http://localhost:3001/health
  Invoke-RestMethod http://localhost:3000/health
  ```

| Where                  | What you verify                                |
| ---------------------- | ---------------------------------------------- |
| GitHub Actions webpage | Pipeline actually completed                    |
| `docker ps` on laptop  | Deployment actually created running containers |
| Browser                | Deployed application is actually usable        |

## 3. Add and verify telemetry

### 3.1. Start OpenTelemetry

- OpenTelemetry is instrumented in the payment service.

- The app exports telemetry to the OpenTelemetry Collector every 5 seconds.

- The Collector exposes the received metrics at:

  ```
  http://127.0.0.1:9464/metrics
  ```

- Start the application, PostgreSQL and OpenTelemetry Collector:

  ```
  docker compose up -d --build
  ```

- Check that the application is ready:

  ```
  Invoke-RestMethod http://localhost:3000/ready
  ```

Checkpoint: ✅ Payment service and OpenTelemetry Collector are running.

### 3.2. Generate application traffic

- Generate successful payments, failed payments and an invalid HTTP request:

  ```
  npm run traffic:demo -- 3
  ```

- Wait for telemetry to be exported:

  ```
  Start-Sleep -Seconds 10
  ```

- This generates:

  ```
  3 successful payments
  3 rejected payments
  1 HTTP 400 request
  ```

### 3.3. View telemetry

- Show a simple telemetry summary:

  ```
  npm run telemetry:show
  ```

- Actual result:

  ```
  HTTP requests: 9 total, 7 to /payments
  HTTP errors: 1 (11.1%)
  Average HTTP latency: 10.13 ms
  Database readiness: ready (1)
  Payment outcomes: 3 succeeded, 3 failed
  ```

- Inspect the raw metrics exposed by the Collector:

  ```
  curl.exe -s http://127.0.0.1:9464/metrics | Select-String 'payment_'
  ```

- Inspect OpenTelemetry Collector logs:

  ```
  docker compose logs --tail=80 otel-collector
  ```

### 3.4. Verify telemetry flow

The current monitoring flow is:

```
Payment Service
    ↓
OpenTelemetry SDK
    ↓
OpenTelemetry Collector
    ↓
/metrics
```

The available telemetry includes:

| Metric                                       | Meaning                            |
| -------------------------------------------- | ---------------------------------- |
| `payment_http_requests_total`                | Number of HTTP requests            |
| `payment_http_errors_total`                  | Number of HTTP errors              |
| `payment_http_request_duration_milliseconds` | HTTP request latency               |
| `payment_service_ready`                      | Database/service readiness         |
| `payment_transactions_total`                 | Successful/failed payment outcomes |

Checkpoint: ✅ Real application activity produces observable telemetry that can later be consumed by the BDI framework.

### 3.5. Telemetry works after GitHub Actions

- Commit new change, Git push

- GitHub Actions

- deploy staging
  - staging app :3001
    ↓
  - staging OTel Collector :9465
    ↓
  - generate traffic
    ↓
  - see real staging metrics

  ```
  $env:PAYMENT_BASE_URL='http://localhost:3001'
  npm run traffic:demo -- 3
  Start-Sleep -Seconds 10

  curl.exe -s http://127.0.0.1:9465/metrics | Select-String 'payment_'
  ```

- deploy production
  - production app :3000
    ↓
  - production OTel Collector :9464
    ↓
  - generate traffic
    ↓
  - see real production metrics

  ```
  $env:PAYMENT_BASE_URL='http://localhost:3000'
  npm run traffic:demo -- 3
  Start-Sleep -Seconds 10

  curl.exe -s http://127.0.0.1:9464/metrics | Select-String 'payment_'
  ```
