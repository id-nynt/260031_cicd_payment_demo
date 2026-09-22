# RQ1 compact study: five scenarios, conventional and BDI CI/CD

## Scope and starting point

Run only the five cases below to examine **normal delivery, safe stopping, waiting for recovery, rollback and candidate repair**. Both approaches use the same app v1/v2 SHAs, worker revision, jobs, telemetry, faults and recovery capabilities. BDI pursues `master_goal`; conventional execution uses the GitHub Actions workflow. A repaired and verified v2 can achieve delivery. Restoring v1 is successful restoration, **not** v2 delivery.

This guide is for your existing setup and release pair. Open **Docker Desktop**, the existing **Linux deployment runner**, **Controller PowerShell** at the repository root, and **GitHub Actions**. Keep the machine awake. If tools or the labelled v1/v2 pair are missing, complete [full-guide Steps 1-2](06_PAIRED_EXPERIMENTS_END_TO_END.md) first, then return here. Do not also run the full study schedule.

| Compact order | Original experiment # | Case | Purpose and evidence to inspect |
|---|---|---|---|
| 1 | 1 | `healthy` | Baseline/control: v2 delivered; both health gates accepted; normal payment traffic |
| 2 | 3 | `test-failure` | Deterministic test failure: safe stop, no production deployment, reset v1 remains |
| 3 | 8 | `production-temporary` | 75 seconds of mixed request errors, then normal traffic: reobserve, recover and continue v2 |
| 4 | 9 | `production-persistent` | Sustained request errors: bounded observations, then verified rollback to v1 |
| 5 | 7 | `candidate-stopped` | Matching production app stopped after deployment succeeds: diagnose, one restart, fresh verification, continue v2 |

These are expected responses to inspect, not guaranteed results. Preserve unexpected outcomes. Both mechanisms can recover; report ties as well as differences. This compact subset does not establish resilience to every possible CI/CD failure.

**Default workload:** one repetition = **10 measured candidate runs**, plus v1 resets and a baseline only if no receipt exists. This is a small descriptive study/pilot, not statistical proof of superiority. If time permits, choose more repetitions **before creating the schedule**. Three repetitions mean 30 candidate runs. Each case runs BDI then conventional in odd repetitions; order reverses in even repetitions. Never run the two approaches concurrently.

**Do not shorten observation/repair budgets to save time.** Reduce repetitions or cases only through an explicitly declared new study. Normal verification uses two consecutive healthy samples; repair retains its 120-second probe window and 300-second decision budget. Runner queues and approval waits can add substantial runtime.

| Your current state | Start here |
|---|---|
| Existing setup/pair; support changes not yet published | Step 1 |
| Current control revision already published and selected | Step 2 |
| Reopening the same compact study | Step 2, then **3.2 only**; resume Step 7 if a trial already started |
| One candidate run finished | Steps 7-9, then Step 5 |
| All 10 scheduled runs finalised | Step 11 |

Manual choices are separate from execution blocks. Paste complete `. { ... }` blocks. Stop after a red error; do not continue with stale variables.

## Step 1. Publish the reviewed control update once

**Open:** your editor/Source Control and GitHub. Review and commit intended changes, including the refactored agent, supporting scripts and generated manifest. Publish/register the reviewed workflows on the default branch through your normal process. **Do not blindly stage all files.** Keep existing immutable v1/v2 app SHAs.

