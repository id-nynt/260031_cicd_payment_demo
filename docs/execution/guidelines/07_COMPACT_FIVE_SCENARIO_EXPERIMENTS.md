# RQ1 compact experiments: six scenarios with BDI and conventional CI/CD

## Where to start

This guide offers a **focused follow-up (C5-C6, four runs)** or the full six-scenario study. The focused follow-up is the default for a completed earlier study. Use one Controller PowerShell window throughout. Every candidate run follows the same sequence:

**Choose one run in C -> D: save and record its evidence -> E: restore v1 -> return to C for the next run.**

| Your situation | Follow these steps |
|---|---|
| First experiment; tools or v1/v2 pair not ready | A1, then A2 if control publication is needed; B1-B4; C1 |
| Pair and control revision already published; creating your first compact study | B1; B2 **new study** branch; B3-B4; C1 |
| Compact study already created, but no candidate has run | B1; B2 **existing study** branch; B3-B4; C1 |
| Returning to the same study after closing PowerShell | B1; B2 **existing study** branch; B3. If a trial started, use F2 before any reset; otherwise B4 and the next C scenario |
| A candidate run just finished | D1-D4, then E; return to the next run in the same C scenario |
| All scheduled trials recorded and final reset passed | G: evaluate and back up |
| Old work is hanging and you want a fresh study | F3 first; then B1, B2 **new study**, B3-B4 |

**For your completed ten-trial study:** keep trials 001-008 and the excluded 009-010 as historical evidence. Do not restart everything. Follow **A2 -> B1 -> B2.1 (`focused`) -> B2.2 -> B3 -> B4 -> C5 -> C6 -> G1**. Complete **D then E after every individual run**. This creates four new trials under a new published control revision; it does not modify the old study. Reuse the existing app v1/v2 pair and compatible baseline receipt. The new C6 replaces the failed-restart case with rollback reconsideration. This document keeps its filename for stable links.

**Open and keep running:** Docker Desktop, the existing Linux deployment runner, Controller PowerShell at the repository root, and your repository's GitHub Actions page. Keep the machine awake. Do not run experiments concurrently.

**Copying commands:** copy complete code blocks, without the Markdown fences or terminal prompt. Paste every `. { ... }` block as a whole. Manual choices appear in separate blocks; no placeholder paths are embedded in execution blocks. After an unexpected error, stop and use F2 rather than continuing with old variables.

### MAS Console: viewing the agent during manual runs

Manual BDI candidates, v1 resets and first-baseline creation now open the **Jason MAS Console**. Open/select `controller_agent` to inspect its output and agent mind; the terminal also prints an agent-mind inspector URL you can open in a browser while the agent is running. Conventional candidates have no BDI agent window.

Wait for **`Campaign finished: outcome=...`** and the saved result message. Inspect the final agent state, then close the completed MAS Console so PowerShell can finish collection/verification and return to its prompt. Gradle waiting at 75% while the completed console remains open is normal. Do not close the window or press Ctrl+C while jobs are still active.

Console output and structured events remain saved automatically; GUI inspection is additional. Optional screenshots of beliefs/intentions can be saved in the current trial folder displayed in D1. Measured outcomes/times come from campaign events, not how long you leave the completed window open.

For unattended execution, append `-Headless` to **each** `Invoke-CompactCandidate` and `Invoke-StudyReset` call; omit `--gui` from the optional F1 baseline command. This keeps automatic logs without waiting for someone to close a window. The default manual commands below show the Console.

If functions were already loaded in your terminal, copy B3 again to replace the candidate function. To replace the reset function, copy just its complete `function Invoke-StudyReset { ... }` definition from B1, or reload B1 when no execution is active. Editing the Markdown alone does not update functions already in memory. An existing headless execution cannot be converted into a MAS Console run; use its printed inspector URL and allow it to finish.

### What the saved files mean

| Item | Meaning |
|---|---|
| Release pair | Immutable v1, candidate v2, published worker revision and baseline receipt |
| `experiments/results/release-pairs/current-pair.txt` | Selects the pair JSON; commands read and trim the path automatically |
| Study | One saved schedule plus all its trial/reset evidence |
| `experiments/results/current-compact-study.txt` | Selects the study folder; changing this file does **not** reset the application |
| Trial | One scenario executed by one approach; focused = four trials, full = twelve |
| Baseline receipt | Historical evidence of a verified v1 deployment; reused as the rollback reference |
| Reset receipt | Evidence of a fresh deployment of v1 to **both** environments before a candidate; used by only one trial |

Creating a study, loading helper functions and deploying v1 are different actions. **B4 and E actually reset the environments.** Merely completing B1-B3 does not.

## Experiment introduction
Run only the six cases below to examine **normal delivery, safe stopping, waiting for recovery, rollback and candidate repair**. Both approaches use the same app v1/v2 SHAs, worker revision, jobs, telemetry, faults and recovery capabilities. BDI pursues `master_goal`; conventional execution uses the GitHub Actions workflow. A repaired and verified v2 can achieve delivery. Restoring v1 is successful restoration, **not** v2 delivery.



| Compact order | Original experiment # | Case | Purpose and evidence to inspect |
|---|---|---|---|
| 1 | 1 | `healthy` | Baseline/control: v2 delivered; both health gates accepted; normal payment traffic |
| 2 | 3 | `test-failure` | Deterministic test failure: safe stop, no production deployment, reset v1 remains |
| 3 | 8 | `production-temporary` | 35 seconds of mixed request errors, then normal traffic: bounded reobservation through the 30-second metric window, then two healthy observations and continued v2 |
| 4 | 9 | `production-persistent` | Sustained request errors: bounded observations, then verified rollback to v1 |
| 5 | 7 | `candidate-stopped` | Matching production app stopped after deployment succeeds: diagnose, one restart, fresh verification, continue v2 |
| 6 | Additional | `rollback-reconsideration` | Errors persist until rollback is selected, then clear: fresh correlated rechecks cancel pending rollback and retain verified v2 |

These are expected responses to inspect, not guaranteed results. Preserve unexpected outcomes. Both mechanisms can recover; report ties as well as differences. This compact subset does not establish resilience to every possible CI/CD failure.

**Default workload:** `focused` runs C5 and C6 with both approaches: **four measured candidate runs**, plus v1 resets. Choose `full` for all six cases (twelve runs). One repetition is a descriptive pilot, not statistical proof of superiority. Choose repetitions before scheduling. Odd repetitions run BDI first; even repetitions reverse the order. Never run both approaches concurrently.

**Matched timing for C3:** 35 seconds of temporary faults, observation starts after a 15-second deployment pause, 30-second rolling error/latency queries, five-second observation spacing and two consecutive healthy samples. Prometheus scrape and app metric export intervals remain five seconds. The rolling window retains earlier faults, so passing is not expected immediately at second 35; allow the window to clear while normal traffic continues. The experiment scripts start traffic before the pause; do not add a manual client.

**Do not shorten observation/repair budgets to save time.** The 180-second observation budget remains; repair probes/decision budgets are unchanged. Both approaches now receive a further bounded 60-second final recheck before committing a telemetry-triggered rollback when the candidate is still ready. C6 uses 195 seconds of request faults so it reaches that decision; a 35-second fault normally recovers during initial observations and cannot demonstrate cancelling a pending rollback. Late recovery in C6 is timing-dependent: the saved rollback-selection event is required evidence. A timing change requires a newly published control revision and a new study; do not mix results with the old 75/60/120-second protocol. Normal verification uses two consecutive healthy samples; repair retains its 120-second probe window and 300-second decision budget. Runner queues and approval waits can add substantial runtime.

