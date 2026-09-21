# Manual experiment: deploy v1 to v2 with BDI

Run commands yourself, one step at a time. There is no end-to-end automation script. This guide uses the existing payment repository, published worker/v2 tags and verified v1 receipt. Replace those selections only when intentionally starting a different experiment.

## Choose your route

| When | Steps |
|---|---|
| First time on this computer | A1 tools/login; A2 local app check; A3 generate and simulate; A4 select published versions |
| Before **every** experiment, including after reopening PowerShell | B1 Docker/runner; B2 restore session settings; B3 check deployed version; B4 restore v1 if needed |
| Healthy deployment | C1, then E1 |
| Build/test/security failure or bounded retry | C2, then E1 |
| Temporary production error traffic, then continue v2 | C3, then E1 |
| Persistent production error traffic, then rollback | C4, then E1 |
| Deterministic production failure, then rollback | C5, then E1 |
| Optional: engineer explicitly wants a failure goal | D1, then E1 |
| Repeat | Stop traffic, close completed MAS, repeat B1-B4, choose another scenario |

**Windows:** keep Controller PowerShell, Observation PowerShell, Traffic PowerShell, the Linux runner terminal, Docker Desktop and a browser available. Run PowerShell blocks from `C:\NHI\2026_IT-Project\260031_payment-repair`. Variables belong to one terminal; the observation/traffic blocks below do not depend on controller variables.

**What starts deployment:** `run_controller.py` starts Jason immediately. Jason selects jobs; Java dispatches and observes; GitHub executes only the selected entity. Do not additionally click **Run workflow**. Publication and generation do not start this controller.

**Timing:** allow several minutes per campaign; hosted queues, downloads and Docker builds vary. Use the stated events as checkpoints, not a promised five-minute finish. A queued deployment job is not evidence that deployment is progressing.

## A. One-time setup and checks

### A1. Check tools and connect GitHub

**Start:** open Docker Desktop; wait for the engine. Open Controller PowerShell. Keep the existing repository and worktree; do not run `git init` or create another repository.

**Actions:** run:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
git status --short --branch
git remote -v
py -3 --version
java -version
node --version
gh --version
docker info
docker compose version
py -3 -m pip install PyYAML==6.0.3
npm ci
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
```

**Explanation:**

- `Set-Location` selects the repaired checkout.
- `git status` shows the branch and pending edits; `git remote` shows the target repository.
- Version commands check Python, JDK 21+, Node 22+ and GitHub CLI.
- Docker commands check the running engine and Compose.
- `pip install` installs the YAML dependency; `npm ci` installs app/traffic dependencies.
- `Remove-Item` clears token overrides in this window; silent output is normal.
- `gh auth login` opens browser authentication; sign in as an account with repository write access.
- `gh auth setup-git` makes Git use the stored CLI credentials.

**Expected results:**

- Browser confirms device connection; CLI completes login.
- Remote is `https://github.com/id-nynt/260031_cicd_payment_demo.git`.
- All tool checks respond without errors.

**Cleanup:** none. Stored login persists; environment variables do not. Never put a token in a file or screenshot.

### A2. Check the app separately on port 3002

**Start:** open a separate Local-check PowerShell. This is a rehearsal, not the deployed v1/v2 stacks.

**Actions:** run:

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

**Explanation:**

- `Set-Location` selects the app source.
- Each environment assignment selects the isolated rehearsal stack, its ports, identity or normal behavior.
- `compose up` builds and starts it; `compose ps` lists its services.
- `Invoke-RestMethod` checks readiness.
- `PAYMENT_BASE_URL` directs traffic to the rehearsal app; `npm run` sends normal fake payments.

**Expected results:**

- Traffic prints successful HTTP 201 responses.
- Browser: open `http://localhost:3002/checkout`; choose **Demo card simulation**, use `4242424242424242`, expiry `12/30`, CVC `123`, and see a receipt.
- Browser: Prometheus at `http://localhost:9092` shows `payment_service_ready{ci_run_id="local"}` equal to `1` after samples arrive.

**Cleanup:** in this same window run `docker compose stop`, then close it. Keep Docker running. Ports 3000/3001 are separate deployment stacks, started or restored in Part B.

### A3. Generate once and rehearse the BDI agent