Before publication, run these read-only checks from the repository root:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
    py -3 -B bdi-cicd-framework/run_controller.py --validate-only
    if ($LASTEXITCODE -ne 0) { throw 'Review inputs and explicitly regenerate before publishing.' }
    py -3 -B ci-cd-conventional/configuration.py --check-bdi-parity
    if ($LASTEXITCODE -ne 0) { throw 'Resolve policy/configuration parity before publishing.' }
    py -3 -B ci-cd-conventional/sync_workflows.py --check
    if ($LASTEXITCODE -ne 0) { throw 'Review and synchronise workflow copies before publishing.' }
}
```

If the current pair already selects this exact published control revision, skip the block below. Otherwise run it from the repository root **after review and commit**. It checks the app is unchanged, creates a fresh control tag and selects a new pair record while retaining the original baseline receipt.

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

**Expected:** new published control tag; old tags, app SHAs and receipts preserved. Proceed to Step 2. Conventional deployment is triggered by `workflow_dispatch`, not by this push.

## Step 2. Load the session and reset helpers

**Open:** Controller PowerShell. Run this at the start of each session. It loads `current-pair.txt`, checks publication against local control files, validates configuration parity, and defines the receipt/reset helpers. It does not deploy yet.

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
    if ($LASTEXITCODE -ne 0) { throw 'Control revision mismatch. Fetch missing commits or complete Step 1 with a new control tag.' }
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

**Expected:** repository, worker, v1 and v2 identities are populated. Missing or stale control files must be resolved through Step 1 before launching. A blank baseline path is handled in Step 3.3.

## Step 3. Create or reload the five-case schedule

### 3.1. New compact study only

**Manual choice - run separately:** keep 1 for the shortest complete set. Do not rerun this subsection when resuming an existing study.

```powershell
$repetitions = 1
$seed = 42
```

**Then run unchanged:**

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($repetitions -lt 1 -or $repetitions -gt 100) { throw 'Choose an explicit repetition count from 1 to 100.' }
    $cases = @('healthy','test-failure','production-temporary','production-persistent','candidate-stopped')
    $catalog = Get-Content experiments/scenarios.json -Raw | ConvertFrom-Json
    if (@($cases | Where-Object { $_ -notin $catalog.PSObject.Properties.Name }).Count) { throw 'Catalog mismatch.' }
    $studyDir = [System.IO.Path]::GetFullPath('experiments/results/studies/compact-five-' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
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
    [pscustomobject]@{ schema_version=1; study_set='compact-five-v1'; pair_file=$pairFile; repository=$pair.repository; v1_sha=$v1Sha; v2_sha=$v2Sha; worker_sha=$workerSha; worker_ref=$workerRef; repetitions=$repetitions; seed=$seed; trials=$trials } |
        ConvertTo-Json -Depth 8 | Set-Content (Join-Path $studyDir 'study.json') -Encoding utf8
    $trials | Export-Csv (Join-Path $studyDir 'schedule.csv') -NoTypeInformation -Encoding utf8
    $studyDir | Set-Content experiments/results/current-compact-study.txt -Encoding utf8
    "Study: $studyDir ; candidate trials: $index"
}
```

**Expected:** `candidate trials: 10` for one repetition. Only the five selected cases are scheduled. The pointer is `experiments/results/current-compact-study.txt`; it does not replace the full study's pointer.

### 3.2. Reload the saved compact study

Run this now, and after reopening PowerShell following Step 2.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-compact-study.txt -Raw).Trim()
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    if ($study.repository -ne $pair.repository -or $study.v1_sha -ne $v1Sha -or $study.v2_sha -ne $v2Sha -or $study.worker_sha -ne $workerSha) { throw 'Current pair/control differs from this study. Restore the selection or create a new study.' }
    if ($study.study_set -ne 'compact-five-v1') { throw 'Select this compact study, not the full study.' }
    $study.trials | Format-Table id,case,repetition,mechanism
}
```

### 3.3. Reuse or establish the verified v1 baseline

If `$knownGood` already contains your verified receipt, run this check and continue to Step 4 if it succeeds:

```powershell
Assert-V1Receipt "$knownGood" ''
```

**Only if an existing receipt was not linked:** select its full path in this separate block. This does not deploy.

```powershell
$knownGood = (Read-Host 'Paste the full verified v1 controller-result.json path, without quotes').Trim()
Assert-V1Receipt "$knownGood" ''
$pair.known_good_receipt = $knownGood
$pair | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pairFile -Encoding utf8
```

**Only if no verified receipt exists:** ensure the runner is idle and rollback is compatible with retained database data, then run this once:

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

**Expected:** the selected pair links an achieved live v1 receipt for both environments. Baseline work is excluded from measured candidate runs. Continue to Step 4.

## Step 4. Restore the first clean v1 starting state

**Open:** Controller PowerShell and GitHub Actions. Settle any previous remote work and stop old traffic first. The same BDI reset routine prepares **both** approaches, outside measured runtime. It retains database volumes; do not claim an empty database or run `down -v`.

```powershell
Assert-V1Receipt "$knownGood" ''
Invoke-StudyReset
```

**Expected:** both environments verified at v1, with a new reset receipt and live identity check. Do not proceed after a failed reset.

## Step 5. Select the next scheduled case and approach

Run this after Step 4, and again after each Step 9. The schedule selects the case automatically; you do not edit fault strings between scenarios.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    $trial = $study.trials | Where-Object { -not (Test-Path (Join-Path $studyDir "trials/$($_.id)/record.json")) } | Select-Object -First 1
    if (-not $trial) {
        'Schedule fully finalised. Continue at Step 11, not another launch.'
    } else {
        $trialRoot = Join-Path $studyDir "trials/$($trial.id)"
        New-Item -ItemType Directory -Force -Path $trialRoot | Out-Null
        $trial.id | Set-Content (Join-Path $studyDir 'current-trial.txt') -Encoding utf8
        $trial | ConvertTo-Json | Set-Content (Join-Path $trialRoot 'planned-trial.json') -Encoding utf8
        $trial | Format-List
    }
}
```