## A. One-time setup and control publication

### A1. Check the existing installation and release pair

**Open:** Controller PowerShell and GitHub Actions.

**Actions:** if this is a new machine, complete [guide 03, A1-A4](03_BDI_MANUAL_EXECUTION_GUIDE.md#a-one-time-setup) for tools, runner/configuration and the labelled v1/v2 pair. Return here after saving the pair; use this guide's compact schedule, not another guide's scenario loop. A missing baseline receipt is handled in F1 below.

For an existing setup, check that `experiments/results/release-pairs/current-pair.txt` exists and that Docker and the existing runner are available. Keep payment data and existing results.

**Expected:** the pair file selects the intended app versions and worker. If the control code is already published, skip A2 and go to B1.

### A2. Publish a changed control revision only when needed

**Only when execution code or protocol has changed:** preserve the previous study and publish a reviewed control revision before creating a new study. Do not combine different revisions as matched pairs. Documentation wording alone does not require a new experiment series.

In Source Control, review and stage intended code, tests and documentation (including new helper files); exclude results and credentials. Commit them, then verify `git status --short` produces no output. Pushing an existing commit does not include unstaged/uncommitted changes. If the block below stops on a dirty worktree, complete this manual step before proceeding. Never bypass the guard.


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

**Manual action:** in Source Control review and stage the intended files. Then inspect the staged list:

```powershell
git diff --cached --stat
```

**Only after reviewing that list**, commit and publish the branch:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    git commit -m "Simplify paired workflows and repair experiment recording"
    if ($LASTEXITCODE -ne 0) { throw 'Commit did not complete. Inspect Git output before proceeding.' }
    if (git status --porcelain) { throw 'Uncommitted files remain. Review them; do not discard them to bypass this check.' }
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Branch publication failed.' }
}
```

Skip the commit block if this exact revision is already committed and the worktree is clean. Publishing a branch does not merge workflows into the default branch; complete that reviewed publication separately. No tag/pair block or experiment step should follow a failed prerequisite.

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

**Expected:** new published control tag; old tags, app SHAs and receipts preserved. Proceed to B1. Conventional deployment is triggered by `workflow_dispatch`, not by this push. Its single workflow has six jobs: build, test, security, staging, production and rollback. Health checks run inside deployment jobs; the local collector aggregates saved artifacts after the workflow ends. The BDI worker retains separate **Diagnose candidate** and **Restart candidate** jobs with static names. They run only when requested by the agent; neither is a normal pipeline phase. The obsolete report job is removed.

## B. Setup for this session and the next candidate

### B1. Load the release pair and reset functions

**Open:** Controller PowerShell at the repository root. Keep this window for the rest of the guide.

**Actions:** run the complete block below once in each new terminal. It clears stale settings, loads the selected pair, checks the control revision and defines functions. **It does not deploy v1 or run a candidate.**

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
    if ($LASTEXITCODE -ne 0) { throw 'Control revision mismatch. Fetch missing commits or complete A2 with a new control tag.' }
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
        param([switch]$Headless)
        Write-Host '[compact-reset] Checking baseline and starting a fresh v1 reset.'
        if (-not $studyDir -or -not $knownGood) { throw 'Load the study and verified baseline first.' }
        foreach ($name in @('BDI_EXECUTION_PLAN','BDI_SCENARIO','BDI_READY_URL','BDI_PROMETHEUS_URL','BDI_PAUSE_AFTER_ENTITY','BDI_PAUSE_MILLISECONDS')) {
            if (Test-Path "Env:$name") { Remove-Item "Env:$name" }
        }
        $env:BDI_RELEASE_SHA = $v1Sha
        $destination = Join-Path $studyDir ('resets/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
        $displayArgs = @()
        if (-not $Headless) { $displayArgs += '--gui' }
        py -3 -B bdi-cicd-framework/run_controller.py @displayArgs --known-good "$knownGood" --confirm-compatible-rollback --artifacts-dir "$destination"
        if ($LASTEXITCODE -ne 0) { throw 'Reset incomplete: inspect evidence; do not launch a candidate.' }
        Assert-V1Receipt (Join-Path $destination 'controller-result.json') (Join-Path $destination 'reset-check.json')
        $resetReceipt = Get-Content (Join-Path $destination 'controller-result.json') -Raw | ConvertFrom-Json
        foreach ($entity in @('staging','production')) {
            py -3 -B scripts/candidate-repair.py preflight --project "payment-$entity" --app app --dependency postgres --expected $resetReceipt.verified_releases.$entity.execution_id --output (Join-Path $destination "container-preflight-$entity.json")
            if ($LASTEXITCODE -ne 0) { throw 'Container preflight failed. Inspect the saved inventory; do not start candidates or delete containers blindly.' }
        }
        $destination | Set-Content (Join-Path $studyDir 'current-reset.txt') -Encoding utf8
        $env:BDI_RELEASE_SHA = $v2Sha
        "Both environments verified at v1: $destination"
    }
    [pscustomobject]@{ Repository=$pair.repository; Worker=$workerRef; WorkerSHA=$workerSha; V1=$v1Sha; V2=$v2Sha; Baseline=$knownGood } | Format-List
}
```

**Expected:** repository, worker SHA, v1, v2 and baseline are printed. If a control check fails, resolve A2. If only the baseline path is blank, continue through B2 and then use F1 before B4.

### B2. Select the study: follow exactly ONE branch

**Existing study:** skip B2.1. Run **B2.2** to continue the saved study.

**New study:** only after old executions are settled (F3), run **B2.1 once**, then **B2.2**. Never recreate the schedule on a terminal restart or operator handoff.

#### B2.1. Create a new study only

**Manual choice:** leave `focused` for the four-run follow-up. Change it to `full` only to run all six cases. Choose before creating the schedule.

```powershell
$studyScope = 'focused'
$repetitions = 1
$seed = 42
```

