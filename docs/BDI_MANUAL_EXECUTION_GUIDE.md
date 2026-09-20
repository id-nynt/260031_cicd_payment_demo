# Manual payment-service BDI experiment

Perform one numbered step at a time and check its result before continuing. This guide does not use an end-to-end experiment script. You start each campaign yourself; within a campaign, Jason selects jobs automatically so you can observe the BDI behavior.

The [generation and runtime explanation](BDI_GENERATION_AND_RUNTIME.md) links the inputs, generators, outputs, environment and telemetry sources. This guide uses the implemented job-level design. Embedded GitHub steps in `01_pipeline.yaml` are a proposed extension, not current syntax.

**PowerShell** commands run at the repository root in a dedicated controller checkout, outside the runner's `_work` directory and execution slot. **Runner terminal** commands run on the Linux deployment runner. The examples assume Windows can reach the runner's services through localhost; verify this if using WSL/Docker Desktop.

## 1. Understand the start buttons

| You do this | What starts | Live BDI deployment? |
|---|---|---|
| Start Docker Desktop / Docker Engine | Container engine | No |
| `docker compose up -d --build` | App, database, collector and Prometheus for that Compose project | Starts that local stack; no Jason |
| Start the self-hosted runner | Runner waiting for GitHub jobs | No |
| Push to `main`, or open a PR | Validation workflow | No deployment campaign |
| Run `generate_project.py` | Project compiler | No; writes persistent contract and agent |
| Run `run_controller.py --validate-only` | Artifact consistency check | No |
| Run `run_controller.py --scenario ...` | Jason with simulated adapters | No real GitHub jobs or deployment |
| Run `run_controller.py --baseline ...` or `--known-good ...`, without `--scenario` | Jason, Java environment and selected GitHub dispatches | Yes |

**The live experiment's start button is `run_controller.py`.** A push does not activate the live agent. Do not separately launch Jason or manually dispatch each entity. After a campaign, the agent stops controlling; it is not an always-running monitoring daemon.

## 2. Check the framework version and tools

Actions:

- Open the controller checkout and inspect its branch/version. Preserve uncommitted work before switching branches.
- The repaired implementation is on `repair/bdi-canonical-controller`; do not assume an older `main` or `fix/bdi-controller-runtime` contains it.
- Verify Python 3.12, JDK 21+, Node 22+, GitHub CLI and the two separate commands.

PowerShell:

```powershell
git status --short
git branch --show-current
git log -3 --oneline
py -3 --version
java -version
node --version
gh --version
py -3 -B bdi-cicd-framework/generate_project.py --help
py -3 -B bdi-cicd-framework/run_controller.py --help
```

If PyYAML is missing:

```powershell
py -3 -m pip install PyYAML==6.0.3
```

Checkpoint: generation supports `--pipeline`, `--goal`, `--project-dir`; runtime supports `--validate-only`, `--gui`, `--scenario`, `--baseline`, `--known-good`. Runtime no longer accepts `--generate-only`. An unrecognized option indicates a different revision or command.

## 3. Turn on the local app and inspect telemetry

Actions:

- Start Docker Desktop (or Docker Engine).
- Use a **separate local-app PowerShell window** and separate ports, so this rehearsal does not occupy staging/production ports.

```powershell
docker info
$env:COMPOSE_PROJECT_NAME = 'payment-local'
$env:APP_PORT = '3002'
$env:POSTGRES_PORT = '5434'
$env:METRICS_PORT = '9466'
$env:PROMETHEUS_PORT = '9092'
$env:DEPLOYMENT_ENVIRONMENT = 'local'
$env:CI_RUN_ID = 'local'
$env:EXPERIMENT_MODE = 'normal'
$env:PAYMENT_PROVIDER = 'fake'
$env:FAKE_PAYMENT_OUTCOME = 'succeeded'
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:3002/health
Invoke-RestMethod http://localhost:3002/ready
```

Open `http://localhost:3002/checkout` and make a fake payment. If readiness has not passed, inspect `docker compose logs --tail=80 app postgres` and repeat the readiness request.

Generate requests and view metrics:

```powershell
$env:PAYMENT_BASE_URL = 'http://localhost:3002'
npm run traffic:experiment -- normal 6
Start-Sleep -Seconds 10
curl.exe -s http://127.0.0.1:9466/metrics | Select-String 'payment_'
```

Open `http://localhost:9092`. Enter this in Prometheus's query box:

```promql
payment_service_ready{ci_run_id="local"}
```

Checkpoint: `/health` shows `deploymentRunId=local`, readiness succeeds and the metric exists. This verifies app telemetry, not BDI control. These local ports do not replace the staging/production URLs in input 01.

When finished, stop the rehearsal stack from the same window:

```powershell
docker compose stop
```

This preserves its database volume. Close that window so its local port variables are not carried into later commands.

## 4. Start the deployment runner

Actions:

- GitHub repository -> Settings -> Actions -> Runners: check the intended runner.
- If absent, use **New self-hosted runner**, select Linux, and follow GitHub's registration commands.
- Add the custom label `payment-deploy`. The worker requires `self-hosted`, `linux`, `payment-deploy`.
- Start the runner in its own Linux terminal unless it is already running as a service.

Runner terminal, using your actual runner directory:

```bash
cd ~/actions-runner-payment
docker info
docker compose version
curl --version
./run.sh
```

Checkpoint: GitHub shows online/idle with the required labels; Docker works as the runner account. Keep that terminal open. A runner waiting for work does not start the app itself.

In GitHub -> Settings -> Environments, verify `staging` and `production`. Understand any reviewer approvals: approve the requested GitHub deployment when appropriate, rather than starting another controller.

## 5. Review endpoints, duration and published worker

Actions:

- Read [01_pipeline.yaml](../bdi-cicd-framework/models/01_pipeline.yaml) and [02_goal.yaml](../bdi-cicd-framework/models/02_goal.yaml).
- Check staging readiness/Prometheus are 3001/9091 and production readiness/Prometheus are 3000/9090 on the intended host. Loopback is relative to the controller making the request; for a remote host, arrange a tunnel/protected endpoint and update/regenerate the configuration. Changing a hostname alone does not expose loopback-bound Prometheus.
- Review the duration budget. The checked-in `production.duration <= 100000` means **100 seconds**, including controller-observed waiting/execution/polling. It is not just application latency.

If 100 seconds is inappropriate, edit that goal before generation. For example, a deliberately chosen 30-minute budget is:

```yaml
- production.duration <= 1800000
```

Record the chosen budget and keep it fixed across comparisons. It is distinct from the worker's 20-minute job timeout and Java's default 20-minute entity wait. Longer queues can still lead to uncertainty requiring reconciliation.

Publish the approved framework/worker through your normal review process before live dispatch. Verify `.github/workflows/entity-execution.yml` is on the repository's default branch, and the selected workflow ref contains the intended worker. GitHub documents the `workflow_dispatch` default-branch requirement in [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax). A tag existing only locally is insufficient.

Checkpoint: the controller is current, endpoints describe the intended deployments, and the approved worker is available on GitHub. This preparation has not started a campaign.

## 6. Generate the project once

