# Manual execution guide for the BDI-controlled payment CI/CD experiment

Status date: 19 September 2026. Repository: `id-nynt/260031_cicd_payment_demo`.

This guide explains the current implementation, how the generated model is constructed, how the Java environment connects Jason to GitHub Actions and telemetry, how to version the payment demo safely, and how to run and observe the experiment manually.

## 1. Current status at a glance

| Area | Status | Meaning |
|---|---|---|
| Payment `pipeline.yaml` | Ready locally | It defines `build`, `test`, `security`, `staging`, and `production`, dependencies, one retry, and observation before production. |
| Payment goal files | Ready locally | Separate staging-only and production goals have been generated and run through the real Jason interpreter. |
| Parser and generator | Verified locally | 13 parser/generator tests pass. Generated model and AgentSpeak are deterministic and the required work changes with the selected goal. |
| Generic Jason controller | Verified locally | Healthy, retry, exhaustion, telemetry block/unknown/delay, pause, and goal-change scenarios ran with actual Jason. |
| Java GitHub adapter | Verified against a local mock API | It dispatches one entity, follows the returned run ID, and accepts only the configured job name. It has not dispatched a real repository workflow yet. |
| Java telemetry adapter | Unit/local verified | It checks `/ready` and queries Prometheus with the exact execution ID. A live staging Prometheus endpoint has not been read by the new controller. |
| Dispatch-only workflow | Implemented locally | `.github/workflows/entity-execution.yml` has no application-stage `needs` chain. It has not been committed or published. |
| Live end-to-end BDI orchestration | Pending | GitHub credentials are currently invalid, the implementation is uncommitted, and Docker engine access from this session is denied. |

The current Git state matters:

- `v1.0` points to commit `7acda70`, the older payment/telemetry baseline.
- Local and remote `experiment-v2` point to `f658daf`, the earlier gate-based implementation.
- The new controller implementation is currently an uncommitted working-tree change on `experiment-v2`.
- Therefore neither the existing `v1.0` tag nor remote `experiment-v2` contains the finished controller described here.

Do not move or overwrite `v1.0`. Section 5 describes a version scheme where both the known-good release and later candidates contain all controller-compatible scripts and manifests.

## 2. Payment pipeline and goals

The controller inputs are:

| Purpose | File |
|---|---|
| Logical pipeline | `bdi-cicd-framework/models/payment_pipeline.yaml` |
| Staging-only goal | `bdi-cicd-framework/models/payment_goal_staging.yaml` |
| Production goal | `bdi-cicd-framework/models/payment_goal_production.yaml` |
| Execution and telemetry manifest | `bdi-cicd-framework/models/payment_project.yaml` |
| Generic AgentSpeak policy | `bdi-cicd-framework/generator/controller_generic.asl` |

The pipeline currently describes this graph:

```text
build ----+---> security --+
test  ----+                |
build ---------------------+---> staging --[observe staging]---> production
test  ---------------------+
```

`max_retries: 1` means one retry after the original attempt. A repeatedly failing entity can therefore run at most twice.

The staging goal requires:

```text
build, test, security, staging
```

Production is not part of that goal closure and is not dispatched. The production goal requires all five entities and adds avoidance requirements preventing production success without successful test and staging results.

## 3. How the parser generates E, D, O, and R

Run the launcher with `--generate-only` to regenerate without starting Jason:

```powershell
py -3 .\bdi-cicd-framework\run_controller.py `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --generate-only `
  --artifacts-dir .\artifacts\generation-check
```

The output model is `bdi-cicd-framework/models/controller_workflow_model.yaml`. The generated project beliefs are in `generator/controller_project.asl`, and the runnable combined agent is `bdi/controller_agent.asl`. The campaign directory receives `generation-manifest.json` with SHA-256 hashes of pipeline, goal, and project manifest.

### 3.1 Entities, E

`entities(E)` comes from the keys under `jobs` in `payment_pipeline.yaml`, preserving their declared order:

```yaml
entities(E):
  - build
  - test
  - security
  - staging
  - production
```

The same names become facts such as `entity(build).` and `entity(staging).` in the generated AgentSpeak. They must be lowercase AgentSpeak atoms and must exactly match keys in `controller.jobs` in the project manifest.

