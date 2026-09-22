# RQ1: End-to-end paired experiments for conventional and BDI CI/CD

**Current compact study:** use [guide 07](07_COMPACT_FIVE_SCENARIO_EXPERIMENTS.md) for the five-case schedule, safe dispatch/resume and schema-checked recording. Current conventional execution has six jobs; `collect.py` generates result JSON locally from downloaded receipts. A new control revision requires a new study.


## Introduction and reading path

**Research question:** Does BDI-based execution improve the reliability and resilience of CI/CD pipelines compared with conventional execution?

Use this document for the **whole paired study**. It combines setup, version selection, a baseline, every scenario, automatic evidence collection, reset and evaluation. You do not need to follow the older execution manuals alongside it. Those remain references for optional MAS GUI demonstrations and implementation details.

Both approaches deploy the same payment service, using the same immutable v1/v2 application SHAs, worker revision, Docker staging/production environments, telemetry, fault scripts and recovery capabilities. The normal jobs remain **build → test → security → staging → production**. GitHub Actions controls the conventional DAG; a generated Jason agent pursues `master_goal` in BDI. The agent can diagnose a stopped candidate, select one restart, verify fresh correlated health, resume delivery, or select verified rollback/safe stopping. Successful restart **can deliver v2**; successful rollback **restores v1 but does not deliver v2**.

This is a fair comparison against a conventional pipeline that also has retry, health checks, restart and rollback. Equivalent outcomes are plausible. Agent decision traces demonstrate goal-directed behavior; they do not by themselves demonstrate superior reliability.

| Situation | Start here |
|---|---|
| First use of this project | Step 1, then Step 2; complete the remaining steps in order |
| Existing tools, labelled v1/v2 pair and successful baseline | Check Step 1, use Step 2.1 if the control tag is old, then Step 3 |
| Returning to this same study after closing PowerShell | Step 3 to reload functions/session; Step 4 **reload** block; Step 11 if interrupted, otherwise Step 6 |
| One candidate trial just finished | Steps 8, 9 and 10; then Step 6 selects the next scheduled trial |
| Every scheduled trial is finalised | Step 12 |

**Execution order:** same scenario first, both approaches, with a verified v1 reset before **every** individual trial. Odd repetitions run BDI first; even repetitions run conventional first. Never run them concurrently. Use one repetition for a technical pilot (26 candidate runs) and a separate study with a predeclared repetition count for measurement (three repetitions = 78 candidate runs, plus baseline/resets). Three repetitions are a practical starting point, not a guarantee of statistical power.

### Scenarios, in execution order

The schedule includes all 13 currently implemented catalog cases. Fault injection and traffic are automatic; **do not manually stop containers or add another traffic client** during these trials.

| Order / case | Fault and why it is suitable | Expected safe behavior in either approach / evidence to inspect |
|---|---|---|
| 1. `healthy` | Normal payment traffic; establishes delivery and orchestration overhead | v2 achieved; staging/production health accepted; successful payments |
| 2. `build-failure` | Controlled nonzero build exit; deterministic failure control | Stop before downstream jobs; production retains reset v1; failed build step |
| 3. `test-failure` | Persistent nonzero test exit; checks promotion protection | No production deployment; verified reset v1 remains; failed test step |
| 4. `service-unavailable` | Stop the production payment app before the deployment job's readiness check; tests failure after deployment side effects | Production job fails; verified v1 rollback and health check |
| 5. `infrastructure-failure` | Stop staging PostgreSQL; dependent infrastructure becomes unavailable | Staging fails; promotion blocked; production remains v1; database-stop evidence |
| 6. `deployment-timeout` | Staging hangs 90 seconds before deployment, with a one-minute job deadline; repeats on retry | Confirmed timeout, one retry, stop before production; timeout timestamps |
| 7. `candidate-stopped` | Stop app **after** the production deployment job passes; database remains ready | Diagnose stopped matching v2 → one restart → fresh verification → deliver v2; repair receipts and `repair_verified` |
| 8. `production-temporary` | Mixed request errors for 35 seconds, then normal traffic; decisions depend on changing observations | Reobserve, accept only after recovery; no restart of a running app; actual error/healthy phases |
| 9. `production-persistent` | Sustained production request errors; repair is inapplicable to a running app | Bounded observations then verified v1 rollback; no blind restart |
| 10. `candidate-restart-fails` | Same stopped-candidate fault, then stop it immediately after its selected restart | One failed repair → verified v1 rollback; v2 goal unmet |
| 11. `transient-test-failure` | Typed first-attempt test failure; tests bounded execution retry | Exactly one additional test attempt, then deliver if all gates pass |
| 12. `staging-temporary` | Temporary request errors before promotion | Wait for fresh healthy staging observations before production |
| 13. `staging-persistent` | Persistent errors before promotion | Block production; production remains reset v1 |

**Scope:** the implemented “service unavailable” case concerns the **deployed payment service**, not an unavailable GitHub/deployment API. Infrastructure failure concerns **staging PostgreSQL**, not complete host loss. Build/test faults are controlled exits, not separate defective source commits. Report these limits explicitly; this study does not establish resilience to runner loss, cloud outages or network partitions. Step 11 handles interruptions as incomplete evidence, not as a measured fault case.

Normal policy: one eligible transient/timeout retry, five-second retry delay, 15-second deployment pause, at most 36 observations within 180 seconds, five-second observation interval, two consecutive healthy samples, error rate ≤5%, p95 ≤500 ms, ready/available and fresh correlated telemetry. Repair policy: one production restart, 120 seconds of shared normal payment probes, and a 300-second decision budget starting at diagnosis. Queue waits count; in-flight calls can add bounded wall-clock overhead. The two stopped-candidate cases use these probes instead of the normal **production** traffic client; normal staging traffic remains. A failed restart intentionally has no successful repair probes.

## Step 1. Prepare tools, repository and runner once

**Open:** Docker Desktop, Controller PowerShell in this repository, your repository on GitHub, and the existing WSL/Linux runner terminal. Commands below assume the current workspace path. On another computer, change only the `Set-Location` path.