PowerShell in the controller checkout:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
Get-Content bdi-cicd-framework/models/03_workflow_model.yaml
Get-Content bdi-cicd-framework/bdi/controller_agent.asl -TotalCount 70
```

Checkpoint: validation succeeds. The agent contains project facts (`entity`, `depends`, `required`, goals and recovery) followed by generic decision rules. No GitHub job has run.

If you changed the inputs, review and commit their generated artifacts together:

```powershell
git diff -- bdi-cicd-framework/models bdi-cicd-framework/bdi/controller_agent.asl
git add bdi-cicd-framework/models/01_pipeline.yaml bdi-cicd-framework/models/02_goal.yaml bdi-cicd-framework/models/03_workflow_model.yaml bdi-cicd-framework/models/generation-manifest.json bdi-cicd-framework/bdi/controller_agent.asl
git diff --cached
git commit -m 'Record payment experiment configuration and generated agent'
```

Commit only intended changes, and publish through the same review process. Do not regenerate for each campaign. Input/compiler/policy changes require explicit regeneration; source-only application changes can reuse the agent.

## 7. Rehearse Jason without deploying

```powershell
$sessionName = 'manual-' + (Get-Date -Format yyyyMMdd-HHmmss)
$rehearsalDir = "bdi-cicd-framework/runs/$sessionName-rehearsal"
py -3 -B bdi-cicd-framework/run_controller.py --gui --scenario production_unhealthy --artifacts-dir $rehearsalDir
```

Watch normal job selection, production telemetry rejection, rollback and verification. Expected final result: `stopped`, `recovery=restored`. Exit code 1 is expected for stopped candidate delivery, even when recovery succeeded.

Close the MAS console after the final result, then inspect:

```powershell
Get-Content "$rehearsalDir/controller-result.json"
```

Checkpoint: `mode=scenario`. This receipt cannot serve as a live known-good release. Omit `--gui` on a headless controller; do not launch a separate MAS.

## 8. Store v1 as an immutable source version

Actions:

- Use a clean approved revision containing the intended framework, worker and generated configuration.
- A commit identifies source; an annotated tag gives it a memorable name. A tag does not prove a successful deployment.
- Use new names; never overwrite earlier experiment tags.

```powershell
git status --short
$sessionName = 'manual-' + (Get-Date -Format yyyyMMdd-HHmmss)
$v1Tag = "$sessionName-v1"
$v1Tag
git tag -a $v1Tag -m 'Payment experiment baseline candidate'
if ($LASTEXITCODE -ne 0) { throw 'Tag creation failed; inspect the error before pushing' }
git show-ref --verify "refs/tags/$v1Tag"
if ($LASTEXITCODE -ne 0) { throw 'The local v1 tag does not exist; do not push yet' }
git push origin "refs/tags/$v1Tag"
if ($LASTEXITCODE -ne 0) { throw 'Push failed; keep this tag name and resolve the reported error' }
$v1Sha = git rev-list -n 1 $v1Tag
$v1Sha
```

This step initializes its own live-session name, so it also works if you skipped step 7 or opened a new PowerShell window. `$v1Tag` should print something like `manual-20260920-233000-v1`, never just `-v1`. PowerShell variables are local to that terminal session; they are not stored by Git or shared between terminal windows.

If you see `src refspec refs/tags/-v1 does not match any`, `$sessionName` was empty when the tag name was constructed and there is no local tag at that ref. Run this corrected block to create a properly named tag. This is not caused by using a separate Git worktree. Check the selected source with `git branch --show-current` and `git log -1 --oneline` before tagging.

If a correctly named tag was already created and only its push failed, keep that tag and retry its push after resolving the error; do not rerun tag creation, force-update it or create replacement versions unnecessarily. In a new terminal, restore the exact existing name with `$v1Tag = 'YOUR-EXISTING-TAG'` and verify it with `git show-ref --verify "refs/tags/$v1Tag"`.

Checkpoint: the tag is available remotely and resolves to a full commit SHA. Tag creation/push does not start a live campaign under these workflows. Record the actual tag name and SHA in your experiment notes and keep these PowerShell variables for later steps. In a new terminal, restore `$sessionName`, `$v1Tag` and `$v1Sha` explicitly from those notes before continuing.

## 9. Authenticate and select the live versions

```powershell
gh auth login -h github.com
gh auth status
$env:GITHUB_TOKEN = gh auth token
if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication failed' }
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:BDI_WORKFLOW_REF = $v1Tag
$env:BDI_RELEASE_SHA = $v1Sha
```

Use your actual repository if different. The token needs Actions dispatch/read access. Do not print or include it in evidence.

| Selection | Meaning |
|---|---|
| `BDI_WORKFLOW_REF` | Published worker definition; keep pinned while comparing v1/v2 |
| `BDI_RELEASE_SHA` | Source revision the normal jobs check out; change for v2 |
| `--known-good` receipt | Verified source to restore if recovery is selected |

Clear old experiment settings:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
Remove-Item Env:BDI_READY_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
```

Endpoint overrides can send both staging and production observations to the same URL. Leave them unset for this walkthrough. The launcher generates its own campaign UUID; do not try to select it with `BDI_CAMPAIGN_ID`. Your evidence directory name is the readable label.

## 10. Press the live experiment's start button

```powershell
$baselineDir = "bdi-cicd-framework/runs/$sessionName-v1"
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir $baselineDir
```

