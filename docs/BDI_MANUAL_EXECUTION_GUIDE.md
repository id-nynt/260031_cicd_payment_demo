# Manual guide: run and observe the BDI CI/CD experiment

This guide takes you from setup to a visible v1-to-v2 deployment. Run each step yourself, watch Jason and GitHub Actions, and choose when to inject faults. There is no end-to-end experiment script.

```text
Save and deploy stable v1 -> keep it running -> prepare visible v2
-> start BDI -> watch selected jobs -> observe success or inject a fault
-> save evidence -> restore v1 for the next experiment
```

## All phases at a glance

Complete **Part A** first. Its local app check and simulated BDI rehearsal do not deploy through GitHub. **Part B** uses real GitHub Actions and Docker containers: B1 establishes the live baseline; B3 onward tests v2.

| Category | Phase | Visible checkpoint |
|---|---|---|
| Setup | A1. Prepare checkout and tools | Tool versions and Docker respond |
| Setup / app test | A2. Test the app separately | Fake payment works on port 3002 |
| Setup | A3. Start the deployment runner | GitHub shows Idle / Online |
| Setup | A4. Review inputs and generate artifacts | Model/agent consistency passes |
| Setup | A5. Publish the repaired worker | Updated workflow exists at the worker tag |
| Setup | A6. Configure controller credentials | Workflow metadata is readable |
| Setup / BDI test | A7. Rehearse Jason locally | MAS Console reaches achieved |
| Live baseline | B1. Save and deploy stable v1 | Both environments run verified v1 |
| Live observation | B2. Open v1 and keep it running | Production checkout works |
| Real experiment | B3. Prepare and publish visible v2 | GitHub has v2; deployed app is still v1 |
| Real experiment | B4. Start the BDI agent | MAS Console selects build |
| Real observation | B5. Watch the pipeline and app | v2 appears, then health is assessed |
| Real experiments | B6. Try one fault scenario | Agent retries, rechecks, stops or restores |
| Evidence | B7. Record results and decisions | Result explains the final state |
| Repeat | B8. Restore v1 | Both environments return to v1 |
| Optional experiment | C. Request a failure goal | Expected staging failure satisfies the goal |

### Windows to keep open

| Window | Purpose |
|---|---|
| **Controller PowerShell** | Generation and campaign commands; keep it open to retain variables |
| **Linux runner terminal** | `./run.sh`, unless the runner already runs as a service |
| **Observation PowerShell** | Follow the journal while the controller terminal is occupied |
| **Traffic PowerShell** | Send temporary or continuous traffic during fault experiments |
| **Browser / Docker Desktop** | GitHub Actions, deployed app, Prometheus and containers |
| **MAS Console** | Opens automatically with `--gui`; shows Jason output |

PowerShell commands run from `C:\NHI\2026_IT-Project\260031_payment-repair` unless stated otherwise. Bash commands run in Ubuntu/WSL. Variables do not transfer between PowerShell windows. Run commands in order and stop if a command fails.

The controller starts Jason; Java executes Jason's selected action; GitHub runs that entity only. A push publishes code. **Starting `run_controller.py` starts the live BDI campaign.** Closing the finished MAS Console does not stop deployed containers.

## Part A - Setup and separate system checks

### A1. Prepare the checkout and tools

Actions:

- Start Docker Desktop and wait for its engine.
- Open Controller PowerShell in the repaired checkout.
- Keep the existing repository: `payment` and `payment-repair` are linked Git worktrees. This second folder needs no new GitHub repository or runner.

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
git status --short --branch
git worktree list
git remote -v
py -3 --version
java -version
node --version
gh --version
docker info
docker compose version
py -3 -m pip install PyYAML==6.0.3
npm ci
```

**Expected result:** Python, JDK 21 or newer, Node 22 or newer, GitHub CLI and Docker respond. Remote is `id-nynt/260031_cicd_payment_demo`. Start from `repair/bdi-canonical-controller`; B3 later creates a candidate branch. Preserve existing edits, including `docs/NOTE.md`.

### A2. Test the app separately on port 3002

In a **new PowerShell window**, run:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$env:COMPOSE_PROJECT_NAME = 'payment-local'
$env:APP_PORT = '3002'
$env:POSTGRES_PORT = '5434'
$env:METRICS_PORT = '9466'
$env:PROMETHEUS_PORT = '9092'
$env:CI_RUN_ID = 'local'
$env:EXPERIMENT_MODE = 'normal'
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:3002/ready
$env:PAYMENT_BASE_URL = 'http://localhost:3002'
npm run traffic:experiment -- normal 6
```