Install Git, GitHub CLI, Python 3.12 with PyYAML, JDK 21+, Node 22+ and Docker Desktop/WSL integration. The Linux deployment runner needs Docker Compose and curl, and labels `self-hosted`, `linux`, `payment-deploy`. Use the same Docker engine for both approaches. In GitHub **Settings → Environments**, configure `staging` and `production`; record any required approval waits. Register a runner only if none exists, using **Settings → Actions → Runners → New self-hosted runner**. Keep its registration token private.

**Actions — Controller PowerShell:**

```powershell
. {
    $ErrorActionPreference = 'Stop'
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
    if ($LASTEXITCODE -ne 0) { throw 'Install PyYAML before continuing.' }
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Resolve dependency installation.' }
    gh auth status
}
```

Only if authentication is missing, run this separate block and complete the browser login:

```powershell
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
```

**Actions — existing Linux runner terminal:** if it is not already running as a service, use its actual installation directory. The current example is:

```bash
cd ~/actions-runner-payment
docker info
docker compose version
./run.sh
```

**Expected:** tools available, correct Git remote/account, Docker running, runner online and listening. Keep the machine awake and the runner open throughout. Do not create another listener for a running service. Controller PowerShell must reach app ports 3001/3000 and Prometheus 9091/9090. These deployment stacks will be created by the baseline/reset, not by starting an unrelated local app.

**Next:** Step 2. No deployment has been requested by the PowerShell checks above.

## Step 2. Freeze application and control revisions once

The four BDI configuration sources and generated outputs are already present. Validate them; regenerate only after an intentional source/generator change, then review the conventional snapshots and parity again. Do not edit generated ASL/03 to fix runtime errors.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    py -3 bdi-cicd-framework/run_controller.py --validate-only
    if ($LASTEXITCODE -ne 0) { throw 'Review inputs and run generate_project.py explicitly before continuing.' }
    py -3 ci-cd-conventional/configuration.py --check-bdi-parity
    if ($LASTEXITCODE -ne 0) { throw 'Review and align conventional snapshots/policy.' }
    py -3 ci-cd-conventional/sync_workflows.py --check
    if ($LASTEXITCODE -ne 0) { throw 'Synchronise and review workflow copies.' }
}
```

**Manual review:** commit intended source, generated, workflow and documentation changes; publish/register the reviewed workflows on the default branch through your normal branch/PR process. GitHub must offer **Conventional Payment CI/CD** and **BDI Entity Execution**. A push may run the separate validation workflow; it does **not** trigger the conventional deployment experiment. The experiment trigger is `workflow_dispatch` (Actions **Run workflow** or `gh workflow run`).

### Step 2.1. Existing labelled v1/v2 pair — retain the app SHAs

This is the appropriate route for the existing experiment pair. If it already selects the fully published repair-capable worker revision, skip the following publication block and continue to Step 3. Otherwise run it after committing/reviewing the control update. It creates a new tag/selection; it never moves old tags or deletes receipts.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $oldPairFile = (Get-Content experiments/results/release-pairs/current-pair.txt -Raw).Trim()
    $oldPair = Get-Content -LiteralPath $oldPairFile -Raw | ConvertFrom-Json
    if (git status --porcelain) { throw 'Commit reviewed changes before freezing control code.' }
    git diff --quiet $oldPair.v2_sha HEAD -- src tests package.json package-lock.json Dockerfile docker-compose.yml
    if ($LASTEXITCODE -ne 0) { throw 'Application differs; use a newly reviewed app pair instead.' }
    $series = (Get-Date -Format yyyyMMdd-HHmmss) + '-paired'
    $workerRef = "comparison-worker-$series"
    $workerSha = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve control commit.' }
    git tag $workerRef $workerSha
    if ($LASTEXITCODE -ne 0) { throw 'Use a fresh tag name.' }
    git push origin "refs/tags/$workerRef"
    if ($LASTEXITCODE -ne 0) { throw 'Resolve publication before continuing.' }
    $pairFile = [System.IO.Path]::GetFullPath("experiments/results/release-pairs/$series.json")
    if (Test-Path -LiteralPath $pairFile) { throw 'Never overwrite a pair record.' }
    [pscustomobject]@{
        series=$series; repository=$oldPair.repository
        v1_tag=$oldPair.v1_tag; v1_sha=$oldPair.v1_sha
        v2_tag=$oldPair.v2_tag; v2_sha=$oldPair.v2_sha
        worker_ref=$workerRef; worker_sha=$workerSha
        known_good_receipt=$oldPair.known_good_receipt; previous_pair=$oldPairFile
    } | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
    $pairFile | Set-Content experiments/results/release-pairs/current-pair.txt -Encoding utf8
}
```

**Expected:** selected JSON preserves app SHAs and the original receipt, but selects a new published control tag. Proceed to Step 3, skipping Step 2.2.

### Step 2.2. Only when no labelled application pair exists

**Open:** `src/release.ts` in your editor. First review the complete app/control revision. Set the declaration to `export const APP_VERSION: 'v1' | 'v2' = 'v1';`. Commit that reviewed baseline through your normal version-control process; do not silently stage unrelated files. At the clean v1 commit:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (git status --porcelain) { throw 'Review and commit the v1 source first.' }
    $series = Get-Date -Format yyyyMMdd-HHmmss
    $v1Tag = "experiment-$series-v1"
    $v2Tag = "experiment-$series-v2"
    $workerRef = "comparison-worker-$series"
    $v1Sha = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve v1.' }
    if ((Get-Content src/release.ts -Raw) -notmatch "APP_VERSION[^=]*= 'v1';") { throw 'Commit must be labelled v1.' }
    git tag $v1Tag $v1Sha
    if ($LASTEXITCODE -ne 0) { throw 'Tag creation failed.' }
    git switch -c "experiment/$series-v2" $v1Sha
    if ($LASTEXITCODE -ne 0) { throw 'Choose a fresh candidate branch.' }
}
```

**Manual edit:** change only the declaration to `export const APP_VERSION: 'v1' | 'v2' = 'v2';`. Review `git diff -- src/release.ts`. Then:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    git add -- src/release.ts
    git commit -m 'Mark paired experiment candidate as v2'
    if ($LASTEXITCODE -ne 0) { throw 'Candidate commit failed.' }
    $v2Sha = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve v2.' }
    git tag $v2Tag $v2Sha
    if ($LASTEXITCODE -ne 0) { throw 'Candidate tag failed.' }
    git tag $workerRef $v2Sha
    if ($LASTEXITCODE -ne 0) { throw 'Worker tag failed.' }
    git push -u origin HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Branch publication failed.' }
    git push origin "refs/tags/$v1Tag" "refs/tags/$v2Tag" "refs/tags/$workerRef"
    if ($LASTEXITCODE -ne 0) { throw 'Tag publication failed.' }
    $repository = gh repo view --json nameWithOwner --jq .nameWithOwner
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine repository.' }
    New-Item -ItemType Directory -Force experiments/results/release-pairs | Out-Null
    $pairFile = [System.IO.Path]::GetFullPath("experiments/results/release-pairs/$series.json")
    if (Test-Path -LiteralPath $pairFile) { throw 'Do not overwrite a pair.' }
    [pscustomobject]@{
        series=$series; repository=$repository; v1_tag=$v1Tag; v1_sha=$v1Sha
        v2_tag=$v2Tag; v2_sha=$v2Sha; worker_ref=$workerRef; known_good_receipt=$null
    } | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
    $pairFile | Set-Content experiments/results/release-pairs/current-pair.txt -Encoding utf8
}
```