This starts Jason, loads `controller_agent` and `ControllerEnvironment`, then dispatches the selected entity through Java. You do not manually start staging/production Compose: the selected deployment jobs do that. Do not click **Run workflow** for entities yourself during the campaign.

Keep these views open:

| View | What to observe |
|---|---|
| Controller terminal / MAS console | `BDI_DECISION=run`, `observe`, telemetry decisions, outcome |
| Jason mind-inspector URL printed at startup | Select `controller_agent`; inspect beliefs, events and intentions |
| GitHub Actions | One workflow run per selected entity/attempt; unselected entity jobs skipped |
| Runner terminal / Docker Desktop | Staging and production containers appear when selected |
| App / Prometheus | Staging 3001/9091; production 3000/9090 |

Expected: build -> test -> security -> staging -> staging verification -> production -> production verification -> achieved. No rollback. The first baseline has no earlier recovery release; a failed baseline must not be accepted as known-good. Resolve failures/uncertainty and use a new directory for another attempt.

## 11. Verify and retain the baseline

After `BDI_CONTROLLER_RESULT=achieved`, close the MAS console:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw | ConvertFrom-Json
$baseline | Select-Object mode, outcome, release_sha, recovery_outcome
$baseline.verified_releases
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$v1Health = Invoke-RestMethod http://localhost:3000/health
$v1Health
Invoke-RestMethod http://localhost:3000/ready
```

Checkpoint: `mode=github`, `outcome=achieved`, SHA equals `$v1Sha`, and production has a verified release record. Match `/health`'s `deploymentRunId` to the journal's production execution UUID. The app does not expose a Git SHA at `/health`; use the receipt, journal and GitHub checkout evidence for that association.

Open `http://localhost:3000/checkout` and make a fake payment. On the runner, `docker ps` should show `payment-staging` and `payment-production`. Keep the entire baseline directory, not only its result JSON.

## 12. Inspect the actual telemetry

```powershell
curl.exe -s http://127.0.0.1:9465/metrics | Select-String 'payment_'
curl.exe -s http://127.0.0.1:9464/metrics | Select-String 'payment_'
$executionId = $v1Health.deploymentRunId
$query = 'payment_service_ready{ci_run_id="' + $executionId + '"}'
Invoke-RestMethod ("http://127.0.0.1:9090/api/v1/query?query=" + [uri]::EscapeDataString($query))
```

In Prometheus at `http://localhost:9090`, paste each full query from input 01 and replace `{{run_id}}` with the actual execution UUID, not the numeric GitHub run ID or a PowerShell variable name. Error rate is a ratio, latency is ms, readiness should be 1.

To produce more traffic for inspection:

```powershell
$env:PAYMENT_BASE_URL = 'http://localhost:3000'
npm run traffic:experiment -- normal 6
Start-Sleep -Seconds 10
```

Checkpoint: app identity, metrics and campaign evidence refer to the same execution. The worker already generates traffic during deployment. Old campaign results do not update when you send later traffic.

## 13. Create and store v2

Actions:

- Retain the trusted v1 receipt.
- Branch from v1 and make a harmless visible app change, such as the `Payment receipt` heading in `receiptPage` in `src/ui.ts`. Avoid a database migration in the first recovery demonstration.
- Run app checks, review, commit and publish.

```powershell
git switch -c "demo/$sessionName-v2" $v1Sha
# Edit the intended receipt wording, then:
npm ci
npm run lint
npm test
npm run build
git add src/ui.ts
git diff --cached
git commit -m 'Prepare visible payment v2 experiment change'
git push -u origin "demo/$sessionName-v2"
$v2Tag = "$sessionName-v2"
git tag -a $v2Tag -m 'Payment experiment v2 candidate'
git push origin "refs/tags/$v2Tag"
$v2Sha = git rev-list -n 1 $v2Tag
```

If changing a different app file, stage that file explicitly. Review relevant PR/validation results before deploying. Neither controller inputs nor generator changed, so **do not regenerate the agent**. Keep `BDI_WORKFLOW_REF=$v1Tag` to compare both candidates with the same worker.

## 14. Start healthy v2

