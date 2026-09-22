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

## 4. Experiments

### 4.0. Mental model

The most important mental model is this:

```text
You start run_controller.py
        ↓
Jason BDI agent starts
        ↓
Jason chooses an entity: build
        ↓
Java environment
        ↓
GitHub Actions dispatch
        ↓
GitHub executes Build entity
        ↓
result comes back to Java/Jason
        ↓
Jason chooses next entity
        ↓
...
staging deployment
        ↓
OpenTelemetry → Prometheus
        ↓
Java reads telemetry
        ↓
Jason decides continue / wait / stop
        ↓
production
        ↓
telemetry
        ↓
achieved OR rollback
```

The manual explicitly says **Jason decides the order; Java does not**, while GitHub executes the entity Jason selected.

### 4.0. After turning on your laptop: understand what needs to be running

There are really **four systems** involved:

```text
1. Your Windows/controller terminal
   └─ Python launcher + Jason + Java

2. GitHub
   └─ receives workflow_dispatch
      and records Actions runs

3. Your Linux self-hosted runner
   └─ receives deployment jobs from GitHub
      and uses Docker

4. Docker
   ├─ staging app
   ├─ staging OTel/Prometheus
   ├─ production app
   └─ production OTel/Prometheus
```

You don't manually start build/test/security/staging/production. **The controller is supposed to cause GitHub Actions to execute them.**

The manual requires Python/PyYAML, JDK 21+, Docker/Compose, and a Linux runner. The controller should run from your durable project checkout, **not from the runner's `_work` directory**.

---

# PHASE 1 — Prepare the machine

### 1. Start Docker Desktop

After turning on your laptop, first start **Docker Desktop** and wait until the Docker engine is ready.

Check:

```powershell
docker ps
docker compose ls -a
```

Don't worry if the payment containers are stopped initially.

Also, **don't click Play on the Docker images**. Those are images, not your complete Compose deployment.

For this experiment, Docker should ultimately contain two logical stacks:

```text
payment-staging
payment-production
```

The manual expects:

```text
staging app        localhost:3001
staging Prometheus localhost:9091

production app        localhost:3000
production Prometheus localhost:9090
```

---

### 2. Make sure the GitHub runner is running

Your Linux self-hosted runner must be online.

On GitHub:

**Repository → Settings → Actions → Runners**

You want:

```text
bdi-demo
Online / Idle

labels:
self-hosted
Linux
X64
payment-deploy
```

The manual specifically says the runner needs the `payment-deploy` label.

If it says **Offline**, the runner process/service isn't connected to GitHub. GitHub also documents that an online matching self-hosted runner is required for a job to be assigned. ([GitHub Docs][1])

On the runner machine, also verify:

```bash
docker ps
docker compose version
```

This matters because **GitHub Actions runs the deployment job on this machine, and that job uses Docker**.

---

# PHASE 2 — Make sure you have the correct code

### 3. Do NOT use the old `main` yet

This is particularly important given the error you just encountered.

The manual says:

> Complete repair = `fix/bdi-controller-runtime`

and says to **review and merge this branch before tagging v1**.

So first:

```powershell
git fetch origin
git switch fix/bdi-controller-runtime
git pull origin fix/bdi-controller-runtime
```

Then:

```powershell
py -3 bdi-cicd-framework/run_controller.py --help
```

According to the manual, the correct version must support commands such as:

```text
--gui
--baseline
--known-good
--confirm-compatible-rollback
```

### This is currently your first blocker.

Earlier you ran:

```text
run_controller.py: error:
unrecognized arguments: --gui --baseline
```

So **do not proceed to the experiment until this discrepancy is resolved**.

The manual requires:

```powershell
py -3 bdi-cicd-framework/run_controller.py --gui --baseline ...
```

Therefore, if your latest `fix/bdi-controller-runtime` still doesn't support that command, **the code and manual are inconsistent**. Fix that first rather than trying to work around it.

---

# PHASE 3 — Test BDI locally BEFORE GitHub

### 4. Run the local BDI rehearsal

Once the correct controller is present, run:

```powershell
py -3 bdi-cicd-framework/run_controller.py `
    --gui `
    --scenario production_unhealthy
```

This is **not GitHub Actions yet**.

It is:

```text
real Jason
real generated agent
simulated jobs
simulated telemetry
```

Expected:

```text
normal jobs
↓
production telemetry = block
↓
BDI_DECISION=rollback
↓
rollback
↓
BDI_RECOVERY=restored
↓
BDI_CONTROLLER_RESULT=stopped recovery=restored
```

The manual explicitly says this scenario creates **no GitHub runs or deployments**.

This test answers:

> **“Does my BDI reasoning work?”**

It does **not** answer:

> “Does BDI control GitHub Actions?”

---

### 5. Run the regression tests

Then:

```powershell
py -3 -m unittest discover `
    -s bdi-cicd-framework/parser `
    -p 'test_*.py'
```

and:

```powershell
py -3 bdi-cicd-framework/verify_controller_experiment.py
```

If these fail, fix the BDI/controller before touching the live experiment.

If they pass:

```text
BDI/controller logic
        ✓
```

Now move to GitHub.

---

# PHASE 4 — Publish the correct controller

### 6. Merge the repair into `main`

The manual says the repair must be reviewed and merged before creating v1.

So after you're satisfied with the repair:

```text
fix/bdi-controller-runtime
          ↓
        PR
          ↓
        main
```

Then locally:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
```

Now check again:

```powershell
py -3 bdi-cicd-framework/run_controller.py --help
```

It should still contain the new options.

---

# PHASE 5 — Your first REAL experiment

### 7. Create v1

Now create the known healthy baseline:

```powershell
git tag -a bdi-console-v1.0.0 `
    -m 'Complete BDI recovery baseline'

git push origin bdi-console-v1.0.0
```

This tag means:

> **This exact source code is my v1 candidate for a known-good release.**

Don't reuse the historical old v1 tags. The manual specifically says to create fresh tags.

---

### 8. Authenticate the controller with GitHub

Run:

```powershell
gh auth login -h github.com
```

Then:

```powershell
$env:GITHUB_TOKEN = gh auth token
```

The manual says not to paste this token into chat or commit it.

Then:

```powershell
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:BDI_WORKFLOW_REF = 'main'
```

What this means:

```text
GITHUB_REPOSITORY
        ↓
which GitHub repo should Java control?

BDI_WORKFLOW_REF
        ↓
which version of the GitHub workflow?
```

---

### 9. Clear old experiment settings

Run exactly what the manual gives:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
Remove-Item Env:BDI_READY_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
```

This prevents an old fault experiment from accidentally affecting your healthy baseline.

---

### 10. Tell BDI which source version to deploy

```powershell
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-console-v1.0.0
```

Conceptually:

```text
bdi-console-v1.0.0
       ↓
exact Git commit
       ↓
BDI_RELEASE_SHA
       ↓
GitHub deployment uses this source
```

Then create a unique experiment ID:

```powershell
$env:BDI_CAMPAIGN_ID = `
    'v1-' + (Get-Date -Format yyyyMMdd-HHmmss)
```

And:

```powershell
$baselineDir = `
    "bdi-cicd-framework/bdi/build/controller-runs/$env:BDI_CAMPAIGN_ID"
```

---

# PHASE 6 — Press the actual START button

### 11. Start the controller

This is effectively the **start button for your experiment**:

```powershell
py -3 bdi-cicd-framework/run_controller.py `
    --gui `
    --baseline `
    --artifacts-dir $baselineDir
```

The manual makes an important distinction:

> **A Git push does not start the deployment campaign. Starting the launcher does.**

So this:

```text
run_controller.py
```

starts:

```text
Jason
 ↓
reason
 ↓
select build
 ↓
Java
 ↓
GitHub
```

---

# PHASE 7 — Watch it instead of just waiting

### 12. Keep four things visible

The manual recommends essentially this arrangement.

**Window 1 — PowerShell**

Your controller output.

Look for decisions and results.

**Window 2 — MAS Console**

This shows Jason.

Select:

```text
controller_agent
```

You can inspect:

```text
beliefs
events
intentions
```

This is your **BDI brain**.

**Window 3 — GitHub → Actions**

This is extremely important.

You should see:

```text
Build entity
```

Then, after it finishes:

```text
Test entity
```

Then:

```text
Security entity
```

etc.

The manual expects **one Actions run per entity/attempt**.

**Window 4 — Docker Desktop**