Keep the app pair immutable throughout measurement. A subsequent control change requires a new study/control revision. **Next: Step 3.**

## Step 3. Load the session and reusable verification/reset functions

**Open:** Controller PowerShell at the repository root. Run this block at the start of every session, including after reopening a terminal. It reads the one-line pair pointer, captures the token without printing it, and checks the local/published control revision. It defines reset helpers; it does not deploy yet.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
    foreach ($name in @('GH_TOKEN','GITHUB_TOKEN','GITHUB_API_URL','BDI_EXECUTION_PLAN','BDI_SCENARIO','BDI_READY_URL','BDI_PROMETHEUS_URL','BDI_PAUSE_AFTER_ENTITY','BDI_PAUSE_MILLISECONDS','BDI_POLL_SECONDS','BDI_ENTITY_TIMEOUT_MINUTES')) {
        if (Test-Path "Env:$name") { Remove-Item "Env:$name" }
    }
    $pairFile = (Get-Content experiments/results/release-pairs/current-pair.txt -Raw).Trim()
    $pair = Get-Content -LiteralPath $pairFile -Raw | ConvertFrom-Json
    foreach ($field in @('repository','v1_sha','v2_sha','worker_ref')) {
        if ([string]::IsNullOrWhiteSpace($pair.$field)) { throw "Missing pair field: $field" }
    }
    $env:GITHUB_REPOSITORY = $pair.repository
    $env:GITHUB_TOKEN = gh auth token --hostname github.com
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Restore GitHub login.' }
    $env:BDI_WORKFLOW_REF = $pair.worker_ref
    $v1Sha = $pair.v1_sha; $v2Sha = $pair.v2_sha; $knownGood = $pair.known_good_receipt
    $workerRef = $pair.worker_ref
    $workerSha = gh api "repos/$($pair.repository)/commits/$workerRef" --jq .sha
    if ($LASTEXITCODE -ne 0) { throw 'Publish/select the worker tag first.' }
    py -3 -B experiments/control_revision.py --worker-sha $workerSha
    if ($LASTEXITCODE -ne 0) { throw 'Control revision mismatch. Fetch missing commits or complete Step 2 with a new control tag.' }
    py -3 bdi-cicd-framework/run_controller.py --validate-only
    if ($LASTEXITCODE -ne 0) { throw 'Resolve artifact consistency.' }
    py -3 ci-cd-conventional/configuration.py --check-bdi-parity
    if ($LASTEXITCODE -ne 0) { throw 'Resolve parity.' }
    py -3 ci-cd-conventional/sync_workflows.py --check
    if ($LASTEXITCODE -ne 0) { throw 'Resolve installed workflow copies.' }

    function Assert-V1Receipt([string]$Path, [string]$CheckPath) {
        $receipt = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        if ($receipt.mode -ne 'github' -or $receipt.outcome -ne 'achieved' -or $receipt.repository -ne $pair.repository -or $receipt.release_sha -ne $v1Sha) { throw 'Receipt does not verify this pair v1.' }
        $checks = @{}
        foreach ($entity in @('staging','production')) {
            $verified = $receipt.verified_releases.$entity
            if ($verified.release_sha -ne $v1Sha -or -not $verified.github_run_id -or -not $verified.execution_id) { throw "Unverified baseline: $entity" }
            if ($CheckPath) {
                $port = if ($entity -eq 'staging') { 3001 } else { 3000 }
                $health = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 10
                $null = Invoke-RestMethod "http://127.0.0.1:$port/ready" -TimeoutSec 10
                if ($health.appVersion -ne 'v1' -or $health.experimentMode -ne 'normal' -or $health.deploymentRunId -ne $verified.execution_id) { throw "Current $entity is not verified reset v1." }
                $checks[$entity] = @{ appVersion=$health.appVersion; experimentMode=$health.experimentMode; deploymentRunId=$health.deploymentRunId; ready=$true }
            }
        }
        if ($CheckPath) { $checks | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $CheckPath -Encoding utf8 }
    }

    function Invoke-StudyReset {
        if (-not $studyDir -or -not $knownGood) { throw 'Load the study and verified baseline first.' }
        foreach ($name in @('BDI_EXECUTION_PLAN','BDI_SCENARIO','BDI_READY_URL','BDI_PROMETHEUS_URL','BDI_PAUSE_AFTER_ENTITY','BDI_PAUSE_MILLISECONDS')) {
            if (Test-Path "Env:$name") { Remove-Item "Env:$name" }
        }
        $env:BDI_RELEASE_SHA = $v1Sha
        $destination = Join-Path $studyDir ('resets/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
        py -3 -B bdi-cicd-framework/run_controller.py --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$destination"
        if ($LASTEXITCODE -ne 0) { throw 'Reset incomplete: inspect evidence; do not launch a candidate.' }
        Assert-V1Receipt (Join-Path $destination 'controller-result.json') (Join-Path $destination 'reset-check.json')
        $destination | Set-Content (Join-Path $studyDir 'current-reset.txt') -Encoding utf8
        $env:BDI_RELEASE_SHA = $v2Sha
        "Both environments verified at v1: $destination"
    }
    [pscustomobject]@{ Repository=$pair.repository; Worker=$workerRef; WorkerSHA=$workerSha; V1=$v1Sha; V2=$v2Sha; Baseline=$knownGood } | Format-List
}
```

**Expected:** all displayed identities are populated, except baseline may be empty for a first pair. Publication/source mismatch must be resolved before proceeding. Do not ignore red errors or continue using stale variables. **Next: Step 4.**

## Step 4. Create the study schedule and establish/link the baseline

### 4.1. New study only: predeclare repetitions and create the ledger

**Manual selection — run separately:** choose 1 for a pilot, or your predeclared number of measured repetitions. Do not combine pilot and measured folders in one report.

```powershell
$repetitions = 3
$seed = 42
```

**Then run unchanged:**

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($repetitions -lt 1 -or $repetitions -gt 100) { throw 'Choose an explicit repetition count from 1 to 100.' }
    $cases = @('healthy','build-failure','test-failure','service-unavailable','infrastructure-failure','deployment-timeout','candidate-stopped','production-temporary','production-persistent','candidate-restart-fails','transient-test-failure','staging-temporary','staging-persistent')
    $catalog = Get-Content experiments/scenarios.json -Raw | ConvertFrom-Json
    if (@($cases | Where-Object { $_ -notin $catalog.PSObject.Properties.Name }).Count) { throw 'Catalog mismatch.' }
    $studyDir = [System.IO.Path]::GetFullPath('experiments/results/studies/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    New-Item -ItemType Directory -Path $studyDir -ErrorAction Stop | Out-Null
    $trials = @(); $index = 0
    for ($repeat = 1; $repeat -le $repetitions; $repeat++) {
        $order = if ($repeat % 2 -eq 1) { @('bdi','github-actions') } else { @('github-actions','bdi') }
        foreach ($case in $cases) {
            foreach ($mechanism in $order) {
                $index++
                $trials += [pscustomobject]@{ id=('{0:D3}-{1}-r{2}-{3}' -f $index,$case,$repeat,$mechanism); case=$case; repetition=$repeat; mechanism=$mechanism }
            }
        }
    }
    [pscustomobject]@{ schema_version=1; pair_file=$pairFile; repository=$pair.repository; v1_sha=$v1Sha; v2_sha=$v2Sha; worker_sha=$workerSha; worker_ref=$workerRef; repetitions=$repetitions; seed=$seed; trials=$trials } |
        ConvertTo-Json -Depth 8 | Set-Content (Join-Path $studyDir 'study.json') -Encoding utf8
    $trials | Export-Csv (Join-Path $studyDir 'schedule.csv') -NoTypeInformation -Encoding utf8
    $studyDir | Set-Content experiments/results/current-study.txt -Encoding utf8
    "Study: $studyDir ; candidate trials: $index"
}
```