**Start:** Controller PowerShell. Review `bdi-cicd-framework/models/01_pipeline.yaml` and `02_goal.yaml`; keep normal staging/production success goals for Part C.

**Actions:** run:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
if ($LASTEXITCODE -ne 0) { throw 'Generation failed; inspect the input error' }
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Artifact validation failed' }
py -3 -B bdi-cicd-framework/run_controller.py --gui --scenario healthy
```

**Explanation:**

- `generate_project.py` validates inputs and saves the workflow model, agent and manifest.
- Each `if` stops the block if the preceding check failed.
- `--validate-only` verifies their consistency without dispatching.
- `--scenario healthy` runs Jason with simulated execution and telemetry.

**Expected results:**

- Persistent outputs: `models/03_workflow_model.yaml`, `models/generation-manifest.json`, `bdi/controller_agent.asl`.
- MAS Console's `controller_agent` log reaches `BDI_CONTROLLER_RESULT=achieved recovery=not_needed`.
- No real GitHub deployment is dispatched by this simulation.

**Cleanup:** close MAS Console after the final result. Gradle's **75% EXECUTING** while the completed GUI remains open is normal. Regenerate only after changing inputs/generator/policy, not before each campaign. Keep generated files with their matching configuration revision.

### A4. Check the saved source versions

**Start:** Controller PowerShell and GitHub web. The existing experiment already has v1, a visible v2 and a worker tag; reuse them.

**Actions:** run:

```powershell
git show -s --oneline 'v1^{commit}'
git show -s --oneline 'manual-20260921-055936-v2^{commit}'
git ls-remote origin 'refs/tags/v1' 'refs/tags/v1^{}' 'refs/tags/manual-20260921-055936-v2' 'refs/tags/bdi-worker-20260921-052412'
```

**Explanation:**

- The two `git show` commands display stable v1 and the existing UI-change v2.
- `git ls-remote` checks the published refs. For annotated v1, compare the peeled `^{}` line with the commit SHA.

**Expected results:**

- v1: `caa26dada2a15b807c325e2d931ee123a206ece8`.
- Existing v2: `22a263c6f9b8939fb3ac3d5f300ccb3cf5c58f2d`.
- GitHub's worker tag contains `.github/workflows/entity-execution.yml` with rollback, transient failure and request-fault support.
- The workflow also exists on the default branch so GitHub accepts dispatches.

**Cleanup:** none. Do not move/recreate these tags. A local documentation commit is not automatically a published candidate.

**Only when creating a different v2:** edit receipt text in `src/ui.ts`, then review and publish the intended app change:

```powershell
npm run lint
if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
npm test
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
git add src/ui.ts
git diff --cached
```

- Each `npm` command checks the new app; each guard stops on failure.
- `git add` stages only the UI file; `git diff` lets you review everything staged before committing.

After reviewing the staged changes:

```powershell
git commit -m 'Update experiment receipt UI'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed' }
$newV2Tag = 'manual-' + (Get-Date -Format yyyyMMdd-HHmmss) + '-v2'
git tag $newV2Tag
if ($LASTEXITCODE -ne 0) { throw 'Tag creation failed' }
git push origin "refs/tags/$newV2Tag"
if ($LASTEXITCODE -ne 0) { throw 'Publication failed; keep this tag and resolve access' }
$newV2Tag
```

- `git commit` records the reviewed change; `$newV2Tag` creates a unique name.
- `git tag` saves that revision; `git push` publishes it without moving old tags.
- The guards prevent continuing after failure; the last line prints the tag to use in B2.

**Expected:** the new tag appears on GitHub; production still runs its previous version. Change B2's v2 tag selection for future runs. No agent regeneration is needed for a UI-only change.

## B. Setup before every run

### B1. Start Docker and the deployment runner

**Start:** open Docker Desktop. In GitHub web open **Settings > Actions > Runners**.

**Actions:** if `bdi-demo` is offline, open a dedicated PowerShell and enter:

```powershell
wsl -d Ubuntu
```

Then, in that Linux terminal:

```bash
cd ~/actions-runner-payment
docker info
docker compose version
./run.sh
```

**Explanation:**

- `wsl` opens Ubuntu; `cd` selects the existing runner installation.
- Docker commands confirm this runner account can reach Docker and Compose.
- `./run.sh` connects the runner and waits for jobs. Do not start a second listener if its service is already online.

**Expected results:**

- Terminal says `Connected to GitHub` and `Listening for Jobs`.
- GitHub shows the runner **Idle/Online**, with `self-hosted`, `Linux`, `payment-deploy` labels.
- If an existing job is running, resolve/wait for it before another campaign.
- Check **Settings > Environments** for required staging/production approvals; approve actual jobs when requested.

**Cleanup:** keep this terminal and Docker open through deployment and recovery. Hosted build/test/security can succeed even when this runner is offline; staging then stays queued.

### B2. Restore the controller session completely

**Start:** Controller PowerShell; close any completed MAS Console first. Run this whole block every time you reopen the window or start another comparison. It does not deploy.

**Actions:** run:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN,Env:GITHUB_API_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO,Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS,Env:BDI_POLL_SECONDS,Env:BDI_ENTITY_TIMEOUT_MINUTES -ErrorAction SilentlyContinue
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:GITHUB_TOKEN = gh auth token --hostname github.com
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Repeat A1 GitHub login' }
$env:BDI_WORKFLOW_REF = 'bdi-worker-20260921-052412'
$v2Tag = 'manual-20260921-055936-v2'
$v2Sha = git rev-parse "$v2Tag^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the selected v2 tag' }
$v2Sha = $v2Sha.Trim()
$env:BDI_RELEASE_SHA = $v2Sha
$knownGood = 'C:\NHI\2026_IT-Project\260031_payment-repair\bdi-cicd-framework\runs\20260921-055346-143-v1\controller-result.json'
$baseline = Get-Content -LiteralPath $knownGood -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or
    $baseline.repository -ne $env:GITHUB_REPOSITORY -or
    $baseline.verified_releases.production.release_sha -ne $baseline.release_sha -or
    -not $baseline.verified_releases.production.github_run_id) { throw 'Select the verified live v1 receipt' }
$v1Sha = $baseline.release_sha
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Resolve artifact consistency before launching' }
[pscustomobject]@{ Worker=$env:BDI_WORKFLOW_REF; V1=$v1Sha; V2=$v2Sha; KnownGood=$knownGood }
```