Open `http://localhost:3002/checkout`. Select **Demo card simulation**, continue, and use card `4242424242424242`, expiry `12/30`, CVC `123`. In Prometheus at `http://localhost:9092`, query `payment_service_ready{ci_run_id="local"}` after allowing 10-20 seconds for metrics.

**Expected result:** a successful fake-payment receipt, readiness reports `ready`, traffic prints HTTP 201, and Prometheus readiness is `1`.

Finish in that same window:

```powershell
docker compose stop
```

Close the rehearsal window. Keep Docker Desktop running. Port 3002 is now stopped intentionally; B1 starts separate live stacks on ports 3001 and 3000.

### A3. Start the existing deployment runner

Actions:

- GitHub repository > **Settings > Actions > Runners**: find the existing Linux runner.
- Check labels `self-hosted`, `linux`, `payment-deploy`.
- If its service is already Online / Idle, leave it running. Otherwise start it below.

PowerShell:

```powershell
wsl -d Ubuntu
```

Ubuntu (adjust the installation path if yours differs):

```bash
cd ~/actions-runner-payment
docker info
docker compose version
./run.sh
```

**Expected result:** terminal says it is listening for jobs; GitHub shows **Idle / Online**. Leave it running. If no runner exists, follow GitHub's New self-hosted runner instructions once.

In **Settings > Environments**, check `staging` and `production`. Grant any required deployment approval when a job waits for it.

These instructions assume Windows can reach WSL/Docker Desktop services through localhost. If the runner is elsewhere, configure reachable telemetry endpoints in input 01 before A4; localhost would refer to the wrong computer.

### A4. Review inputs and generate the project

Actions:

- Open `bdi-cicd-framework/models/01_pipeline.yaml`: entities, dependencies, worker mappings, retry/observation limits and telemetry endpoints.
- Open `models/02_goal.yaml` in that framework: keep normal staging/production success goals for Part B.
- Generate after changing inputs or generator/policy. Do not edit the generated agent manually.

Controller PowerShell:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
```

**Expected result:** generation lists the saved workflow model, agent and manifest; validation prints `Project artifacts are consistent`. The generated `bdi/controller_agent.asl` contains `achievement(staging, success)` and `achievement(production, success)`.

The persistent outputs are `models/03_workflow_model.yaml`, `bdi/controller_agent.asl` and `models/generation-manifest.json`. Campaigns reuse them. App-only changes and fault selections need no regeneration. If you customize inputs, review and commit them together with the generated outputs before publication.

### A5. Publish the repaired worker

The local repair and GitHub's older `main` can differ. The selected worker must include `rollback`, `transient_failure` and `request_faults`.

These are publication commands **for you to execute after reviewing the revision**. They publish code; they do not deploy containers.

```powershell
$publishBranch = git branch --show-current
git log -1 --oneline
git status --short
git push -u origin $publishBranch
if ($LASTEXITCODE -ne 0) { throw 'Branch push failed; resolve authentication first' }
$workerRef = 'bdi-worker-' + (Get-Date -Format yyyyMMdd-HHmmss)
git tag $workerRef
if ($LASTEXITCODE -ne 0) { throw 'Worker tag creation failed' }
git push origin "refs/tags/$workerRef"
if ($LASTEXITCODE -ne 0) { throw 'Push failed; keep this tag and retry after fixing access' }
$workerRef
```

On GitHub, select this tag and open `.github/workflows/entity-execution.yml`. Check the three capabilities above. Keep this worker tag unchanged for all comparisons. The workflow must also exist on the default branch for dispatch; it already existed there when the repository was checked for this guide.

**Expected result:** GitHub shows the repair branch and worker tag. These pushes do not start deployment under the repaired workflow definitions. Opening a pull request runs validation; merging is not required just to dispatch the worker tag. Historical Actions entries may remain visible.

A push 403 is a Git credential problem, not a duplicate-folder problem. Fix access and retry the same tag. Do not proceed with an unpublished worker ref.

### A6. Configure controller credentials

Use a fine-grained token for this repository with **Actions: Read and write**. Git publication credentials may differ from the controller token. Never commit or print tokens.

Controller PowerShell:

```powershell
$dispatchToken = Read-Host 'Controller token (hidden)' -AsSecureString
$env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new('', $dispatchToken).Password
Remove-Variable dispatchToken
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:BDI_WORKFLOW_REF = $workerRef
$headers = @{ Authorization = "Bearer $env:GITHUB_TOKEN"; Accept = 'application/vnd.github+json' }
Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$env:GITHUB_REPOSITORY/actions/workflows/entity-execution.yml" | Select-Object name, state, path
Remove-Variable headers
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL,Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
```

**Expected result:** metadata shows `BDI Entity Execution`, `active`, and its path. This checks read access only; confirm Actions write in token settings. `Remove-Item` is silent when a variable does not exist; that is normal.

### A7. Rehearse the agent without deploying

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --gui --scenario healthy
```