### 4.2. Always reload the saved study, including after terminal restart

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-study.txt -Raw).Trim()
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    if ($study.repository -ne $pair.repository -or $study.v1_sha -ne $v1Sha -or $study.v2_sha -ne $v2Sha -or $study.worker_sha -ne $workerSha) { throw 'Current pair/control differs from this study. Restore the selection or create a new study.' }
    $study.trials | Format-Table id,case,repetition,mechanism
}
```

### 4.3. Baseline: reuse a verified receipt, or create it once

The baseline is setup, not a measured trial. If `$knownGood` is populated and `Assert-V1Receipt "$knownGood" ''` succeeds, skip the deployment block and go to Step 5. A historical receipt proves prior verification, not current state; Step 5 still restores both environments.

If a successful v1 receipt exists but was never linked, select it in this separate block:

```powershell
$knownGood = (Read-Host 'Paste the full verified v1 controller-result.json path, without quotes').Trim()
Assert-V1Receipt "$knownGood" ''
$pair.known_good_receipt = $knownGood
$pair | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pairFile -Encoding utf8
```

**Only if no verified receipt exists:** confirm the runner is idle, old traffic is stopped and v1 remains compatible with retained database data. Run:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $env:BDI_RELEASE_SHA = $v1Sha
    $baselineDir = Join-Path $studyDir ('baseline-' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    $baselineDir | Set-Content (Join-Path $studyDir 'current-baseline.txt') -Encoding utf8
    py -3 -B bdi-cicd-framework/run_controller.py --baseline --artifacts-dir "$baselineDir"
    if ($LASTEXITCODE -ne 0) { throw 'Baseline incomplete; inspect its logs before any candidate run.' }
    $knownGood = Join-Path $baselineDir 'controller-result.json'
    Assert-V1Receipt "$knownGood" (Join-Path $baselineDir 'reset-check.json')
    $pair.known_good_receipt = $knownGood
    $pair | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pairFile -Encoding utf8
    $env:BDI_RELEASE_SHA = $v2Sha
}
```

**Expected:** achieved live v1 receipt for this repository/SHA with both environments verified; its path is saved in the pair. All console output is retained automatically. If interrupted after success but before saving the pointer, use the existing receipt block; do not redeploy merely to link it. **Next: Step 5.**

## Step 5. Prepare the first clean v1 starting state

**Open:** Controller PowerShell and GitHub Actions. Ensure no candidate/controller/remote deployment is still running. The same BDI reset procedure is used for **both** mechanisms as standardised preparation; its time is excluded from candidate runtime. It redeploys both app stacks and starts their databases, but retains database volumes. Do not run `down -v` or claim a pristine database snapshot.

```powershell
Assert-V1Receipt "$knownGood" ''
Invoke-StudyReset
```

**Expected:** `Both environments verified at v1`, `current-reset.txt`, reset result/console/journal and `reset-check.json`. Both `/checkout` pages at ports 3001/3000 display v1; readiness and deployment IDs were checked by the function. A reset failure stops the procedure. **Next: Step 6.**

## Step 6. Select the next scheduled trial

