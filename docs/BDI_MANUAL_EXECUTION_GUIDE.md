# Payment BDI manual experiment

Run commands from the repository root. PowerShell examples use Python 3.12, PyYAML and JDK 21+; on Linux use `python` and `bash ./gradlew` instead of `py -3` and `gradlew.bat`.

## 1. Review the payment configuration

Actions:

- Read `bdi-cicd-framework/models/01_pipeline.yaml`: normal work is build, test, security, staging, production. Rollback is a separate recovery capability.
- Read `models/02_goal.yaml`: production delivery requires successful prerequisites and accepted production health, within the configured duration budget.
- Check the selected worker in `.github/workflows/entity-execution.yml`. It executes only the entity chosen by Jason. Build/test/security run on hosted workers; deployment and rollback use `self-hosted, linux, payment-deploy`.
- Check controller-host reachability before a live experiment. Loopback URLs require the controller to reach the deployment host's loopback services. Change the pipeline endpoints if necessary, then regenerate.

| Binding | Staging | Production / rollback |
|---|---|---|
| Compose project | payment-staging | payment-production |
| App readiness | http://127.0.0.1:3001/ready | http://127.0.0.1:3000/ready |
| Prometheus | http://127.0.0.1:9091 | http://127.0.0.1:9090 |
| Collector metrics | http://127.0.0.1:9465/metrics | http://127.0.0.1:9464/metrics |

The worker passes the execution UUID as `CI_RUN_ID`; `src/telemetry.ts` attaches `ci_run_id`. The app exports OTLP to the collector, Prometheus scrapes the collector, and contract queries filter on that UUID. The worker generates payment traffic after deployment. Java checks readiness and sample freshness; Jason applies error/latency thresholds and observation budgets.

Checkpoint: entity names, job display names, environments, endpoints and telemetry describe the intended service. Recovery restores a verified known-good source revision into production and observes it again.

## 2. Generate the project once

Actions:

- Validate the two engineer inputs and explicitly generate the persistent project revision.
- Inspect and retain the outputs with the corresponding inputs and generator revision.
- Repeat this phase only when the inputs or generator change, including the generic policy.

Commands:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
```

Persistent artifacts:

1. `models/01_pipeline.yaml`: engineer-defined entities, dependencies, monitoring and recovery mappings.
2. `models/02_goal.yaml`: engineer-defined goals and constraints.
3. `models/03_workflow_model.yaml`: generated project contract and capability dictionary.
4. `bdi/controller_agent.asl`: generated project agent for subsequent experiments.

Paths above are under `bdi-cicd-framework`. `models/generation-manifest.json` records input, generator and output hashes. Generation of the agent reloads only the saved workflow contract and the framework policy. Runtime checks hashes, recompiles inputs for comparison without writing outputs, validates capability bindings, and compares the entire agent with the contract/policy projection. Editing a generated fact or plan is rejected. Change the input or generator, then explicitly regenerate.

Checkpoint: validation prints `Project artifacts are consistent`. No campaign, GitHub dispatch or deployment has occurred.

## 3. Rehearse locally with the existing agent

Actions:

- Start two independent campaigns using the same project artifacts.
- Inspect their journals and results. Add `--gui` to inspect Jason beliefs, events and intentions; close the console before the next campaign.

Commands (choose new evidence directory names for each repetition):

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --scenario healthy --artifacts-dir bdi-cicd-framework/runs/manual-healthy
py -3 -B bdi-cicd-framework/run_controller.py --scenario production_unhealthy --artifacts-dir bdi-cicd-framework/runs/manual-recovery
Get-Content bdi-cicd-framework/runs/manual-recovery/controller-result.json
Get-Content bdi-cicd-framework/runs/manual-recovery/controller-journal.jsonl
```

Checkpoint: healthy reaches `achieved` after production verification. Production-unhealthy selects rollback once, verifies recovery and finishes `stopped/restored`; production remains an unmet candidate goal. These use real Jason reasoning with simulated adapters and do not deploy.

Campaign directories contain execution state/evidence, runtime source provenance and exact archival copies of the persistent artifacts. `generation-manifest.json` identifies the source artifact paths and generation-manifest hash; `project-generation-manifest.json` is the archived project generation record. The manifest filename is retained for evidence compatibility; startup does not perform generation. All campaign directories must be new.

Full local checks:

```powershell
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
Push-Location bdi-cicd-framework/bdi
.\gradlew.bat --no-daemon test
Pop-Location
py -3 -B bdi-cicd-framework/verify_controller_experiment.py
```