**Explanation:**

- `Set-Location` ensures relative paths refer to the right checkout.
- The three `Remove-Item` commands clear stale authentication overrides, faults, telemetry overrides and timing settings; they do not delete evidence or containers.
- Repository and worker assignments select the existing GitHub integration.
- `gh auth token` loads the stored credential without printing it; its guard detects missing login.
- `$v2Tag`, `git rev-parse`, its guard and `Trim` resolve the published candidate explicitly, rather than using local HEAD.
- `BDI_RELEASE_SHA` selects the candidate source for dispatch.
- `$knownGood` selects the saved receipt; `Get-Content` reads it; the receipt guard checks successful live production evidence.
- `$v1Sha` comes from that receipt, not from a lost variable in another window.
- Validation and its guard check persistent artifacts; the final table displays selections without the token.

**Expected results:**

- The settings table has worker, v1, v2 and an existing receipt path; validation passes.
- No missing `--known-good` argument, missing repository, or silent local-HEAD selection.

**Cleanup:** keep this terminal open. Do not rerun this block in the middle of a fault campaign. If you genuinely have no baseline receipt, follow F1 first and replace the receipt path here; do not invent a receipt.

### B3. Start existing app containers and identify the deployed version

**Start:** Docker Desktop, browser and Controller PowerShell. No campaign should be executing.

**Actions:** in Docker Desktop, expand `payment-staging` and `payment-production`. If their existing services are stopped, start those two groups with **Play**. Do not rebuild from your local checkout to reset the version. Then run:

```powershell
docker ps
Invoke-RestMethod http://localhost:3001/ready
Invoke-RestMethod http://localhost:3000/ready
Invoke-RestMethod http://localhost:3001/health
Invoke-RestMethod http://localhost:3000/health
```

**Explanation:**

- `docker ps` shows running containers and published ports.
- The two `/ready` calls check readiness; the two `/health` calls show deployment execution identity and experiment mode.
- Starting existing containers resumes their existing revision; it neither deploys v1 nor establishes a new verified baseline.

**Expected results:**

