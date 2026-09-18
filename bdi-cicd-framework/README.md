# BDI CI/CD framework — payment-service baseline

This copy of the framework is wired to the payment app in the parent directory. It has a **read-only Jason promotion gate** connected between staging and production in `.github/workflows/ci-cd.yml`. The generator maps real workflow job IDs to stable BDI roles; Java reads the current GitHub Actions run and Prometheus; Jason revises its beliefs as observations change and decides `allow`, `block`, or `unknown`. GitHub runs production only after `allow`. The framework does not itself deploy or roll back the app.

The project-specific contract is `models/payment_project.yaml`. It contains workflow job IDs and display names, health/Prometheus endpoints, PromQL queries, thresholds, and the staging-to-production promotion gate. For a second application, supply another contract and goal file, then regenerate; no metric names or ports need to be put in the active observer code.

## Requirements and layout

- Python 3 with PyYAML and JDK 21+ for the framework; the checked-in Gradle wrapper supplies Gradle 8.13.
- Node.js 22+ and Docker Compose for the parent payment app.
- `parser/`: workflow-to-BDI generator and tests.
- `models/`: application contracts, goals, and generated workflow model.
- `generator/`: reusable AgentSpeak template and generated beliefs.
- `bdi/`: Jason MAS, Java runtime, fixture, and tests.
- `monitoring/`: telemetry observation code.
- `actions/`: older action interfaces; the baseline does not invoke deployment actions.

Run commands below from the **payment repository root** unless the command changes directory. On Windows PowerShell, use `.\gradlew.bat`; on Linux/macOS use `bash ./gradlew`.

## 1. Regenerate the payment agent

```powershell
py -m pip install PyYAML
py .\bdi-cicd-framework\parser\model_transform.py `
  --pipeline .\.github\workflows\ci-cd.yml `
  --goals .\bdi-cicd-framework\models\payment_goal.yaml `
  --project .\bdi-cicd-framework\models\payment_project.yaml `
  --workflow .\bdi-cicd-framework\models\payment_workflow_model.yaml `
  --beliefs .\bdi-cicd-framework\generator\payment_bdi_project.asl `
  --agent .\bdi-cicd-framework\bdi\payment_bdi_agent.asl `
  --generic .\bdi-cicd-framework\generator\bdi_generic.asl
py -m unittest discover -s .\bdi-cicd-framework\parser -p 'test_*.py' -v
```

The generator validates mapped jobs, dependencies, cycles, and the gate. Regenerate after changing the workflow or model. The MAS points to `bdi/payment_bdi_agent.asl`—generating an agent only under `generator/` will not update the running MAS.

## 2. Start the payment app and create measurable traffic

If the default ports are free, start the stack:

```powershell
docker compose up -d --build
$env:PAYMENT_BASE_URL='http://127.0.0.1:3000'
npm run traffic:experiment -- normal 6
```

You should see six `POST /payments: HTTP 201` lines. The checkout UI is at `http://127.0.0.1:3000/checkout`; Prometheus is at `http://127.0.0.1:9090`. The sample manifest uses an **isolated local stack** at app port 3301 and Prometheus port 19091, so for the default stack override its URLs in the current shell:

```powershell
$env:BDI_READY_URL='http://127.0.0.1:3000/ready'
$env:BDI_PROMETHEUS_URL='http://127.0.0.1:9090'
```

For the isolated stack instead, use `PAYMENT_BASE_URL=http://127.0.0.1:3301` and leave the manifest URLs unchanged. Wait 10–20 seconds after traffic; rate and histogram queries need at least two Prometheus samples. Keep generating traffic while evaluating: with no recent requests, latency is absent and the gate becomes `unknown`, not healthy.

## 3. Probe workflow and telemetry without Jason

The included JSON is a **saved, illustrative successful run**, not evidence of your current GitHub workflow. It exercises the workflow adapter while the telemetry side reads the live payment stack:

```powershell
Set-Location .\bdi-cicd-framework\bdi
.\gradlew.bat test
.\gradlew.bat probeBaseline '-PprobeArgs=--project ../models/payment_project.yaml --environment local --jobs-json fixtures/payment-jobs-success.json'
```

Expect five role/status records (`build`, `test`, `security`, `staging`, `production`), then `gate=allow`, `readiness=ready`, `error_rate`, `latency`, and `assessment=allow reason=healthy`. With no recent samples expect `assessment=unknown reason=metrics_unavailable`; with high error rate expect `assessment=block reason=high_http_error_rate`. An HTTP 503 from `/ready` also blocks.

To repeat the high-error check on a **local disposable** Compose stack, set `EXPERIMENT_MODE=high_error_rate`, recreate only its app service with `docker compose up -d --no-deps --force-recreate app`, run `npm run traffic:experiment -- high_error_rate 12` with `PAYMENT_BASE_URL` pointing at that stack, wait for two scrapes, then rerun the probe. Afterwards set `EXPERIMENT_MODE=normal` and recreate only the app again. Recent 503s remain in the two-minute PromQL window briefly if the same `CI_RUN_ID` is reused; GitHub assigns a distinct run/attempt label to each run. Do not use this experiment command against a shared staging or production deployment.