When deployment begins, you should see the actual staging/production Docker stacks.

---

# PHASE 8 — Understand where to look when something breaks

This is probably the most useful part for you as you're learning.

Suppose:

```text
build never appears in GitHub Actions
```

Look at:

```text
Jason
 ↓
Java dispatch
 ↓ X
GitHub
```

Likely investigate controller/Java/GitHub authentication.

---

Suppose:

```text
GitHub job says:
Waiting for runner
```

Look at:

```text
GitHub
 ↓ X
self-hosted runner
```

Check:

```text
runner online?
payment-deploy label?
```

GitHub routes a self-hosted job only to a runner matching its requested labels. ([GitHub Docs][1])

---

Suppose GitHub starts the job but says:

```text
permission denied:
/var/run/docker.sock
```

Then:

```text
GitHub ✓
runner ✓
Docker X
```

That's a **runner → Docker permission** problem, not BDI.

GitHub's own troubleshooting documentation identifies Docker socket permission as a self-hosted-runner account permission issue. ([GitHub Docs][2])

---

Suppose staging deploys successfully but Jason gets:

```text
telemetry unknown
```

Then:

```text
deployment ✓

App
 ↓
OpenTelemetry
 ↓
Prometheus
 ↓ X
Java
 ↓
Jason
```

Check:

```text
http://localhost:3001/ready
http://localhost:9091
```

The manual says Java reads `/ready` and the Prometheus HTTP API and turns those observations into Jason beliefs.

---

Suppose production runs but BDI doesn't continue.

Now inspect:

```text
GitHub production result
+
production readiness
+
Prometheus metrics
        ↓
      Jason
```

Because according to the manual:

```text
production.health == healthy
```

requires both readiness and metric thresholds.

---

# PHASE 9 — Know when v1 is successful

### 13. Wait for `achieved`

For the healthy baseline, you ultimately want:

```text
build ✓
  ↓
test ✓
  ↓
security ✓
  ↓
staging ✓
  ↓
staging telemetry healthy
  ↓
production ✓
  ↓
production telemetry healthy
  ↓
ACHIEVED
```

The baseline is special because it has **no previous known-good release to roll back to**. Therefore if this first baseline fails, automatic recovery isn't available.

---

### 14. Verify the actual application

After `achieved`:

```powershell
$knownGood = `
    (Resolve-Path "$baselineDir/controller-result.json").Path
```

Then:

```powershell
$v1Health = Invoke-RestMethod http://localhost:3000/health
$v1Health
```

and:

```powershell
Invoke-RestMethod http://localhost:3000/ready
```

Open:

```text
http://localhost:3000/checkout
```

Make a fake payment.

Now you have established:

```text
v1
=
known-good production release
```

The manual says to record its commit SHA, `deploymentRunId`, result receipt, and GitHub production run URL.

---

# PHASE 10 — Only now create v2

### 15. Make a harmless visible change

```powershell
git switch -c demo/payment-v2 main
```

Change something such as receipt wording.

Then:

```powershell
npm test
npm run lint
npm run build
```

Commit:

```powershell
git add -p
git diff --cached
git commit -m 'Prepare payment v2 candidate'
git push -u origin demo/payment-v2
```

Tag:

```powershell
git tag -a bdi-console-v2.0.0-rc1 `
    -m 'Payment v2 candidate'

git push origin bdi-console-v2.0.0-rc1
```

Set:

```powershell
$env:BDI_RELEASE_SHA = `
    git rev-list -n 1 bdi-console-v2.0.0-rc1

$env:BDI_CAMPAIGN_ID = `
    'v2-' + (Get-Date -Format yyyyMMdd-HHmmss)
```

Then:

```powershell
$controllerArgs = @(
    '--gui',
    '--known-good', $knownGood,
    '--confirm-compatible-rollback'
)

py -3 bdi-cicd-framework/run_controller.py @controllerArgs
```

The manual expects healthy v2 to do:

```text
build
test
security
staging
observe staging
production
observe production
→ achieved
```

with **no rollback**.

---

# PHASE 11 — Now deliberately break v2

Only after healthy v1 **and** healthy v2 work should you test adaptation.

The manual defines these main experiments:

| Experiment                    | You deliberately cause     | What BDI should do               |
| ----------------------------- | -------------------------- | -------------------------------- |
| Transient test failure        | first test fails           | retry                            |
| Retry exhaustion              | test repeatedly fails      | stop                             |
| Bad staging                   | staging error rate high    | stop before production           |
| Bad production                | production error rate high | rollback                         |
| Production deployment failure | production job fails       | rollback                         |
| Recovery failure              | rollback itself fails      | stop / failed                    |
| Missing telemetry             | Prometheus unavailable     | reconsider, then recover/unknown |

These exact expected behaviours are defined by the manual.

---

# PHASE 12 — Your main rollback experiment

For the strongest demonstration, prepare the fault file:

```powershell
New-Item -ItemType Directory -Force `
    bdi-cicd-framework/bdi/build/manual-control |
    Out-Null

Set-Content `
    bdi-cicd-framework/bdi/build/manual-control/faults.properties `
    '' `
    -Encoding ascii

$env:BDI_EXECUTION_PLAN = `
    (Resolve-Path bdi-cicd-framework/bdi/build/manual-control/faults.properties).Path
```

Start v2 but pause after staging:

```powershell
$env:BDI_CAMPAIGN_ID = `
    'fault-' + (Get-Date -Format yyyyMMdd-HHmmss)

py -3 bdi-cicd-framework/run_controller.py `
    @controllerArgs `
    --pause-after staging `
    --pause-ms 60000
```

Wait for:

```text
controller_pause after_entity=staging
```

Now in Terminal B:

```powershell
Set-Content `
    bdi-cicd-framework/bdi/build/manual-control/faults.properties `
    'production.force_error_rate=1' `
    -Encoding ascii
```

Then observe:

```text
BDI chooses production
        ↓
GitHub deploys bad v2
        ↓
app produces bad telemetry
        ↓
OTel
        ↓
Prometheus
        ↓
Java
        ↓
Jason receives BLOCK
        ↓
BDI_DECISION=rollback
        ↓
GitHub Actions:
Rollback entity
        ↓
redeploy v1
        ↓
new telemetry healthy
        ↓
BDI_RECOVERY=restored
        ↓
stopped / restored
```

That exact behavior is the manual's expected recovery demonstration.

---

# Finally: what evidence do you keep?

For **every live experiment**, preserve:

```text
generation-manifest.json
controller-journal.jsonl
controller-result.json
MAS output
GitHub Actions run URLs
execution UUIDs
telemetry readings
expected sequence
actual sequence
source/config hashes
recovery result
```

The manual specifically distinguishes real GitHub evidence from:

```text
scenario://...
```

which is only local simulation and **cannot count as live evidence**.

## Your checklist from laptop OFF → completed experiment

If everything above feels overwhelming, **use only this list while working**:

1. **Turn laptop on → start Docker Desktop.**
2. **Make sure `bdi-demo` runner is online and has `payment-deploy`.**
3. **Check Docker works from the runner.**
4. **Get `fix/bdi-controller-runtime` working and confirm `--gui --baseline` actually exists.**
5. **Run local `production_unhealthy` rehearsal.**
6. **Run regression tests.**
7. **Merge repair into `main`.**
8. **Create/tag v1.**
9. **Set GitHub/controller environment variables.**
10. **Run `run_controller.py --gui --baseline`.**
11. **Watch Jason + GitHub Actions + Docker simultaneously.**
12. **Get v1 to `achieved`.**
13. **Check `/health`, `/ready`, `/checkout`.**
14. **Save v1 receipt as `$knownGood`.**
15. **Create v2.**
16. **Run healthy v2 → `achieved`.**
17. **Run transient-test experiment.**
18. **Run bad-staging experiment.**
19. **Run bad-production → rollback experiment.**
20. **Save all evidence.**

And **right now you are at Step 4, not Step 10**. The fact that your actual `run_controller.py` rejected `--gui --baseline` means the immediate job is to reconcile **the implementation with this manual**. Don't try to run the live baseline until that is fixed.

[1]: https://docs.github.com/en/actions/reference/runners/self-hosted-runners?utm_source=chatgpt.com "Self-hosted runners reference - GitHub Docs"
[2]: https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot?utm_source=chatgpt.com "Monitoring and troubleshooting self-hosted runners - GitHub Docs"