**Expected result:** MAS Console opens. Select the `controller_agent` log tab if tabs appear. Look for:

```text
Master goal started.
BDI_DECISION=run entity=build attempt=1
...
Master goal achieved.
BDI_CONTROLLER_RESULT=achieved recovery=not_needed
```

Open the **Agent mind inspector** URL printed at startup and select `controller_agent`. Inspect beliefs such as `achievement(...)`, `phase_result(...)`, `telemetry(...)`, and finally `master_goal_achieved` and `workflow_completed`. Use the printed URL; its address varies.

This is real Jason with simulated jobs/telemetry. No GitHub runs or deployments should appear. At the final result, close MAS Console to return to PowerShell. Gradle can remain at **75% EXECUTING** until the GUI closes; that percentage is not campaign progress.

## Part B - Real v1-to-v2 experiment and observation

### B1. Save and deploy stable v1

The existing `v1` tag records source; a successful live campaign establishes it as a verified baseline. Preserve that tag. If you already have a verified live v1 receipt and the app is running, set `$knownGood` to its full path and reuse it. Otherwise run this baseline campaign.

First select v1 and check it is published:

```powershell
$v1Tag = 'v1'
$v1Sha = git rev-list -n 1 $v1Tag
if ($LASTEXITCODE -ne 0 -or -not $v1Sha) { throw 'Local v1 tag is missing; select the intended stable version first' }
$v1Sha
git ls-remote origin 'refs/tags/v1' 'refs/tags/v1^{}'
```

The remote must identify the same commit. For an annotated tag, compare its `^{}` line. The remote v1 was confirmed at `caa26da` when this guide was written. If the local tag exists but is unpublished, publish it with `git push origin refs/tags/v1`; do not move an existing remote tag.

Then launch in Controller PowerShell:

```powershell
$env:BDI_RELEASE_SHA = $v1Sha
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$baselineDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-v1'
$baselineDir
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir $baselineDir
```

**Watch:** MAS starts build, test, security, staging and production in order, with health checks after deployments. GitHub **Actions > BDI Entity Execution** shows a separate run per selected entity/attempt. Inside a run, the selected job executes and sibling entity jobs are skipped. Hosted runners execute build/test/security; your Linux runner executes deployments.

**Expected result:** staging and production stacks start and health is verified. Console prints `BDI_CONTROLLER_RESULT=achieved recovery=not_needed`. See B5 for the observation checklist. A 403 means no verified baseline was established.