The matrix generates four isolated test configurations once, before its twenty campaigns. It covers retry/exhaustion, reobservation, reconciliation, recovery, staging-only goals, duration constraints and reporting. It uses shortened test observation waits; the saved payment project retains its live budgets.

## 4. Generate a different project revision explicitly

Actions:

- Keep the payment project intact while trying the second application's simulated contract.
- Generate reporting artifacts once, then reuse them for its campaigns.

Commands:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py --project-dir bdi-cicd-framework/runs/reporting-project --pipeline bdi-cicd-framework/examples/reporting_pipeline.yaml --goal bdi-cicd-framework/examples/reporting_goal.yaml
py -3 -B bdi-cicd-framework/run_controller.py --project-dir bdi-cicd-framework/runs/reporting-project --scenario healthy
```

Checkpoint: reporting selects `package, verify, preview` through the same compiler, policy and Java runtime. This verifies a second topology; it is not a live reporting integration. For staging-only payment, generate another project directory with the payment pipeline and `examples/staging_goal.yaml`.

## 5. Prepare a live baseline (remaining operator work)

Actions:

- Ensure the approved worker revision is already dispatchable in the intended GitHub repository.
- Verify the Linux runner is online with `payment-deploy`, Docker/Compose works, and configured GitHub Environment approvals are understood.
- Run the controller in a durable checkout outside the runner checkout and its execution slot.
- Select a full immutable release SHA. Supply an Actions-write token through the environment without printing it.
- Remove any old experiment plan and endpoint overrides from the shell unless deliberately needed. Verify any overrides target the same intended environment.
- Revalidate project artifacts. Source-only candidate changes do not require project regeneration; input or generator changes do.

Commands (replace placeholders before executing):

```powershell
$env:GITHUB_REPOSITORY = 'OWNER/REPOSITORY'
$env:BDI_WORKFLOW_REF = 'APPROVED_DISPATCHABLE_REF'
$env:BDI_RELEASE_SHA = 'FULL_40_CHARACTER_BASELINE_SHA'
# Supply GITHUB_TOKEN securely in this shell.
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --baseline --artifacts-dir bdi-cicd-framework/runs/live-baseline
```

Checkpoint: only an `achieved` live result with verified production telemetry establishes a baseline. Inspect `/health`, `/ready`, `/checkout`, the journal and selected GitHub run. Match `deploymentRunId` to the execution UUID. Keep the entire campaign and its result receipt. A baseline has no earlier rollback source; failure cannot restore one automatically.

## 6. Run a candidate and verify recovery

Actions:

- Select an available candidate SHA and retain the trusted baseline receipt.
- Confirm the baseline source can use the retained database schema/data. Recovery rebuilds source; it neither restores the database nor promotes an attested immutable image.
- Start a new campaign with the same persistent agent. Jason alone selects retries, observation, stopping and recovery.

Commands:

```powershell
$env:BDI_RELEASE_SHA = 'FULL_40_CHARACTER_CANDIDATE_SHA'
$knownGood = (Resolve-Path bdi-cicd-framework/runs/live-baseline/controller-result.json).Path
py -3 -B bdi-cicd-framework/run_controller.py --known-good $knownGood --confirm-compatible-rollback --artifacts-dir bdi-cicd-framework/runs/live-candidate
```

Checkpoint: candidate success includes production telemetry acceptance. An intentional recovery experiment should finish `stopped/restored`, with candidate delivery unmet and the restored source verified by a new execution identity. Scenario receipts and receipts from another repository/environment are rejected as live recovery evidence. Receipts are trusted operator evidence, not signed attestations.

For an approved controlled failure experiment, create a properties file outside the campaign directory and set `BDI_EXECUTION_PLAN` to its absolute path. `production.failure_mode=force_failure` triggers the worker's post-deployment failure; `production.force_error_rate=1` selects its high-error experiment mode. Run with the known-good arguments and a new campaign directory. Clear the environment variable after the experiment. Do not use this against an environment without authorization for the deliberate fault.

## 7. Reconcile uncertain execution

Actions:

- If an acknowledgement is lost, Java retains durable intent and Jason requests bounded read-only reconciliation before any redispatch.
- After a stopped process, inspect the pending GitHub execution and reconcile it. An absent or ambiguous match never permits blind retry.

Command:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Checkpoint: reconciliation records remote evidence and never resumes the old campaign or declares candidate achievement. Confirmed terminal status clears pending intent; unknown preserves it and blocks later dispatch. Do not erase the pending marker to force a run. Worktrees share a lock in the common Git directory; separate clones require external coordination.

No live steps in sections 5-7 were executed as part of the lifecycle correction. Historical validation and experiment evidence remain under `docs/experiments`.