**Open:** Controller PowerShell. There is no manual scenario string to change: the frozen schedule chooses case, repetition and mechanism. After every completed Step 10, return here. Do not advance because a terminal command merely returned.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    $trial = $study.trials | Where-Object { -not (Test-Path (Join-Path $studyDir "trials/$($_.id)/record.json")) } | Select-Object -First 1
    if (-not $trial) {
        'Schedule fully finalised. Continue at Step 12, not another launch.'
    } else {
        $trialRoot = Join-Path $studyDir "trials/$($trial.id)"
        New-Item -ItemType Directory -Force -Path $trialRoot | Out-Null
        $trial.id | Set-Content (Join-Path $studyDir 'current-trial.txt') -Encoding utf8
        $trial | ConvertTo-Json | Set-Content (Join-Path $trialRoot 'planned-trial.json') -Encoding utf8
        $trial | Format-List
    }
}
```

**Expected:** one scheduled case and approach. Review the corresponding scenario row above for fault, suitability and expected result. **Next: Step 7.** If this folder already contains `started.json`, resume its collection/troubleshooting instead of launching again.

## Step 7. Run exactly one candidate trial

### 7.1. Automatic fault/traffic launch

**Open:** Controller PowerShell and the GitHub Actions page. Keep Docker/runner open. No MAS GUI or separate traffic terminal is needed. This block verifies the current reset again, marks it consumed, and runs the scheduled approach. BDI blocks until completion; conventional dispatch returns while GitHub continues.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (Test-Path (Join-Path $trialRoot 'started.json')) { throw 'This trial already started. Resume Step 8 or Step 11; never redispatch it.' }
    $resetDir = (Get-Content (Join-Path $studyDir 'current-reset.txt') -Raw).Trim()
    if (Test-Path (Join-Path $resetDir 'used-by-trial.txt')) { throw 'Reset already used. Complete Step 10 first.' }
    $resetResult = Join-Path $resetDir 'controller-result.json'
    $resetCheck = Join-Path $trialRoot 'reset-check.json'
    Assert-V1Receipt "$resetResult" "$resetCheck"
    $trial.id | Set-Content (Join-Path $resetDir 'used-by-trial.txt') -Encoding utf8
    [pscustomobject]@{ started_at=(Get-Date).ToUniversalTime().ToString('o'); reset_result=$resetResult; reset_check=$resetCheck } |
        ConvertTo-Json | Set-Content (Join-Path $trialRoot 'started.json') -Encoding utf8
    if ($trial.mechanism -eq 'bdi') {
        $resultDir = Join-Path $trialRoot 'bdi'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        py -3 -B bdi-cicd-framework/run_experiment.py --mechanism bdi --case $trial.case --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed $study.seed --artifacts-dir "$resultDir"
        "BDI exit code: $LASTEXITCODE. Inspect the stored outcome in Step 8; failure cases may correctly stop delivery."
    } elseif ($trial.mechanism -eq 'github-actions') {
        $resultDir = Join-Path $trialRoot 'native/artifacts/native-result/result'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        $payload = @{ release_sha=$v2Sha; scenario=$trial.case; baseline='false'; known_good_receipt=(Get-Content -LiteralPath $knownGood -Raw); confirm_compatible_rollback='true'; seed=[string]$study.seed } | ConvertTo-Json -Compress
        $payload | gh workflow run ci-cd.yml --repo $pair.repository --ref $workerRef --json
        if ($LASTEXITCODE -ne 0) { throw 'Dispatch failed/uncertain. Inspect Step 11; do not blindly dispatch again.' }
        gh run list --repo $pair.repository --workflow ci-cd.yml --limit 10 --json databaseId,displayTitle,headSha,createdAt,status,url
    } else { throw 'Unknown mechanism in schedule.' }
}
```

### 7.2. Conventional only: identify and watch the dispatched run

Skip this subsection for BDI. In the displayed GitHub list/web page, choose the run created just after this trial's `started_at`, with the frozen worker SHA and title `conventional-<case>-<v2 SHA>`. Do not assume the latest run is yours. Selecting a remote run ID is the one manual correlation step in this route.

**Manual input only:**

```powershell
$runId = (Read-Host 'Paste this conventional trial GitHub run ID').Trim()
```

