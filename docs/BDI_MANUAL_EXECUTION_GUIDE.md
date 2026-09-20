# Manual v1-to-v2 BDI experiment

The experiment starts with a **verified, deployed v1 that stays running**. You prepare v2, start Jason, watch its decisions and GitHub jobs, retain the results, and restore v1 for another run. These are manual steps, not an end-to-end script.

| Phase | What you do |
|---|---|
| 1 | Save and verify stable deployed v1 |
| 2 | Open the deployed app and keep it running |
| 3 | Change the app visibly and save v2 |
| 4 | Start the BDI agent for v2 |
| 5 | Watch decisions, workflow executions and app updates |
| 6 | Run healthy, transient-failure and persistent-failure scenarios |
| 7 | Record results and decision evidence |
| 8 | Restore v1 and repeat |

Before phase 1, complete [one-time setup](BDI_SETUP.md): Docker, runner, credentials, publication of the updated worker, and persistent artifact generation. Setup/rehearsal is separate from the real experiment. Run PowerShell commands in the current controller checkout. Keep that checkout current; selecting a release SHA does not require switching it back to v1.

## 1. Save and verify stable deployed v1

Actions:

- Preserve the existing `v1` tag. A tag records source; it does not prove deployment health.
- If you already have an achieved live v1 receipt, set `$knownGood` to its `controller-result.json` and skip the baseline launch below.
- Otherwise run one baseline campaign to deploy and verify v1. This is preparation for the v2 experiment, not something to repeat before every command.

```powershell
$v1Tag = 'v1'
$v1Sha = git rev-list -n 1 $v1Tag
if ($LASTEXITCODE -ne 0 -or -not $v1Sha) { throw 'Select an existing stable source tag first' }
$env:BDI_RELEASE_SHA = $v1Sha
# Keep BDI_WORKFLOW_REF set to the updated worker tag selected during setup.
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$baselineDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-v1'
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir $baselineDir
```

When the campaign finishes, close the MAS Console to release Gradle and return to PowerShell. Then:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw | ConvertFrom-Json
$baseline | Select-Object mode, outcome, release_sha, recovery_outcome
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $v1Sha) {
    throw 'Baseline not verified; inspect the journal before continuing'
}
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$baseline.verified_releases
```

**Expected:** build → test → security → staging → health verification → production → health verification → `achieved/not_needed`. Staging and production containers are running. Retain this receipt for rollback. If GitHub returns 403, no baseline was deployed; follow setup troubleshooting.

## 2. Open the deployed app and keep it running

```powershell
Invoke-RestMethod http://localhost:3001/health
Invoke-RestMethod http://localhost:3001/ready
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/ready
```

Open production `http://localhost:3000/checkout`, and optionally staging `http://localhost:3001/checkout`. Make a fake payment and inspect its receipt. Keep Docker, the runner and these browser tabs open. Prometheus is production `http://localhost:9090`, staging `http://localhost:9091`.

**Expected:** v1 is usable and `/ready` succeeds. Match `/health.deploymentRunId` with the receipt's verified execution ID; `/health` does not expose a Git SHA. Closing the BDI console does not stop containers. The separate local rehearsal app on port 3002 is not this deployment. If containers are stopped, restore/verify v1 through a campaign; clicking Play alone does not establish a new verified baseline.

## 3. Change the app visibly and save v2

Create a candidate branch from the **current repaired revision**, so it includes the new app fault capability and current framework. Do not switch this controller checkout back to the old v1 source. For this first experiment, change the receipt heading in `src/ui.ts` to `Payment receipt — v2`; avoid database migrations.

```powershell
$sessionName = 'manual-' + (Get-Date -Format yyyyMMdd-HHmmss)
$candidateBranch = "experiment/$sessionName-v2"
git status --short
git switch -c $candidateBranch
# Edit the receipt heading in src/ui.ts, then:
npm run lint
npm test
npm run build
git add src/ui.ts
git diff --cached
git commit -m 'Show v2 on the payment receipt'
git push -u origin $candidateBranch
$v2Tag = "$sessionName-v2"
git tag $v2Tag
git push origin "refs/tags/$v2Tag"
$v2Sha = git rev-list -n 1 $v2Tag
```

Run each command after checking the previous result. Preserve unrelated edits; do not use `git add .`.

**Expected:** published immutable v1 and v2 selections. Production still serves v1. A push may run validation CI; it does not start a BDI deployment. Keep `BDI_WORKFLOW_REF` pinned to the updated worker tag from setup, independently of `$v1Tag`/`$v2Tag`. App-only changes do not require agent regeneration.

## 4. Start the BDI agent for v2

Confirm v1 remains compatible with the retained database; rollback restores source, not database contents.