- Browser: `http://localhost:3000/checkout` is production; `http://localhost:3001/checkout` is staging.
- Make a **new** fake payment to see the receipt title: v2 says `Payment receipt - v2`. An already-open receipt page may show old content.
- Prometheus opens at ports 9090 (production) and 9091 (staging).
- `/health.deploymentRunId` is an execution UUID, not a Git SHA. Match it to `executions.production.executionId` or `executions.staging.executionId` in the relevant campaign result, then read that result's `release_sha`.

**Cleanup/decision:** if both are verified v1 in normal mode, skip B4. If either is v2, unhealthy, absent, has a fault mode, or its identity is uncertain, perform B4. Starting Play alone does not prove you restored v1.

### B4. Restore both environments to verified v1 when needed

**Start:** complete B1-B2 in this controller window; stop old traffic and reconcile any interrupted execution using troubleshooting below. This is a real deployment of saved v1, not a Git reset.

**Actions:** run:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$env:BDI_RELEASE_SHA = $v1Sha
$resetDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-restore-v1'
$resetDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$resetDir"
```

**Explanation:**

- `Remove-Item` disables fault injection; `BDI_RELEASE_SHA` selects saved v1.
- `$resetDir` creates a fresh evidence path; the next line displays it.
- The controller deploys and verifies v1 through all normal jobs. The compatibility flag confirms v1 source can use the retained database; it does not undo database changes.

**Expected results:**

- MAS reaches `BDI_CONTROLLER_RESULT=achieved recovery=not_needed`.
- GitHub shows build, test, security, staging and production in separate selected-entity runs.
- Both ports serve v1 after fresh fake payments.

Close MAS after completion, then verify:

```powershell
$reset = Get-Content "$resetDir/controller-result.json" -Raw -ErrorAction Stop | ConvertFrom-Json
if ($reset.outcome -ne 'achieved' -or $reset.release_sha -ne $v1Sha) { throw 'Reset did not achieve verified v1; inspect its journal' }
$reset.verified_releases
$env:BDI_RELEASE_SHA = $v2Sha
```

- `Get-Content` reads the reset result; the guard prevents treating a failed reset as success.
- `verified_releases` displays the new deployment identities; the last assignment reselects v2 for the next experiment.

**Cleanup:** retain `$knownGood` as the original v1 receipt. Keep app, Docker and runner running. Do not recreate v2 or regenerate the agent for each repeat.

## C. Choose one deployment scenario

Before each scenario, finish B1-B4. Use the same worker, v2 SHA, goals and thresholds when comparing outcomes. The following launches assume B2 variables exist in **Controller PowerShell**. Do not run two controllers together.

### C1. Successful v2 deployment

**Start:** v1 is running in staging and production. Open GitHub **Actions > BDI Entity Execution** and both checkout pages.

**Actions:** Controller PowerShell:

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-healthy-v2'
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$candidateDir"
```

**Explanation:**

- `Remove-Item` disables prior faults; the release assignment selects published v2.
- `$candidateDir` creates a unique path; printing it lets you copy it into the observation window.
- The controller starts the campaign immediately using the existing generated agent.

**Expected results:**

- MAS `controller_agent` log: build -> test -> security -> staging -> production, with health checks around deployment.
- In the printed Agent mind inspector URL, select `controller_agent`; inspect goals, `phase_result(...)` and final `master_goal_achieved` / `workflow_completed` beliefs.
- GitHub: one separate workflow run per selected entity. Other jobs inside each run are **skipped**, which is expected.
- Staging becomes v2 first; production becomes v2 later. Make fresh fake payments to see the change.
- Final MAS: `BDI_CONTROLLER_RESULT=achieved recovery=not_needed`.

**Cleanup:** record E1, then close the finished console. Before another comparison, repeat B and restore v1. If the campaign stopped, inspect its result rather than assuming production changed.

### C2. Execution failure or bounded retry

**Start:** v1 running; choose exactly one fault below. These are controlled worker failures, not traffic faults.