**Actions:** run unchanged. It preserves the old study and backs up the old pointer.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($repetitions -lt 1 -or $repetitions -gt 100) { throw 'Choose an explicit repetition count from 1 to 100.' }
    if ($studyScope -notin @('focused','full')) { throw 'Choose focused or full in the manual block.' }
    $studySet = if ($studyScope -eq 'focused') { 'focused-recovery-v1' } else { 'compact-six-v3' }
    $cases = if ($studyScope -eq 'focused') { @('candidate-stopped','rollback-reconsideration') } else { @('healthy','test-failure','production-temporary','production-persistent','candidate-stopped','rollback-reconsideration') }
    $catalog = Get-Content experiments/scenarios.json -Raw | ConvertFrom-Json
    if (@($cases | Where-Object { $_ -notin $catalog.PSObject.Properties.Name }).Count) { throw 'Catalog mismatch.' }
    # Starting a new study changes only the selection, never the old evidence.
    # Complete F3 first if the previous study has unfinished work.
    $studyPointer = 'experiments/results/current-compact-study.txt'
    if (Test-Path $studyPointer) {
        $oldSelection = (Get-Content $studyPointer -Raw).Trim()
        if (-not (Test-Path (Join-Path $oldSelection 'study.json'))) { throw 'Previous study pointer is invalid; resolve F3.1 before replacing it.' }
        $historyDir = 'experiments/results/study-pointer-history'
        New-Item -ItemType Directory -Force -Path $historyDir | Out-Null
        $pointerBackup = Join-Path $historyDir ('compact-six-' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '.txt')
        if (Test-Path $pointerBackup) { throw 'Pointer backup already exists; use a fresh timestamp.' }
        Copy-Item -LiteralPath $studyPointer -Destination $pointerBackup -ErrorAction Stop
        "Previous study preserved: $oldSelection ; pointer backup: $pointerBackup"
    }
    $studyDir = [System.IO.Path]::GetFullPath('experiments/results/studies/' + $studySet + '-' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
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
    [pscustomobject]@{ schema_version=1; study_set=$studySet; scope=$studyScope; pair_file=$pairFile; repository=$pair.repository; v1_sha=$v1Sha; v2_sha=$v2Sha; worker_sha=$workerSha; worker_ref=$workerRef; repetitions=$repetitions; seed=$seed; trials=$trials } |
        ConvertTo-Json -Depth 8 | Set-Content (Join-Path $studyDir 'study.json') -Encoding utf8
    $trials | Export-Csv (Join-Path $studyDir 'schedule.csv') -NoTypeInformation -Encoding utf8
    $studyDir | Set-Content experiments/results/current-compact-study.txt -Encoding utf8
    "Study: $studyDir ; candidate trials: $index"
}
```

**Expected:** a new study folder and `candidate trials: 4` (`12` for full). This has created the schedule only; neither environment has been reset.

#### B2.2. Load the saved study and show progress

**Actions:** run after B1 on every session, including immediately after creating a study.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-compact-study.txt -Raw).Trim()
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    if ($study.repository -ne $pair.repository -or $study.v1_sha -ne $v1Sha -or $study.v2_sha -ne $v2Sha -or $study.worker_sha -ne $workerSha) { throw 'Current pair/control differs from this study. Restore the selection or create a new study.' }
    if ($study.study_set -notin @('compact-five-v1','compact-six-v2','focused-recovery-v1','compact-six-v3')) { throw 'Select this compact study, not the full study.' }
    "Study folder: $studyDir"
    foreach ($item in $study.trials) {
        $folder = Join-Path $studyDir "trials/$($item.id)"
        [pscustomobject]@{ Trial=$item.id; Started=(Test-Path (Join-Path $folder 'started.json')); Recorded=(Test-Path (Join-Path $folder 'record.json')) }
    }
}
```

**Expected:** your study folder and each trial's progress. `Started=True, Recorded=False` means resume evidence collection using F2; do not launch that trial again or reset before preserving its final state.

### B3. Load the shared candidate launcher

**Actions:** paste this function once per terminal. It uses the next unrecorded trial in the saved schedule, checks the scenario and approach you requested, verifies an unused v1 reset, then runs **one** candidate. For conventional execution it also waits and collects artifacts. Defining the function does not run anything.

Scenario C instructions call this function with explicit case and approach names. Fault injection, background traffic and repair probes are automatic. Do not add another traffic client or stop containers manually.

```powershell
function Invoke-CompactCandidate {
    param(
        [Parameter(Mandatory=$true)][string]$Case,
        [Parameter(Mandatory=$true)][ValidateSet('bdi','github-actions')][string]$Mechanism,
        [switch]$Headless
    )
    $ErrorActionPreference = 'Stop'
    Write-Host "[compact-launcher] Checking $Case / $Mechanism prerequisites."
    if (-not $studyDir -or -not $pair) { throw 'Complete B1 and B2 first.' }
    Write-Host "[compact-launcher] Study: $studyDir"
    $study = Get-Content (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    $trial = $study.trials | Where-Object { -not (Test-Path (Join-Path $studyDir "trials/$($_.id)/record.json")) } | Select-Object -First 1
    if (-not $trial) { throw 'All trials are recorded. Complete E if needed, then G; do not launch again.' }
    if ($study.study_set -notin @('focused-recovery-v1','compact-six-v3')) { throw 'Preserve the old study. After A2, create the new schedule in B2.1.' }
    if ($trial.case -ne $Case -or $trial.mechanism -ne $Mechanism) { throw "Next scheduled trial is $($trial.id). Use its C instruction; do not skip or repeat trials." }
    $trialRoot = Join-Path $studyDir "trials/$($trial.id)"
    if (Test-Path (Join-Path $trialRoot 'started.json')) { throw 'Already started: use F2 to resume collection, never redispatch.' }
    if (-not (Test-Path (Join-Path $studyDir 'current-reset.txt'))) {
        throw 'No verified reset is saved for this study. Complete B4 and wait for Both environments verified at v1 before running C.'
    }
    New-Item -ItemType Directory -Force -Path $trialRoot | Out-Null
    $trial.id | Set-Content (Join-Path $studyDir 'current-trial.txt') -Encoding utf8
    $trial | ConvertTo-Json | Set-Content (Join-Path $trialRoot 'planned-trial.json') -Encoding utf8
    $trial | Format-List
    $resetDir = (Get-Content (Join-Path $studyDir 'current-reset.txt') -Raw).Trim()
    if (Test-Path (Join-Path $resetDir 'used-by-trial.txt')) { throw 'Reset already used. Complete E first.' }
    $resetResult = Join-Path $resetDir 'controller-result.json'
    $resetCheck = Join-Path $trialRoot 'reset-check.json'
    Assert-V1Receipt "$resetResult" "$resetCheck"
    $resetReceipt = Get-Content -LiteralPath $resetResult -Raw | ConvertFrom-Json
    foreach ($entity in @('staging','production')) {
        $preflightPath = Join-Path $trialRoot ("container-preflight-$entity-" + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '.json')
        py -3 -B scripts/candidate-repair.py preflight --project "payment-$entity" --app app --dependency postgres --expected $resetReceipt.verified_releases.$entity.execution_id --output "$preflightPath"
        if ($LASTEXITCODE -ne 0) { throw 'Stale, duplicate or incorrect containers detected. Review the preflight evidence before running.' }
    }
    $trial.id | Set-Content (Join-Path $resetDir 'used-by-trial.txt') -Encoding utf8
    [pscustomobject]@{ started_at=(Get-Date).ToUniversalTime().ToString('o'); reset_result=$resetResult; reset_check=$resetCheck } |
        ConvertTo-Json | Set-Content (Join-Path $trialRoot 'started.json') -Encoding utf8
    Write-Host "[compact-launcher] Starting $($trial.id). Evidence: $trialRoot"
    if ($trial.mechanism -eq 'bdi') {
        $resultDir = Join-Path $trialRoot 'bdi'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        $displayArgs = @()
        if (-not $Headless) { $displayArgs += '--gui' }
        py -3 -B bdi-cicd-framework/run_experiment.py @displayArgs --mechanism bdi --case $trial.case --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed $study.seed --artifacts-dir "$resultDir"
        "BDI exit code: $LASTEXITCODE. Inspect the stored outcome in D; failure cases may correctly stop delivery."
    } elseif ($trial.mechanism -eq 'github-actions') {
        $resultDir = Join-Path $trialRoot 'native/artifacts/native-result/result'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        py -3 -B experiments/dispatch_trial.py --study "$studyDir" --trial $trial.id
        if ($LASTEXITCODE -ne 0) { throw 'Dispatch failed/uncertain. Use F2; never blindly redispatch.' }
    } else { throw 'Unknown mechanism in schedule.' }
    if ($trial.mechanism -eq 'github-actions') {
        $runId = (Get-Content (Join-Path $trialRoot 'github-run-id.txt') -Raw).Trim()
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
        if ($LASTEXITCODE -ne 0 -or $status -ne 'completed') { throw 'Remote work is not known terminal. Use F2.' }
        $nativeDir = Join-Path $trialRoot 'native'
        py -3 experiments/collect.py --repo $pair.repository --run-id $runId --output "$nativeDir"
        $collectionExit = $LASTEXITCODE
        $resultDir = Join-Path $nativeDir 'artifacts/native-result/result'
        $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
        "Collection exit: $collectionExit. Keep incomplete evidence and inspect collection.json."
    }
    "Candidate command finished. Complete D1-D4, then E before another candidate."
}
```