Confirm that v1 can still use the retained database schema/data. Recovery rebuilds v1 source; it does not restore the database or an attested immutable image.

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = "bdi-cicd-framework/runs/$sessionName-v2-healthy"
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

Checkpoint: achieved, no rollback, visible v2 change. Close the console before the next campaign. Keep `$knownGood` pointing to v1 for the deliberate v2-to-v1 recovery demonstration; replacing it with v2 changes what you restore.

## 15. Run individual fault experiments

Create the controller's fault file. It is reloaded before each selected dispatch; it does not change the persistent agent or contract.

```powershell
New-Item -ItemType Directory -Force bdi-cicd-framework/runs/manual-control | Out-Null
$faultFile = Join-Path (Resolve-Path bdi-cicd-framework/runs/manual-control).Path 'faults.properties'
Set-Content $faultFile '' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
```

Choose one row at a time. Replace the whole file with its content, use a new directory name, then start one v2 campaign with the known-good arguments.

| Experiment | File content | Expected with healthy surrounding infrastructure |
|---|---|---|
| Transient test failure | `test.1.failure_mode=force_failure` | test fails once, Jason retries, delivery can achieve |
| Test exhaustion | `test.failure_mode=force_failure` | two test attempts, stop before deployment |
| Bad staging health | `staging.force_error_rate=1` | staging deployed but blocked; no production dispatch |
| Bad production health | `production.force_error_rate=1` | production blocked, one rollback to v1, verified restoration |
| Production job failure | `production.failure_mode=force_failure` | post-deployment job fails, one rollback to v1 |
| Recovery failure | Two lines: `production.force_error_rate=1` and `rollback.failure_mode=force_failure` | rollback attempted once; recovery failed |

For example:

```powershell
Set-Content $faultFile 'test.1.failure_mode=force_failure' -Encoding ascii
$retryDir = "bdi-cicd-framework/runs/$sessionName-test-retry"
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $retryDir
```

Checkpoint: GitHub shows two distinct test executions; the journal has attempts 1 and 2. `force_error_rate=1` selects the app's high-error mode; it does not assert the measured ratio equals exactly 1.0. Run intentional faults only in the designated experiment environment.

## 16. Demonstrate rollback with a visible pause

Controller Terminal A:

```powershell
Set-Content $faultFile '' -Encoding ascii
$recoveryDir = "bdi-cicd-framework/runs/$sessionName-v2-recovery"
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --pause-after staging --pause-ms 60000 --artifacts-dir $recoveryDir
```

Wait for the journal event `controller_pause` with `after_entity=staging`. This is after the staging executor returns, before its result is published to Jason. A pause alone does not prove telemetry acceptance; Jason checks staging after the pause.

Terminal B, same checkout root, during the pause:

```powershell
Set-Content bdi-cicd-framework/runs/manual-control/faults.properties 'production.force_error_rate=1' -Encoding ascii
```

Watch these steps:

1. Jason accepts staging and selects production.
2. GitHub deploys v2 in high-error mode and generates traffic.
3. Java supplies production measurements; Jason classifies them as blocked.
4. Jason selects rollback once; Java supplies the verified v1 SHA.
5. GitHub rebuilds v1 in normal mode with a new execution UUID.
6. Jason verifies restored telemetry and finishes `stopped/restored`.

Close the console and inspect:

```powershell
$recovery = Get-Content "$recoveryDir/controller-result.json" -Raw | ConvertFrom-Json
$recovery | Select-Object outcome, recovery_outcome, release_sha, known_good_sha
$recovery.unmet_goals
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/ready
```

Checkpoint: stopped/restored, production candidate delivery unmet. Match the current app identity to rollback's execution and its source to `$v1Sha`; verify the v1 wording. The result's `release_sha` still identifies attempted v2, not restored v1.

Clear the fault before any healthy campaign:

```powershell
Set-Content $faultFile '' -Encoding ascii
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
```

## 17. Diagnose the boundary and reconcile uncertainty