| Put this one line in `$faultLine` | Expected behavior |
|---|---|
| `build.failure_mode=force_failure` | Build fails once; no test or deployment; production stays v1 |
| `test.failure_mode=force_failure` | Test fails once; no production deployment |
| `security.failure_mode=force_failure` | Security fails once; no production deployment |
| `staging.failure_mode=force_failure` | Staging job fails before deployment; production stays v1 |
| `test.1.failure_mode=transient_failure` | Test attempt 1 fails, attempt 2 succeeds; v2 can finish successfully |
| `test.failure_mode=transient_failure` | Both test attempts fail; stop, production stays v1 |
| `production.1.failure_mode=transient_failure` | First production attempt fails before deployment; retry can deliver v2 |

**Actions:** Controller PowerShell, edit only the chosen `$faultLine`:

```powershell
$faultLine = 'test.1.failure_mode=transient_failure'
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-execution-fault'
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value $faultLine -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$candidateDir"
```

**Explanation:**

- `$faultLine` selects the condition; `BDI_RELEASE_SHA` selects v2.
- `$candidateDir` names fresh evidence; `$faultFile` gives the fault file an absolute, campaign-specific path next to it.
- `Set-Content` writes the chosen fault; `BDI_EXECUTION_PLAN` tells Java to read it before dispatch.
- The last two commands display the evidence path and start the agent. The file chooses the fault, not the agent's decision.

**Expected results:**

- GitHub's selected job shows the controlled failing step.
- A transient retry prints `BDI_DECISION=retry`; `max_retries: 1` means two total attempts at most.
- Deterministic build/test/security failure normally finishes `stopped / not_attempted`; no blind retry.
- The first-attempt-only fault can finish `achieved / not_needed` after the second attempt succeeds.

**Cleanup:** E1, then `Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue`. Preserve the fault file as evidence. Repeat B before the next case; a failed production attempt may leave staging at v2.

### C3. Temporary production error traffic, then continue v2

**Start:** v1 running. Prepare Observation and Traffic PowerShell windows **before launching**. Read all of this step first. Enabling `request_faults` does not itself create errors.

**Actions 1 - launch:** Controller PowerShell:

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-temporary-traffic'
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value 'production.experiment_mode=request_faults' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --pause-after production --pause-ms 60000 --artifacts-dir "$candidateDir"
```

**Explanation:**

- The release assignment selects v2; the directory assignment identifies this campaign.
- `$faultFile` resolves an absolute file path; `Set-Content` enables header-triggered production errors.
- `BDI_EXECUTION_PLAN` selects that file; the next command prints the campaign directory.
- The launcher pauses for 60 seconds **after the production GitHub job finishes, before the agent receives its result and observes health**. The pause is automatic, not a prompt waiting for you.

**Actions 2 - watch immediately:** Observation PowerShell:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$watchDir = Read-Host 'Paste the current campaign directory printed above'
Get-Content "$watchDir/controller-journal.jsonl" -Tail 30 -Wait
```

- `Set-Location` resolves the copied relative path; `Read-Host` records this campaign's path in this window.
- `Get-Content` follows the journal; start after the file appears. Watch this file, not only the agent log tab.

**Actions 3 - at `controller_pause` with `after_entity: production`:** immediately run in Traffic PowerShell:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$health = Invoke-RestMethod http://localhost:3000/health
$health
if ($health.experimentMode -ne 'request_faults') { throw 'Wrong app mode; inspect this campaign before injecting' }
$env:PAYMENT_BASE_URL = 'http://localhost:3000'
npm run traffic:experiment -- inject_error 6 --continuous
```

- `Set-Location` selects the traffic script's repository.
- The health request and display confirm the new app's mode/identity; the guard rejects a normal-mode app.
- `PAYMENT_BASE_URL` targets production; `npm run` continuously sends fault-header requests.

**Actions 4 - stop the temporary fault:** keep errors running through the end of the pause until the journal shows a production `telemetry_measurement` with an error rate above `0.05` and MAS shows `BDI_DECISION=wait_reconsider`. Then **immediately Ctrl+C in Traffic PowerShell**, and run:

```powershell
npm run traffic:experiment -- normal 6 --continuous
```

- This sends successful requests while the two-minute metric window clears. Do not wait another two minutes before starting normal traffic.

**Expected results:**

- Error traffic produces HTTP 503; normal traffic produces HTTP 201.
- The agent actually observes unhealthy production before you remove the cause; otherwise this is not a demonstrated fault-recovery experiment.
- It rechecks rather than redispatching production. If health clears within the count/time budget, two consecutive healthy samples allow `achieved / not_needed`; production stays v2.
- Default maximum: 36 observations, five seconds apart, within 180 seconds from the first observation. This is a maximum, not a mandatory wait; two healthy observations can finish quickly.
- If errors clear too late or another metric remains unhealthy, rollback is a valid outcome. Record it, rather than claiming temporary recovery succeeded.

**Cleanup:** stop normal traffic after the final result, perform E1, then repeat B to reset. If you missed the pause and the campaign already succeeded, it cannot be faulted retrospectively: reset and start a fresh campaign.

### C4. Persistent production error traffic, then rollback

**Start:** repeat B1-B4. Prepare the two extra terminals as in C3; do not reuse the previous campaign directory.

**Actions - launch:** Controller PowerShell:

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-persistent-traffic'
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value 'production.experiment_mode=request_faults' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --pause-after production --pause-ms 60000 --artifacts-dir "$candidateDir"
```

