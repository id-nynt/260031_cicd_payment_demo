# Persistent project lifecycle validation - 20 September 2026

Implementation: `4db514f` on `repair/bdi-canonical-controller`, an additional commit after `4b01b86`. Earlier history and the historical experiment directories are preserved.

## What changed

Project generation now writes `models/03_workflow_model.yaml`, `bdi/controller_agent.asl` and `models/generation-manifest.json` explicitly. Campaign startup validates and snapshots them without regeneration. Input/generator changes, missing files, changed hashes, inconsistent capability dictionaries and agent contract/policy disagreement are rejected before Java starts. Hashes in the persistent manifest normalize text newlines for portable Git checkouts; campaign hashes identify exact archived bytes.

The payment inputs were checked against the selected worker jobs, environment names, Compose port bindings, execution-ID propagation, service metric instruments and Prometheus scrape target. The generated persistent payment artifacts are committed. The existing generic Jason policy, Java action executor, telemetry implementation and GitHub worker behavior were preserved.

## Validation

- 36 Python tests passed: input/model validation, baseline receipt restrictions, worker/payment mappings, missing/stale artifacts, generator changes, corrupted capability dictionaries, changed agent entities/actions/observations/recovery/goals, forged output hashes, generation using only the saved contract, and two campaigns preserving project bytes and modification times.
- 20 Java tests passed with `--rerun-tasks`: adapters, telemetry freshness, receipt behavior, execution reconciliation and campaign snapshot integrity.
- 20 actual Jason scenarios passed using simulated adapters: healthy, staging-only, retry/exhaustion, delayed/unknown/unhealthy telemetry, candidate and rollback failures, duration violation, reconciliation, unresolved execution, baseline without recovery, pause, and reporting topology.
- The checked-in persistent payment agent separately completed a healthy simulated campaign using normal observation budgets. Its result, journal and provenance are retained under `persistent-payment/`.
- `run_controller.py --validate-only` passed for the committed payment artifacts. `git diff --check` passed.

The matrix generates four test configuration revisions once before campaigns begin. Payment scenarios reuse one saved project; staging-only, duration and reporting use their own saved revisions. `summary.json` retains per-case results, execution identities and complete source/artifact provenance. Selected recovery and uncertain-execution journals are retained alongside the summary. Full disposable local output is under `bdi-cicd-framework/bdi/build/lifecycle-final/`.

Commands from the repository root:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
Push-Location bdi-cicd-framework/bdi
.\gradlew.bat --no-daemon test --rerun-tasks
Pop-Location
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/lifecycle-final
py -3 -B bdi-cicd-framework/run_controller.py --scenario healthy --artifacts-dir bdi-cicd-framework/bdi/build/lifecycle-persistent-payment
```

The first sandboxed test attempts were blocked by Windows temporary-directory and Gradle cache permissions. The same suites passed with approved access outside the sandbox. No application code or dependencies changed, so payment npm checks were not repeated for this lifecycle-only correction; the earlier application results remain in the canonical repair record. Existing Gradle/Jason configuration warnings did not prevent execution.

## Remaining live experiment work

Follow [the manual walkthrough](../../../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md): verify the dispatchable worker revision and Linux runner, configure repository/token/release SHA and reachable endpoints, establish a telemetry-verified baseline, retain its receipt, then run a compatible candidate and an authorized recovery experiment. Verify GitHub run identity, production health and `stopped/restored` without candidate achievement. Reconcile uncertain dispatch before another campaign.

No GitHub deployment, push, merge, tag movement, branch deletion or history rewrite was performed. Simulated reporting coverage does not claim a second live application. Rollback remains source restoration with retained database data and operator-trusted receipts.
