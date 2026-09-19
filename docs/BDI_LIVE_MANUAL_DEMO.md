# Manual payment deployment and BDI recovery experiment

This is the current guide. Earlier audit/results sections describe historical versions.

## 1. What is implemented

The generated Jason agent selects build, test, security, staging and production. It evaluates production telemetry before declaring success. On a configured production failure it selects one rollback, then checks the restored release. A successful rollback gives `outcome=stopped, recovery_outcome=restored`: delivery of the candidate failed, but service recovery succeeded.

Rollback is a conditional branch in the agent's policy. It is absent from the healthy sequence and from staging-only campaigns. GitHub executes the chosen entity; there is no `needs` chain or BDI gate job in the entity workflow. A push publishes source. Starting the launcher starts the deployment campaign.

`Validate application and BDI controller` runs non-deploying checks on PRs/pushes. It does not advance a release or compete for the deployment runner.

| Engineer input | Responsibility |
|---|---|
| `bdi-cicd-framework/models/01_pipeline.yaml` | Logical entities, dependencies, retry budget, observation ordering and recovery triggers |
| `bdi-cicd-framework/models/02_goal.yaml` | Candidate achievements, duration budget, required production health and prerequisites |
| `bdi-cicd-framework/models/payment_project.yaml` | Entity/job names, recovery source selection, environments, endpoints, PromQL queries and thresholds |
| `.github/workflows/entity-execution.yml` | Actual npm, Docker, deployment and traffic-generation commands |

Keep each job as one logical entity. For another application, change the YAML model/manifest and its worker job bodies. The controller launcher rejects embedded `steps`/`runs-on` rather than pretending to execute them. It supports this small model, not arbitrary GitHub workflow syntax. The reporting example remains usable with the same Java and generic AgentSpeak.

Generated outputs are `models/03_workflow_model.yaml`, its compatibility copy `models/controller_workflow_model.yaml`, `generator/controller_project.asl`, and `bdi/controller_agent.asl`. `controller.mas2j` starts that generated agent. Older replay/gate agents are not started.

| Model part | Where values come from |
|---|---|
| E | Keys under `jobs` |
| D | Logical `needs` edges; these are agent beliefs, not worker scheduling |
| O | Status/duration from the exact selected GitHub run/job; health from readiness plus execution-ID-filtered Prometheus queries |
| R | `recover_from`, `recover_on`, `observe_after` on the recovery entity |

`production.health == healthy` requires readiness and metric thresholds to pass. App metrics flow through OpenTelemetry Collector to Prometheus; Java reads Prometheus's HTTP query API and `/ready`, then supplies beliefs to Jason. Jason decides whether to wait, proceed, stop or recover. Java does not choose the job order. Unknown telemetry is reconsidered up to 18 times, five seconds apart. A timeout or uncertain GitHub response stops as `unknown`; it cannot trigger another deployment while the earlier run might still be active.

## 2. Branches and prerequisites

The complete repair is on `fix/bdi-controller-runtime`, based on remote `main` at `dd1b5c8`. Review and merge this branch before tagging v1. Historical `v1.0` and `bdi-demo-v1.0.0` remain unchanged; use fresh tags for this complete experiment. Do not use the stale `release/bdi-demo-v2` branch for new work.

The old gate workflow remains visible on GitHub until the repair is merged. Historical run graphs keep their old gate even after removal. Only new runs reflect the new workflow. Do not run the legacy workflow or the emergency manual rollback concurrently with a controller campaign.

Checked on 20 September 2026: GitHub authentication works outside the tool sandbox; runner `bdi-demo` is online with labels `self-hosted,Linux,X64`, but lacks `payment-deploy`. Add that label to the intended deployment runner, or deliberately change the worker's runner selection. The inspected local Docker context has no running stacks. The `production` and `staging` Environments currently have no protection rules; any approval expectations below apply only if you configure reviewers. This implementation preserves configured protections.

Prepare Python/PyYAML, JDK 21+, Docker/Compose and the Linux runner. The controller runs in a durable checkout outside the runner's `_work` directory and outside its only execution slot. Verify the controller can reach the runner-hosted application and Prometheus; `localhost` refers to the controller's machine. For a different host, configure reachable protected endpoints in the project manifest.

Windows in the demo:

- Terminal A: controller launcher and MAS Console (`controller_agent`).
- Browser: Jason mind-inspector URL printed at startup; select `controller_agent` for beliefs/events/intentions.
- Browser: repository Actions page; one run per entity/attempt and any Environment approvals.
- Browser: production `http://localhost:3000/checkout`; staging app `http://localhost:3001/checkout`.
- Browser: Prometheus staging `http://localhost:9091`, production `http://localhost:9090`.
- Terminal B: journal and fault-file edits. Docker fault commands run on the deployment host.