**Explanation:**

- Release and directory assignments select published v2 and new evidence.
- `$faultFile` gives this campaign its own file; `Set-Content` enables request faults.
- The plan assignment selects it; printing the directory lets you follow the correct journal.
- The launcher starts the campaign and gives the same 60-second production pause.

Follow **C3 Actions 2 and 3** to watch the journal and start error traffic at the pause. This time **keep errors running throughout the observation period**. When MAS prints `BDI_DECISION=rollback` or the journal records `bdi_recovery_decision`, stop error traffic with Ctrl+C.

**Expected results:**

- Repeated unhealthy observations and `wait_reconsider`, then rollback when the configured budget is exhausted.
- GitHub runs **Rollback entity** using verified v1 source.
- MAS ends `BDI_CONTROLLER_RESULT=stopped recovery=restored` after recovery health is verified.
- A new payment on production shows v1. Staging may still show v2: automatic rollback restores production only.
- Once rollback starts, this campaign will not resume v2 even if traffic stops.

**Cleanup:** E1, then B4 restores both environments before the next comparison. If recovery is failed/unverified, inspect its job and telemetry before proceeding.

**Staging variant:** use `staging.experiment_mode=request_faults`, `--pause-after staging`, and port `3001` in the traffic block. The pause event must name staging. Sustained unhealthy staging stops promotion; production stays v1, with no production rollback needed.

### C5. Production job failure after deployment, then rollback

**Start:** B1-B4 complete. This deterministic case avoids traffic timing and tests recovery after the production worker has changed the app.