**Expected:** one trial ID, case and mechanism. If `started.json` already exists, resume Step 7/10 rather than dispatching it again. When the schedule is fully finalised, go to Step 11.

## Step 6. Execute exactly one trial

### 6.1. Dispatch the selected approach

**Open:** Controller PowerShell and GitHub Actions; keep Docker and the existing runner active. The script rechecks v1, consumes this reset, and launches one candidate trial. Fault injection and traffic are automatic. **Do not stop containers manually or add another traffic client.**

BDI runs locally until completion. Conventional execution dispatches the GitHub workflow and returns; use 6.2 to watch it.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (Test-Path (Join-Path $trialRoot 'started.json')) { throw 'This trial already started. Resume Step 7 or Step 10; never redispatch it.' }
    $resetDir = (Get-Content (Join-Path $studyDir 'current-reset.txt') -Raw).Trim()
    if (Test-Path (Join-Path $resetDir 'used-by-trial.txt')) { throw 'Reset already used. Complete Step 9 first.' }
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
        "BDI exit code: $LASTEXITCODE. Inspect the stored outcome in Step 7; failure cases may correctly stop delivery."
    } elseif ($trial.mechanism -eq 'github-actions') {
        $resultDir = Join-Path $trialRoot 'native/artifacts/native-result/result'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        $payload = @{ release_sha=$v2Sha; scenario=$trial.case; baseline='false'; known_good_receipt=(Get-Content -LiteralPath $knownGood -Raw); confirm_compatible_rollback='true'; seed=[string]$study.seed } | ConvertTo-Json -Compress
        $payload | gh workflow run ci-cd.yml --repo $pair.repository --ref $workerRef --json
        if ($LASTEXITCODE -ne 0) { throw 'Dispatch failed/uncertain. Inspect Step 10; do not blindly dispatch again.' }
        gh run list --repo $pair.repository --workflow ci-cd.yml --limit 10 --json databaseId,displayTitle,headSha,createdAt,status,url
    } else { throw 'Unknown mechanism in schedule.' }
}
```

### 6.2. Conventional only: select its run, wait and collect

Skip this subsection for BDI. Select the GitHub run matching this trial's creation time, case, worker SHA and v2 SHA; do not blindly select the latest run.

**Manual input - separate block:**

```powershell
$runId = (Read-Host 'Paste this conventional trial GitHub run ID').Trim()
```

**Then run unchanged:**

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
    if ($LASTEXITCODE -ne 0 -or $status -ne 'completed') { throw 'Remote work is not known terminal. Use Step 10.' }
    $nativeDir = Join-Path $trialRoot 'native'
    py -3 experiments/collect.py --repo $pair.repository --run-id $runId --output "$nativeDir"
    $collectionExit = $LASTEXITCODE
    $resultDir = Join-Path $nativeDir 'artifacts/native-result/result'
    $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
    "Collection exit: $collectionExit. Keep incomplete evidence and inspect collection.json."
}
```

**Expected:** a terminal run and saved evidence. Red can mean a correct safe stop or rollback. Check results before concluding failure/success.