**Expected now:** defining the function returns to the prompt without deploying anything. Calling it in C must immediately print `[compact-launcher] Checking ...`, followed by the study path or an error. If that first line never appears, do not assume Java or GitHub is running; inspect the function loaded in this terminal using F2. Later, calling the function in C blocks until the controller or GitHub run finishes. For BDI, close the MAS Console only after `Campaign finished` so the function can return. A failed outcome must still be saved and recorded.

### B4. Actually restore both environments to v1

**Open:** Controller PowerShell and GitHub Actions. Confirm no previous candidate, repair, rollback or traffic process is active. If uncertain, use F2/F3 first.

**Actions:** run this block. If no valid baseline receipt is linked, complete F1 first and then return here.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Assert-V1Receipt "$knownGood" ''
    Invoke-StudyReset
}
```

**Expected:** a MAS Console opens and deployment jobs run. After `Campaign finished`, inspect `controller_agent` and close the completed console. PowerShell then prints `Both environments verified at v1:` followed by a new reset folder. Both staging and production must pass identity/readiness checks. A browser showing v1 is not enough.

**Next:** choose the next pending trial in C. After a successful E reset in this session, go directly to C; do not reset twice. On a new session, an existing unused reset may be replaced by this fresh reset once no candidate is active.

**Container checkpoint:** the reset and candidate launch both save `container-preflight-*.json`. The read-only check verifies a unique expected app, reports stale app containers and checks dependency uniqueness/running state. A failure stops the next candidate. Inspect IDs, deployment identities and state; remove only a confirmed obsolete container without force or volume deletion. Never remove the baseline/current candidate just because its service label matches. A stale container does not necessarily occupy a port.

The previously confirmed obsolete `relaxed_kepler` container was removed during this repair; its removal audit is under `experiments/results/maintenance/`. Existing experiment evidence is preserved.

The identical BDI reset routine prepares both approaches outside measured candidate time. Database volumes are retained. Do not use `docker compose down -v`.

## C. Run the six scenarios, one approach at a time

For **focused**, go directly to C5 (trials 001/002), then C6 (003/004). For **full**, follow C1 through C6; the table below gives full-study numbers. Each scenario has two runs. **After each run, complete D and E before starting the other approach.** Do not paste both approach commands together.

| Scenario | First run | Second run | After both are recorded and reset |
|---|---|---|---|
| C1 healthy | 001 BDI | 002 conventional | C2 |
| C2 test failure | 003 BDI | 004 conventional | C3 or operator handoff in G2 |
| C3 temporary degradation | 005 BDI | 006 conventional | C4 |
| C4 persistent degradation | 007 BDI | 008 conventional | C5 |
| C5 stopped candidate | 009 BDI | 010 conventional | C6 |
| C6 rollback reconsideration | 011 BDI | 012 conventional | G1 evaluation |

If you deliberately selected multiple repetitions, follow the saved schedule: odd repetitions use BDI first, even repetitions conventional first. Return to C1 for each new repetition; the launcher refuses out-of-order requests.

### C1. Healthy execution (`healthy`)

**Open:** Controller PowerShell and GitHub Actions. Docker and the existing runner must remain running.

**Setup:** B1-B3 must be loaded and B4/E must have produced a fresh unused v1 reset. No injected fault. Normal traffic runs at each reached staging and production gate.

**Run 1 - BDI** (trial 001 for repetition 1):

```powershell
Invoke-CompactCandidate -Case 'healthy' -Mechanism bdi
```

**When it finishes:** complete **D1-D4** to save/record this trial, then **E** to reset. Return here for Run 2. If interrupted, use F2; do not rerun the command.

**Run 2 - conventional** (trial 002 for repetition 1), only after Run 1 is recorded and E passes:

```powershell
Invoke-CompactCandidate -Case 'healthy' -Mechanism github-actions
```

**When it finishes:** complete **D1-D4**, then **E**, including after a red GitHub run.

**Expected results to inspect:** Both approaches should deliver verified v2. Inspect accepted health gates, normal traffic and total runtime; this is the baseline for orchestration cost.

**Next:** after both records and resets, continue to **C2**. Unexpected outcomes remain part of the study; do not repeat until a preferred result appears.

### C2. Deterministic test failure (`test-failure`)

**Open:** Controller PowerShell and GitHub Actions. Docker and the existing runner must remain running.

**Setup:** B1-B3 must be loaded and B4/E must have produced a fresh unused v1 reset. The script injects a deterministic test failure. No manual file edit is needed.

**Run 1 - BDI** (trial 003 for repetition 1):

```powershell
Invoke-CompactCandidate -Case 'test-failure' -Mechanism bdi
```

**When it finishes:** complete **D1-D4** to save/record this trial, then **E** to reset. Return here for Run 2. If interrupted, use F2; do not rerun the command.

**Run 2 - conventional** (trial 004 for repetition 1), only after Run 1 is recorded and E passes:

```powershell
Invoke-CompactCandidate -Case 'test-failure' -Mechanism github-actions
```

**When it finishes:** complete **D1-D4**, then **E**, including after a red GitHub run.

**Expected results to inspect:** Build should succeed, test should fail and downstream deployment should stop. Both environments should retain reset v1. No staging/production traffic is expected because deployment gates are never reached. A red test job is expected evidence of safe stopping, not permission to skip recording.

**Next:** after both records and resets, continue to **C3 (or G2 for operator handoff)**. Unexpected outcomes remain part of the study; do not repeat until a preferred result appears.

### C3. Temporary production degradation (`production-temporary`)

**Open:** Controller PowerShell and GitHub Actions. Docker and the existing runner must remain running.

**Setup:** B1-B3 must be loaded and B4/E must have produced a fresh unused v1 reset. The script injects mixed request errors for 35 seconds and then restores normal traffic. Observations begin after a 15-second pause, using the same 30-second rolling window for both approaches.

**Run 1 - BDI** (trial 005 for repetition 1):

```powershell
Invoke-CompactCandidate -Case 'production-temporary' -Mechanism bdi
```

**When it finishes:** complete **D1-D4** to save/record this trial, then **E** to reset. Return here for Run 2. If interrupted, use F2; do not rerun the command.

**Run 2 - conventional** (trial 006 for repetition 1), only after Run 1 is recorded and E passes:

```powershell
Invoke-CompactCandidate -Case 'production-temporary' -Mechanism github-actions
```

**When it finishes:** complete **D1-D4**, then **E**, including after a red GitHub run.

**Expected results to inspect:** Inspect early unhealthy observations, bounded reobservation and two fresh healthy samples before v2 is accepted. Older errors can remain in the window after second 35. Check for unnecessary restart/rollback; preserve and explain it if it happens.

**Next:** after both records and resets, continue to **C4**. Unexpected outcomes remain part of the study; do not repeat until a preferred result appears.

### C4. Persistent production degradation (`production-persistent`)

**Open:** Controller PowerShell and GitHub Actions. Docker and the existing runner must remain running.

**Setup:** B1-B3 must be loaded and B4/E must have produced a fresh unused v1 reset. Production request errors persist through the observation budget; do not stop the injector yourself.

**Run 1 - BDI** (trial 007 for repetition 1):

```powershell
Invoke-CompactCandidate -Case 'production-persistent' -Mechanism bdi
```

**When it finishes:** complete **D1-D4** to save/record this trial, then **E** to reset. Return here for Run 2. If interrupted, use F2; do not rerun the command.

**Run 2 - conventional** (trial 008 for repetition 1), only after Run 1 is recorded and E passes:

```powershell
Invoke-CompactCandidate -Case 'production-persistent' -Mechanism github-actions
```

**When it finishes:** complete **D1-D4**, then **E**, including after a red GitHub run.

**Expected results to inspect:** Inspect sustained unhealthy observations, the bounded decision to stop waiting, and verified rollback to v1. Restoring v1 is successful recovery but does not achieve candidate v2 delivery. Compare safe final state, observations, retries and recovery time.

**Next:** after both records and resets, continue to **C5**. Unexpected outcomes remain part of the study; do not repeat until a preferred result appears.

### C5. Recoverable service failure: stopped candidate (`candidate-stopped`)

**Open:** Controller PowerShell and GitHub Actions. Docker and the existing runner must remain running.

**Setup:** B1-B3 must be loaded and B4/E must have produced a fresh unused v1 reset. After successful deployment the helper stops only the correlated candidate app container. Staging uses normal traffic; production uses the repair worker probes instead of a separate normal traffic client.

**Run 1 - BDI** (focused trial 001; full trial 009):

```powershell
Invoke-CompactCandidate -Case 'candidate-stopped' -Mechanism bdi
```

**When it finishes:** complete **D1-D4** to save/record this trial, then **E** to reset. Return here for Run 2. If interrupted, use F2; do not rerun the command.

**Run 2 - conventional** (focused trial 002; full trial 010), only after Run 1 is recorded and E passes:

```powershell
Invoke-CompactCandidate -Case 'candidate-stopped' -Mechanism github-actions
```

**When it finishes:** complete **D1-D4**, then **E**, including after a red GitHub run.

**Expected results to inspect:** Inspect diagnosis of the matching stopped candidate, one bounded restart and fresh identity-correlated health verification. Successful repair should continue v2 delivery. A restart command alone is not proof of recovery; if verification fails, inspect verified rollback or safe stop.

**Next:** after both records and resets, continue to **C6**. Unexpected outcomes remain part of the study; do not repeat until a preferred result appears.

### C6. Cancel pending rollback after recovery (`rollback-reconsideration`)

**Open:** Controller PowerShell, MAS Console for BDI, and GitHub Actions. Keep Docker and the runner running.

**Setup:** use the new schedule and a fresh unused E reset. Production request errors last 195 seconds, then normal traffic resumes. Initial unhealthy observations exhaust the usual budget. Both controllers select rollback, but check fresh, deployment-correlated health for up to 60 more seconds before dispatching it. Do not inject faults manually.

**Run 1 - BDI** (focused trial 003; full trial 011):

```powershell
Invoke-CompactCandidate -Case 'rollback-reconsideration' -Mechanism bdi
```

**When finished:** D1-D4, then E. Return here for Run 2.

**Run 2 - conventional** (focused trial 004; full trial 012):

```powershell
Invoke-CompactCandidate -Case 'rollback-reconsideration' -Mechanism github-actions
```

**When finished:** D1-D4, then E, including the final reset.

**Expected:** `rollback_selected`, followed by fresh correlated observations, two consecutive healthy samples and `rollback_cancelled`. No rollback job should execute; verified v2 remains and candidate delivery succeeds. Selection is an intention: it can be cancelled only before rollback dispatch. If health does not recover within the final window, rollback must execute and verify v1 instead.

**Evidence:** inspect `rollback_selected`, `rollback_cancelled`, `rollback_reconsideration_seconds`, `rollback_attempts`, final safety and the ordered controller events. If errors clear before rollback selection, the trial does not test this case and is excluded with `rollback_intention_not_observed`. Preserve it rather than claiming reconsideration occurred.

**Why this case:** it makes changing a pending recovery decision visible. C5 tests repair, while C6 tests reacting to changing observations. Both approaches have the same final recheck and may tie. These trials demonstrate BDI capabilities; comparative superiority requires an observed benefit under equal conditions.

**Next:** G1 after the final reset; for another scheduled repetition, return to C5 (focused) or C1 (full).

## D. Finalise EVERY candidate: save, inspect and record

Do this after each individual C command, before resetting or launching another candidate. Most logs are already saved automatically. These steps collect remote logs, capture the current final state and create the comparison record. They also apply to failed trials. Before capturing final state in D3, confirm the controller has stopped and all candidate/diagnostic/repair/rollback jobs are terminal in GitHub Actions. If execution was interrupted or remote status is uncertain, use F2 first.

### D1. Reload this trial and inspect saved evidence

**Open:** Controller PowerShell. If reopened, complete B1 and B2.2 first. Reloading paths avoids relying on variables inside the launcher function.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content -LiteralPath 'experiments/results/current-compact-study.txt' -Raw).Trim()
    $study = Get-Content -LiteralPath (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    $trialId = (Get-Content -LiteralPath (Join-Path $studyDir 'current-trial.txt') -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($trialId)) { throw 'Saved trial ID is blank. Inspect current-trial.txt; do not guess a trial.' }
    $trialMatches = @($study.trials | Where-Object { $_.id -eq $trialId })
    if ($trialMatches.Count -ne 1) { throw 'Saved trial does not uniquely match this study schedule.' }
    $trial = $trialMatches[0]
    $trialRoot = Join-Path $studyDir "trials/$trialId"
    $resultDir = (Get-Content (Join-Path $trialRoot 'result-path.txt') -Raw).Trim()
    if (Test-Path (Join-Path $resultDir 'controller-result.json')) {
        $result = Get-Content (Join-Path $resultDir 'controller-result.json') -Raw | ConvertFrom-Json
        $result | Select-Object mode,outcome,recovery_outcome,release_sha,known_good_sha | Format-List
        $result.executions; $result.telemetry; $result.verified_releases
    } else { 'Result missing: retain this incomplete trial; inspect F2.' }
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
| Traffic | `bdi-traffic*/`; client logs in `bdi-experiment/` | `native/artifacts/native-staging/` and `native-production/`; summaries beside `result/` |
| Diagnosis/restart evidence | `bdi/operation-<UUID>/receipt.json` | `native/artifacts/native-production/health/` receipts |
| Launch failure | `bdi-experiment/launch-status.json` | GitHub run/job and collection status |

Inspect `traffic_by_entity` for required traffic and profile/seed/deployment/release mismatches. Missing evidence is not success. A restart returning `executed` is not verified delivery. Use the five-case table above to inspect the actual fault and response; retain unexpected but well-evidenced outcomes.

### D2. BDI only: download acknowledged GitHub job logs

Skip D2 for conventional: the C launcher already collected its logs. Continue to D3. The following reads GitHub without dispatching. Missing logs remain an explicit collection problem.

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

### D3. Both approaches: capture the final live state

Run before reset, including after failed trials. Run only once for this trial; if `final-state.json` already exists, inspect and preserve it. Never overwrite it with observations taken after a reset. Endpoint failures are retained as errors, not labelled healthy.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (Test-Path (Join-Path $trialRoot 'final-state.json')) { throw 'Final state already saved. Preserve it and continue at D4.' }
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

Console logs and traffic logs are automatic. Conventional result JSON/metrics are assembled offline by `collect.py` from terminal job metadata and per-attempt receipts. A missing required receipt is a collection failure, not an inferred success. Screenshots are optional; if wanted, save them in `$trialRoot`. Do not manually recreate missing JSON or rerun to manufacture evidence for an earlier trial.

### D4. Save the comparison record

**Open:** Controller PowerShell after D1-D3. If `record.json` already exists, preserve it and continue to E once remote work is terminal. The helper derives fault exposure and final safety from the saved evidence, reads the reset references from `started.json`, and writes the exact schema required by the evaluator. It never assumes an expected outcome actually occurred. Missing evidence remains unverified/ineligible; failures are still recorded. Do not hand-write another `record.json` format or set eligibility yourself.

**Manual input - only information that logs cannot establish:**

```powershell
$interventionText = (Read-Host 'Human interventions during candidate execution; blank if unknown').Trim()
$notes = Read-Host 'Notes: approvals, additional agent intervention, interruptions or unexpected behaviour'
```

For C5, `fault_injected=true` requires a worker log line beginning `FAULT_INJECTION_JSON=` whose container and deployment identity confirm the injected stop. `diagnosis_succeeded=true` separately requires a correlated stopped-app diagnosis. A requested failure mode or unavailable HTTP endpoint alone does not prove injection. Missing injection evidence is not inferred from diagnosis. Failed diagnosis remains explicit as `stopped_candidate_diagnosis_not_confirmed`; do not reinterpret old records using the new fields.

The recording block reloads the study and trial ID from disk, so it does not depend on `$trial` surviving previous steps. If an earlier attempt reported `argument --trial: expected one argument`, rerun only this corrected D4 block; keep D2/D3 evidence and do not repeat the candidate.

An execution agent may supply these from its own documented action history. Unknown intervention counts must stay unknown. Routine reset and collection do not count as candidate repair interventions.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content -LiteralPath 'experiments/results/current-compact-study.txt' -Raw).Trim()
    $study = Get-Content -LiteralPath (Join-Path $studyDir 'study.json') -Raw | ConvertFrom-Json
    $trialId = (Get-Content -LiteralPath (Join-Path $studyDir 'current-trial.txt') -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($trialId)) { throw 'Saved trial ID is blank. Inspect current-trial.txt; do not guess a trial.' }
    $trialMatches = @($study.trials | Where-Object { $_.id -eq $trialId })
    if ($trialMatches.Count -ne 1) { throw 'Saved trial does not uniquely match this study schedule.' }
    $trial = $trialMatches[0]
    $trialRoot = Join-Path $studyDir "trials/$trialId"
    if (-not (Test-Path -LiteralPath (Join-Path $trialRoot 'started.json'))) { throw 'This trial has no start record. Do not record an unrun trial.' }
    if (Test-Path -LiteralPath (Join-Path $trialRoot 'record.json')) { throw 'Record already exists. Preserve it; continue to E when remote work is terminal.' }
    Write-Host "Recording saved trial: $trialId"
    $recordArgs = @('--study', $studyDir, '--trial', $trialId)
    if ($interventionText) {
        if ($interventionText -notmatch '^\d+$') { throw 'Use a nonnegative count or leave blank.' }
        $recordArgs += @('--human-interventions', $interventionText)
    }
    if ($notes) { $recordArgs += @('--notes', $notes) }
    py -3 -B experiments/record_trial.py @recordArgs
    if ($LASTEXITCODE -ne 0) { throw 'Recording failed: inspect error; do not invent or overwrite evidence.' }
}
```