```powershell
$env:BDI_RELEASE_SHA = $v2Sha
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-v2-healthy'
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

**Expected:** Jason loads the existing agent, activates `workflow_active`, and immediately selects build. Java dispatches only the selected entity. Do not separately start Jason or click GitHub's Run workflow. Every campaign uses a new evidence directory; omit `--artifacts-dir` if you prefer the automatically unique name printed at startup.

## 5. Watch decisions and execution

| View | Expected evidence |
|---|---|
| MAS Console | `BDI_DECISION=run`, `retry`, `wait_reconsider`, `rollback`; final outcome |
| Jason mind inspector, URL printed at startup | Entity/attempt beliefs, retry budget, goals and health counts |
| GitHub Actions | One workflow run per selected action; other entity jobs skipped |
| Runner / Docker Desktop | Staging and production stacks update only when selected |
| Browser and Prometheus | New receipt wording and execution-correlated metrics |

**Expected:** production remains v1 while build/test/security/staging are evaluated. After production deployment, refresh the browser and make a new payment to see v2 on its receipt. Physical deployment happens before BDI finishes health verification; v2 visible in the browser alone is not achievement.

At completion, the console prints the outcome and result path. **Gradle at 75% while the GUI is open is not deployment progress.** Inspect beliefs, close the console, then read the result. No additional jobs run after completion; BDI is not a permanent monitoring daemon.

## 6. Run one scenario per campaign

Restore v1 using phase 8 when you need the same starting state. Keep the same candidate SHA, worker tag, goals and thresholds across comparisons. Create one fault-control file:

```powershell
New-Item -ItemType Directory -Force bdi-cicd-framework/runs/manual-control | Out-Null
$faultFile = Join-Path (Resolve-Path bdi-cicd-framework/runs/manual-control).Path 'faults.properties'
$env:BDI_EXECUTION_PLAN = $faultFile
$env:BDI_RELEASE_SHA = $v2Sha
```

The file is read before each dispatch. It changes experimental inputs, not the generated policy. Replace its contents for each scenario; use a new `$candidateDir` and the phase 4 launch command, **without removing `BDI_EXECUTION_PLAN`**.

| Scenario | File content | Expected result |
|---|---|---|
| Healthy v2 | Empty file | `achieved/not_needed`; production v2 |
| One temporary test failure | `test.1.failure_mode=transient_failure` | First test fails, Jason retries once, then continues |
| Persistent transient test failure | `test.failure_mode=transient_failure` | Two test attempts, then `stopped/not_attempted`; production stays v1 |
| Deterministic job failure | `build.failure_mode=force_failure`, or `test...`, or `security...` | One failed execution, stop; unchanged code is not retried |
| Temporary production execution failure | `production.1.failure_mode=transient_failure` | Failure before deployment, one retry, then verify v2 |
| Persistent production health fault | `production.force_error_rate=1` | Reobserve to budget, rollback once, verify v1; `stopped/restored` |

Example selection and launch:

```powershell
Set-Content $faultFile 'test.1.failure_mode=transient_failure' -Encoding ascii
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-test-retry'
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $candidateDir
```

### Inject temporary or continuous error traffic manually

Use the v2 source that contains `request_faults`. Set production to accept deliberate faults on individual fake-payment requests, then pause after deployment so you can start traffic before BDI observes it:

```powershell
Set-Content $faultFile 'production.experiment_mode=request_faults' -Encoding ascii
$candidateDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-traffic'
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --pause-after production --pause-ms 60000 --artifacts-dir $candidateDir
```

Wait for `controller_pause` with `after_entity=production`. In **another PowerShell window at this checkout**, confirm `/health` reports `experimentMode=request_faults`, then:

```powershell
$env:PAYMENT_BASE_URL = 'http://localhost:3000'
npm run traffic:experiment -- inject_error 6 --continuous
```

**Persistent scenario:** keep error traffic running through the observation budget. Expect `wait_reconsider`, then rollback. Stop the traffic command with Ctrl+C when rollback begins. The worker creates healthy verification traffic for restored v1.

**Temporary scenario:** send errors for about 15–20 seconds, Ctrl+C, then immediately send normal traffic:

```powershell
npm run traffic:experiment -- normal 6 --continuous
```

**Expected:** requests now succeed; the two-minute Prometheus error window gradually clears. Jason continues observing, accepts two consecutive healthy observations within the budget, and finishes `achieved/not_needed`. Stop normal traffic after completion. If the fault clears too late, rollback is the correct result—do not extend limits mid-experiment.

The policy allows at most 36 observations and 180 seconds from the first observation, with five seconds between requests. Execution retry count is separate: one additional execution for a confirmed transient failure of a retry-safe job. For a staging traffic experiment, use `staging.experiment_mode=request_faults`, `--pause-after staging` and port 3001; persistent bad staging stops promotion and leaves production v1 untouched.

## 7. Record results and decisions

Close the MAS Console, then:

```powershell
$result = Get-Content "$candidateDir/controller-result.json" -Raw | ConvertFrom-Json
$result | Select-Object mode, outcome, recovery_outcome, release_sha, known_good_sha
$result.executions
$result.telemetry
Get-Content "$candidateDir/controller-journal.jsonl" |
    Select-String 'bdi_decision|telemetry_measurement|observation_clock|bdi_recovery_decision|controller_finished'
```

**Expected:** the complete campaign directory contains decisions, observations, execution IDs, GitHub run references, source hashes and snapshots of the persistent agent/model. Record traffic start/stop times and scenario settings alongside it. Keep `$knownGood` pointing to v1 for comparisons. `stopped/restored` means v1 restoration succeeded; it does not mean v2 delivery succeeded. `unknown/unresolved` means reconcile before another campaign.

## 8. Restore v1 and repeat

Stop any traffic generator, close the old console, and ensure no execution is unresolved. Clear fault settings and select the original v1 SHA; do not reset Git, move tags, or delete evidence.

```powershell
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
$env:BDI_RELEASE_SHA = $v1Sha
$resetDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-restore-v1'
py -3 -B bdi-cicd-framework/run_controller.py --gui --known-good $knownGood --confirm-compatible-rollback --artifacts-dir $resetDir
```

**Expected:** both staging and production return to verified v1, and the reset campaign is achieved. Automatic rollback restores production only; this reset restores both environments. Database records remain. Keep the containers running, set `BDI_RELEASE_SHA=$v2Sha`, choose the next phase 6 scenario, and use a fresh evidence directory.

For failures outside the intended experiment—403, stopped containers, unresolved dispatch or stale artifacts—use [setup and troubleshooting](BDI_SETUP.md). Do not treat those as successful fault experiments.