**Actions:** Controller PowerShell:

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-production-failure'
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value 'production.failure_mode=force_failure' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$candidateDir"
```

**Explanation:**

- The first two assignments select v2 and a new campaign path.
- `$faultFile` defines an absolute path; `Set-Content` requests a controlled production failure.
- The plan assignment enables the fault; the path display identifies evidence.
- The launch lets Jason select deployment and, on failure, recovery.

**Expected results:**

- Production job fails at **Controlled post-deployment failure**, after its Compose deployment command.
- Jason selects rollback; successful verified restoration ends `stopped / restored`.
- Production returns to v1, staging can remain v2. Restoration is not successful candidate delivery.

**Cleanup:** E1, then repeat B for the next experiment. Remove the fault environment setting before restoring v1.

<a id="optional-experiment-require-staging-to-fail"></a>

## D. Optional goal experiment

### D1. Request an actual staging failure as the achievement

**Start:** B1-B4 complete. This changes the goal, not just the fault. Use a separate generated project to preserve normal deployment goals.

**Actions:** Controller PowerShell:

```powershell
$negativeProject = 'bdi-cicd-framework/projects/staging-failure'
py -3 -B bdi-cicd-framework/generate_project.py --project-dir "$negativeProject" --pipeline bdi-cicd-framework/models/01_pipeline.yaml --goal bdi-cicd-framework/examples/staging_failure_goal.yaml
if ($LASTEXITCODE -ne 0) { throw 'Negative-goal generation failed' }
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-expected-staging-failure'
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value 'staging.failure_mode=force_failure' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
py -3 -B bdi-cicd-framework/run_controller.py --project-dir "$negativeProject" --gui --baseline --artifacts-dir "$candidateDir"
```

**Explanation:**

- `$negativeProject` selects a separate artifact folder; generation writes its failure goal and agent. Regenerate this project only when its inputs/generator change.
- The guard stops on generation failure; the release assignment selects v2.
- The campaign/fault path assignments keep evidence separate; `Set-Content` selects a real controlled staging failure.
- The plan assignment enables that fault; the path display identifies the journal.
- `--project-dir` loads the separate agent; `--baseline` means no prior recovery receipt, not a verified healthy release.

**Expected results:**

- Generated agent contains `achievement(staging, failure)`.
- Build/test/security succeed, staging fails, and MAS reports the expected failure and goal achievement.
- Result has `negative_goal_experiment: true` and no verified release receipts; do not use it as `$knownGood`.
- Production is not dispatched. An unknown/rejected dispatch does not satisfy a failure goal.

**Cleanup:** E1, remove the fault setting and omit this `--project-dir` for normal experiments. To test an unmet failure goal, repeat this project's launch with a fresh directory and no fault plan: healthy staging should end with goals unmet rather than deliberately failing itself. Restore v1 afterward if staging changed.

## E. Finish and retain evidence

### E1. Record the outcome before the next run

**Start:** wait for the final MAS result. Capture its log/agent mind, then close the completed MAS Console to return to Controller PowerShell.

**Actions:** run:

```powershell
$result = Get-Content "$candidateDir/controller-result.json" -Raw -ErrorAction Stop | ConvertFrom-Json
$result | Select-Object mode,outcome,recovery_outcome,release_sha,known_good_sha,goal_message
$result.executions
$result.telemetry
$result.verified_releases
Get-Content "$candidateDir/controller-journal.jsonl" | Select-String 'bdi_decision|telemetry_measurement|bdi_recovery_decision|controller_finished'
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
```

**Explanation:**

- `Get-Content` reads this campaign's result; `Select-Object` summarizes its outcome and source.
- The three property displays show executed attempts, health decisions and verified deployment identities.
- The journal filter retains decision/measurement history beyond fast-changing beliefs.
- `Remove-Item` disables faults for subsequent commands, without deleting the evidence file.

**Expected results:**

- `$candidateDir` contains result, journal, provenance and exact model/agent snapshots.
- `achieved / not_needed`: goals met; ordinary delivery passed required health checks.
- `stopped / not_attempted`: stopped without recovery, commonly before production.
- `stopped / restored`: candidate failed, verified v1 restored.
- `stopped / failed` or `unknown`: investigate; do not assume a safe baseline.
- Keep the matching `*-faults.properties` file, screenshots, GitHub run links and traffic start/stop times.

**Cleanup:** Ctrl+C in Traffic and Observation windows; leave app/runner running for another experiment. Repeat B, then choose C or D. Keep original v1 evidence; never delete pending execution records to bypass an unresolved campaign.

## F. First baseline and troubleshooting

### F1. Establish v1 only if no verified baseline receipt exists

**Start:** A1-A4 and B1 complete. Existing users with the saved successful receipt should skip this. Controller PowerShell, normal success-goal project:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN,Env:GITHUB_API_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO,Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL,Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$env:GITHUB_TOKEN = gh auth token --hostname github.com
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Complete GitHub login in A1' }
$env:BDI_WORKFLOW_REF = 'bdi-worker-20260921-052412'
$v1Sha = git rev-parse 'v1^{commit}'
if ($LASTEXITCODE -ne 0) { throw 'Select and publish stable v1 before continuing' }
$v1Sha = $v1Sha.Trim()
$env:BDI_RELEASE_SHA = $v1Sha
$baselineDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-v1'
$baselineDir
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Resolve artifact validation first' }
py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir "$baselineDir"
```

**Explanation:**

- `Set-Location` selects the checkout; the removal commands clear prior credential/fault/pause overrides.
- Repository, token and worker assignments establish the connection; the token guard stops if login is absent.
- `git rev-parse`, its guard and `Trim` resolve stable v1; `BDI_RELEASE_SHA` selects it.
- The directory assignment and display give this baseline fresh evidence.
- Validation and its guard check the generated project; `--baseline` explicitly starts with no rollback source.