**Then watch and collect automatically:**

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($runId -notmatch '^\d+$') { throw 'Run ID must contain only digits.' }
    $metadataText = gh run view $runId --repo $pair.repository --json databaseId,displayTitle,headSha,createdAt,status,workflowName,url
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect selected run.' }
    $remote = $metadataText | ConvertFrom-Json
    $start = Get-Content (Join-Path $trialRoot 'started.json') -Raw | ConvertFrom-Json
    if ($remote.headSha -ne $workerSha -or $remote.displayTitle -ne "conventional-$($trial.case)-$v2Sha" -or $remote.workflowName -ne 'Conventional Payment CI/CD' -or [DateTimeOffset]::Parse($remote.createdAt) -lt [DateTimeOffset]::Parse($start.started_at).AddSeconds(-5)) { throw 'Run does not match this trial. Recheck its ID.' }
    $runId | Set-Content (Join-Path $trialRoot 'github-run-id.txt') -Encoding utf8
    gh run watch $runId --repo $pair.repository
    $status = gh run view $runId --repo $pair.repository --json status --jq .status
    if ($LASTEXITCODE -ne 0 -or $status -ne 'completed') { throw 'Remote work is not known terminal. Use Step 11.' }
    $nativeDir = Join-Path $trialRoot 'native'
    py -3 experiments/collect.py --repo $pair.repository --run-id $runId --output "$nativeDir"
    $collectionExit = $LASTEXITCODE
    $resultDir = Join-Path $nativeDir 'artifacts/native-result/result'
    $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
    "Collection exit: $collectionExit. Keep incomplete evidence and inspect collection.json."
}
```

**Traffic evidence:** plans now declare `traffic_targets` for both environments. Healthy/background traffic is checked for each gate actually reached. An early build/test failure needs no deployment traffic. Stopped-candidate cases use staging traffic and separate production repair probes. Metrics validate profile, seed, deployment identity and release SHA for reached gates; inspect `traffic_by_entity` and its validation issues. `BDI_STAGE` log lines do not trigger traffic or count as retries. Traffic follows correlated deployment-pause and completion events.

**Launcher problems:** BDI saves `<campaign>-experiment/launch-status.json` and `traffic-staging-console.log` / `traffic-production-console.log` (only clients configured for that scenario). A missing controller result means incomplete evidence, not a successful or safely stopped deployment. Follow Step 11 before another dispatch. Native gates save `traffic-console.log` in their uploaded health artifacts.

**Expected:** the conventional run can be red for a correct stop/rollback. Automatic artifacts contain receipts, metrics, common events, job logs and traffic. For BDI, expected agent traces include `diagnose_candidate`, `restart_candidate`, `verify_repair`, `resume_candidate` for successful repair; failed repair leads to recovery while the v2 goal stays unmet. A green job or successful restart alone is not delivery. **Next: Step 8 for either approach.**

## Step 8. Save and inspect evidence before changing the environment

### 8.1. Reload this trial and inspect automatic files

This also works after reopening PowerShell once Steps 3 and 4.2 have restored the session.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $trialId = (Get-Content (Join-Path $studyDir 'current-trial.txt') -Raw).Trim()
    $trial = $study.trials | Where-Object id -eq $trialId
    $trialRoot = Join-Path $studyDir "trials/$trialId"
    $resultDir = (Get-Content (Join-Path $trialRoot 'result-path.txt') -Raw).Trim()
    if (Test-Path (Join-Path $resultDir 'controller-result.json')) {
        $result = Get-Content (Join-Path $resultDir 'controller-result.json') -Raw | ConvertFrom-Json
        $result | Select-Object mode,outcome,recovery_outcome,release_sha,known_good_sha | Format-List
        $result.executions; $result.telemetry; $result.verified_releases
    } else { 'Result missing: retain this incomplete trial; inspect Step 11.' }
    if (Test-Path (Join-Path $resultDir 'experiment-metrics.json')) { Get-Content (Join-Path $resultDir 'experiment-metrics.json') -Raw }
    if (Test-Path (Join-Path $resultDir 'experiment-events.jsonl')) {
        Get-Content (Join-Path $resultDir 'experiment-events.jsonl') | Select-String 'action_started|action_finished|diagnosis_|repair_|observation|health_accepted|recovery_started|campaign_finished'
    }
}
```

| Evidence | BDI location inside this trial | Conventional location inside this trial |
|---|---|---|
| Result / metrics / common event timeline | `bdi/` | `native/artifacts/native-result/result/` |
| Agent mind/decision text | `bdi/controller-console.log`, `controller-journal.jsonl` | Not an agent; use GitHub logs and gate event timeline |
| Frozen plan/config | `bdi-experiment/plan.json`, snapshots in `bdi/` | `native/artifacts/native-prepare/`, and `result-experiment/plan.json` |
| Traffic requests/transitions | `bdi-traffic*/` siblings | `native/artifacts/native-staging/`, `native/artifacts/native-production/` |
| Repair evidence | `bdi/operation-<UUID>/receipt.json` | `native/artifacts/native-production/health/diagnose-receipt.json`, `restart-receipt.json` |
| Complete remote job logs | Step 8.2 below | Already collected: `native/github-run.log`, `github-run.json` |
| Reset evidence | Path in `started.json` plus this trial's `reset-check.json` | Same |

For restart, check stopped matching container + ready database, one repair, same deployment identity after restart, probes, fresh samples and final v2 verification. For persistent errors, inspect real fault requests and observations; merely enabling fault mode is insufficient. For execution faults, inspect the failed worker step and blocked downstream jobs. **Do not exclude an unexpected but well-evidenced outcome just because it differs from the scenario table.**

### 8.2. BDI only: download acknowledged GitHub logs