**Expected:** path to `record.json`, eligibility and explicit issues. An unexpected valid rollback can be eligible even though the scenario expectation was not met. Recording does not prove remote work has stopped. Preserve the original on corrections; use a separately documented amendment, never silently overwrite old records. Continue to E only after all remote work is terminal.

## E. Clean up and restore v1 after EVERY candidate

Confirm candidate, diagnostic, repair and rollback jobs are terminal. Close the completed candidate MAS Console before continuing. The reset below opens its own MAS Console; close that one after `Campaign finished` so v1 verification can complete. Normal traffic clients stop automatically; stop only a leftover client you started for this trial. Keep Docker and the runner running.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (-not (Test-Path (Join-Path $trialRoot 'record.json'))) { throw 'Complete D4 before reset.' }
    Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO -ErrorAction SilentlyContinue
    Invoke-StudyReset
}
```

**Expected:** new verified v1 reset in both environments; completed evidence is unchanged. This reset is also required when production already appears v1, and after the final trial. Do not delete database volumes or result folders.

**Next:** return to the C scenario you just used: after its first approach run the second; after both, follow its Next instruction. After the final scheduled trial (004 focused / 012 full), evaluate in G1. Never reuse one reset for two candidate trials.

## F. Baseline and troubleshooting

### F1. Link or create a verified v1 baseline only if missing

Complete B1 and B2 first. A previously verified baseline can be reused; it does not replace the fresh reset required before each trial.

If `$knownGood` already contains your verified receipt, run this check and continue to B4 if it succeeds:

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
    py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir "$baselineDir"
    if ($LASTEXITCODE -ne 0) { throw 'Baseline incomplete; inspect its logs before any candidate run.' }
    $knownGood = Join-Path $baselineDir 'controller-result.json'
    Assert-V1Receipt "$knownGood" (Join-Path $baselineDir 'reset-check.json')
    $pair.known_good_receipt = $knownGood
    $pair | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pairFile -Encoding utf8
    $env:BDI_RELEASE_SHA = $v2Sha
}
```