Close MAS Console after completion, then read the receipt:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw | ConvertFrom-Json
$baseline | Select-Object mode, outcome, release_sha, recovery_outcome
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $v1Sha) {
    throw 'Baseline not verified; inspect its journal before continuing'
}
$baseline.verified_releases
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$knownGood
```

**Checkpoint:** mode is `github`, outcome is `achieved`, and `verified_releases` includes staging and production. Save this receipt path for recovery. A simulated receipt from A7 cannot serve as the live baseline.

### B2. Open v1 and keep it running

```powershell
docker ps
Invoke-RestMethod http://localhost:3001/health
Invoke-RestMethod http://localhost:3001/ready
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/ready
```

| View | Open / inspect | Expected result |
|---|---|---|
| Production | `http://localhost:3000/checkout` | Make a fake payment and see the v1 receipt |
| Staging | `http://localhost:3001/checkout` | Baseline app is usable |
| Production telemetry | `http://localhost:9090` | Prometheus loads |
| Staging telemetry | `http://localhost:9091` | Prometheus loads |
| Docker Desktop | `payment-production` and `payment-staging` | App, database and monitoring containers run |

In Prometheus, query `payment_service_ready`. Select the series whose `ci_run_id` matches `/health.deploymentRunId`; it should be `1`. `/health` exposes a deployment execution ID, not a Git SHA. The receipt maps that ID to the source SHA.

**Checkpoint:** v1 visibly works. Keep Docker, the runner and browser tabs open. Do not stop these stacks after this check. Port 3002 was a separate rehearsal. Clicking Play on old containers alone does not establish a new verified baseline.

### B3. Change the app visibly and publish v2

Create a candidate branch from the current repaired revision. Do not check out old v1 to prepare v2. Change display text only for this experiment, keeping source rollback compatible with the database.

```powershell
$sessionName = 'manual-' + (Get-Date -Format yyyyMMdd-HHmmss)
$candidateBranch = "experiment/$sessionName-v2"
git switch -c $candidateBranch
```

Open `src/ui.ts`. In `receiptPage`, change `<h1>Payment receipt</h1>` to `<h1>Payment receipt - v2</h1>`. Save, then:

```powershell
npm run lint
npm test
npm run build
git add src/ui.ts
git diff --cached
git commit -m 'Show v2 on the payment receipt'
git push -u origin $candidateBranch
if ($LASTEXITCODE -ne 0) { throw 'Candidate push failed' }
$v2Tag = "$sessionName-v2"
git tag $v2Tag
if ($LASTEXITCODE -ne 0) { throw 'Candidate tag creation failed' }
git push origin "refs/tags/$v2Tag"
if ($LASTEXITCODE -ne 0) { throw 'Candidate tag push failed; keep this tag and fix access' }
$v2Sha = git rev-list -n 1 $v2Tag
$v2Sha
```

Check each command before continuing. Stage only the intended UI change, not unrelated edits.

**Expected result:** GitHub shows the candidate commit/tag. Production still shows v1: publishing did not deploy it. No regeneration is needed for this UI-only change. `$workerRef` selects the repaired worker; `$v2Sha` selects the app it deploys.

### B4. Start the BDI agent for v2

Read B5 and arrange observation windows before launching. First run the healthy case below; B6 has separate fault-case commands.

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-v2-healthy'
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

**Expected result:** MAS Console opens, `Master goal started.` appears and Jason selects build immediately. Do not separately launch Jason or click Run workflow on GitHub. The rollback flag acknowledges that v1 source is compatible with the retained database; it does not restore database contents.

Use a **fresh campaign directory every time**, including after closing a console early. Directory already exists / WinError 183 protects old evidence. Run the directory-assignment line again, not the old launch alone. If the previous execution is unresolved, reconcile it before starting again.

### B5. Watch the pipeline and app

**MAS Console:** select the `controller_agent` log tab. Open the printed Agent mind inspector URL and select that agent.

| Campaign point | What you should see |
|---|---|
| Start | `workflow_active`, `achievement(production,success)`, and `BDI_DECISION=run entity=build attempt=1` |
| Job completed | Beliefs such as `status(build,1,success)` and `phase_result(build,success)`; next eligible entity starts |
| Staging deployed | New receipt on port 3001 shows v2; port 3000 still shows v1; agent observes staging telemetry |
| Production deployed | New receipt on port 3000 shows `Payment receipt - v2`; agent still needs health verification |
| Healthy finish | `Master goal achieved.`, `master_goal_achieved`, `workflow_completed`, and `BDI_CONTROLLER_RESULT=achieved recovery=not_needed` |
| Unmet goal | `Attempted but failed to achieve goals.`, `workflow_stopped`, and a stopped or unknown result |