Skip for conventional. This is read-only remote collection and includes diagnostic/restart jobs. All logs go in a fresh folder; failures are retained explicitly.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $journalPath = Join-Path $resultDir 'controller-journal.jsonl'
    $remoteComplete = $true
    $remoteDir = Join-Path $trialRoot ('github-evidence-' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    New-Item -ItemType Directory -Path $remoteDir | Out-Null
    if (-not (Test-Path $journalPath)) { $remoteComplete = $false } else {
        $journal = Get-Content $journalPath | ForEach-Object { $_ | ConvertFrom-Json }
        $ids = @($journal | Where-Object { $_.github_run_id } | ForEach-Object { $_.github_run_id } | Sort-Object -Unique)
        if ($ids.Count -eq 0) { $remoteComplete = $false }
        foreach ($id in $ids) {
            $text = gh run view $id --repo $pair.repository --log
            if ($LASTEXITCODE -ne 0) { $remoteComplete = $false }
            $text | Set-Content (Join-Path $remoteDir "$id.log") -Encoding utf8
            $text = gh run view $id --repo $pair.repository --json databaseId,headSha,status,conclusion,url,jobs
            if ($LASTEXITCODE -ne 0) { $remoteComplete = $false }
            $text | Set-Content (Join-Path $remoteDir "$id.json") -Encoding utf8
        }
    }
    [pscustomobject]@{ complete=$remoteComplete; directory=$remoteDir } | ConvertTo-Json | Set-Content (Join-Path $trialRoot 'remote-collection.json') -Encoding utf8
    "Remote collection complete: $remoteComplete"
}
```

### 8.3. Capture final live identity/readiness

Before reset, run this for **both approaches**, even failed trials. It catches endpoint failures and records them; it does not label an unreachable service healthy.

```powershell
. {
    $observed = @{}
    foreach ($entity in @('staging','production')) {
        $port = if ($entity -eq 'staging') { 3001 } else { 3000 }
        $item = @{ observed_at=(Get-Date).ToUniversalTime().ToString('o'); ready=$false }
        try { $item.health = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 10 } catch { $item.health_error = $_.Exception.Message }
        try { $null = Invoke-RestMethod "http://127.0.0.1:$port/ready" -TimeoutSec 10; $item.ready=$true } catch { $item.ready_error = $_.Exception.Message }
        $observed[$entity]=$item
    }
    $observed | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $trialRoot 'final-state.json') -Encoding utf8
    Get-Content (Join-Path $trialRoot 'final-state.json') -Raw
}
```

**Manual evidence only if needed:** save a screenshot as `checkout-final.png` in `$trialRoot`; optionally save an agent-mind screenshot only if you deliberately used a GUI route outside this matched schedule. Terminal agent text is already automatic. Keep operator/approval notes; do not manually recreate missing JSON or rerun to fabricate an earlier log. **Next: Step 9.**

## Step 9. Review and finalise the trial ledger

**Open:** `$trialRoot`, its raw evidence, and GitHub logs. Human review is needed to confirm the actual fault and interpret safety; the evaluator does not infer this from the case name.

Use `verified_candidate` only when final production identity matches the accepted v2 receipt and live readiness. Use `verified_baseline` when final production matches the reset v1 identity (pre-production failure) or the successfully executed/health-accepted rollback identity. Rollback identity is in `executions.rollback.executionId` (or the journal), not necessarily `verified_releases`. Use `unsafe` for demonstrated unsafe final state; use `unverified` when evidence is insufficient. Report staging containment separately in notes; a safe production v1 does not imply staging is healthy.

**Manual answers — separate block:** enter `yes` only after reviewing evidence; for healthy, confirm normal traffic/gates rather than a fault. Count interventions **during candidate execution** (for example approvals, corrective commands), excluding standard baseline/reset/collection. If the count is unknown, leave it blank.

```powershell
$faultReview = (Read-Host 'Fault exposure (or healthy traffic) confirmed from raw evidence? yes/no').Trim()
$safety = (Read-Host 'Production safety: verified_candidate / verified_baseline / unsafe / unverified').Trim()
$interventionText = (Read-Host 'Number of human interventions during this trial; blank if unknown').Trim()
$notes = Read-Host 'Notes: approvals, unexpected outcomes, staging state, interruptions or exclusions'
```

**Save without overwriting a previous finalisation:**

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($faultReview -notin @('yes','no')) { throw 'Answer yes or no.' }
    if ($safety -notin @('verified_candidate','verified_baseline','unsafe','unverified')) { throw 'Choose one documented safety value.' }
    $interventions = $null
    if ($interventionText) {
        if ($interventionText -notmatch '^\d+$') { throw 'Intervention count must be nonnegative or blank.' }
        $interventions = [int]$interventionText
    }
    $recordPath = Join-Path $trialRoot 'record.json'
    if (Test-Path $recordPath) { throw 'Already finalised. Preserve the original; document corrections separately.' }
    $start = Get-Content (Join-Path $trialRoot 'started.json') -Raw | ConvertFrom-Json
    $complete = $false
    if ($trial.mechanism -eq 'github-actions' -and (Test-Path (Join-Path $trialRoot 'native/collection.json'))) {
        $complete = (Get-Content (Join-Path $trialRoot 'native/collection.json') -Raw | ConvertFrom-Json).complete_download
    } elseif ($trial.mechanism -eq 'bdi' -and (Test-Path (Join-Path $trialRoot 'remote-collection.json'))) {
        $complete = (Get-Content (Join-Path $trialRoot 'remote-collection.json') -Raw | ConvertFrom-Json).complete
    }
    [pscustomobject]@{ result_dir=$resultDir; reset_result=$start.reset_result; reset_check=$start.reset_check; evidence_complete=[bool]$complete; fault_reviewed=($faultReview -eq 'yes'); safety=$safety; human_interventions=$interventions; notes=$notes; finalised_at=(Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $recordPath -Encoding utf8
    Get-Content -LiteralPath $recordPath -Raw
}
```

**Expected:** failed/unexpected trials are retained just like successes. Missing metrics or collection errors will be reported as exclusions/incomplete evidence, not converted into success. Finalisation does not mean remote work has stopped; resolve any uncertainty in Step 11 before resetting. **Next: Step 10.**

## Step 10. Clean up and restore v1 for the next trial

**Open:** Controller PowerShell and GitHub Actions. Confirm the candidate/repair/rollback remote runs are terminal; close only completed MAS windows if any. The C1 wrapper/gates normally stop their traffic clients automatically. Stop only a leftover traffic process that you started for this trial; do not stop the runner or Docker between trials.

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO -ErrorAction SilentlyContinue
Invoke-StudyReset
```

**Expected:** both environments redeployed and verified at v1 with new IDs; a fresh reset folder and pointer, original known-good receipt retained, completed trial evidence untouched. This reset is required even when production already appears v1. After the last trial it leaves a verified baseline deployed.

**Next:** Step 6 selects the paired approach or next case automatically. When no unfinalised trial remains, proceed to Step 12. Do not run two candidate trials from one reset. Do not delete database volumes or results to “clean up.”

## Step 11. Interrupted runs and troubleshooting (only when needed)

| Symptom | Required action before continuing |
|---|---|
| Terminal closed; variables lost | Repeat Step 3 and 4.2. Read `current-trial.txt`, `started.json`, `result-path.txt` and, for native, `github-run-id.txt`. Resume collection, not dispatch. |
| BDI remote execution unknown/interrupted | Close the old local controller if still running, then run the reconciliation block below. Inspect every acknowledged remote run; do not reset while one may still be executing. |
| Conventional cancelled/runner lost | Inspect GitHub run/jobs and Docker state. Wait for known terminal execution; preserve incomplete collection. Do not use “Re-run failed jobs” as a new experimental trial. |
| No `result-path.txt` after a failed conventional dispatch | Save the expected path `Join-Path $trialRoot 'native/artifacts/native-result/result'` to that pointer; inspect whether a remote run exists before any retry. If none can be established, finalise as incomplete with notes; no fabricated result. |
| Collection failed | Keep original folder/error record. Download again to a **new** folder for inspection; record the correction explicitly. Never count a second download as another trial. An unrepaired incomplete record stays excluded. |
| Old worker/missing operation or input | Publish a correct control revision in Step 2; start a new study if its worker/policy changes. Old tags do not gain local edits. |
| Runner queued / environment approval | Keep the same run. Check runner online/labels/permissions and approve in GitHub if configured. Record waiting/intervention. |
| Security audit blocks healthy case | Preserve the finding as a prerequisite/uncontrolled failure. Do not disable the gate to force delivery; any dependency fix creates a new reviewed app/control series. |
| Missing p95/telemetry despite ready endpoint | Inspect successful payment probes/traffic, scrape/export health, identity and freshness. Missing data is not zero errors or proven health. |
| Restart completes but goal fails | Check post-repair identity/samples and total budget, including queue waits. `executed` is not equivalent to `candidate_repaired`. |
| No production traffic folder for a stopped-candidate case | Expected: use repair receipt/probes and subsequent correlated observations; staging traffic still exists. |
| Reset fails | Preserve it; settle remote state, fix the cause, then invoke a new reset. Never mark the candidate's start state verified by hand. |

**BDI reconciliation (does not resume/dispatch):**

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Inspect its saved result and GitHub status; an unresolved result remains a stop condition. Do not delete pending-state files or locks to bypass it. Once settled, collect/finalise the interrupted trial, then reset. An incomplete run remains part of the attempted-trial record. Do not silently replace it with a success; any additional repetitions belong in an explicitly amended/new study plan.

## Step 12. Evaluate and report the paired results

**Open:** Controller PowerShell after every trial has been finalised and the final reset has passed. You may also run this read-only evaluation mid-study to see pending entries. It never dispatches, injects faults or changes evidence.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-study.txt -Raw).Trim()
    $reportDir = [System.IO.Path]::GetFullPath('experiments/reports/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    py -3 experiments/evaluate_study.py --study "$studyDir" --output "$reportDir"
    if ($LASTEXITCODE -ne 0) { throw 'Fix the reported ledger/format error without altering original evidence.' }
    Get-Content (Join-Path $reportDir 'summary.json') -Raw
    "Report: $reportDir"
}
```