**Expected:** the selected pair links an achieved live v1 receipt for both environments. Baseline work is excluded from measured candidate runs. Continue to B4.

### F2. Resume an interrupted trial or resolve an error

**No output after calling the launcher:** in the same terminal, once its prompt is available, run the read-only commands below. They show the actual function definition and selected study in that session; a function loaded before a guide edit does not update automatically.

```powershell
Get-Command Invoke-CompactCandidate -ErrorAction Stop | Format-List Name,CommandType,Definition
$studyDir
```

Compare the definition with B3. Reload the entire B3 function if it is empty, outdated or different. Look for the first `[compact-launcher]` message when invoking it. A missing reset is resolved with B4, not by making another study. If remote work might already be active, resolve its state before any new launch/reset.

**Editor Java Problems panel:** messages such as `Failed to configure project` or `java.lang.Error cannot be resolved` concern the editor's Java project/classpath. They do not prove the experiment's Gradle launch failed. Inspect the experiment terminal and saved `controller-console.log` for an actual runtime/build error. Guide 03 and this guide both ultimately launch `run_controller.py`; the compact launcher adds traffic coordination and evidence collection. Python/Gradle startup output, MAS Console and the saved journal provide evidence that the agent has started.

| Situation | Action |
|---|---|
| Terminal reopened | B1, B2.2 and D1; use saved pointers rather than guessing paths |
| Trial already has `started.json` | Run D1 to reload its paths, check terminal status, then resume collection/review; never dispatch it again |
| BDI interrupted or remote execution unknown | Stop the old local controller if still running, then use the reconciliation command below; inspect GitHub before resetting |
| Conventional dispatch uncertain | Run `py -3 -B experiments/dispatch_trial.py --study "$studyDir" --trial $trial.id --resolve-only`. Never delete its intent file or assume no response means no run. |
| Conventional cancelled or runner lost | Inspect all remote jobs and Docker state; preserve incomplete evidence; do not count GitHub `Re-run jobs` as another planned trial |
| Collection incomplete | Keep the failure record; download again into a fresh folder for inspection and document any correction; never count duplicate downloads as extra trials |
| Old control tag / file mismatch | A2, then start a new compact study if the control revision changed |
| Security gate blocks a healthy run | Preserve the finding; fix through a reviewed new app/control series rather than disabling the gate |
| Missing production traffic for `candidate-stopped` | Expected; inspect repair probes, identity and fresh observations; staging traffic remains required |
| Reset fails | Save the failure, settle remote state, fix the cause and create a new reset; never fabricate verification |

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Reconciliation reads remote status; it does not resume or dispatch. An unresolved outcome remains a stop condition. Do not delete locks/pending records to bypass it. Finish collecting and recording the interrupted trial, then reset. Document any amended schedule; do not silently replace an unsuccessful observation.