Healthy/background traffic runs for each reached staging/production gate. `test-failure` stops before deployment traffic. `candidate-stopped` uses normal staging traffic and the shared repair worker's production probes instead of the normal production traffic client. Stage markers (`BDI_STAGE`) do not trigger traffic or count as retries.

## Step 7. Save and inspect results before reset

### 7.1. Reload the current trial and inspect its files

This block also restores trial variables after reopening PowerShell and completing Steps 2 and 3.2.

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
    } else { 'Result missing: retain this incomplete trial; inspect Step 10.' }
    if (Test-Path (Join-Path $resultDir 'experiment-metrics.json')) { Get-Content (Join-Path $resultDir 'experiment-metrics.json') -Raw }
    if (Test-Path (Join-Path $resultDir 'experiment-events.jsonl')) {
        Get-Content (Join-Path $resultDir 'experiment-events.jsonl') | Select-String 'action_started|action_finished|diagnosis_|repair_|observation|health_accepted|recovery_started|campaign_finished'
    }
}
```

| What to inspect | BDI, inside this trial | Conventional, inside this trial |
|---|---|---|
| Result, metrics and common events | `bdi/` | `native/artifacts/native-result/result/` |
| Agent decisions / execution log | `bdi/controller-console.log`, `controller-journal.jsonl` | `native/github-run.log`, gate events |
| Traffic | `bdi-traffic*/`; client logs in `bdi-experiment/` | `native/artifacts/native-*-health/`; summaries beside `result/` |
| Diagnosis/restart evidence | `bdi/operation-<UUID>/receipt.json` | `native/artifacts/native-production-health/production/` receipts |
| Launch failure | `bdi-experiment/launch-status.json` | GitHub run/job and collection status |

Inspect `traffic_by_entity` for required traffic and profile/seed/deployment/release mismatches. Missing evidence is not success. A restart returning `executed` is not verified delivery. Use the five-case table above to inspect the actual fault and response; retain unexpected but well-evidenced outcomes.

### 7.2. BDI only: download acknowledged GitHub job logs

Skip for conventional: its logs were collected in 6.2. The following reads GitHub without dispatching. Missing logs remain an explicit collection problem.

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

### 7.3. Both approaches: capture the final live state

Run before reset, including after failed trials. Endpoint failures are retained as errors, not labelled healthy.

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

Console logs, result JSON and traffic logs are automatic. Screenshots are optional; if wanted, save them in `$trialRoot`. Do not manually recreate missing JSON or rerun to manufacture evidence for an earlier trial.

## Step 8. Finalise this trial's record

**Open:** `$trialRoot`, its raw evidence and GitHub logs. This brief manual review confirms actual fault exposure and production safety.

- `verified_candidate`: live ready production matches the accepted v2 execution ID.
- `verified_baseline`: live ready production matches reset v1 (test failure) or the successfully verified rollback ID (persistent degradation).
- `unsafe`: evidence demonstrates an unsafe final state.
- `unverified`: evidence cannot establish safety.

Confirm normal traffic/gates for `healthy`; for other cases confirm the actual injected fault. Count interventions during candidate execution, excluding routine setup/reset/collection; leave the count blank if unknown. Describe staging state and unexpected outcomes in notes.

**Manual answers - separate block:**

```powershell
$faultReview = (Read-Host 'Fault exposure (or healthy traffic) confirmed from raw evidence? yes/no').Trim()
$safety = (Read-Host 'Production safety: verified_candidate / verified_baseline / unsafe / unverified').Trim()
$interventionText = (Read-Host 'Number of human interventions during this trial; blank if unknown').Trim()
$notes = Read-Host 'Notes: approvals, unexpected outcomes, staging state, interruptions or exclusions'
```

**Save the record without overwriting an earlier finalisation:**

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

**Expected:** `record.json` saved even for failures/incomplete trials. This does not prove remote work has stopped. Resolve uncertainty through Step 10 before resetting.

## Step 9. Clean up and restore v1

Confirm candidate, diagnostic, repair and rollback jobs are terminal. Normal traffic clients stop automatically; stop only a leftover client you started for this trial. Keep Docker and the runner running.

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO -ErrorAction SilentlyContinue
Invoke-StudyReset
```