**Expected:** all five normal entities finish and both deployments pass health checks; MAS reports achieved. Close the completed console, then:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw -ErrorAction Stop | ConvertFrom-Json
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $v1Sha -or
    -not $baseline.verified_releases.production.github_run_id -or -not $baseline.verified_releases.staging.github_run_id) { throw 'Baseline not verified; inspect its journal' }
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$knownGood
```

- `Get-Content` reads the receipt; the guard requires live success at v1 with both verified environments.
- `Resolve-Path` saves the full receipt path; the final line displays it.

**Cleanup:** put that exact path into B2's `$knownGood` assignment for future sessions. Keep the receipt and containers. Do not use a simulation, build-only or negative-goal result as the baseline.

### F2. Diagnose common mistakes

| Symptom | Meaning and next action |
|---|---|
| Starting another scenario while app is already v2 | The v1-to-v2 comparison is no longer clean. Stop the finished campaign's traffic and perform B1-B4 before retrying. |
| `--known-good: expected one argument`, missing repository, or empty version | Variables were lost or set in another terminal. Repeat the entire B2 block in Controller PowerShell. |
| `Cannot find path C:\controller-result.json` | `$baselineDir` was empty. Use B2's saved absolute receipt path; do not infer the baseline from an empty variable. |
| Checkout: `upload-pack: not our ref ...` | The chosen SHA is not available on GitHub. Select the published v2 tag in B2; do not use local HEAD containing unpublished docs/code. |
| Git push or dispatch 403 | Authentication/permission issue, not a duplicated-folder issue. Repeat A1 login with the correct account; dispatch needs Actions write. Publication of workflow changes also needs workflow write access. |
| GitHub staging is queued | Check B1: self-hosted runner online, labels match, no earlier busy job, environment approval granted. Keep the existing campaign; do not start another. |
| Runner says Docker permission denied | Fix Docker access for the Linux runner account; Controller PowerShell's Docker access alone is insufficient. |
| Ports 3000/3001 do not respond | B3 checks existing containers. If absent or unhealthy, inspect deployment logs and restore using B4 after resolving prerequisites. Starting the local port-3002 rehearsal does not start production. |
| Fault command says wrong experiment mode | The new request-fault deployment has not arrived, or you targeted the wrong port. Inspect `/health` and the current journal before injecting. |
| Campaign succeeds just after the pause | Both observed samples were healthy. Enabling request faults alone injects nothing. C3 requires actual HTTP 503 traffic and a confirmed bad observation. |
| Temporary traffic causes rollback | Errors or another unhealthy metric outlasted the fixed observation budget. Inspect measurements/timing; remove errors promptly at the first confirmed unhealthy observation on the next run. |
| WinError 183 / campaign directory exists | Generate a new timestamp/path. Do not erase or reuse the old evidence directory. |
| Missing/stale project artifacts | Review changed inputs/generator, run A3 generation explicitly, then validate. Do not delete the generation manifest. |
| Gradle 75% after `Campaign finished` | Campaign is complete; close MAS Console after capturing evidence. That percentage is not pipeline progress. |
| Another controller holds lock | An earlier controller/console remains active. Resolve it first; linked worktrees share the lock. |
| `execution_uncertain` after interruption | Follow F3. Closing local Jason does not necessarily cancel GitHub execution. |

### F3. Reconcile an interrupted campaign

**Start:** close the stopped MAS Console. In GitHub Actions, inspect the run URL from the old journal: it may still be queued/running, completed or cancelled. Restore session settings with B2; this does not launch anything.

**Actions:** Controller PowerShell:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

**Explanation:**

- The command reads the pending execution's remote status and records reconciliation. It neither dispatches nor resumes the old campaign.

**Expected results:**

- A confirmed terminal execution settles the pending record.
- Still unknown means do not redispatch: fix access/runner issues, let the old job reach a terminal state, and reconcile again. Preserve the output if it remains uncertain.
- Confirming a completed staging/build job is not equivalent to a successful whole deployment.

**Cleanup:** once resolved, check the app in B3, restore v1 with B4 if needed, and use a new campaign directory. Never manually delete pending state to force progress.

Further reference: [framework customization](../bdi-cicd-framework/README.md), [generation and runtime policy](BDI_GENERATION_AND_RUNTIME.md), [setup details](BDI_SETUP.md). The previous manual is retained in [the manual archive](archive/manual-guides/BDI_MANUAL_EXECUTION_GUIDE-before-session-rewrite.md) for history; use this guide's current steps.