| Output | What to read |
|---|---|
| `trials.csv` | One row for **every scheduled trial**, including unfinalised/missing/excluded rows and reasons; original outcomes, safety annotations and intervention counts |
| `pairs.csv` | One case/repetition pair; `matched=true` requires eligible BDI + conventional evidence with the same `protocol_key`; differences are **BDI minus conventional** |
| `groups.csv` | Per case/approach counts, delivery/restoration/repair rates with denominators, verified-safety rate, unknown-safety count, mean/median costs and number of available measurements |
| `summary.json` | Planned/recorded/eligible counts, planned/matched pairs, group results and interpretation limits |

The evaluator checks scheduled case/mechanism/seed, candidate/baseline/repository/worker, actual reset receipt plus saved live reset identity, artifact completeness, fault-review attestation, duplicate result evidence, reused resets, and pairing keys. Claims of a verified safe candidate/baseline must also match the captured final production readiness and deployment identity. It preserves unexpected but valid outcomes. These checks do not replace review of the fault or prove equality of database/queue state. Bootstrap/reset folders and old studies are outside the candidate ledger; there is no broad scan mixing them with measured trials.

### Outcome definitions and interpretation

| Dimension | Definition and caution |
|---|---|
| Delivery reliability | Candidate delivered / eligible trials, reported separately **per scenario**. A deterministic failure should stop; low delivery in that scenario is not an orchestration defect. |
| Safe final deployment | Annotated verified-candidate or verified-baseline / trials with assessed production safety; report `unsafe` and `unverified` separately. Do not treat missing evidence as safe. |
| Candidate repair | Verified v2 after executed restart / trials that attempted repair; distinguish from passive reobservation and job retries. |
| Restoration | Verified v1 restoration / trials that attempted rollback; never count this as candidate delivery. |
| Execution cost | Whole-campaign runtime, retries, restart attempts and explicit human interventions; report means/medians, sample counts and raw timestamps. Missing intervention counts remain unknown. |
| Recovery time | `recovery_seconds`: first adverse production event to accepted rollback; `candidate_repair_seconds`: restart request to accepted candidate health. These are different recovery paths and clocks. |
| Protocol expectation | `protocol_expectation_met` compares the outcome with the stated expected response. It is not independent correctness evidence and must not determine exclusions. |

Use **matched pairs** for comparative claims; marginal group averages can contain unmatched eligible trials. In `pairs.csv`, positive delivery difference favors BDI delivery; negative runtime difference means BDI was faster. Recovery-time differences are meaningful only when both values exist. Do not replace missing times with zero. Report ties, BDI wins and conventional wins, and review the decision trace for each difference.

Conclude where both stopped correctly, where each recovered, whether any delivery/safety difference occurred, and what overhead BDI introduced. If outcomes match, say so and discuss traceability/configuration separately. Small descriptive samples do not prove statistically significant superiority. For a publication, predefine the analysis/sample-size plan and use uncertainty intervals/paired methods appropriate to the resulting binary and timing data; this script deliberately does not manufacture p-values from a tiny pilot.

**Final archive:** retain the complete `$studyDir`, the reports, selected pair JSON/pointer, the original known-good receipt directory (possibly outside this study), and the frozen control/app revision identifiers. These result folders are Git-ignored: copy the bundle to your chosen backup location. Leave verified v1 running or, only after recording completion and when no other use depends on it, stop the experiment stacks deliberately. Do not remove volumes by default.

## Who can execute this, and what is triggered?

An assistant with access to this workspace/terminal, authenticated GitHub CLI, reachable deployment/telemetry endpoints and an online runner can perform the commands, monitor runs, collect evidence and evaluate results. The operator must first provide the functioning Docker/runner environment and published reviewed revisions, complete interactive authentication/registration, and handle any repository environment approvals requiring their account. Explicitly authorise live dispatch, fault injection, v1 resets and compatible rollback before asking the assistant to execute the study. Keeping the session/machine available is necessary for BDI orchestration; permission or connectivity restrictions may still require operator action. This guide's creation/evaluator checks do not constitute live execution.

**Conventional trigger:** `.github/workflows/ci-cd.yml` has **`workflow_dispatch` only**. Start it using `gh workflow run ci-cd.yml ...` as above, or GitHub Actions **Run workflow** with the same inputs. It does not deploy on push. `.github/workflows/validate-controller.yml` is the separate push/PR validation workflow. BDI is started by the local Python command; its agent dispatches selected shared-worker jobs. Do not launch a conventional workflow alongside a BDI trial.