**Expected:** new verified v1 reset in both environments; completed evidence is unchanged. This reset is also required when production already appears v1, and after the final trial. Do not delete database volumes or result folders.

**Next:** return to Step 5 for the paired approach or next case. When all scheduled trials are finalised and the last reset passed, continue to Step 11. Never reuse one reset for two candidate trials.

## Step 10. Resume or troubleshoot only when needed

| Situation | Action |
|---|---|
| Terminal reopened | Step 2, then 3.2 and 7.1; use saved pointers rather than guessing paths |
| Trial already has `started.json` | Resume collection/review; never dispatch it again as though it were new |
| BDI interrupted or remote execution unknown | Stop the old local controller if still running, then use the reconciliation command below; inspect GitHub before resetting |
| Conventional cancelled or runner lost | Inspect all remote jobs and Docker state; preserve incomplete evidence; do not count GitHub `Re-run jobs` as another planned trial |
| Collection incomplete | Keep the failure record; download again into a fresh folder for inspection and document any correction; never count duplicate downloads as extra trials |
| Old control tag / file mismatch | Step 1, then start a new compact study if the control revision changed |
| Security gate blocks a healthy run | Preserve the finding; fix through a reviewed new app/control series rather than disabling the gate |
| Missing production traffic for `candidate-stopped` | Expected; inspect repair probes, identity and fresh observations; staging traffic remains required |
| Reset fails | Save the failure, settle remote state, fix the cause and create a new reset; never fabricate verification |

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Reconciliation reads remote status; it does not resume or dispatch. An unresolved outcome remains a stop condition. Do not delete locks/pending records to bypass it. Finish collecting and recording the interrupted trial, then reset. Document any amended schedule; do not silently replace an unsuccessful observation.

## Step 11. Evaluate the five-case study and archive it

**Open:** Controller PowerShell after finalisation and the final reset. The evaluator is read-only; it can also show pending trials mid-study.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-compact-study.txt -Raw).Trim()
    $reportDir = [System.IO.Path]::GetFullPath('experiments/reports/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    py -3 experiments/evaluate_study.py --study "$studyDir" --output "$reportDir"
    if ($LASTEXITCODE -ne 0) { throw 'Fix the reported ledger/format error without altering original evidence.' }
    Get-Content (Join-Path $reportDir 'summary.json') -Raw
    "Report: $reportDir"
}
```

| Output | Use |
|---|---|
| `trials.csv` | All scheduled trials, outcomes, safety, interventions and exclusion reasons |
| `pairs.csv` | Compare the same case/repetition; `matched=true` requires eligible evidence with equal protocol keys |
| `groups.csv` | Per-case/per-approach delivery, restoration and repair rates with denominators; runtime, retries, repair time and interventions |
| `summary.json` | Planned/recorded/eligible counts, matched pairs and interpretation limits |

For one complete eligible repetition, expect **10 recorded trials and 5 matched pairs**. Missing or excluded evidence reduces the matched count; retain and explain it. Pair differences are **BDI minus conventional**. Positive delivery difference favours BDI; negative runtime difference means BDI was faster. Do not turn missing times into zero.

Report each case separately:

1. **Healthy:** did both deliver v2, and what orchestration overhead occurred?
2. **Test failure:** did both stop safely and retain v1? Non-delivery is expected here.
3. **Temporary degradation:** did each wait for recovery and deliver v2 without unnecessary restart/rollback?
4. **Persistent degradation:** did each restore verified v1? Restoration does not achieve v2 delivery.
5. **Stopped candidate:** did diagnosis, bounded restart and fresh verification deliver v2? Compare repair attempts/time and interventions.

`recovery_seconds` measures first adverse production event to accepted rollback. `candidate_repair_seconds` measures restart request to accepted candidate health. They are different paths; compare only like-for-like values. Use matched pairs for conclusions, report ties, and do not infer statistical superiority from one run per case. This set illustrates runtime decision-making; comparative benefit must come from the observed outcomes/costs.

**Archive:** back up the entire compact study directory, reports, selected pair JSON, original baseline receipt directory and frozen revision identifiers. Results are Git-ignored. Keep the final verified v1 deployed unless you deliberately stop the stacks after recording completion. The full study and its pointer remain separate.