### 3.2 Dependencies, D

Every `needs` entry becomes a directed dependency `{from, to}`. For example:

```yaml
security:
  needs: [build, test]
```

becomes:

```yaml
- from: build
  to: security
- from: test
  to: security
```

and the AgentSpeak fact:

```text
depends(security, [build, test]).
```

The parser rejects unknown dependencies and cycles. Jason's `holds(Requirements)` rule permits an entity only when every dependency has a `phase_result(..., success)` belief.

### 3.3 Observable properties, O

The generated `observable_properties(O)` currently contains only:

```yaml
status:
  values: [success, failure, cancelled, skipped, timeout]
duration:
  value: time
```

Their sources are:

| Observable | Configuration/source | Runtime value |
|---|---|---|
| `status` | The parser's `SUPPORTED_STATUS` list | Normalized conclusion of the exact configured job in the exact GitHub run returned by dispatch |
| `duration` | Always included by the supported model; unit comes from `goal.duration_unit` | Controller wall-clock milliseconds from dispatch until selected job completion |

`status` and `duration` are inserted into Jason as correlated percepts:

```text
status(entity, attempt, value)
duration(entity, attempt, milliseconds)
```

There is an architectural limitation here: health, readiness, latency, and error rate are not first-class items in generated `O`. Although the parser recognizes those property names during validation, the current goal translator supports only:

- achievement: `entity.status == success`;
- maintenance: `entity.duration <= integer`;
- avoidance: do not succeed one entity when a required entity did not succeed.

Runtime telemetry is configured separately in `payment_project.yaml`. Java evaluates the metric values and publishes one belief:

```text
telemetry(staging, allow)
telemetry(staging, block)
telemetry(staging, unknown)
```

This is sufficient for the bounded promotion experiment, but a future richer BDI model should generate individual `health`, `readiness`, `error_rate`, and `latency` observables and let AgentSpeak compare their configured thresholds.

### 3.4 Recovery, R

`recovery(R)` is generated from explicitly declared recovery jobs in the supported syntax. A recovery job must have one dependency and a condition matching failure of that dependency. The payment controller pipeline declares no recovery job, so its current value is:

```yaml
recovery(R): []
```

Retry is separate from `R`. It is controlled by `execution.max_retries` and the generic AgentSpeak retry plans. Autonomous production rollback is also separate and is intentionally not implemented because the project does not yet promote a known-good immutable image or define safe database recovery.

### 3.5 Goals and required work

The parser calculates a closure starting with all achievement and maintenance entities, then adds their transitive dependencies and safety prerequisites. It emits `required(entity).` beliefs only for that closure.

The generic agent then:

1. Finds a required entity whose dependencies succeeded.
2. Checks avoidance rules before dispatch.
3. Dispatches only when no other entity is running.
4. Consumes the correlated status and duration.
5. Retries within the configured bound or stops.
6. Runs configured telemetry observation before the next entity.
7. Finishes as `achieved`, `stopped`, or `unknown`.

## 4. What the Java environment does

The runtime entry point is `bdi/controller.mas2j`, which starts the generated `controller_agent.asl` with `ControllerEnvironment`.

The Java environment is generic enough for different entity names, dependency topologies, job display names, environment URLs, PromQL, thresholds, and retry policies. This was demonstrated locally with the separate `package → verify → preview` reporting example. The GitHub worker workflow itself remains payment-specific, so a second project's live workflow would still need matching entity job bodies.

The payment manifest currently contains both architectures. `ControllerProjectConfig` reads the new `controller` block for workflow name, exact job display names, environment association, and observation timing. `ProjectConfig` reads `environments`, `metrics`, and `thresholds` for runtime telemetry. The older `jobs`, `github_job_names`, `promotion_gate`, and `infrastructure_jobs` fields remain for the legacy gate/replay programs and do not determine the new controller's ordering.

### 4.1 Handling `run_job`

When Jason selects `run_job(Entity, Attempt)`, `GitHubEntityExecution`:

1. Confirms the entity is present in `controller.jobs`.
2. Generates a unique execution UUID.
3. Reads any configured experiment fault for that entity/attempt.
4. Dispatches `entity-execution.yml` through the GitHub Actions API.
5. Passes entity, campaign ID, execution ID, attempt, immutable release SHA, and fault mode.
6. Polls the returned GitHub run ID until it completes.
7. Searches that run for the exact configured job display name.
8. Rejects a missing or skipped selected job and normalizes its conclusion.
9. Journals the run URL and publishes `status` and `duration` percepts to Jason.

This does not use a local port or the old BDI gate to obtain job status. It uses authenticated GitHub REST API calls. Only staging and production use the self-hosted runner; build, test, and security use GitHub-hosted runners.

### 4.2 Reading OpenTelemetry-derived data

Java does not speak OTLP directly. The path is:

```text
Payment application
  -> OTLP/HTTP metrics on container port 4318
  -> OpenTelemetry Collector
  -> Prometheus exporter on container port 9464
  -> Prometheus scrape every 5 seconds
  -> Prometheus HTTP query API
  -> ProjectTelemetryProvider
  -> telemetry(staging, allow|block|unknown)
```

`ProjectTelemetryProvider` first sends HTTP `GET /ready`, then queries Prometheus using the exact execution UUID substituted for `{{run_id}}`. It checks:

- error rate greater than 5%;
- p95 latency greater than 500 ms;
- readiness below 1;
- unavailable/nonfinite query results.

A confirmed threshold violation becomes `block`; missing data becomes `unknown`; healthy results become `allow`. The controller tries up to 18 observations, five seconds apart, according to `payment_project.yaml`.

This is the new AgentSpeak observation point, expressed as `observe_before(production, staging)`. It replaces the old architecture's separate `bdi-gate` job. The legacy gate remains in `ci-cd.yml` only for manual comparison with `legacy_deployment=true`.

### 4.3 Correlation and concurrency

- Every attempt receives a unique execution UUID.
- Deployment health reports that UUID as `deploymentRunId`.
- Prometheus queries select `ci_run_id` equal to the same UUID.
- The adapter accepts only the GitHub run returned by its dispatch.
- The environment permits one in-flight entity.
- A repository-wide local lock prevents two launcher processes in the same checkout.
- Legacy and controller deployment jobs share GitHub concurrency group `payment-deployment-control`.

## 5. Versioning, retry, and manual rollback

### 5.1 Recommended tag strategy

Keep the historical `v1.0` tag unchanged. It predates the controller and should remain historical evidence. It is not a safe controller rollback target because it may not contain the dispatch workflow's traffic and telemetry scripts.

Create new immutable tags after the controller infrastructure is reviewed and merged:

- `bdi-demo-v1.0.0`: first known-good application revision containing all controller-compatible files.
- `bdi-demo-v2.0.0-rc1`: later candidate with the application change being evaluated.
- `bdi-demo-v2.0.0`: candidate promoted after the experiment succeeds.

Both the known-good and candidate tags must contain `docker-compose.yml`, migrations, telemetry setup, traffic scripts, and any source files used by the entity jobs.

### 5.2 Publish the current implementation safely

GitHub authentication currently needs repair first:

```powershell
gh auth login -h github.com
gh auth status
```

Review and commit from `experiment-v2`. Do not stage the pre-existing Gradle lock-file change accidentally:

```powershell
git switch experiment-v2
git status --short
git diff --check
git add -p
git diff --cached --stat
git diff --cached
git commit -m "Add BDI-controlled CI/CD experiment"
git push origin experiment-v2
```

In `git add -p`, include the controller implementation, workflow, models, tests, and documentation. Leave `bdi-cicd-framework/config/.gradle/9.2.0/fileHashes/fileHashes.lock` unstaged unless you independently intend to commit it. Also inspect the modification to `models/03_workflow_model.yaml`; it is an older generated model and is not the new controller output.

Open a pull request from `experiment-v2` to `main`, allow required checks/review to complete, and merge normally. `entity-execution.yml` must exist on the default branch before GitHub will accept its manual dispatch.

After merging, create the new controller-compatible baseline tag:

```powershell
git switch main
git pull --ff-only origin main
py -3 -m unittest discover -s .\bdi-cicd-framework\parser -p 'test_*.py' -v
Set-Location .\bdi-cicd-framework\bdi
.\gradlew.bat --no-daemon test
Set-Location ..\..
npm test
git tag -a bdi-demo-v1.0.0 -m "Known-good BDI controller payment demo"
git push origin bdi-demo-v1.0.0
```