| Symptom | Inspect first |
|---|---|
| No Actions run | Startup error, token/repository, published worker/default branch, selected ref |
| Waiting for runner | Online status, `payment-deploy` label, Environment approvals |
| Docker permission error | `docker info` as the runner account |
| Port already allocated | Existing stacks and `docker ps`; avoid a second stack on production ports |
| Telemetry unknown | `/ready`, Prometheus reachability, execution UUID, traffic/histograms and freshness |
| Healthy-looking production triggers recovery | Duration goal and recorded error/latency measurements |
| Stopped after successful rollback | Expected: restoration does not satisfy v2 delivery |

After a stopped process with uncertain execution, close its MAS and reconcile before another campaign:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Keep the same repository credentials and intended project configuration. Reconciliation reads remote state; it does not resume the old campaign or declare achievement. Unknown preserves pending intent; confirmed terminal status clears it. Do not erase the marker to force deployment. Worktrees share a repository lock; independent clones do not.

## 18. Return to v1 and repeat the experiment

Use the original v1 tag/commit and run a new healthy v1 campaign. You do not need to undo the v2 commits, delete the v2 branch or move any tags.

### 18.1. Decide what you need to restore

| Operation | What it changes |
|---|---|
| Select `$env:BDI_RELEASE_SHA = $v1Sha` | Source for the next normal jobs; it does not deploy until you start a campaign |
| Run a new v1 campaign | Rebuilds and deploys v1 to both staging and production and verifies their health |
| Successful automatic rollback | Restores production; staging may still contain v2 |
| Switch a local branch to v1 | Local source files only; existing containers keep running their previous version |
| Restart existing containers | Restarts their current configuration/image; does not select the Git v1 source |

**Recommended reset:** a fresh v1 campaign using the existing verified v1 receipt, followed by the same v2 source in a new campaign. This keeps the software versions and agent configuration comparable across repetitions. It resets deployed source and experiment mode, not database contents.

### 18.2. Finish the previous campaign first

Actions:

- Preserve its entire evidence directory and note its outcome.
- Confirm GitHub has no still-running selected deployment; close the old MAS after it finishes.
- If the controller stopped with uncertain execution, follow step 17's reconciliation before redeploying. Do not delete its pending marker or lock to force a run.
- Keep Docker and the deployment runner running, or restart them using steps 3/4 as appropriate. Do not start the separate local rehearsal stack on deployment ports.

Checkpoint: there is no unresolved or overlapping deployment. A previous `stopped/restored` result is evidence of restoration, not an `achieved` candidate receipt; use the original achieved v1 receipt below.

### 18.3. Recover the original version and receipt selections

If you kept the same PowerShell window, `$v1Tag`, `$v1Sha`, `$v2Tag` and `$knownGood` may still exist. In a new window, set them explicitly from your saved evidence. Replace the three example values before running:

```powershell
$v1Tag = 'YOUR-ORIGINAL-SESSION-v1'
$v2Tag = 'YOUR-ORIGINAL-SESSION-v2'
$knownGood = (Resolve-Path 'bdi-cicd-framework/runs/YOUR-ORIGINAL-SESSION-v1/controller-result.json').Path
$v1Sha = git rev-list -n 1 $v1Tag
$v2Sha = git rev-list -n 1 $v2Tag
$receipt = Get-Content $knownGood -Raw | ConvertFrom-Json
$receipt | Select-Object mode, outcome, release_sha, repository
if ($receipt.mode -ne 'github' -or $receipt.outcome -ne 'achieved' -or $receipt.release_sha -ne $v1Sha) {
    throw 'Select the original achieved live v1 receipt matching the v1 tag'
}
```

The launcher also checks project/repository identity and verified recovery environment. If you used a different pinned worker ref originally, recover that value from the earlier campaign's `generation-manifest.json` rather than changing worker versions accidentally. Local tags and their referenced commits must still exist; retrieve missing published tags through your normal Git workflow if needed, without overwriting existing tags.

If the trusted achieved receipt is lost, recover it from your evidence backup. A tag alone cannot replace it. If no trusted receipt exists, explicitly establish v1 again with `--baseline` and a new directory, as in step 10; that campaign has no automatic recovery source. Do not manufacture a receipt or use a scenario result.

### 18.4. Clear faults and select v1 for deployment

Use the same repository and controller configuration as the original experiment. Reauthenticate in a new shell:

```powershell
gh auth status
$env:GITHUB_TOKEN = gh auth token
if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication failed' }
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:BDI_WORKFLOW_REF = $v1Tag
$env:BDI_RELEASE_SHA = $v1Sha
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
Remove-Item Env:BDI_READY_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
```

Substitute your actual repository and original worker ref if different. Clearing `BDI_EXECUTION_PLAN` disconnects the fault file, even if it still contains a previous fault. When later reattaching it, empty it first as in step 15.

Checkpoint: the persistent project artifacts are valid and candidate source is v1. The controller checkout can remain on the current framework or v2 branch: selected GitHub jobs check out `BDI_RELEASE_SHA`. Do not regenerate just because you repeat a campaign. If configuration/generator changed, intentionally restore the compatible project revision or generate and record a new revision; then describe the repeat as a changed-configuration experiment.

### 18.5. Redeploy and verify v1

Confirm v1 is compatible with the database/schema currently retained from v2. Then choose a new evidence directory:

```powershell
$repeatName = 'repeat-' + (Get-Date -Format yyyyMMdd-HHmmss)
$resetDir = "bdi-cicd-framework/runs/$repeatName-v1"
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $resetDir
```

The existing v1 receipt is valid as the recovery selection even when the candidate is also v1. A recovery attempt still finishes stopped/restored, not achieved; only a completely healthy normal campaign establishes the reset checkpoint.

After the final result, close the console and inspect:

```powershell
$reset = Get-Content "$resetDir/controller-result.json" -Raw | ConvertFrom-Json
$reset | Select-Object mode, outcome, release_sha, recovery_outcome
if ($reset.mode -ne 'github' -or $reset.outcome -ne 'achieved' -or $reset.release_sha -ne $v1Sha) {
    throw 'v1 reset is not verified; inspect this campaign before repeating v2'
}
Invoke-RestMethod http://localhost:3001/health
Invoke-RestMethod http://localhost:3001/ready
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/ready
$knownGood = (Resolve-Path "$resetDir/controller-result.json").Path
```

Checkpoint: staging and production are healthy v1 deployments, their new execution IDs match this campaign's evidence, and v1 wording appears in the UI. Keep both the original receipt and this fresh achieved v1 receipt. Do not reuse an old directory or overwrite earlier evidence.

### 18.6. Repeat v2 without recreating versions

For the same comparison, reuse the existing v2 tag/SHA. You do not need a new v2 commit or tag unless its source actually changes.

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = "bdi-cicd-framework/runs/$repeatName-v2-healthy"
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

Then repeat the individual fault experiments in steps 15/16, using new directory names based on `$repeatName` and an explicitly selected fault each time. Keep the v1 receipt as `$knownGood` when demonstrating v2-to-v1 restoration.

For editing local files from v1 rather than merely deploying it, first preserve uncommitted work and stop using that checkout for an active controller. A new branch preserves the existing v2 history:

```powershell
git status --short
git switch -c "demo/$repeatName-from-v1" $v1Sha
```

This optional source checkout does not deploy anything. Keep a compatible controller checkout available; an older app tag may contain an older framework. Do not use `git reset --hard`, force-update tags, or delete branches to repeat the experiment.

Database rows, volumes and historical Prometheus samples remain. Execution-ID correlation separates new observations, but this is not a pristine-data reset. If the research protocol needs identical initial data, plan a separate verified database backup/restore procedure; do not treat `docker compose down -v` as routine repetition.

## 19. Retain evidence and finish

Keep each entire campaign directory: snapshots, `generation-manifest.json`, `project-generation-manifest.json`, journal and result. Add expected/actual sequence, GitHub URLs, app/Prometheus observations and MAS screenshots. Keep the trusted v1 receipt for subsequent recovery experiments.

The app continues running after the controller ends. Closing the MAS does not cancel a remote GitHub job. Before stopping the runner, confirm no campaign or remote deployment is active. Preserve database volumes.

No live commands in this guide were executed while writing it. Local simulation is not live deployment evidence. Historical records remain under [experiments](experiments/).

For files that can be regenerated, legacy compatibility material and cleanup candidates, see the [project file audit](BDI_FILE_AUDIT.md). Campaign evidence and known-good receipts are not disposable caches.