#### F2.1. Resume conventional waiting/collection without dispatching

**Only if the conventional C command was interrupted:** load B1, B2.2 and D1. Resolve an uncertain dispatch with the read-only `--resolve-only` command above, then run this block. It uses the saved run ID. If `native/` already contains a collection attempt, preserve it and inspect `collection.json`; do not overwrite it with this block.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if ($trial.mechanism -ne 'github-actions') { throw 'This continuation is conventional only.' }
    if (Test-Path (Join-Path $trialRoot 'native')) { throw 'Collection already exists. Inspect it and preserve original evidence; see F2.' }
    $runId = (Get-Content (Join-Path $trialRoot 'github-run-id.txt') -Raw).Trim()
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
    if ($LASTEXITCODE -ne 0 -or $status -ne 'completed') { throw 'Remote work is not known terminal. Use F2.' }
    $nativeDir = Join-Path $trialRoot 'native'
    py -3 experiments/collect.py --repo $pair.repository --run-id $runId --output "$nativeDir"
    $collectionExit = $LASTEXITCODE
    $resultDir = Join-Path $nativeDir 'artifacts/native-result/result'
    $resultDir | Set-Content (Join-Path $trialRoot 'result-path.txt') -Encoding utf8
    "Collection exit: $collectionExit. Keep incomplete evidence and inspect collection.json."
}
```

**Next:** D1-D4 and E. Missing evidence stays explicit. A known terminal failure can still be recorded; uncertain remote execution must be settled before reset.

### F3. Retire an old/hanging study before starting fresh

**Do not delete the previous experiment folders or `current-compact-study.txt`.** The text file only selects a study directory; it does not run, stop or reset anything. B2.1 creates a new directory and replaces the pointer automatically, keeping a timestamped copy of the previous pointer. Old results, run IDs and baseline receipts remain available for audit. Keep old directories in place because records contain absolute paths; moving them can break evidence references.

Distinguish **an incomplete study** (some trials have no record) from **an active execution** (a controller, traffic client or GitHub job is still running). Creating a new pointer does not stop an active execution. Use the following order.

#### F3.1. Identify the previous study

**Open:** a new Controller PowerShell at the repository root. This block only reads the old selection; it does not require B1 or change the pointer.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Set-Location C:\NHI\2026_IT-Project\260031_payment-repair
    $previousStudyDir = $null
    $previousStudy = $null
    if (Test-Path experiments/results/current-compact-study.txt) {
        $previousStudyDir = (Get-Content experiments/results/current-compact-study.txt -Raw).Trim()
        if (-not (Test-Path (Join-Path $previousStudyDir 'study.json'))) { throw 'Old pointer is invalid. Locate its existing study folder before replacing the selection.' }
        $previousStudy = Get-Content (Join-Path $previousStudyDir 'study.json') -Raw | ConvertFrom-Json
        [pscustomobject]@{ Study=$previousStudyDir; Repository=$previousStudy.repository; Worker=$previousStudy.worker_ref; Pair=$previousStudy.pair_file } | Format-List
        if (Test-Path (Join-Path $previousStudyDir 'current-trial.txt')) { Get-Content (Join-Path $previousStudyDir 'current-trial.txt') }
        foreach ($item in $previousStudy.trials) {
            $folder = Join-Path $previousStudyDir "trials/$($item.id)"
            [pscustomobject]@{ Trial=$item.id; Started=(Test-Path (Join-Path $folder 'started.json')); Recorded=(Test-Path (Join-Path $folder 'record.json')) }
        }
    } else { 'No existing study pointer. Check for any independently started execution before proceeding.' }
}
```

#### F3.2. Settle unfinished work before any reset

**Open:** the previous controller/traffic terminals, MAS window if used, and **GitHub > repository > Actions**.

