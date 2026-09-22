# Manual experiment: deploy v1 to v2 with BDI

**Configuration lifecycle:** edit the two models plus `bdi-cicd-framework/config/controller_policy.yaml` and `runtime_bindings.yaml`; regenerate explicitly after changing any of them. Missing policy fields fail validation. Campaign startup reuses the saved schema-2 contract and agent; the BDI campaign never regenerates them. Conventional has its own frozen configuration; verify parity before paired trials. Publish the complete migrated control revision for native trials and select the same revision for BDI; existing application v1/v2 tags and verified release receipts remain usable.

**Returning after the app-version update:** start at [Refresh the version pair, step 1](06_REFRESH_VERSION_PAIR.md#1-review-and-publish-the-new-v1-source). Keep your existing tools/runner, but create new labelled v1/v2 commits and a fresh v1 receipt. Then return to B1-B4 and C6.

Run commands yourself, one step at a time. C0-C5 retain manual execution/injection; C6 manually launches one comparative trial with automatic fault timing, traffic and evidence. This guide loads the current immutable application/control selections and verified v1 receipt from the saved release-pair JSON.

For the research comparison, use the [comparative execution guide](02_COMPARATIVE_EXECUTION_GUIDE.md): one manually launched trial with automatic fault setup, traffic timing and metric extraction, supporting BDI and the native GitHub Actions pipeline. Both approaches have the same 11-case catalog; use C6 below for paired trials. The conventional activation walkthrough is [here](04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md). The steps below remain available for individual/manual experiments.

New comparison trials store evidence under `experiments/results/bdi/`; historical runs remain in `bdi-cicd-framework/runs/`. Follow the [results inspection guide](05_EXPERIMENT_RESULTS_GUIDE.md) to retain console, journal, traffic and GitHub evidence. The conventional project is now independent in `ci-cd-conventional/`; BDI orchestration remains this guide's Jason agent.

## Choose your route

| When | Steps |
|---|---|
| First time on this computer | A1 tools/login; A2 local app check; A3 generate and simulate; A4 select published versions |
| Before **every** experiment, including after reopening PowerShell | B1 Docker/runner; B2 restore session settings; B3 check deployed version; B4 restore v1 if needed |
| Matched BDI versus native GitHub comparison (all 11 cases) | C6 and the comparison guide |
| Healthy deployment | C1, then E1 |
| Build/test/security failure or bounded retry | C2, then E1 |
| Scripted traffic: healthy, fluctuating, burst, temporary/persistent/intermittent errors, idle | C0, then E1 |
| Scripted staging failures: temporary or persistent | C0-S, then E1 |
| Manual temporary production error traffic, then continue v2 | C3, then E1 |
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

### A3. Validate the configuration and rehearse the BDI agent

**Start:** Controller PowerShell. Keep normal staging/production success goals for Part C. All paths below are inside `bdi-cicd-framework/`.

| Source file | Review or change here |
|---|---|
| `models/01_pipeline.yaml` | Jobs, dependencies, worker job names, environments, recovery relationship and `max_retries` |
| `models/02_goal.yaml` | Achievement, maintenance and avoidance goals |
| `config/controller_policy.yaml` | Retry-safe entities, observation/reconciliation budgets, recovery rules and error/latency thresholds |
| `config/runtime_bindings.yaml` | Readiness/Prometheus URLs, correlated metric queries and freshness limit |

**Actions 1 - generation, only when needed:** the migration already generated the current artifacts. Skip this block if you have not changed any source or generator and validation below passes; run it for a new configuration revision or after reviewing a stale-artifact error. Do not copy relocated settings back into 01/02, edit generated 03/ASL, or delete the manifest.

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
if ($LASTEXITCODE -ne 0) { throw 'Generation failed; inspect the input error' }
```

**Actions 2 - always validate, then rehearse:** run:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Artifact validation failed' }
py -3 -B bdi-cicd-framework/run_controller.py --gui --scenario healthy
```

**Explanation:**

- `generate_project.py` validates all four sources, saves/reloads 03, and generates the agent solely from that saved contract; the manifest records source/generator hashes.
- Each `if` stops the block if the preceding check failed.
- `--validate-only` verifies their consistency without dispatching.
- `--scenario healthy` runs Jason with simulated execution and telemetry.

**Expected results:**

- Validation prints `Project artifacts are consistent`; a missing/stale profile stops startup with an explicit regeneration instruction.
- Persistent outputs: `models/03_workflow_model.yaml`, `models/generation-manifest.json`, `bdi/controller_agent.asl`.
- Existing payment policy is unchanged: one execution retry for eligible retryable failures, at most 36 observations at five-second intervals within 180 seconds, and two consecutive healthy observations. These are explicit configuration values, not hidden defaults.
- MAS Console's `controller_agent` log reaches `BDI_CONTROLLER_RESULT=achieved recovery=not_needed`.
- No real GitHub deployment is dispatched by this simulation.

**Cleanup:** close MAS Console after the final result. Gradle's **75% EXECUTING** while the completed GUI remains open is normal. Regenerate only after changing inputs/generator/policy, not before each campaign. Keep generated files with their matching configuration revision.

### A4. Select the current version pair

Use the [version-pair refresh guide](06_REFRESH_VERSION_PAIR.md) to create and publish labelled v1/v2 commits, freeze the common control tag, and record their SHAs in a local pair JSON. This is also the route for existing users who have completed the old setup. Do not move the historical `v1` tag or reuse an old receipt for the new v1 source.

For an already prepared pair, locate its saved JSON path. B2 loads the repository, worker, source SHAs and verified receipt from it. First-baseline setup is F1 (or refresh guide step 4) if that pair has no receipt yet. Neither app-label changes nor selecting a different app SHA requires agent regeneration.

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
$pairFile = 'REPLACE_WITH_ABSOLUTE_PATH_TO_RELEASE_PAIR_JSON'
$pair = Get-Content -LiteralPath $pairFile -Raw | ConvertFrom-Json
$env:GITHUB_REPOSITORY = $pair.repository
$env:GITHUB_TOKEN = gh auth token --hostname github.com
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Repeat A1 GitHub login' }
$env:BDI_WORKFLOW_REF = $pair.worker_ref
$v1Tag = $pair.v1_tag
$v2Tag = $pair.v2_tag
$v2Sha = $pair.v2_sha
$env:BDI_RELEASE_SHA = $v2Sha
$knownGood = $pair.known_good_receipt
if ([string]::IsNullOrWhiteSpace($knownGood)) { throw 'Establish this pair baseline using refresh guide step 4 or F1' }
$baseline = Get-Content -LiteralPath $knownGood -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or
    $baseline.repository -ne $env:GITHUB_REPOSITORY -or $baseline.release_sha -ne $pair.v1_sha -or
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
- The saved pair supplies the new v1/v2 tags, candidate SHA and control revision. Do not fall back to historical example tags or local HEAD.
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

- Browser: `http://localhost:3000/checkout` is production; `http://localhost:3001/checkout` is staging. Refresh both pages after deployment.
- The banner immediately shows **Payment Service v1** or **Payment Service v2**; no payment is needed. `/health.appVersion` reports the same source label. A browser tab opened before deployment may show the previous release until refreshed.
- Prometheus opens at ports 9090 (production) and 9091 (staging).
- `/health.deploymentRunId` is an execution UUID, not a Git SHA. Match it to `executions.production.executionId` or `executions.staging.executionId` in the relevant campaign result, then read that result's `release_sha`.

**Cleanup/decision:** for a measured C6 trial, perform B4 before every trial and retain its reset evidence. For an individual manual demonstration, an already verified v1 in normal mode can be reused; if either environment is uncertain, perform B4. Starting Play alone does not prove you restored v1.

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

### C0. Scenario-driven traffic (recommended for repeatable timing)

**Start:** finish B1-B4. Use this instead of the C1/C3/C4 launch commands for a scripted-traffic run. BDI still owns deployment and recovery; this separate client only sends fake-payment requests and observes the journal. Manual injection remains available in C3/C4.

Choose one profile:

| `$trafficScenario` | Traffic after the selected deployment pause | What to assess |
|---|---|---|
| `healthy` | About 3 normal payments/second | Healthy delivery |
| `fluctuating` | 1, 6, 2, then 4 normal requests/second | Verification under varying load |
| `burst` | 2 requests/second for 15s, 10 for 30s, then 3 | Short traffic peak; errors are not guaranteed |
| `temporary-errors` | 70% fault headers at 4 requests/second for 75s, then all normal | Reobserve, then continue if health recovers within budget |
| `persistent-errors` | 70% fault headers at 4 requests/second | Reobserve, then recover if health remains bad |
| `intermittent-errors` | Faults 75s, normal 20s, faults 20s, then normal | Whether the rolling metric window clears before the deadline |
| `idle` | No payments from this client | Lack of request evidence is not proof of application failure |

Rates are targets, with seeded +/-25% spacing variation and a single request in flight. Request latency reduces achieved throughput. Fault fractions are sampled probabilities, not exact quotas. Profiles last at most 600 seconds of active traffic and stop earlier on campaign completion/recovery. The client waits up to 30 minutes for the pause. A seed repeats choices; real scheduling and responses still vary.

**Actions 1 - prepare, do not launch yet:** Controller PowerShell:

```powershell
$trafficScenario = 'temporary-errors'
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-' + $trafficScenario
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
if ($trafficScenario -in @('temporary-errors','persistent-errors','intermittent-errors')) {
    $faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
    Set-Content -LiteralPath $faultFile -Value 'production.experiment_mode=request_faults' -Encoding ascii
    $env:BDI_EXECUTION_PLAN = $faultFile
}
$candidateDir
```

- `$trafficScenario` selects the profile; `BDI_RELEASE_SHA` selects published v2.
- `$candidateDir` assigns fresh evidence; do not create this directory yourself.
- `Remove-Item` clears old faults. The conditional block writes/selects request-fault configuration only for error profiles.
- The last command prints the exact path to copy to the traffic terminal.

**Actions 2 - arm the traffic client:** in Traffic PowerShell, choose the same profile as above and paste the printed directory:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$trafficScenario = 'temporary-errors'
$trafficCampaign = Read-Host 'Paste the campaign directory from Actions 1'
node scripts/run-traffic-scenario.mjs --campaign "$trafficCampaign" --scenario "$trafficScenario" --seed 42
```

- `Set-Location` selects the local client; it does not need publication to run on your computer.
- `$trafficScenario` must match the controller setup; `Read-Host` transfers the campaign path between terminals.
- `node` prints **WAITING** and an evidence path. It waits for this campaign's fresh production pause, then verifies `/health.deploymentRunId` against its execution ID. Error profiles also require `request_faults` mode.
- Keep this terminal running. It can start before the campaign directory exists; it does not create that directory or dispatch GitHub work.

**Actions 3 - deploy:** back in Controller PowerShell:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --pause-after production --pause-ms 60000 --artifacts-dir "$candidateDir"
```

- This starts BDI with the same 60-second pause used by manual injection. The traffic client notices the journal event automatically; you do not need to race it.

**Expected results:**

- Traffic terminal: **WAITING -> STARTED -> PHASE**, then **ACTIVE** counters every five seconds. Fault requests count as `injected503`; normal requests count as `HTTP201`.
- `temporary-errors` automatically switches to normal traffic after 75 seconds from traffic start, spanning the pause and initial observation. Do not stop it manually at that transition.
- BDI continues making its own decisions from real app/Prometheus measurements. A traffic profile name does not guarantee a BDI outcome.
- On rollback selection, the client stops sending candidate traffic; the rollback worker provides its own verification traffic. A request already in flight may finish. Identity changes also stop the client.
- Evidence appears next to the campaign in a unique `*-traffic-*` directory: `profile.json`, per-request/phase `traffic.jsonl`, and final `summary.json`. The summary's `stopped` refers to the traffic client, not the BDI outcome; inspect E1 separately.
- `profile_duration_limit` means the client stopped on its own time cap; if BDI is still active, inspect it rather than treating this as a completed experiment.
- Attaching after the pause expired, to an old completed campaign, or to the wrong deployment produces a refusal/early stop, not uncorrelated injection. Reset and use a new campaign when appropriate.

**Cleanup:** after BDI finishes, inspect E1 and the traffic evidence. Ctrl+C stops the client early and saves a summary; it does not stop BDI. Repeat B before another comparison. Keep the manual client off while the scenario client runs, unless intentionally testing combined load.

**Staging scenarios:** use the complete C0-S procedure below instead of adapting production commands manually.

**Customization:** profiles are in `scripts/traffic-scenarios/`. Copy a JSON profile, adjust phase seconds, target rate (0..10), error fraction (0..1), jitter and seed, then use `--profile path/to/profile.json` instead of `--scenario`. These are payment-app profiles: another app needs its own request body/endpoints and identity/fault integration. This is not a high-concurrency capacity benchmark. True server-latency injection is not available through the current published worker's request-fault interface; normal load fluctuations measure actual response latency but do not manufacture delay.

### C0-S. Staging traffic failures: recover or block promotion

**Start:** finish B1-B4 so production and staging are verified v1. Choose **one** of these profiles; repeat setup/reset before the other comparison:

| Profile | Staging traffic | Expected BDI behavior |
|---|---|---|
| `staging-temporary-errors` | 70% error headers for 75 seconds, then continuous normal traffic | Wait/reobserve staging; if health recovers within budget, continue to production and verify v2 |
| `staging-persistent-errors` | 70% error headers until campaign completion or the 600-second cap | Exhaust staging observation budget and stop promotion; production stays v1 |

Both profiles select staging and port **3001** by default. The runner rejects a conflicting `--entity production` argument. Production receives no traffic from this client. BDI outcomes still depend on real measurements.

**Actions 1 - prepare:** Controller PowerShell; change only `$trafficScenario` to choose the second case:

```powershell
$trafficScenario = 'staging-temporary-errors'
$env:BDI_RELEASE_SHA = $v2Sha
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-' + $trafficScenario
$faultFile = [System.IO.Path]::GetFullPath("$candidateDir-faults.properties")
Set-Content -LiteralPath $faultFile -Value 'staging.experiment_mode=request_faults' -Encoding ascii
$env:BDI_EXECUTION_PLAN = $faultFile
$candidateDir
```

- The first two assignments choose the scenario and published v2.
- `$candidateDir` names fresh campaign evidence; `$faultFile` resolves its separate configuration file.
- `Set-Content` enables request faults **only in staging**; the next assignment selects that file.
- The last command prints the path to paste in the Traffic terminal. Do not launch yet.

**Actions 2 - arm traffic:** in Traffic PowerShell, use the same scenario name:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$trafficScenario = 'staging-temporary-errors'
$trafficCampaign = Read-Host 'Paste the staging campaign directory from Actions 1'
node scripts/run-traffic-scenario.mjs --campaign "$trafficCampaign" --scenario "$trafficScenario" --seed 42
```

- `Set-Location` selects the client; the scenario assignment matches Actions 1.
- `Read-Host` transfers the campaign path to this window.
- `node` prints **WAITING for fresh staging controller_pause**. Keep it running.

**Actions 3 - launch:** back in Controller PowerShell:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good "$knownGood" --confirm-compatible-rollback --pause-after staging --pause-ms 60000 --artifacts-dir "$candidateDir"
```

- The controller pauses after staging deployment; the client verifies its execution ID and automatically begins staged traffic. Production is still v1 at this point.

**Expected results:**

- Traffic terminal: STARTED, PHASE, then ACTIVE counters for injected HTTP 503 and successful HTTP 201 requests. Evidence records `entity: staging` and a port-3001 URL.
- MAS: `observe entity=staging` and repeated `wait_reconsider` while errors remain in the metric window.
- **Temporary:** the client automatically switches to normal traffic after 75 seconds. On healthy verification, GitHub then receives **Production entity**; final result can be `achieved / not_needed`. If health does not recover in time, stopping is valid; inspect the journal.
- **Persistent:** the normal success-goal campaign stops, ordinarily `stopped / not_attempted`. No production job or production rollback should be selected for this staging health failure. Port 3000 remains v1; port 3001 may serve the failed candidate in request-fault mode.
- The traffic client stops on `controller_finished`. During successful temporary recovery it keeps normal staging traffic running until the campaign ends, supporting the pre-production staging check.

**Cleanup:** E1, then B1-B4. Even when production remains v1, restore staging too before the next comparison. Preserve both campaign and sibling traffic evidence. For manual staging injection instead, C4 retains the port-3001 variant.

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

**Why traffic must continue during this release-verification experiment:** this script is the client sending payment requests. Without `--continuous`, it sends six requests and exits; the app itself can remain ready. The two-minute latency query needs recent payment samples. Once requests stop, the histogram rate can become zero and p95 undefined, so the controller cannot confirm healthy telemetry. Stopping errors must therefore be followed immediately by **normal traffic**, not silence.

Use the direct `node` commands below. In the observed Windows invocation, the npm wrapper did not forward `--continuous`. Direct invocation removes that argument-forwarding dependency. Do not change missing metrics to zero or extend the observation budget just to conceal missing traffic.

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
- `Get-Content` follows the journal; start after the file appears. **The pause is a Java journal event, not a message in the MAS `controller_agent` tab.** Keep this Observation terminal visible.

**Expected start signal in Observation PowerShell** (field order can differ):

```json
{"event":"controller_pause","after_entity":"production","milliseconds":60000}
```

This excerpt identifies a 60-second pause that resumes automatically. It is not a prompt awaiting input. Watch the current campaign's new event, not a pause from a previous journal. If the event is already more than 60 seconds old, inspect the current outcome before proceeding; do not guess from `run entity=production`, which only means dispatch started.

**Actions 3 - at `controller_pause` with `after_entity: production`:** immediately run in Traffic PowerShell:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
$health = Invoke-RestMethod http://localhost:3000/health
$health
if ($health.experimentMode -ne 'request_faults') { throw 'Wrong app mode; inspect this campaign before injecting' }
$env:PAYMENT_BASE_URL = 'http://localhost:3000'
node scripts/generate-experiment-traffic.mjs inject_error 6 --continuous
```

- `Set-Location` selects the traffic script's repository.
- The health request and display confirm the new app's mode/identity; the guard rejects a normal-mode app.
- `PAYMENT_BASE_URL` targets production; `node` passes `--continuous` directly to the script and continuously sends fault-header requests.

**Traffic checkpoint before continuing:**

- `/health` must show `request_faults`. If the guard throws or the connection resets, stop here; the app may still be changing. Recheck `/health` before retrying. Do not continue past the error.
- HTTP 503 lines and `Summary` lines must repeat across multiple batches, approximately once a second plus request time.
- The `PS C:\...>` prompt must **not** return until you press Ctrl+C or the script fails.
- Six responses followed by a prompt means the client stopped. The final `Wait 10-20 seconds...` message also means the script exited; it is not running in the background.
- Keep the Traffic terminal visible. If it exits with an error, retain that error and check the app/mode before restarting.

**Actions 4 - stop the temporary fault:** keep errors running through the end of the pause until the journal shows a production `telemetry_measurement` with `data_status: fresh` and an error rate above `0.05` and MAS shows `BDI_DECISION=wait_reconsider`. Then **immediately Ctrl+C in Traffic PowerShell**, and run:

```powershell
node scripts/generate-experiment-traffic.mjs normal 6 --continuous
```

- This sends successful requests while the two-minute metric window clears. Do not wait another two minutes before starting normal traffic.

**Normal-traffic checkpoint:**

- Repeated HTTP 201 responses and increasing success totals must appear; the PowerShell prompt must not return. Leave this running until the agent's final result.
- In the Observation terminal, production measurements should remain/become `data_status: fresh`; error rate should fall below the configured limit as the old errors leave the window. Latency must also pass.
- `wait_reconsider` alone does not prove a bad error rate: it also appears for missing data or while waiting for the next healthy sample.
- An `unavailable` measurement's numeric zeros are placeholders, not proof of zero errors or zero latency. If normal traffic is repeating but measurements remain unavailable beyond the export/scrape delay, inspect Prometheus rather than assuming success (see F2).
- If the campaign already ended or rollback began, new traffic cannot resume that campaign. Finish recording it, reset with Part B and start a new C3 run.

**Expected results:**

- Error traffic produces HTTP 503; normal traffic produces HTTP 201.
- The agent actually observes unhealthy production before you remove the cause; otherwise this is not a demonstrated fault-recovery experiment.
- It rechecks rather than redispatching production. If health clears within the count/time budget, two consecutive healthy samples allow `achieved / not_needed`; production stays v2.
- Current `config/controller_policy.yaml` maximum: 36 observations, five seconds apart, within 180 seconds from the first observation. This is a maximum, not a mandatory wait; two healthy observations can finish quickly.
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

### C6. Matched comparison: all 11 scenarios

**Start:** one-time setup is already complete, and B1-B4 has restored the selected pair's v1. Use the pair created by the [returning-user procedure](06_REFRESH_VERSION_PAIR.md); B2 must load its new worker ref and baseline receipt. Do not repeat tool installation for each pair.

**Actions - Controller PowerShell:** retain the pair, verified `$knownGood` path and `$v2Sha` loaded in B2. This launches one BDI trial, with automatic fault timing and traffic:

```powershell
$env:GITHUB_REPOSITORY = $pair.repository
$workerRef = $pair.worker_ref # loaded in B2; same control revision as conventional
$env:BDI_WORKFLOW_REF = $workerRef
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
$env:GITHUB_TOKEN = (gh auth token --hostname github.com)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Load a valid controller token first' }
if ([string]::IsNullOrWhiteSpace($knownGood) -or -not (Test-Path $knownGood)) { throw 'Restore the verified v1 receipt path using B2' }
if ([string]::IsNullOrWhiteSpace($v2Sha)) { throw 'Resolve the existing v2 tag using B2' }
$case = 'healthy'
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Resolve artifact consistency before launching' }
py -3 ci-cd-conventional/configuration.py --check-bdi-parity
if ($LASTEXITCODE -ne 0) { throw 'Paired configurations differ' }
py -3 -B bdi-cicd-framework/run_experiment.py --mechanism bdi --case $case --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed 42
```

- Select the same newly published worker tag used by the conventional trial; adjust the example tag if you chose another name.
- Clear leftover manual fault/pause values. The wrapper creates fresh trial-specific settings, a new campaign and automatic traffic.
- Load the controller token without printing it; GitHub Actions needs Actions-write access for BDI dispatch.
- Select any case from the [shared 11-scenario table](02_COMPARATIVE_EXECUTION_GUIDE.md#shared-scenarios): `healthy`, `build-failure`, `test-failure`, `transient-test-failure`, `service-unavailable`, `infrastructure-failure`, `deployment-timeout`, `staging-temporary`, `staging-persistent`, `production-temporary`, `production-persistent`.
- This research route uses terminal output rather than the keep-open MAS GUI. For interactive MAS inspection and manual injection, C0-C5 remain available.

**Expected results:** `Master goal started` and `BDI_DECISION` output; selected-entity runs on GitHub; traffic `STARTED`/`PHASE` messages for traffic scenarios; a campaign directory under `experiments/results/bdi/`, its experiment plan directory, and separate target/background traffic directories (clients exit without payments if their stage is never reached). Read `controller-result.json` and `experiment-metrics.json`. Use the shared scenario table for expected v2 delivery, v1 restoration or safe stopping. Missing fault evidence invalidates a claimed fault trial.

**Reverse/cleanup:** wait for terminal remote execution, stop any residual traffic, then restore both environments to v1 using B4. Keep the same pair selections after B2/B4. Launch the conventional counterpart with the same case/seed/v2/receipt. Do not edit or recreate the v2 tag between trials.

## D. Optional goal experiment

### D1. Request an actual staging failure as the achievement

**Start:** B1-B4 complete. This changes the goal, not just the fault. Use a separate generated project to preserve normal deployment goals.

**Actions:** Controller PowerShell:

```powershell
$negativeProject = 'bdi-cicd-framework/projects/staging-failure'
py -3 -B bdi-cicd-framework/generate_project.py --project-dir "$negativeProject" --pipeline bdi-cicd-framework/models/01_pipeline.yaml --goal bdi-cicd-framework/examples/staging_failure_goal.yaml --policy bdi-cicd-framework/config/controller_policy.yaml --bindings bdi-cicd-framework/config/runtime_bindings.yaml
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
- Four source snapshots are present: `01_pipeline.input.yaml`, `02_goal.input.yaml`, `controller_policy.input.yaml` and `runtime_bindings.input.yaml`. Keep them with the saved 03, agent and manifest so later configuration edits do not change this campaign's evidence.
- `achieved / not_needed`: goals met; ordinary delivery passed required health checks.
- `stopped / not_attempted`: stopped without recovery, commonly before production.
- `stopped / restored`: candidate failed, verified v1 restored.
- `stopped / failed` or `unknown`: investigate; do not assume a safe baseline.
- Keep the matching `*-faults.properties` file, screenshots, GitHub run links and traffic start/stop times.

**Cleanup:** Ctrl+C in Traffic and Observation windows; leave app/runner running for another experiment. Repeat B, then choose C or D. Keep original v1 evidence; never delete pending execution records to bypass an unresolved campaign.

## F. First baseline and troubleshooting

### F1. Establish v1 only if no verified baseline receipt exists

**Start:** A1-A4 and B1 complete. Skip this only if the receipt verifies the selected pair's exact v1 SHA. Existing users need a fresh baseline after updating the v1 source. Controller PowerShell, normal success-goal project:

```powershell
Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN,Env:GITHUB_API_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO,Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL,Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
$pairFile = 'REPLACE_WITH_ABSOLUTE_PATH_TO_RELEASE_PAIR_JSON'
$pair = Get-Content -LiteralPath $pairFile -Raw | ConvertFrom-Json
$env:GITHUB_REPOSITORY = $pair.repository
$env:GITHUB_TOKEN = gh auth token --hostname github.com
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Complete GitHub login in A1' }
$env:BDI_WORKFLOW_REF = $pair.worker_ref
$v1Sha = $pair.v1_sha
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
- The saved pair selects the newly labelled v1 SHA; `BDI_RELEASE_SHA` selects it for deployment.
- The directory assignment and display give this baseline fresh evidence.
- Validation and its guard check the generated project; `--baseline` explicitly starts with no rollback source.

**Expected:** all five normal entities finish and both deployments pass health checks; MAS reports achieved. Close the completed console, then:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw -ErrorAction Stop | ConvertFrom-Json
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $v1Sha -or
    -not $baseline.verified_releases.production.github_run_id -or -not $baseline.verified_releases.staging.github_run_id) { throw 'Baseline not verified; inspect its journal' }
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$pair.known_good_receipt = $knownGood
$pair | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
$knownGood
```

- `Get-Content` reads the receipt; the guard requires live success at v1 with both verified environments.
- `Resolve-Path` saves the full receipt path; the final line displays it.

**Cleanup:** B2 loads that receipt from the updated pair JSON. Verify both `/health.appVersion` values are `v1` and identities match the receipt, as in refresh guide step 4. Keep the receipt and containers. Do not use a simulation, build-only or negative-goal result as the baseline.

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
| Traffic prints six responses and returns to PowerShell | It is a single batch, not continuous traffic. Use the direct `node ... --continuous` commands in C3; verify repeated batches and no returned prompt. |
| No pause message in the agent tab | Follow C3 Actions 2 in Observation PowerShell. `controller_pause` is in the campaign journal, not the `controller_agent` log. |
| App ready but telemetry unavailable | Check that normal payment traffic continues. No recent payments can make p95 undefined; readiness alone is insufficient. If traffic continues, check current-execution queries in Prometheus, scrape/export health and sample freshness. |
| Temporary traffic causes rollback | Errors or another unhealthy metric outlasted the fixed observation budget. Inspect measurements/timing; remove errors promptly at the first confirmed unhealthy observation on the next run. |
| WinError 183 / campaign directory exists | Generate a new timestamp/path. Do not erase or reuse the old evidence directory. |
| Missing/stale project artifacts or profiles | Check all four source files in A3, including `config/`; review changes, explicitly regenerate once, then validate. Do not delete the generation manifest or reuse an old 03 with new configuration. |
| Unknown/conflicting fields after migration | Policy belongs in `config/controller_policy.yaml`; telemetry bindings belong in `config/runtime_bindings.yaml`. Remove duplicate inline settings from 01/02 after checking their intended values. Required policy fields must be explicit. |
| Gradle 75% after `Campaign finished` | Campaign is complete; close MAS Console after capturing evidence. That percentage is not pipeline progress. |
| Another controller holds lock | An earlier controller/console remains active. Resolve it first; linked worktrees share the lock. |
| `execution_uncertain` after interruption | Follow F3. Closing local Jason does not necessarily cancel GitHub execution. |

**If telemetry stays unavailable despite repeating normal HTTP 201 responses:** open production Prometheus at `http://localhost:9090`. Copy the exact `latency_p95_ms_query` from `bdi-cicd-framework/config/runtime_bindings.yaml` (`telemetry.metrics`), replace `{{run_id}}` with the current `/health.deploymentRunId`, and execute it. A finite p95 is required; `NaN` or an empty result is not healthy evidence. Check the error-rate, availability and sample-age queries the same way. Use port 9091 for staging. The journal currently suppresses the individual metric exception, so `unavailable` alone cannot distinguish no traffic from a scrape, query or freshness problem. Preserve the query results if this continues; do not disable correlation or freshness checks.

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

Further reference: [framework customization](../../../bdi-cicd-framework/README.md), [generation and runtime policy](../../resources-and-plans/02_BDI_GENERATION_AND_RUNTIME.md), [setup details](01_ENVIRONMENT_CHECKLIST.md). The superseded previous manual is retained in [the manual archive](../../archives/04_manual-guides/01_BDI_MANUAL_EXECUTION_GUIDE-before-session-rewrite.md) for history; use this guide's current steps.


### F4. Idle application versus insufficient telemetry

No users is a normal operating condition; it does **not** mean the app is broken. Readiness can be healthy while request latency has no recent samples. The current adapter groups missing/undefined request metrics and transport failures into `unavailable`, so the agent cannot distinguish all these causes from that belief alone. The numeric zeros on such an event are placeholders.

The current campaign verifies a **new release**, including its payment path. It reobserves insufficient evidence for a bounded time. `config/controller_policy.yaml` explicitly includes `telemetry_unknown` under `recovery_policy.rollback.run_after`, so an unverified candidate can be rolled back even if readiness is good. This means "could not verify the candidate", not "proved the application failed". After the campaign ends, BDI does not keep monitoring and will not roll back merely because normal user traffic later stops.

For these experiments, synthetic normal payments supply verification evidence even when no people are using the app. The `idle` profile deliberately supplies none; existing worker-generated samples may still be enough to finish before they age out, so idle does not guarantee rollback. Do not replace undefined latency with zero: that would claim unmeasured performance is good.

A future idle-aware policy should distinguish `insufficient_request_samples` from `telemetry_transport_failure`, check exporter freshness/readiness separately, and request bounded synthetic probes before deciding whether verification must stop or recover. That is a contract/agent/environment policy change, not something this traffic client silently changes. The current observation and recovery policy remains intact.

## Historical verification and current live checkpoints

The historical four-source migration preserved the payment contract values and generated agent at that revision. The [verification record](../../archives/06_experiment-records/four-source-migration-2026-09-22/00_README.md) includes 35 actual Jason simulations and eight paired simulations covering successful delivery, retries, uncertain execution and verified recovery. These are offline checks; they do not prove current GitHub credentials, runner availability or Docker health.

Before freezing a new experiment revision, run C6 for `healthy`, `transient-test-failure` and `production-persistent`, paired with the conventional approach using the same published control revision. Reset both environments to v1 between trials. Expect healthy delivery, successful delivery after the transient retry, and stopped candidate delivery with verified v1 restoration respectively; retain E1 evidence and the common experiment metrics. Use the [current study plan](../../resources-and-plans/01_EXPERIMENT_PLAN.md) and [comparative protocol](02_COMPARATIVE_EXECUTION_GUIDE.md#verification-before-live-experiments) for the live pilot checklist; the migration record is historical evidence only.
