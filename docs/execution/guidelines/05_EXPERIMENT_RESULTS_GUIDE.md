# Inspect and compare experiment results

The local file `experiments/results/release-pairs/current-pair.txt` contains the path of the selected release-pair JSON. The execution guides read that path automatically. In the JSON, check `v1_sha`, `v2_sha`, `worker_ref` and `known_good_receipt`; the last field must point to the successful v1 baseline result before measured trials. A null receipt means it has not been linked, even if deployment succeeded. The pointer, pair JSON and referenced run directories are Git-ignored; back them up together. The pointer identifies a selection, not current deployment state.


Read this after either manual. A candidate deployment, a safe stop, and restoration of v1 are different outcomes. Keep raw evidence even when the experiment fails, is cancelled, or lacks enough evidence to classify.

For the labelled app pair, record `/health.appVersion` and a refreshed checkout screenshot alongside `deploymentRunId`, the receipt and source SHA. The page banner and startup log show v1/v2 immediately, but a label alone does not uniquely identify a commit or prove health. New app commits require a new baseline receipt and pair selection; follow [the returning-user guide](03_BDI_MANUAL_EXECUTION_GUIDE.md#a4-create-or-refresh-the-version-pair).

## 1. Find the trial and preserve the whole bundle

| Approach | Location | First files to inspect |
|---|---|---|
| BDI comparative C1 | `experiments/results/bdi/<trial>/` | `controller-result.json`, `experiment-metrics.json`, `controller-journal.jsonl`, `experiment-events.jsonl` |
| BDI supporting evidence | Sibling `<trial>-experiment/`, `<trial>-traffic/`, `<trial>-traffic-<stage>/` | `plan.json`, `controller-console.log`, `faults.properties`, traffic `summary.json` and request/transition logs |
| BDI repair evidence | `<trial>/operation-<operation UUID>/` | `receipt.json` and `download.log`; result `candidate_repair_operations` maps operations to GitHub runs |
| BDI GUI/manual C2-C7 and baselines | Explicit `$candidateDir`/`$baselineDir` printed in the manual | Result/journal plus automatic controller-console.log; retain fault files, traffic output and optional agent-mind screenshots |
| Conventional | `experiments/results/conventional/<run-id>/` | `github-run.json`, `github-run.log`, `collection.json` |
| Conventional result | `artifacts/native-result/result/` beneath that directory | `controller-result.json`, `experiment-metrics.json`, `experiment-events.jsonl`, `github-jobs.json` |
| Conventional supporting evidence | `artifacts/native-prepare/`, `artifacts/native-staging/`, `artifacts/native-production/`, `artifacts/native-rollback/`, and sibling `result-experiment/`, `result-traffic/` | Plan, frozen config/input snapshots, gate decisions, complete traffic traces |
| Conventional repair evidence | `artifacts/native-production/health/` | `diagnose-receipt.json`, `restart-receipt.json` and gate events |

Download conventional evidence with `py -3 experiments/collect.py --repo OWNER/REPO --run-id RUN_ID`. It refuses existing directories. To retry collection after a transient download error, use a new `--output` folder and retain the original failure; do not include both copies as two trials in the analysis tree. Download before artifact retention expires. Results/reports are Git-ignored: archive them deliberately outside the working tree as well.

For BDI, manual **D** automatically selects all acknowledged GitHub execution IDs from the journal and downloads their logs/metadata into a fresh `github-evidence-*` folder inside the campaign. Use that block; do not manually copy IDs or terminal JSON.

BDI manual D reloads `$candidateDir` from `experiments/results/current-bdi-trial.json`, saved automatically by C1/C2 and manual scenarios. Console output is already captured beside the plan. New GUI runs also save controller-console.log in the campaign folder. Manually retain agent-mind screenshots only if needed; older runs without a console log require manual text capture while MAS remains open. Screenshots supplement the JSON evidence; they do not replace it.

New schema-2 plans contain `traffic_targets`; metrics expose `traffic_by_entity` and aggregate request/error totals across those clients. Only reached gates require normal traffic. An injected-traffic scenario that never reaches its fault target is flagged. Legacy plans retain legacy validation; do not mix old and new control revisions in a matched pair. A stage marker (`BDI_STAGE`) is a log annotation, not an execution attempt.

For launcher failures, inspect `<trial>-experiment/launch-status.json` and `traffic-<entity>-console.log`. Native traffic console logs reside in each health artifact. Preserve incomplete evidence and reconcile remote work before retrying. Re-running the read-only metric extractor does not repair missing traffic or recreate a lost result.

## 2. Read outcomes before metrics

Choose the existing result directory in this separate input block (for BDI, manual D already sets `$candidateDir`):

```powershell
$resultDir = (Read-Host 'Paste the result directory from the table, without quotes').Trim()
```

Then inspect it:

```powershell
if (-not (Test-Path -LiteralPath (Join-Path $resultDir 'controller-result.json'))) { throw 'Select an existing result directory.' }
$r = Get-Content "$resultDir/controller-result.json" -Raw | ConvertFrom-Json
$r | Select-Object mode,mechanism,outcome,recovery_outcome,release_sha,known_good_sha
$r.executions
$r.telemetry
$r.verified_releases
Get-Content "$resultDir/experiment-metrics.json" -Raw
```

| Evidence | What it demonstrates |
|---|---|
| `mode=github`, `outcome=achieved`, production `verified_releases.release_sha` equals candidate | Live v2 delivery passed execution and health gates |
| `outcome=stopped`, `recovery_outcome=restored`, `telemetry.rollback=allow` | Candidate failed; recovery was verified. This is not candidate success |
| Build/test failure and no production action | Promotion was blocked; use reset/deployed identity to establish production stayed at v1 |
| `recovery_outcome=failed` or `unknown` | No proven restoration; inspect remote execution and current service |
| Missing result, terminal event or artifacts | Incomplete/unclassified trial, never a successful deployment |
| `eligible_for_comparison=false` | Automatic validation found a problem; retain it in the exclusion ledger |

The eligibility flag is only a screen. Review the injected fault's real exposure and reset before accepting a trial. `protocol_expectation_met` compares a result with the expected scenario response; it is not independent proof of correctness and is not a reason to discard an unexpected result.

## 3. Inspect the exact observations, retries and fault

```powershell
Get-Content "$resultDir/experiment-events.jsonl" |
  Select-String 'action_started|action_finished|diagnosis_|repair_|observation|health_accepted|recovery_started|campaign_finished'
# BDI only:
Get-Content "$resultDir/controller-journal.jsonl" |
  Select-String 'bdi_decision|telemetry_measurement|bdi_recovery_decision|controller_finished'
```

Read JSONL records in timestamp order. `action_started.attempt > 1` proves another execution was requested; pair it with `action_finished.status`. A belief mentioning retry is not enough. `observation` records data freshness, readiness, availability, error rate and p95; missing telemetry is not a healthy zero. `health_accepted.decision=allow` is the gate's acceptance. Compare the first adverse production event with the recovery event and accepted rollback observation.

| Scenario | Evidence required beyond the plan |
|---|---|
| `candidate-stopped` | Successful original production job, stopped matching app + ready dependency diagnosis, one restart, same container/deployment ID, normal probes, two new accepted samples and final v2 delivery |
| `candidate-restart-fails` | Stopped candidate diagnosis, one failed restart receipt, rollback to verified v1 and accepted rollback health; candidate delivery false |
| `healthy` | Successful real payment traffic and accepted staging/production gates |
| `build-failure`, `test-failure` | Worker log **Controlled experiment failure**, nonzero step result and blocked downstream jobs |
| `transient-test-failure` | **Controlled transient failure** on attempt 1, actual tests on attempt 2 |
| `service-unavailable` | **Make deployment service unavailable**, failed readiness and rollback verification |
| `infrastructure-failure` | **Stop deployment database infrastructure**, failed staging readiness and no production action |
| `deployment-timeout` | **Controlled deployment timeout before side effects**, actual terminal timeout and bounded retry |
| Temporary/persistent traffic faults | Traffic requests with injected failures, phase transitions and unhealthy correlated observations; temporary cases must also show the normal phase |

Inspect each traffic `summary.json`: `requests`, `successful`, `injected_errors`, `unexpected_responses`, `network_errors`, `stop_reason`. Retain the full request/transition files beside it. Fault selection alone does not establish injection, and an unrelated audit failure before the target stage is not exposure to the intended deployment fault.

For BDI compare `BDI_DECISION` and agent beliefs with the journal. For conventional compare the `needs`/conditions in the frozen workflow and GitHub job/step statuses. A tolerated intermediate job failure allows conventional retry handling; only the final evidence certifies delivery.

## 4. Annotate reset and interventions

Keep `trial-notes.json` beside the plan with repetition number, execution order, reset run/campaign ID, visible v1/v2 checks, database-reset policy, runner identity, unexpected events and reviewer classification. Record actual start/end times and approval/queue waits. Record intervention entries in sibling `*-experiment/interventions.json`:

```json
[{"timestamp":"2026-09-22T01:00:00Z","action":"restarted runner","reason":"runner disconnected"}]
```

Use `[]` only after explicitly confirming no intervention. Missing entries mean unknown, not zero. The conventional collector's `--no-interventions` flag records that operator attestation. Re-extract metrics to include annotations; original downloaded server metrics can be retained as a separate copy first.

## 5. Produce comparison outputs

Re-extract one annotated trial if needed:

```powershell
py -3 experiments/experiment_metrics.py "$resultDir"
```

Use the actual v2 SHA to exclude bootstrap and reset releases:

```powershell
$report = 'experiments/reports/' + (Get-Date -Format yyyyMMdd-HHmmss-fff)
py -3 experiments/summarize.py --root experiments/results --candidate $v2Sha --output "$report"
```

`trials.csv` keeps every recorded metric row, including excluded rows and evidence paths. `summary.json` groups by case/mechanism and lists incomplete downloads plus protocol groups. Empty denominators produce `null`, not 0% or 100%. Use a curated analysis tree containing each trial once; filter other worker revisions/pilot trials before final analysis. Manually register interrupted BDI trials without metrics in the study ledger; the report cannot discover trials whose files were never recorded.

| Metric | Definition/interpretation |
|---|---|
| Delivery rate | `candidate_delivered` / eligible trials, per case and mechanism |
| Restoration rate | `service_restored` / eligible trials that attempted rollback; report that denominator explicitly |
| Recovery time | First recorded adverse production event → accepted rollback; unknown when timestamps are absent |
| Runtime | Recorded campaign start → finish; native preparation/setup before the start event is excluded |
| Retries | Started execution attempts numbered above 1, excluding rollback |
| Repair attempts / diagnoses | `repair_attempts` counts started restarts; `diagnoses` counts diagnostic operations, separately from retries |
| Candidate repair rate | `candidate_repaired` among eligible trials with `repair_attempts > 0`; summary includes denominator |
| Candidate repair time | `candidate_repair_seconds`: restart request to post-repair health acceptance, distinct from v1 rollback recovery time |
| Repair failures | Restart actions with status other than `executed`; an executed but unhealthy repair is identified by false `candidate_repaired`, not this action-status count |
| Recovery by retry/recheck | Candidate delivered after the relevant recorded failure; inspect traces separately from v1 restoration |
| Interventions | Explicit operator annotations; absence is unknown |

Match `protocol_key` across BDI and `github-actions`. It covers planned case, seed, candidate/baseline, worker, policy, contract/input hashes and traffic profiles. Balanced counts do not establish one-to-one trial pairing: use repetition/order notes. Matching keys do not prove equal database state or actual fault duration.

Native job times and BDI adapter-observed times have different scheduling/polling boundaries. Report whole-trial times and raw GitHub timestamps separately; do not interpret summed entity time as billed cost. State all exclusions and incomplete trials alongside eligible rates. Equal outcomes are plausible with the matched recovery policy; do not weaken the conventional baseline or count rollback as deployment success to manufacture BDI superiority.
