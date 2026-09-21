# Manual conventional experiment: deploy v1 to v2

Use the **same repository, v1/v2 application commits, Docker environment and runner** as BDI. The entry point is [`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml). GitHub's job dependencies and scripts choose what happens next; Jason is not started.

| Phase | Steps | When |
|---|---|---|
| One-time setup | 1. Publish the experiment workflows; 2. Check tools and select versions | Once for this framework revision |
| Before each trial | 3. Start Docker/runner; 4. Check and restore v1 | Every trial, including the paired BDI trial |
| Real experiment | 5. Select a scenario and launch; 6. Observe; 7. Save evidence | Once per scenario/repetition |
| Repeat | 8. Reset, then run the same case with BDI | Between every trial |

## 1. Publish the experiment revision once

**Start:** repository maintainer, in GitHub and your normal review/publication process.

**Actions:** publish the new `ci-cd.yml`, `conventional-entity.yml`, updated `entity-execution.yml`, scripts and framework files together. Register the workflows on the default branch, then create a **new immutable worker tag** for that published revision. Example name used below: `comparison-worker-20260921`. Do not move existing worker, v1 or v2 tags. Publication is a separate manual action; the development changes have not been pushed or deployed for you.

- The workflow revision supplies orchestration and fault controls.
- `release_sha` supplies application code, so the original v1/v2 remain usable.
- Deployment uses `workflow_dispatch` only; an ordinary push does not deploy through this workflow.
- The existing validation workflow may still run tests on pushes/PRs.
- Both approaches must select this same **new** worker revision. `bdi-worker-20260921-052412` lacks the new fault controls.

**Expected results:** GitHub → Actions lists **Conventional Payment CI/CD** and **BDI Entity Execution**. The new tag exists remotely. GitHub requires a manually dispatched workflow to exist on the default branch; see [GitHub's manual-run instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

**Cleanup:** none; retain all old release tags and evidence.

## 2. Check tools and select fixed versions

**Start:** PowerShell in `C:\NHI\2026_IT-Project\260031_payment-repair`. Finish BDI guide A1-A3 if this computer is new.

**Actions:** after step 1, adjust the new worker tag below if you chose another name:

```powershell
$ErrorActionPreference = 'Stop'
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$workerRef = 'comparison-worker-20260921'
$env:BDI_WORKFLOW_REF = $workerRef
$knownGood = (Resolve-Path 'bdi-cicd-framework/runs/20260921-055346-143-v1/controller-result.json').Path
$baseline = Get-Content $knownGood -Raw | ConvertFrom-Json
$v1Sha = $baseline.release_sha
$v2Sha = (git rev-parse 'manual-20260921-055936-v2^{commit}').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Resolve the existing v2 tag first' }
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved') { throw 'Use a verified live v1 receipt' }
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Complete gh auth login first' }
git ls-remote --exit-code origin "refs/tags/$workerRef"
if ($LASTEXITCODE -ne 0) { throw 'Publish the new worker revision before running either approach' }
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Resolve project artifact consistency before experimenting' }
```

- Select the existing verified v1 receipt and immutable v2 application revision.
- Check authentication without displaying a token.
- Verify that the selected new workflow tag is published.
- Validate persistent project artifacts; runtime never regenerates them.

**Expected results:** authentication succeeds, a remote tag SHA is printed, and `Project artifacts are consistent`. The old receipt remains valid as a known-good application source. If your baseline receipt is elsewhere, change that one path.

**Cleanup:** none. Repeat this step after reopening PowerShell; variables do not survive a new terminal.

## 3. Start Docker and the runner before every trial

**Start:** Docker Desktop, then a separate WSL/Ubuntu terminal.

```bash
cd ~/actions-runner-payment
./run.sh
```

- Start the existing runner; do not register another runner.
- Keep this terminal and Docker Desktop open until the trial finishes.

**Expected results:** terminal says **Listening for Jobs**; GitHub → Settings → Actions → Runners shows **Idle/Online** with `linux` and `payment-deploy` labels. Hosted jobs perform build/test/security; your runner deploys and observes the app. It needs Docker Compose, outbound access for setup actions, and access to localhost ports 3000/3001/9090/9091.

**Cleanup:** do not close it during a run. Never run BDI and conventional trials simultaneously against these environments.

## 4. Check and restore v1 before every trial

**Start:** browser and PowerShell. Complete BDI guide **B3-B4** to check app identities and restore **both environments** to the verified v1 source if needed. Those are common preparation steps, not a measured conventional trial. After that guide's environment setup, reselect the new worker:

```powershell
$workerRef = 'comparison-worker-20260921'
$env:BDI_WORKFLOW_REF = $workerRef
Invoke-RestMethod http://127.0.0.1:3001/health
Invoke-RestMethod http://127.0.0.1:3000/health
Invoke-RestMethod http://127.0.0.1:3000/ready
```

- Confirm v1 through the successful restoration receipt and its deployment identity.
- Check staging and production reachability; `/health` reports execution identity, not a source SHA.
- Keep the deployed app running. Clicking Play on old containers is not proof that v1 was restored.

**Expected results:** production checkout at `http://localhost:3000/checkout` displays v1, readiness succeeds, and restoration evidence identifies `$v1Sha`. No previous traffic client or workflow is running.

**Cleanup:** stop old traffic clients. For the database-failure case, restoration must also restart the staging database; verify staging `/ready` before continuing. Keep database volumes; record that test data is retained rather than claiming identical database snapshots.

## 5. Choose one scenario and launch the conventional pipeline

**Start:** same PowerShell. Choose one of the **11 shared scenarios** in the [comparison guide](BDI_COMPARATIVE_EXECUTION_GUIDE.md#shared-scenarios). For the first pilot use `healthy`.

```powershell
$case = 'healthy'
$payload = @{
    release_sha = $v2Sha
    scenario = $case
    known_good_receipt = (Get-Content $knownGood -Raw)
    baseline = 'false'
    confirm_compatible_rollback = 'true'
    seed = '42'
} | ConvertTo-Json -Compress
$payload | gh workflow run ci-cd.yml --repo $env:GITHUB_REPOSITORY --ref $workerRef --json
if ($LASTEXITCODE -ne 0) { throw 'Dispatch failed; no experiment result has been established' }
gh run list --repo $env:GITHUB_REPOSITORY --workflow ci-cd.yml --limit 5
```

- `$case` controls fault type, target stage and traffic profile. Change only this value for the next scenario.
- `$v2Sha` keeps the candidate version fixed across both approaches.
- The receipt identifies a previously verified v1 for rollback; compatibility confirmation concerns retained database schema/data.
- `gh workflow run` manually starts **one** complete conventional pipeline. No agent command is needed.
- Normal traffic starts automatically at each staging/production observation gate; the scenario replaces it with fault traffic at its target. Do not add manual fault traffic to a scripted trial.

**Expected results:** a new **Conventional Payment CI/CD** run named `conventional-<case>-<sha>`. Build → test → security → staging → staging health → production → production health appear as jobs. Retry and rollback jobs may be skipped when unnecessary.

**Alternative — GitHub web:** Actions → Conventional Payment CI/CD → Run workflow; select the published workflow revision, enter the full candidate SHA, case and seed, paste the contents of the verified v1 JSON receipt, leave `baseline` false and confirm compatible rollback. Submit once. The PowerShell method avoids pasting a long receipt.

**Cleanup:** wait for a terminal result. Do not click **Re-run failed jobs** for a new experiment: reset v1 and create a fresh run instead.

## 6. Observe the selected scenario

**Start:** GitHub → Actions → your run; browser tabs for staging/production checkout.

**Actions:** open the current job, then **Observe health with bounded rechecks** when present.

- `ENTITY test = success (attempt 2)` means a confirmed transient execution was retried once.
- Traffic prints `STARTED`, `PHASE 1`, then subsequent phases automatically. You do not need to find `controller_pause` in a MAS Console.
- `OBSERVE production round=...` records a fresh measurement/recheck.
- `HEALTH production = allow` means the telemetry gate accepted the candidate.
- Production fault containment runs `rollback`, then `rollback_health`. Restoration is verified separately from candidate delivery.

**Expected results:** use the scenario table. Healthy/temporary-recovery cases can deliver v2; persistent production faults should restore v1. Build/test/staging failures leave production at v1. A correctly contained failed candidate is still a failed deployment, so a red workflow can be the expected experiment result.

**Timing:** queues/downloads/builds vary. Each staging/production traffic gate has a 60-second warmup, then up to 36 observations/180 seconds, requiring two consecutive healthy observations. Temporary faults last 75 seconds, then normal traffic continues so the two-minute metrics window can clear. No promise that every temporary run recovers: inspect actual samples and timing.

**Cleanup:** traffic stops at the end of its observation gate. Confirm its summary exists; a crashed client does not establish a valid fault trial.

## 7. Save evidence and compare

**Start:** GitHub run summary → Artifacts. Copy the run ID from the URL into `$runId`:

```powershell
$runId = 'REPLACE_WITH_THIS_RUN_ID'
$evidenceDir = "bdi-cicd-framework/runs/native-$runId"
gh run download $runId --repo $env:GITHUB_REPOSITORY --dir $evidenceDir
if ($LASTEXITCODE -ne 0) { throw 'Evidence download failed' }
Get-Content "$evidenceDir/native-result/result/controller-result.json" -Raw
Get-Content "$evidenceDir/native-result/result/experiment-metrics.json" -Raw
```

- Download `native-prepare`, gate/traffic artifacts and `native-result` into a new directory.
- Read `outcome`, `recovery_outcome`, `verified_releases` and metric validation issues.
- Keep failed/incomplete trials and human interventions; do not retain only successful runs.

**Expected results:** result JSON, common event JSONL, GitHub job timings, configuration snapshots, traffic requests/transitions and metrics. The native run has mechanism `github-actions`. The old Java comparator has mechanism `conventional`; do not mix these baselines.

**Cleanup:** keep all evidence. Restore v1 using step 4 before the next trial.

## 8. Run the paired BDI trial

**Start:** after restoring v1, follow BDI guide **C6** with the **same case, seed, candidate, receipt and new worker tag**. Repeat all 11 cases for both mechanisms and alternate order across repetitions.

**Expected results:** BDI produces agent decisions and local campaign evidence; conventional produces GitHub DAG/gate logs. Matching `protocol_key` means planned inputs match, not that actual fault exposure, database state or queue conditions were identical.

**Cleanup:** reset v1 after each trial. You do not need another v2 commit unless the application changes.

## Troubleshooting

- **Workflow missing / dispatch 404:** publish/register the new workflow on the default branch; select its new tag. A local file is not a published workflow.
- **Unknown failure_mode / unexpected input:** the old worker tag is selected. Reselect the new tag in both approaches.
- **Queued at staging:** verify the existing Linux runner is online and idle. Do not start a second campaign to work around a queue.
- **v2 remains after a stopped run:** inspect whether production was reached and recovery verified. Never infer rollback merely from a red workflow.
- **No current traffic / telemetry unknown:** missing measurements do not prove the app is broken. Inspect the traffic summary, Prometheus and gate reasons. Insufficient delivery evidence blocks certification.
- **Interrupted native run:** inspect/cancel or wait for all its remote jobs, inspect containers, then reset. `run_controller.py --reconcile-only` settles BDI dispatch state; it does not resume a native GitHub workflow.
- **Artifact missing after cancellation/runner failure:** classify the trial as incomplete; do not count it as a successful recovery.