Create the v2 candidate only after making the intended application change:

```powershell
git switch -c release/bdi-demo-v2 main
# Make and test the intended application change.
git add -p
git commit -m "Prepare payment candidate for BDI experiment"
git push -u origin release/bdi-demo-v2
```

Merge that branch through review, update `main`, and tag it `bdi-demo-v2.0.0-rc1` using the same annotated-tag procedure.

### 5.3 Redoing an experiment

You do not need a new tag when only the campaign failed because of a temporary runner, network, approval, or telemetry issue. Reuse the same immutable release SHA and assign a new campaign ID. That makes the rerun distinguishable while keeping source constant.

### 5.4 Returning to the known-good release

The controller has no autonomous rollback action. A manual known-good redeployment runs the normal staging checks before production:

```powershell
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-demo-v1.0.0
$env:BDI_CAMPAIGN_ID = 'payment-rollback-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:BDI_WORKFLOW_REF = 'main'
py -3 .\bdi-cicd-framework\run_controller.py `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --artifacts-dir ".\artifacts\$env:BDI_CAMPAIGN_ID"
```

If the candidate was blocked before production, the previous production stack should still be present and normally needs no rollback. If production was partially replaced, use the known-good campaign above. Database migrations can make source rollback unsafe; inspect migrations and take an approved backup before rolling back across schema changes. Do not use `git reset --hard` or move an existing tag to represent rollback. Use `git revert` and a reviewed corrective commit if repository history itself must be corrected.

## 6. Payment service ports, environments, and exposed data

### 6.1 Port map

| Component | Local/default | Staging | Production | Exposure |
|---|---:|---:|---:|---|
| Payment application | 3000 | 3001 | 3000 | Published on the host by Compose |
| PostgreSQL | 5432 | 5433 | 5432 | Published on the host; restrict with host firewall for a real environment |
| Collector Prometheus exporter | 9464 | 9465 | 9464 | Bound to `127.0.0.1` only |
| Prometheus UI/API | 9090 | 9091 | 9090 | Bound to `127.0.0.1` only |
| Collector OTLP/HTTP receiver | container 4318 | container 4318 | container 4318 | Compose-network only; not published to the host |

Staging uses Compose project `payment-staging`; production uses `payment-production`. They use separate project-scoped PostgreSQL and Prometheus volumes.

The project manifest tells Java to read:

| Environment | Readiness | Prometheus API |
|---|---|---|
| Local framework fixture | `http://127.0.0.1:3301/ready` | `http://127.0.0.1:19091` |
| Staging | `http://127.0.0.1:3001/ready` | `http://127.0.0.1:9091` |
| Production | `http://127.0.0.1:3000/ready` | `http://127.0.0.1:9090` |

Because these are loopback URLs, the simplest live layout is to run the controller as a separate process and durable checkout on the same host as the self-hosted runner. It must not run as a runner job or inside the runner's disposable checkout. If the controller runs on another machine, change the manifest to reachable protected addresses and configure firewall/authentication before running.

### 6.2 Useful endpoints and data

| Endpoint | Data |
|---|---|
| `/health` | Process status, deployment execution ID, and experiment mode |
| `/ready` | PostgreSQL/application readiness; HTTP 200 or 503 |
| `/config` | Enabled payment providers, Stripe readiness, merchant name, and Stripe publishable key when configured |
| `/checkout`, `/payment`, `/receipt` | Demo UI |
| `/metrics` on 9464/9465 | Collector's Prometheus-format metrics |
| Prometheus `/api/v1/query` | Run-correlated metric query results |

The application emits request count, HTTP error count, response-duration histogram, readiness gauge, and payment outcome count. Request metrics and readiness include `ci_run_id`; payment outcome count currently does not. Application logs may contain request paths and generated transaction identifiers, but the fake flow does not store full card numbers.

Before deployment, check for conflicts without deleting data:

```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 3000,3001,5432,5433,9090,9091,9464,9465
docker compose config --quiet
```

## 7. What starts CI/CD now

For the new controller experiment, a push does not start deployment. The human starts the persistent controller by running `run_controller.py`. The sequence is:

```text
launcher validates and generates
  -> Jason starts
  -> Jason selects first required entity
  -> Java dispatches one workflow_dispatch run
  -> GitHub runner executes exactly that selected entity
  -> Java receives its terminal result
  -> Jason updates beliefs and decides again
```

`entity-execution.yml` itself has only `workflow_dispatch`; the Java API call is its normal trigger. A person can also see the manual Run workflow control in GitHub, but manually dispatching entities bypasses BDI ownership and should not be used as experiment evidence.

The older `ci-cd.yml` still starts build/test/security on pull requests and pushes to `main`. Its staging, gate, and production jobs run only from a manual dispatch with `legacy_deployment=true`. Keep that input false during controller experiments.

## 8. Manual live execution

### Step 1: Publish and identify one immutable release

Complete the reviewed merge and tagging procedure in section 5. Record the full SHA:

```powershell
git rev-list -n 1 bdi-demo-v1.0.0
```

The controller rejects branch names or short hashes as `BDI_RELEASE_SHA`.

### Step 2: Prepare GitHub

In repository settings:

1. Confirm `.github/workflows/entity-execution.yml` is visible on `main`.
2. Confirm `staging` and `production` GitHub Environments exist.
3. Preserve required reviewers or other production protection rules.
4. Confirm one online, idle, **Linux** self-hosted runner has label `payment-deploy`.

The current deployment scripts use Bash syntax. The `payment-deploy` custom label alone does not enforce Linux, so verify the runner operating system manually. Adding the standard `linux` label to `runs-on` is recommended before supporting more than one runner host.

### Step 3: Prepare the execution host

Use a durable controller checkout outside the runner work directory, preferably on the same host because telemetry endpoints are loopback-only. Open/start:

- Docker Desktop or Docker Engine;
- the existing self-hosted runner service/process;
- a terminal in the durable controller checkout.

Do not manually launch Jason or a Jason GUI. Do not launch the old gate/replay agent.

Verify tools and topology:

```powershell
java -version
javac -version
py -3 --version
py -3 -c "import yaml; print(yaml.__version__)"
node --version
npm --version
docker info
docker compose version
gh auth status
```

At the time of writing, `gh auth status` reports an invalid token and `docker info` returns pipe access denied in this session. Those must be fixed on the actual execution host.

### Step 4: Supply credentials and campaign identity

Provide a repository-scoped token with Actions dispatch/read access through the process environment. Do not write it into YAML, properties, documentation, or the journal.

```powershell
$env:GITHUB_REPOSITORY='id-nynt/260031_cicd_payment_demo'
$env:GITHUB_TOKEN='<securely supplied token>'
$env:BDI_WORKFLOW_REF='main'
$env:BDI_RELEASE_SHA=(git rev-list -n 1 bdi-demo-v1.0.0)
$env:BDI_CAMPAIGN_ID='payment-healthy-001'
```

### Step 5: Start the production-goal campaign

```powershell
py -3 .\bdi-cicd-framework\run_controller.py `
  --pipeline .\bdi-cicd-framework\models\payment_pipeline.yaml `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --artifacts-dir .\artifacts\payment-healthy-001
```

Expected sequence:

```text
build -> test -> security -> staging -> observe staging -> production -> achieved
```

Build and test are logically independent, but the current single-in-flight agent selects them one at a time. Production may wait for GitHub Environment approval. While it waits, Jason dispatches nothing else.

### Step 6: Observe the controller

Use four views:

1. **Controller terminal:** look for `BDI_DECISION`, `BDI_BELIEF`, and `BDI_CONTROLLER_RESULT`.
2. **GitHub Actions:** each selected entity appears as a separate `BDI Entity Execution` run. Only one application job should execute; other jobs are skipped by their entity conditions.
3. **Campaign journal:** inspect decisions, UUIDs, run IDs/URLs, status, telemetry, and final result.
4. **Service/Prometheus:** inspect deployment identity, readiness, and run-correlated queries.

```powershell
Get-Content .\artifacts\payment-healthy-001\controller-journal.jsonl -Wait
Get-Content .\artifacts\payment-healthy-001\controller-result.json
Invoke-RestMethod http://127.0.0.1:3001/health
Invoke-RestMethod http://127.0.0.1:3001/ready
Invoke-RestMethod http://127.0.0.1:9091/-/ready
```

