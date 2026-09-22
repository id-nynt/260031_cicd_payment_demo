> ARCHIVED: consolidated into [03 BDI complete manual](../../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md). Do not use these superseded commands for new runs.

# Optional BDI manual injection and goal demonstrations

These are alternative diagnostic demonstrations, not sequential study steps. For routine traffic experiments use [manual 03, route 3B](../../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#3b-gui-with-scripted-traffic); for matched research use route 3A.

Before choosing exactly one procedure below, complete manual 03 steps 1 and 2. After it finishes, use manual 03 steps 4 and 5 to preserve evidence and restore both environments. Legacy labels C1-C5/D1 are retained only to identify these optional recipes. F2 refers to the main guide troubleshooting appendix.

For these optional recipes, after the launch returns, save the selected trial so main-guide step 4 can find it:

```powershell
[pscustomobject]@{ campaign = [System.IO.Path]::GetFullPath($candidateDir); route = 'manual'; scenario = 'manual'; pair_file = $pairFile } | ConvertTo-Json | Set-Content experiments/results/current-bdi-trial.json -Encoding utf8
```

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

**Finish:** record main-guide step 4, then close the finished console. Before another comparison, use main-guide step 5 and restore v1. If the campaign stopped, inspect its result rather than assuming production changed.

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
```

Then run this execution block unchanged:

```powershell
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

**Finish:** main-guide step 4, then `Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue`. Preserve the fault file as evidence. Repeat B before the next case; a failed production attempt may leave staging at v2.

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
- An `unavailable` measurement's numeric zeros are placeholders, not proof of zero errors or zero latency. If normal traffic is repeating but measurements remain unavailable beyond the export/scrape delay, inspect Prometheus rather than assuming success (see main-guide troubleshooting).
- If the campaign already ended or rollback began, new traffic cannot resume that campaign. Finish recording it, reset with main-guide step 5 and start a new C3 run.

**Expected results:**

- Error traffic produces HTTP 503; normal traffic produces HTTP 201.
- The agent actually observes unhealthy production before you remove the cause; otherwise this is not a demonstrated fault-recovery experiment.
- It rechecks rather than redispatching production. If health clears within the count/time budget, two consecutive healthy samples allow `achieved / not_needed`; production stays v2.
- Current `config/controller_policy.yaml` maximum: 36 observations, five seconds apart, within 180 seconds from the first observation. This is a maximum, not a mandatory wait; two healthy observations can finish quickly.
- If errors clear too late or another metric remains unhealthy, rollback is a valid outcome. Record it, rather than claiming temporary recovery succeeded.

**Finish:** stop normal traffic after the final result, perform main-guide step 4, then use main-guide step 5 to reset. If you missed the pause and the campaign already succeeded, it cannot be faulted retrospectively: reset and start a fresh campaign.

### C4. Persistent production error traffic, then rollback

**Start:** repeat main-guide steps 1-2. Prepare the two extra terminals as in C3; do not reuse the previous campaign directory.

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

**Finish:** main-guide step 4, then main-guide step 5 restores both environments before the next comparison. If recovery is failed/unverified, inspect its job and telemetry before proceeding.

**Staging variant:** use `staging.experiment_mode=request_faults`, `--pause-after staging`, and port `3001` in the traffic block. The pause event must name staging. Sustained unhealthy staging stops promotion; production stays v1, with no production rollback needed.

### C5. Production job failure after deployment, then rollback

**Start:** main-guide steps 1-2 complete. This deterministic case avoids traffic timing and tests recovery after the production worker has changed the app.

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

**Finish:** main-guide step 4, then use main-guide step 5 for the next experiment. Remove the fault environment setting before restoring v1.

## D. Optional goal experiment

### D1. Request an actual staging failure as the achievement

**Start:** main-guide steps 1-2 complete. This changes the goal, not just the fault. Use a separate generated project to preserve normal deployment goals.

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

**Finish:** main-guide step 4, remove the fault setting and omit this `--project-dir` for normal experiments. To test an unmet failure goal, repeat this project's launch with a fresh directory and no fault plan: healthy staging should end with goals unmet rather than deliberately failing itself. Restore v1 afterward if staging changed.