Metrics exporters are loopback ports 9465/9464; OTLP port 4318 stays inside Compose. MAS requires a desktop display; no separate Jason GUI launch is needed. It remains open after completion. Close it before the next campaign. Closing the console during a live job does not cancel GitHub; inspect the outstanding run before restarting anything.

## 3. Local rehearsal first

From the repository root:

```powershell
py -3 bdi-cicd-framework/run_controller.py --gui --scenario production_unhealthy
```

Expected MAS: normal jobs, production observation `block`, `BDI_DECISION=rollback`, rollback job, `BDI_RECOVERY=restored`, `BDI_CONTROLLER_RESULT=stopped recovery=restored`. This uses the actual generated Jason agent with simulated jobs/telemetry; it creates no GitHub runs or deployments.

Reproduce the local regression matrix:

```powershell
py -3 -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
py -3 bdi-cicd-framework/verify_controller_experiment.py
```

The matrix checks healthy/failed recovery, missing telemetry, retry, uncertainty, a pause, staging-only goals and the second project. It shortens observation waits in a copied test manifest; the live manifest remains 18 observations at five-second intervals.

## 4. Publish and establish healthy v1

Merge the repair PR, then in a clean checkout:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git tag -a bdi-console-v1.0.0 -m 'Complete BDI recovery baseline'
git push origin bdi-console-v1.0.0
gh auth login -h github.com
$env:GITHUB_TOKEN = gh auth token
if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication required' }
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:BDI_WORKFLOW_REF = 'main'
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
Remove-Item Env:BDI_READY_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-console-v1.0.0
$env:BDI_CAMPAIGN_ID = 'v1-' + (Get-Date -Format yyyyMMdd-HHmmss)
$baselineDir = "bdi-cicd-framework/bdi/build/controller-runs/$env:BDI_CAMPAIGN_ID"
py -3 bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir $baselineDir
```

`--baseline` explicitly allows the first deployment without an earlier recovery target. It still verifies all goals and production telemetry. A failing baseline cannot recover automatically. Wait for `achieved`, handle configured Environment approvals, then close MAS. The duration budget in `02_goal.yaml` includes job waiting/execution; adjust it before the run if the stated budget is unsuitable.

```powershell
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$v1Health = Invoke-RestMethod http://localhost:3000/health
$v1Health
Invoke-RestMethod http://localhost:3000/ready
```

Open `/checkout` and make a fake payment. Record v1's commit SHA, `deploymentRunId`, the result receipt and GitHub production run URL. The receipt must show an achieved **live** run and verified production telemetry. Scenario receipts, wrong-repository receipts and unverified releases are rejected as recovery targets.

## 5. Publish candidate v2, then run it

```powershell
git switch -c demo/payment-v2 main
# Make an intentional candidate change, such as receipt wording.
npm test
npm run lint
npm run build
git add -p
# Explicitly add any new candidate files too; git add -p omits untracked files.
git diff --cached
git commit -m 'Prepare payment v2 candidate'
git push -u origin demo/payment-v2
git tag -a bdi-console-v2.0.0-rc1 -m 'Payment v2 candidate'
git push origin bdi-console-v2.0.0-rc1
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-console-v2.0.0-rc1
$env:BDI_CAMPAIGN_ID = 'v2-' + (Get-Date -Format yyyyMMdd-HHmmss)
$controllerArgs = @('--gui', '--known-good', $knownGood, '--confirm-compatible-rollback')
py -3 bdi-cicd-framework/run_controller.py @controllerArgs
```

The confirmation asserts v1 source can run against the retained database schema/data. Recovery rebuilds the pinned v1 source; it does not restore database contents or guarantee an identical image digest. Use compatible demo revisions. No persistent volumes are deleted.

Healthy expected sequence: `build,test,security,staging,observe staging,production,observe production → achieved`; rollback is absent. `/health` identifies the production execution UUID. Match it to the journal's run URL and source SHA.

## 6. Watch a pause and inject failures

Before a new campaign, close the previous MAS, choose a new campaign ID and prepare a control file in Terminal A:

```powershell
New-Item -ItemType Directory -Force bdi-cicd-framework/bdi/build/manual-control | Out-Null
Set-Content bdi-cicd-framework/bdi/build/manual-control/faults.properties '' -Encoding ascii
$env:BDI_EXECUTION_PLAN = (Resolve-Path bdi-cicd-framework/bdi/build/manual-control/faults.properties).Path
$env:BDI_CAMPAIGN_ID = 'fault-' + (Get-Date -Format yyyyMMdd-HHmmss)
py -3 bdi-cicd-framework/run_controller.py @controllerArgs --pause-after staging --pause-ms 60000
```

Wait for `controller_pause after_entity=staging`. GitHub must show no production successor yet. The fault file is reloaded before every dispatch. Within the minute, Terminal B writes:

```powershell
Set-Content bdi-cicd-framework/bdi/build/manual-control/faults.properties 'production.force_error_rate=1' -Encoding ascii
```

Expected human-visible result:

1. Production job deploys v2 in high-error mode and creates run-correlated traffic.
2. MAS receives production telemetry `block` and prints `BDI_DECISION=rollback`.
3. A separate `Rollback entity` Actions run appears. Approve production again if required. Its source is v1's SHA, not v2's.
4. Recovery job redeploys v1 with normal fake-payment behaviour and creates fresh telemetry.
5. MAS observes the rollback execution ID and reports `stopped / restored` only when healthy.
6. `/health` now matches the rollback execution UUID; `/ready` and a fake payment succeed. Candidate production goal remains unmet in the result.

For each other case, clear the file, use a new campaign ID, and choose the indicated pause:

| Case | Pause / file contents | Expected result |
|---|---|---|
| Transient test failure | after build / `test.1.failure_mode=force_failure` | Test fails once, Jason retries, then progresses |
| Retry exhaustion | after build / `test.failure_mode=force_failure` | Two failures, stopped; no deployment |
| High-error staging | after security / `staging.force_error_rate=1` | Staging telemetry blocks; no production or rollback |
| Terminal deployment failure | after staging / `production.failure_mode=force_failure` | Production fails after deployment; Jason selects rollback |
| Recovery job failure | after staging / both `production.force_error_rate=1` and `rollback.failure_mode=force_failure` on separate lines | One failed rollback; stopped/failed; operator intervention |

For missing production telemetry, pause after **production**, then stop only production Prometheus on the deployment host:

```powershell
docker compose -p payment-production stop prometheus
```

MAS prints `wait_reconsider`. Restart it within the observation window to demonstrate reconsideration and eventual success:

```powershell
docker compose -p payment-production start prometheus
```

If the production observation budget is exhausted, Jason selects rollback. That job's Compose startup also starts Prometheus, and Jason verifies recovery using the rollback UUID. To demonstrate *unverified recovery*, use local scenario `rollback_unknown`, or stop Prometheus during `--pause-after rollback --pause-ms 60000`. Expect `unknown / unverified`; never label that a successful restore. Restart Prometheus afterwards. If two-minute metric samples have expired, regenerate healthy fake-payment traffic before expecting `allow`.

## 7. Same pipeline, staging-only goal

```powershell
$env:BDI_CAMPAIGN_ID = 'staging-only-' + (Get-Date -Format yyyyMMdd-HHmmss)
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
py -3 bdi-cicd-framework/run_controller.py --gui --goal bdi-cicd-framework/models/payment_goal_staging.yaml
```

Expected: `build,test,security,staging,observe staging → achieved`. Neither production nor rollback is selected. No known-good receipt is required because this goal cannot reach production.

## 8. Repeat and record

Clear faults; reuse the same source SHA with a fresh campaign ID. To return to v1 deliberately, redeploy its SHA through the normal controller with the known-good receipt. The separate `Manual production rollback` workflow is an emergency operator tool outside the experiment; use it only after stopping the controller and settling outstanding GitHub runs.

Keep `generation-manifest.json`, `controller-journal.jsonl`, `controller-result.json`, MAS decision output and GitHub run URLs. Record expected/actual sequences, source/configuration hashes, every execution UUID, telemetry readings, recovery outcome and unmet candidate goals. Automated scenario URLs start with `scenario://`; they are never live evidence. There is no continuous production monitor after the bounded campaign ends.

## 9. What to provide for an assisted live run

- Authenticate locally with `gh auth login` or set a scoped token in the controller process. Do not paste a token into chat or commit it. Dispatch needs repository Actions write access; reading runs needs Actions read. Publishing changes separately needs repository/workflow write authority. See [GitHub's dispatch API permissions](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
- Publish/review this branch and provide the exact baseline/candidate refs. The baseline must produce a successful live receipt. Confirm both releases use compatible database schemas.
- Identify the intended Linux deployment runner/host and give it the `payment-deploy` label; Docker/Compose must work under its account. Confirm the designated demo ports/volumes and controller-to-telemetry connectivity.
- Keep a desktop session available only for visible MAS inspection. A browser is optional for automation. Required Environment approvals still need an authorized reviewer; this agent does not bypass them.
- Confirm permission to deploy/inject faults into these fake-payment staging/production demo stacks and, separately, permission to publish any branch/PR changes. No unrelated infrastructure is needed.

The saved GitHub login already works in this session outside the sandbox. A new token is not currently the missing prerequisite. Runner labels, target connectivity, published workflow versions and a verified compatible v1 baseline still need to be established for live recovery evidence.
