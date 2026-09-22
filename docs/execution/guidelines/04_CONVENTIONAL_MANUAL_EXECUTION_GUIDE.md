# Manual conventional experiment: v1 to v2

This is a standalone GitHub Actions route. No Java, Jason, BDI controller, generation or BDI baseline receipt is required. Use the root payment app unchanged and the implementation in [ci-cd-conventional/](../../../ci-cd-conventional/README.md). The five named stages are **build → test → security → staging → production**. Preparation, bounded health gates, rollback and evidence are supporting jobs, retained to provide a realistic conventional baseline.

**Returning after the app-version update:** start with [BDI manual A4: version pair](03_BDI_MANUAL_EXECUTION_GUIDE.md#a4-create-or-refresh-the-version-pair). You can reuse your tools and runner, but need new application tags and a receipt for the updated v1 SHA. Then resume this guide at step 2, skip step 3 only if that new baseline is already verified, and use steps 4-5 for each trial.

## 1. One-time setup and publication

Install Git, GitHub CLI, Python 3.12, Node 22 and Docker Desktop with WSL integration. Use PowerShell in the repository root. The dedicated Linux deployment runner needs Docker Compose, curl and outbound access for setup actions; label it `self-hosted`, `linux`, `payment-deploy`. Both deployment environments must use the same Docker engine. To register a new runner, follow repository Settings → Actions → Runners → New self-hosted runner. Configure GitHub environments `staging` and `production`; record any approval waits.

```powershell
$ErrorActionPreference = 'Stop'
gh auth status
py -3 -m pip install PyYAML==6.0.3
py -3 ci-cd-conventional/configuration.py
if ($LASTEXITCODE -ne 0) { throw 'Invalid conventional configuration' }
py -3 ci-cd-conventional/sync_workflows.py --check
if ($LASTEXITCODE -ne 0) { throw 'Run sync_workflows.py and review installed copies' }
```

If needed, authenticate with `gh auth login --hostname github.com --git-protocol https --web --scopes workflow` and `gh auth setup-git`.

Publish the reviewed control revision including the conventional folder, shared worker, `experiments/`, `scripts/` and root app. Register the workflows on the default branch and freeze a **new immutable control tag**, for example `comparison-worker-20260922-separated`. Do not move old control or application tags. These local changes have not been published automatically. [GitHub requires workflow registration on the default branch for manual dispatch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Workflow sources live in `ci-cd-conventional/workflows/`; GitHub installation copies must live in `.github/workflows/`. Edit sources, run `sync_workflows.py`, and commit both. CI checks drift. The shared mechanical worker retains its historical display name **BDI Entity Execution**; calling it does not start an agent.

## 2. Start the session and select versions

From the repository root, check `experiments/results/release-pairs/current-pair.txt`. The block reads the path automatically and trims trailing newlines. If any command fails, stop before dispatching.

```powershell
$ErrorActionPreference = 'Stop'
$ErrorActionPreference = 'Stop'
$pairFile = (Get-Content -LiteralPath experiments/results/release-pairs/current-pair.txt -Raw -ErrorAction Stop).Trim()
$pairFile
if ([string]::IsNullOrWhiteSpace($pairFile) -or -not (Test-Path -LiteralPath $pairFile -PathType Leaf)) {
  throw 'Pair file not found. Check current-pair.txt and stop here.'
}
$pair = Get-Content -LiteralPath $pairFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
foreach ($field in @('series','repository','v1_tag','v1_sha','v2_tag','v2_sha','worker_ref')) {
  if ([string]::IsNullOrWhiteSpace($pair.$field)) { throw "Incomplete pair: missing $field. Select the named pair JSON, not .json." }
}
$env:GITHUB_REPOSITORY = $pair.repository
$workerRef = $pair.worker_ref
$v1Sha = $pair.v1_sha
$v2Sha = $pair.v2_sha
$knownGood = $pair.known_good_receipt
git ls-remote --exit-code origin "refs/tags/$workerRef"
if ($LASTEXITCODE -ne 0) { throw 'Publish the control tag first' }
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Authenticate before dispatch' }
```

The pair JSON stores the new immutable application SHAs and common worker revision. Do not substitute the historical `v1` tag or prior v2 SHA: those commits lack the new version banner. Application jobs check out `release_sha`, so the source label follows deployment and rollback automatically.

Start Docker Desktop, then in a separate WSL/Ubuntu terminal:

```bash
cd ~/actions-runner-payment
docker info
docker compose version
./run.sh
```

Keep it listening; do not start another listener if the runner service already runs. Verify it is online in GitHub. Stop previous traffic and settle all remote jobs. Never run BDI and conventional trials concurrently against these environments.

## 3. Establish v1 independently of BDI

Skip this only if you have a successful live receipt for **this pair's exact new v1 SHA** from either approach for this repository/environment. A receipt proves a past deployment; step 4 still resets current state.

```powershell
$payload = @{
  release_sha = $v1Sha; scenario = 'healthy'; baseline = 'true'
  confirm_compatible_rollback = 'false'; seed = '42'
} | ConvertTo-Json -Compress
$payload | gh workflow run ci-cd.yml --repo $env:GITHUB_REPOSITORY --ref $workerRef --json
if ($LASTEXITCODE -ne 0) { throw 'Baseline dispatch failed' }
gh run list --repo $env:GITHUB_REPOSITORY --workflow ci-cd.yml --limit 5
```

Select the new run using its revision, name and timestamp; copy its ID. Do not assume another user's latest run is yours.

```powershell
$runId = 'REPLACE_WITH_BASELINE_RUN_ID'
gh run watch $runId --repo $env:GITHUB_REPOSITORY
py -3 experiments/collect.py --repo $env:GITHUB_REPOSITORY --run-id $runId
if ($LASTEXITCODE -ne 0) { throw 'Inspect incomplete baseline evidence' }
$knownGood = (Resolve-Path "experiments/results/conventional/$runId/artifacts/native-result/result/controller-result.json").Path
$baseline = Get-Content $knownGood -Raw | ConvertFrom-Json
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $v1Sha -or
    -not $baseline.verified_releases.staging.github_run_id -or -not $baseline.verified_releases.production.github_run_id) {
  throw 'Baseline is not verified'
}
$pair.known_good_receipt = $knownGood
$pair | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
$knownGood
```

Save that absolute receipt path for future sessions. Keep bootstrap/reset runs outside the measured v2 dataset; the results guide explains filtering. A simulation, screenshot or red run is not a valid receipt.

## 4. Restore BOTH environments before EVERY trial

Restore `$knownGood` from your saved path after reopening PowerShell. Confirm v1 remains compatible with retained database schema/data. Reset redeploys services, including staging PostgreSQL, without resetting database volumes.

```powershell
$payload = @{
  release_sha = $v1Sha; scenario = 'healthy'; baseline = 'false'
  known_good_receipt = (Get-Content $knownGood -Raw)
  confirm_compatible_rollback = 'true'; seed = '42'
} | ConvertTo-Json -Compress
$payload | gh workflow run ci-cd.yml --repo $env:GITHUB_REPOSITORY --ref $workerRef --json
if ($LASTEXITCODE -ne 0) { throw 'Reset dispatch failed' }
gh run list --repo $env:GITHUB_REPOSITORY --workflow ci-cd.yml --limit 5
```

Watch/collect this reset as in step 3, but retain the original `$knownGood`. Confirm the reset result is `achieved`, `release_sha=$v1Sha`, and verifies both environments. Record the reset run ID in trial notes. Do not begin v2 while reset is running.

```powershell
Invoke-RestMethod http://127.0.0.1:3001/health
Invoke-RestMethod http://127.0.0.1:3001/ready
Invoke-RestMethod http://127.0.0.1:3000/health
Invoke-RestMethod http://127.0.0.1:3000/ready
```

Refresh `/checkout` at both ports: the banner must immediately show **Payment Service v1** and `/health.appVersion` must be `v1`. No payment is needed to see the label. Health's `deploymentRunId` must match reset evidence; it is not a source SHA. Starting old containers is not a verified reset.

## 5. Manually launch one measured trial

Select any of the [11 shared scenarios](02_COMPARATIVE_EXECUTION_GUIDE.md#shared-scenarios): `healthy` (normal), `build-failure`, `test-failure`, `transient-test-failure`, `service-unavailable`, `infrastructure-failure`, `deployment-timeout`, `staging-temporary`, `staging-persistent`, `production-temporary`, `production-persistent`.

```powershell
$case = 'healthy'
$payload = @{
  release_sha = $v2Sha; scenario = $case; baseline = 'false'
  known_good_receipt = (Get-Content $knownGood -Raw)
  confirm_compatible_rollback = 'true'; seed = '42'
} | ConvertTo-Json -Compress
$payload | gh workflow run ci-cd.yml --repo $env:GITHUB_REPOSITORY --ref $workerRef --json
if ($LASTEXITCODE -ne 0) { throw 'Trial dispatch failed; no result established' }
gh run list --repo $env:GITHUB_REPOSITORY --workflow ci-cd.yml --limit 5
$runId = 'REPLACE_WITH_THIS_TRIAL_RUN_ID'
gh run watch $runId --repo $env:GITHUB_REPOSITORY
```

Alternatively use Actions → Conventional Payment CI/CD → Run workflow with identical inputs. Faults and traffic timing are automatic. Do not add manual fault traffic. Do not use **Re-run failed jobs** as a new trial; reset and dispatch a fresh run.

## 6. Observe and retain results

Open the run's stage and health jobs. Look for:

- `ENTITY test = success (attempt 2)`: one confirmed retry completed.
- `STARTED`, `PHASE`: traffic began and changed phase automatically.
- `OBSERVE production round=...`: actual telemetry observations.
- `HEALTH production = allow`: candidate health accepted.
- Rollback followed by `HEALTH rollback = allow`: v1 restored, not v2 delivered.

Successful staging/production deployments have a 60-second warmup, then at most 36 observations/180 seconds requiring two consecutive healthy samples. Temporary errors last 75 seconds; the two-minute metric window can delay recovery. Inspect actual samples rather than assuming success.

```powershell
py -3 experiments/collect.py --repo $env:GITHUB_REPOSITORY --run-id $runId
if ($LASTEXITCODE -ne 0) { Write-Warning 'Incomplete evidence retained; inspect collection.json' }
$resultDir = "experiments/results/conventional/$runId/artifacts/native-result/result"
Get-Content "$resultDir/controller-result.json" -Raw
Get-Content "$resultDir/experiment-metrics.json" -Raw
```

This collects every artifact, full GitHub logs and run metadata. Existing folders are never overwritten. Interrupted runs may lack results; `collection.json` preserves collection errors. A red workflow can correctly mean “candidate failed; v1 restored.” Follow [the results inspection guide](05_EXPERIMENT_RESULTS_GUIDE.md), record interventions/reset IDs, and restore v1 before continuing.

## 7. Pair with BDI and repeat

For paired research, run `py -3 ci-cd-conventional/configuration.py --check-bdi-parity`. Reset v1, then follow **C1** in the [BDI manual](03_BDI_MANUAL_EXECUTION_GUIDE.md) with the same case, seed, candidate, receipt and worker revision. Run every case, alternate order and predeclare repetition count. Match `protocol_key`; inspect actual fault exposure and reset evidence separately.

## Troubleshooting and scope

| Symptom | Action |
|---|---|
| Missing workflow/unknown input | Publish/register the new control revision; old tags do not acquire local changes |
| Deployment or health job queued | Check the deployment runner and environment approvals; retain queue time |
| Missing traffic/undefined metric | Inspect traffic summary and Prometheus at 9090/9091; missing data is not zero |
| Staging database still stopped | Reset must restart PostgreSQL and pass staging readiness |
| Cancelled run/lost runner | Retain evidence, settle remote jobs, inspect deployed identity, then reset |
| v2 visible after a red run | Check whether rollback executed and health verification passed |
| Security audit blocks a healthy case | Retain findings as an uncontrolled prerequisite failure; do not disable the gate |

These faults have scoped meanings: service-unavailable stops the **payment app**, infrastructure-failure stops **staging PostgreSQL**, and timeout hangs **before deployment side effects**. Build/test faults are controlled nonzero job exits. They do not demonstrate deployment API outages, host loss, network partitions or genuine source defects. Record these limitations when answering the RQ.