1. If work is still progressing normally, let it finish and collect its evidence. If intentionally abandoning a stuck run, stop only the old controller/traffic processes belonging to this study (Ctrl+C in their terminals; close its MAS window). If process ownership is unclear, stop here and identify it. Do not kill every Java, Python or Node process.
2. Inspect the old trial's saved GitHub run IDs and the repository Actions page for running, queued or approval-waiting jobs, including diagnosis, restart, rollback and resets. Let them finish, or explicitly cancel **only the old experiment runs** using the GitHub UI. Verify each becomes terminal; a cancellation request alone is not sufficient. Leave the runner and Docker running.
3. For an interrupted BDI execution, restore GitHub login if needed and reconcile its durable execution state:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (-not $previousStudy) { throw 'Load the old study in F3.1 first.' }
    Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN,Env:GITHUB_API_URL -ErrorAction SilentlyContinue
    $env:GITHUB_REPOSITORY = $previousStudy.repository
    $env:BDI_WORKFLOW_REF = $previousStudy.worker_ref
    $env:BDI_RELEASE_SHA = $previousStudy.v2_sha
    $env:GITHUB_TOKEN = gh auth token --hostname github.com
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Restore GitHub login.' }
    Remove-Item Env:BDI_SCENARIO,Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
    py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
    if ($LASTEXITCODE -ne 0) { throw 'Reconciliation did not complete. Inspect the output; do not launch a reset or new trial.' }
}
```

Reconciliation does not resume the old campaign. **An unresolved execution remains a stop condition even if you have a new pair or pointer.** Never delete controller locks, pending-execution files or dispatch intents to bypass it. For conventional dispatch uncertainty, use F2's `dispatch_trial.py --resolve-only` against the **old** study and trial, not a newly created study. Read-only evidence collection may continue while resolving a blocker.

4. Save available logs/results and record interrupted outcomes using the old frozen study's tools where compatible. Preserve existing records unchanged; do not manufacture a final state after a later reset. Missing evidence stays missing. Add a dated note inside the old study explaining why it was stopped/superseded and which trials remain incomplete. Do not label unrun trials successful or mark the old study complete.

**Expected:** no old execution or traffic can still modify the deployment; unresolved operations have been reconciled. Old evidence remains intact. A clean terminal alone is not proof that remote jobs stopped.

#### F3.3. Create the new selection and restore v1

Open a **fresh Controller PowerShell** to avoid stale `$trial`, `$studyDir` and helper variables, then follow this sequence:

| Order | Action | Expected result |
|---|---|---|
| 1 | A2: commit/publish/select the reviewed control revision if needed | Correct worker tag; existing app v1/v2 SHAs and baseline preserved |
| 2 | B1: load the selected pair and reset helpers | Session variables populated; stale experiment environment overrides cleared |
| 3 | B2.1 once, then B2.2 | New twelve-trial schedule; previous pointer backed up; `current-compact-study.txt` selects the new directory |
| 4 | B3; F1 only if the baseline is missing | Load the candidate launcher; reuse the verified baseline |
| 5 | B4 | Fresh reset receipt verifies **both staging and production at v1** |
| 6 | C1 onward | Start new trial 001; old trial numbering/results belong to the old study |

Do not delete database volumes, run `docker compose down -v`, remove release tags, or delete baseline receipts. This is a reset to the verified v1 application with retained database data, not an empty-database experiment. If B4 fails, preserve its logs and resolve the failure before starting a candidate. Merely seeing v1 in the browser is insufficient; both execution identities/readiness checks must pass.

If you only closed the terminal and want to **continue the same unchanged study**, skip F3 and B2.1: use B1, B2.2, then D/F2 for any already-started trial. For manual-to-agent handoff after trial 004, keep the same pointer and schedule.

## G. Evaluate the study and hand off remaining work

### G1. Evaluate and back up (twelve trials in the new study)

**Open:** Controller PowerShell after finalisation and the final reset. The evaluator is read-only; it can also show pending trials mid-study.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $studyDir = (Get-Content experiments/results/current-compact-study.txt -Raw).Trim()
    $reportDir = [System.IO.Path]::GetFullPath('experiments/reports/' + (Get-Date -Format yyyyMMdd-HHmmss-fff))
    py -3 experiments/evaluate_study.py --study "$studyDir" --output "$reportDir"
    if ($LASTEXITCODE -ne 0) { throw 'Fix the reported ledger/format error without altering original evidence.' }
    $summary = Get-Content (Join-Path $reportDir 'summary.json') -Raw | ConvertFrom-Json
    $summary | ConvertTo-Json -Depth 8
    "Report: $reportDir"
    if (-not $summary.study_complete) { throw 'Study is incomplete: finalise pending trials and verify the final unused v1 reset in both environments.' }
    if ($summary.matched_pairs -lt $summary.planned_pairs) { 'Some pairs are excluded. Inspect trials.csv and pairs.csv; do not claim all comparisons are valid.' }
}
```

| Output | Use |
|---|---|
| `trials.csv` | All scheduled trials, outcomes, safety, interventions and exclusion reasons |
| `pairs.csv` | Compare the same case/repetition; `matched=true` requires eligible evidence with equal protocol keys |
| `groups.csv` | Per-case/per-approach delivery, restoration and repair rates with denominators; runtime, retries, repair time and interventions |
| `summary.json` | Planned/recorded/eligible counts, matched pairs and interpretation limits |

A study is complete only when all scheduled records exist, evidence exclusions are explained, the final reset verifies **both** environments at v1, and evaluation outputs are saved. Agent task completion alone is not study completion.

For one complete eligible repetition, expect **4 recorded trials and 2 matched pairs for focused**, or **12 recorded trials and 6 matched pairs for full**, with `final_reset_complete=true` and `study_complete=true`. These completion flags do not override evidence exclusions. Missing or excluded evidence reduces the matched count; retain and explain it. Pair differences are **BDI minus conventional**. Positive delivery difference favours BDI; negative runtime difference means BDI was faster. Do not turn missing times into zero.

Report each case separately:

1. **Healthy:** did both deliver v2, and what orchestration overhead occurred?
2. **Test failure:** did both stop safely and retain v1? Non-delivery is expected here.
3. **Temporary degradation:** did each wait for recovery and deliver v2 without unnecessary restart/rollback?
4. **Persistent degradation:** did each restore verified v1? Restoration does not achieve v2 delivery.
5. **Stopped candidate:** did diagnosis, bounded restart and fresh verification deliver v2? Compare repair attempts/time and interventions.
6. **Failed restart:** did the controller stop repairing after one failed attempt and restore verified v1? Compare decision/recovery time and interventions.

`recovery_seconds` measures first adverse production event to accepted rollback. `candidate_repair_seconds` measures restart request to accepted candidate health. They are different paths; compare only like-for-like values. Use matched pairs for conclusions, report ties, and do not infer statistical superiority from one run per case. This set illustrates runtime decision-making; comparative benefit must come from the observed outcomes/costs.

**Archive:** back up the entire compact study directory, reports, selected pair JSON, original baseline receipt directory and frozen revision identifiers. Results are Git-ignored. Keep the final verified v1 deployed unless you deliberately stop the stacks after recording completion. The full study and its pointer remain separate.

### G2. Optional operator handoff

**Focused study:** the execution agent loads B1, B2.2 and B3, then resumes the next pending C5/C6 trial. It must save D and reset E after each run, preserve completed/started records and finish G1. Never create another schedule on handoff. Use `-Headless` for unattended runs.

**Full study only: run C1-C2 manually, delegate C3-C6.**

Use **one study**, one repetition and seed 42 throughout. Complete B, then C1-C2 with D/E after every trial for trials **001-004**: healthy BDI, healthy conventional, test-failure BDI, test-failure conventional. A red test-failure run is expected, but it still requires collection, final-state capture, `record_trial.py`, and reset. After trial 004, complete E and verify both environments at v1. Stop before dispatching trial 005.

Before handoff, evaluate the study (the evaluator command in G1 may be used mid-study, but the completion guard will correctly report incomplete). Expect four recorded/eligible trials and two matched pairs; trials 005-012 are pending. If the first four are ineligible, explain/correct evidence through documented amendments before treating them as valid comparisons. Keep the saved pointer, records and reset receipts.

The execution agent must read this guide, load B1, **B2.2 only**, and B3, confirm the first four records and unused reset, then resume C3 at trial 005. Do not create another schedule, overwrite records, repeat completed trials or assume an existing `started.json` is safe to dispatch again. It completes trials 005-012, records each and resets after each, including the final trial; then evaluates and reports the full study. This handoff changes the operator, not the experiment configuration. Human interventions during measured execution must be recorded honestly; routine setup/collection is excluded.

For an unattended handoff, the agent must use `-Headless` on every candidate and reset helper call. Otherwise it must inspect and close each completed MAS Console before collection or the next reset can finish. Record this display-mode choice in operator notes.