To read a real Actions run instead of the fixture, set `GITHUB_REPOSITORY=owner/repo`, `GITHUB_TOKEN` to an Actions-read token, and use:

```powershell
.\gradlew.bat probeBaseline '-PprobeArgs=--project ../models/payment_project.yaml --environment local --repository owner/repo --run-id 123456789'
```

The job display names in `payment_project.yaml` must match the GitHub Jobs API. The current observer reads the first 100 latest jobs of one run; pagination and matrix jobs are not yet supported. This live API path has not been verified with credentials in this workspace.

## 4. Run the Jason decision replay

From `bdi/`, using the saved job fixture and the local telemetry endpoint:

```powershell
$env:BDI_GITHUB_JOBS_FIXTURE='fixtures/payment-jobs-success.json'
$env:BDI_TARGET_ENV='local'
.\gradlew.bat runBaseline
```

The agent observes job completions and staging telemetry. With `gate(staging,allow)`, it proceeds to observe `production`; with `gate(staging,unknown)` or `gate(staging,block)`, it prints `BDI promotion blocked`. Inspect `build/runtime.jsonl` for `bdi_action_requested` and `percept_published` events. Press Ctrl+C after the decision; this MAS is a long-running observer. The fixture already includes a completed production job, so this is a replay of a run, **not** a pre-production approval.

For live GitHub observation, unset `BDI_GITHUB_JOBS_FIXTURE`, set `BDI_GITHUB_RUN_ID`, `GITHUB_REPOSITORY`, and `GITHUB_TOKEN`, and select `BDI_TARGET_ENV=staging` once staging endpoints are reachable. `BDI_READY_URL` and `BDI_PROMETHEUS_URL` can override those endpoints. Do not put tokens in the manifest or logs.

## 5. Run the one-shot Jason promotion gate

From `bdi/`, after fresh payment traffic and at least two Prometheus scrapes:

```powershell
$env:BDI_GITHUB_JOBS_FIXTURE='fixtures/payment-jobs-pre-promotion.json'
$env:BDI_TARGET_ENV='local'
.\gradlew.bat gate
$LASTEXITCODE
```

`gate.mas2j` starts `gate_agent.asl`, not the long-running replay agent. The Java environment periodically publishes separate workflow and telemetry beliefs. AgentSpeak waits on `unknown`, reconsiders new evidence every five seconds, blocks on a confirmed failure, and allows only when all mapped prerequisite jobs except the promotion target succeeded and telemetry is healthy. Look for exactly one `BDI_GATE_RESULT=...` line:

| Result | Meaning | Direct JVM exit | Gradle task |
|---|---|---:|---|
| `allow` | All required jobs succeeded and telemetry is healthy | 0 | Succeeds |
| `block` | A required job failed or telemetry is unhealthy | 1 | Fails |
| `unknown` | A job, telemetry, configuration, or the Jason decision is unavailable | 2 | Fails |

Gradle itself normally returns exit 1 for either nonzero JVM exit; use the printed result to distinguish `block` from `unknown`. The gate has a 90-second fail-closed watchdog (`BDI_GATE_TIMEOUT_SECONDS` can adjust it). No traffic for the selected `BDI_TELEMETRY_RUN_ID` in the recent Prometheus window is `unknown`, not `allow`.

The fixture is for local tests **only**. For a real run, remove `BDI_GITHUB_JOBS_FIXTURE` and provide `BDI_GITHUB_RUN_ID`, `GITHUB_REPOSITORY`, and an Actions-read `GITHUB_TOKEN`; the gate also needs access to the staging `/ready` and Prometheus endpoints. Its live GitHub API path still needs validation with your credentials. This command does not itself deploy anything.

## What is working, and what is next

The payment baseline generates a Jason agent from the real workflow, reads saved/live-format job state, reads actual `/ready` and run-specific Prometheus values, and fails closed when metrics remain absent. The gate has been exercised locally against changing healthy and high-error payment telemetry and against unreachable telemetry. Parser and Java tests cover mapping, fixture reading, prerequisite jobs, and missing/nonfinite samples. The earlier `CicdEnvironment` and dispatch-oriented executor remain for older experiments; neither is selected by `project.mas2j` or `gate.mas2j`.

The workflow integration is in place locally, but a **live GitHub Actions run is still unverified**. Commit/push the copied framework and workflow through your normal review process, then follow [the experiment guide](../docs/BDI_EXPERIMENT.md) to observe normal and high-error runs. This baseline chooses promotion or avoidance; it does not perform post-production rollback or claim to control arbitrary workflows.