Beliefs/intentions change quickly; use the journal to retain past events. Seeing v2 in the browser proves deployment occurred, but not that BDI accepted its health.

**GitHub Actions:** open the `bdi-...` runs and selected job logs. Skipped sibling jobs are expected. Deployment may wait for a runner or environment approval. A red job can be intentional in a fault experiment; interpret it with the final agent result.

**Observation PowerShell:** enter the checkout directory and copy the campaign path printed in B4. This window does not know `$candidateDir`. After the journal exists:

```powershell
$watchDir = Read-Host 'Paste the current campaign directory'
Get-Content "$watchDir/controller-journal.jsonl" -Tail 30 -Wait
```

Look for `bdi_decision`, `entity_execution_finished`, `telemetry_measurement`, `bdi_recovery_decision`, and `controller_finished`. Ctrl+C stops only this viewer.

**At completion:** capture final beliefs before closing MAS Console. `Campaign finished` means the campaign ended. Gradle remaining at 75% until the GUI closes is normal. Containers stay running. A finished campaign does not monitor forever or resume v2 if conditions later change.

### B6. Run one fault scenario per campaign

Use B8 to restore v1 before each comparison. Keep candidate SHA, worker tag, goals and thresholds fixed. Fault settings create conditions; Jason chooses the response.

#### B6.1. Execution retry or deterministic failure

Controller PowerShell:

```powershell
New-Item -ItemType Directory -Force bdi-cicd-framework/runs/manual-control | Out-Null
$faultFile = Join-Path (Resolve-Path bdi-cicd-framework/runs/manual-control).Path 'faults.properties'
$env:BDI_EXECUTION_PLAN = $faultFile
$env:BDI_RELEASE_SHA = $v2Sha
```

Choose **one** file-content line from the table. Java reads it before dispatch and passes the setting to the selected worker.

| Experiment | File content | Visible expected result |
|---|---|---|
| One transient test failure | `test.1.failure_mode=transient_failure` | First Test entity fails; MAS prints `BDI_DECISION=retry`; second succeeds; continue |
| Persistent transient test failure | `test.failure_mode=transient_failure` | Two Test entity runs fail; stop; production stays v1 |
| Deterministic build failure | `build.failure_mode=force_failure` | Build fails once; stop before test |
| Deterministic test/security failure | `test.failure_mode=force_failure` or `security.failure_mode=force_failure` | Selected job fails once; production is not dispatched |
| One transient production failure | `production.1.failure_mode=transient_failure` | First attempt fails before deployment; one retry can deploy/verify v2 |
| Persistent production health fault | `production.force_error_rate=1` | Reobserve bad telemetry, roll back, verify v1 |

Example: first row and launch:

```powershell
Set-Content $faultFile 'test.1.failure_mode=transient_failure' -Encoding ascii
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-test-retry'
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

**Expected result:** `max_retries: 1` allows one additional execution. Eligible transient failures/timeouts are retried only on retry-safe jobs. Ordinary deterministic failures stop or use configured recovery. Permission rejection is not a job retry experiment.

#### B6.2. Temporary error traffic, then recovery within the observation window

Prepare `$faultFile` as in B6.1. Configure deliberate request faults, and pause after the production job finishes so you can begin traffic:

```powershell
$env:BDI_EXECUTION_PLAN = $faultFile
$env:BDI_RELEASE_SHA = $v2Sha
Set-Content $faultFile 'production.experiment_mode=request_faults' -Encoding ascii
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-temporary-traffic'
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --pause-after production --pause-ms 60000 --artifacts-dir $candidateDir
```

Follow the journal. Wait for `controller_pause` with `after_entity` equal to `production`. The pause lasts 60 seconds. Do not wait for campaign completion.

In **Traffic PowerShell** at this checkout:

```powershell
Invoke-RestMethod http://localhost:3000/health
$env:PAYMENT_BASE_URL = 'http://localhost:3000'
npm run traffic:experiment -- inject_error 6 --continuous
```

First confirm `/health.experimentMode` is `request_faults`. Send errors for **15-20 seconds**, Ctrl+C, then immediately start normal traffic:

```powershell
npm run traffic:experiment -- normal 6 --continuous
```

**Expected result:** error traffic prints HTTP 503; normal traffic prints HTTP 201. MAS prints `BDI_DECISION=wait_reconsider` while old errors remain in the two-minute Prometheus window. If telemetry recovers in time, two consecutive healthy observations allow `achieved/not_needed`; production keeps v2. Stop normal traffic after completion.

Default policy: at most 36 observations, five seconds apart, within 180 seconds from the first observation. This is separate from job retries. If errors clear too late or another metric stays unhealthy, recovery is a valid result; do not change limits mid-campaign.

#### B6.3. Continuous error traffic until rollback

Restore v1 with B8. Repeat B6.2 with a fresh directory ending in `-persistent-traffic`. At the production pause, start `inject_error` again and **keep it running through the observation period**.

**Expected result:** repeated `wait_reconsider`, followed by `BDI_DECISION=rollback`. Stop injected traffic with Ctrl+C when rollback starts. GitHub shows **Rollback entity**. After verified recovery, MAS prints:

```text
BDI_RECOVERY=restored entity=rollback
Attempted but failed to achieve goals.
BDI_CONTROLLER_RESULT=stopped recovery=restored
```

Make a new payment at port 3000: the v1 receipt returns. Staging can still be v2; automatic rollback restores production only. Once rollback starts, that campaign will not resume v2. Reset and start a new campaign.

For a staging traffic fault, select `staging.experiment_mode=request_faults`, pause after `staging`, and use port 3001. Persistent bad staging stops promotion; production remains v1.

### B7. Record results and decisions

After closing MAS Console, in Controller PowerShell:

```powershell
$result = Get-Content "$candidateDir/controller-result.json" -Raw | ConvertFrom-Json
$result | Select-Object mode, outcome, recovery_outcome, release_sha, known_good_sha, goal_message
$result.requested_goals
$result.achieved_goals
$result.unmet_goals
$result.executions
$result.telemetry
Get-Content "$candidateDir/controller-journal.jsonl" | Select-String 'bdi_decision|telemetry_measurement|bdi_recovery_decision|controller_finished'
```

| Result | Human meaning |
|---|---|
| `achieved / not_needed` | Goals satisfied; normal delivery also passed health verification |
| `stopped / not_attempted` | Delivery stopped without recovery, commonly before production |
| `stopped / restored` | Candidate failed; verified v1 was restored |
| `stopped / failed` | Recovery failed; inspect the recovery evidence and app |
| `unknown / unresolved` | Execution uncertain; reconcile before another campaign |
| Other `unknown` result | Required evidence, such as health verification, was insufficient |

**Expected result:** the directory contains `controller-result.json`, `controller-journal.jsonl`, `generation-manifest.json` and model/agent snapshots. Save screenshots of final MAS beliefs and browser receipts, GitHub run links, fault-file content, and traffic start/stop times. Keep `$knownGood` pointing to the original verified v1 receipt for comparisons.

### B8. Restore v1 and repeat

Actions:

- Stop traffic with Ctrl+C and close the old MAS Console.
- Reconcile any unresolved execution before another campaign.
- Clear faults and deploy the saved v1 SHA using the current controller and worker.

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$env:BDI_RELEASE_SHA = $v1Sha
$resetDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-restore-v1'
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $resetDir
```

**Expected result:** both staging and production return to verified v1; reset reports achieved. Check fresh receipts on ports 3001 and 3000. Database records remain: this restores application source, not database history.

Keep the app running. Set `$env:BDI_RELEASE_SHA = $v2Sha`, choose B4 or a B6 scenario, and use a fresh directory. Do not reset Git, move tags, delete evidence or regenerate unchanged artifacts.

<a id="optional-experiment-require-staging-to-fail"></a>

## C. Optional experiment: require staging to fail

This uses a different goal. A matching executed failure satisfies the experiment; it does not certify candidate delivery. Generate a separate project, preserving Part B's normal goals:

```powershell
$negativeProject = 'bdi-cicd-framework/projects/staging-failure'
py -3 -B bdi-cicd-framework/generate_project.py --project-dir $negativeProject --pipeline bdi-cicd-framework/models/01_pipeline.yaml --goal bdi-cicd-framework/examples/staging_failure_goal.yaml
py -3 -B bdi-cicd-framework/run_controller.py --project-dir $negativeProject --validate-only
```