For every `entity_execution_started`, verify an earlier `bdi_decision` names the same entity and attempt. Verify production has a prior staging `telemetry_terminal` with `allow`.

### Step 7: Run the staging-only goal

Use the same pipeline and release SHA with a new campaign ID:

```powershell
$env:BDI_CAMPAIGN_ID='payment-staging-goal-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --goal .\bdi-cicd-framework\models\payment_goal_staging.yaml `
  --artifacts-dir .\artifacts\payment-staging-goal-001
```

Expected sequence is `build, test, security, staging, achieved`. There must be no production run URL.

### Step 8: Run retry experiments

Transient failure properties:

```properties
test.1.failure_mode=force_failure
test.2.failure_mode=none
```

Retry exhaustion properties:

```properties
test.1.failure_mode=force_failure
test.2.failure_mode=force_failure
```

Save one block as a file, then set:

```powershell
$env:BDI_EXECUTION_PLAN=(Resolve-Path .\transient.properties)
$env:BDI_CAMPAIGN_ID='payment-transient-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --artifacts-dir .\artifacts\payment-transient-001
```

Transient failure should produce `test#1 failure`, `test#2 success`, then continue. Exhaustion should stop after `test#2 failure`, with no security, staging, or production dispatch.

Unset the plan before another scenario:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN
```

### Step 9: Run the high-error staging experiment

Use a properties file containing:

```properties
staging.force_error_rate=1
```

Start a new production-goal campaign. The staging job generates fake payments with injected HTTP 503 responses. The staging job remains successful after confirming those samples exist; Java should calculate an error rate above 5%, publish `telemetry(staging, block)`, and Jason should finish `stopped` without dispatching production.

### Step 10: Demonstrate BDI ownership with a pause

```powershell
$env:BDI_CAMPAIGN_ID='payment-pause-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --pause-after security --pause-ms 30000 `
  --artifacts-dir .\artifacts\payment-pause-001
```

During the 30-second pause, GitHub Actions should have no staging run. The journal records `successor_dispatched:false`. Staging starts only after the result is returned to Jason and it reasons again.

## 9. What is proven and what remains

### Proven locally

- Input validation and deterministic generation.
- Correct E and D generation, empty current R, and minimal status/duration O.
- Goal closure changes actual agent actions.
- Generic AgentSpeak progression, retry, avoidance, telemetry decisions, pause, and explicit outcomes.
- A second topology runs with unchanged framework Java and AgentSpeak.
- GitHub API request/result correlation against a mock HTTP server.
- Payment application tests and telemetry classification components.

### Not yet proven live

- A real controller API dispatch to GitHub.
- Real hosted/self-hosted job progression driven by the agent.
- Real GitHub Environment approval waiting.
- The new controller reading the deployed staging Prometheus instance.
- Live high-error blocking and known-good redeployment.

### Gaps before claiming the final live experiment

1. Commit, review, merge, and tag the current implementation.
2. Repair GitHub authentication and provide the external controller token.
3. Restore Docker engine access and confirm an online Linux `payment-deploy` runner.
4. Verify loopback endpoint reachability from the separate controller process.
5. Run the live scenario matrix and add actual GitHub run URLs to `BDI_CONTROLLER_EXPERIMENT_RESULTS.md`.
6. Move delayed/missing telemetry ownership fully into BDI for the live experiment. Currently the staging entity itself waits for usable telemetry before succeeding. This proves local AgentSpeak reconsideration, but a live missing-telemetry case can fail the staging job before `observe_telemetry` runs. The smallest follow-up is to let staging deploy and generate traffic without making metric availability a terminal job gate, then let `ProjectTelemetryProvider` perform the bounded wait and return `unknown`.
7. If richer BDI reasoning over telemetry values is required, generate telemetry observables in `O` and publish numeric beliefs instead of only the Java-classified allow/block/unknown belief.

Until those live steps pass, the accurate statement is: **the BDI agent has orchestrated the generated workflow with actual Jason locally and has independently tested GitHub/telemetry adapters, but it has not yet orchestrated and monitored a real GitHub Actions deployment end to end.**