**Expected result:** its model contains `staging.status == failure`, and its agent contains `achievement(staging, failure)`. Generate once per configuration revision.

Prepare `$faultFile` as in B6.1, then:

```powershell
Set-Content $faultFile 'staging.failure_mode=force_failure' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$env:BDI_RELEASE_SHA = $v2Sha
$negativeDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-expected-failure'
py -3 -B bdi-cicd-framework/run_controller.py --project-dir $negativeProject --gui --baseline --artifacts-dir $negativeDir
```

Here `--baseline` supplies no recovery receipt; it does not certify the negative experiment as a healthy deployment baseline.

**Expected result:** build/test/security succeed, staging fails before deployment, and MAS prints `Expected failure observed: staging` then `Master goal achieved.` Production is not dispatched. The result has `negative_goal_experiment: true` and no verified release receipt. Rejected dispatch, timeout and uncertain execution do not satisfy an exact failure goal.

To test an unmet goal, clear the fault and use a fresh campaign with the same project:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$negativeDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-unmet-failure'
py -3 -B bdi-cicd-framework/run_controller.py --project-dir $negativeProject --gui --baseline --artifacts-dir $negativeDir
```

**Expected if staging succeeds and telemetry is healthy:** staging serves v2, production stays unchanged, and MAS prints `Attempted but failed to achieve goals.` Result is `stopped`, with staging in `unmet_goals`. Use B8 to restore both environments. Resume normal experiments without `--project-dir $negativeProject`.

## Resume after closing PowerShell or restarting the laptop

Start Docker and the runner. In a new Controller PowerShell at the checkout, restore these values from your experiment notes:

```powershell
$workerRef = Read-Host 'Existing published worker tag'
$v2Tag = Read-Host 'Existing published v2 tag'
$v1Sha = git rev-list -n 1 v1
$v2Sha = git rev-list -n 1 $v2Tag
$knownGood = Read-Host 'Full path to verified live v1 controller-result.json'
```

Repeat A6 to load credentials and the worker ref. Validate artifacts, reconcile pending execution if necessary, and use B8 if the app is stopped or you need a verified v1 starting state. Do not recreate existing tags or reuse campaign directories.

## Troubleshooting: identify where execution stopped

| What you see | Meaning / action |
|---|---|
| Git push 403 | Git credential lacks needed repository/workflow write access. Fix it and retry the same branch/tag. |
| Controller dispatch 403 | Check controller token's Actions write permission, repository selection and approval. Separate from Git credentials. |
| Invalid worker input / missing rollback | Check `BDI_WORKFLOW_REF`; an older worker may be selected. |
| GitHub Waiting for runner | Check runner status, labels and environment approval. |
| Docker socket permission denied | Linux runner account cannot use Docker. Fix runner access. |
| Staging/production site unreachable | Inspect deployment logs and `docker ps -a`. Failed dispatch does not start old containers. |
| Telemetry unknown | Check readiness, Prometheus reachability, execution ID and fresh samples. |
| Directory already exists | Use a fresh campaign directory; retain old evidence. |
| Missing/stale artifacts | Review changes and generate explicitly in A4. |
| Finished, but Gradle stays at 75% | Inspect final beliefs, then close MAS Console. Campaign is over. |
| Another controller holds lock | Close previous controller; worktrees share the controller lock. |

For Git authentication, in a separate PowerShell:

```powershell
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
```

Use the account with repository write access. A fine-grained publication token needs Contents write and Workflows write for workflow changes; dispatch needs Actions write. Loading the controller token does not automatically replace Git credentials. Never paste token values into logs or documentation.

For uncertain execution, close MAS Console and run:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

**Expected result:** confirmed terminal execution settles the pending record; uncertainty keeps it pending. Reconciliation does not resume the campaign or claim achievement. Never delete pending state to force redispatch.

More detail: [setup and troubleshooting](BDI_SETUP.md), [generation and runtime](BDI_GENERATION_AND_RUNTIME.md). The historical guides are style references; their old agent names, commands and environment variables are not the current procedure.
