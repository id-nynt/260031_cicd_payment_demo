# Comparative CI/CD experiments: BDI and conventional control

The current comparator is an **imperative scripted controller**, implemented in `ConventionalMain` / `ConventionalPolicy`, over GitHub Actions jobs. It does not start Jason or execute agent plans. It is not an independent native GitHub Actions `needs` workflow: both mechanisms deliberately share the same selected-entity worker and adapters to control for dispatch, queue and execution differences. A separately engineered native workflow remains an optional external-validity comparator.

## What is shared, and what differs?

| Shared | Different |
|---|---|
| Published candidate SHA and worker ref | Jason beliefs/plans versus a fixed imperative loop |
| Build/test/security/deployment/recovery commands | BDI console decisions versus conventional terminal decisions |
| Raw telemetry, retry safety, budgets, thresholds and verified rollback source | Agent can use its supported project models/goals; the comparator deliberately supports only the payment success-goal contract |
| GitHub dispatch/polling, correlation, pending-state reconciliation and repository lock | Mechanism label in provenance, results and common events |
| Identical 60-second pause and scenario traffic for each pair | No claimed superiority before repeated live trials |

The conventional controller validates its supported topology, achievements, maintenance and observation settings before launch; it rejects unsupported negative goals or custom topology rather than silently ignoring them. Both mechanisms retain the persistent contract/agent artifacts for consistency checks. The conventional executable reads a validated `conventional-policy.json` snapshot, not AgentSpeak. Neither mechanism repairs a broken app, runner or infrastructure automatically.

## 1. Prepare the environment and baseline

Complete manual guide **B1-B4**: Docker and runner online, credentials loaded, published v2 selected, verified v1 receipt available, and both environments restored to v1. Keep your current worker tag: these changes are local control/traffic tools using its existing dispatch interface. No worker publication is needed unless you change the worker itself.

Use ordinary success goals for comparisons. Use the same database starting conditions (or document retained state), candidate, worker, thresholds, fault profile and seed for each pair. Do not run mechanisms concurrently against the shared environments. Alternate their order across repetitions.

The existing baseline source receipt can be reused. The wrappers do not certify your starting container state: check the app identity and restoration result before each trial. Do not assume `--known-good` itself restores v1.

## 2. Optionally inspect the plan without deploying

Controller PowerShell, after manual B2:

```powershell
py -3 -B bdi-cicd-framework/run_experiment.py --mechanism conventional --case production-temporary --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed 42 --prepare-only
```

Expected: a new sibling `*-experiment/plan.json` and `faults.properties` containing the configuration to review. No controller or traffic runs. A live invocation gets a new directory; a prepared directory is not reused automatically. The explicit SHA must be the published candidate, not a new unpublished local commit. Prepare-only plans do not query GitHub; live startup checks candidate publication and records the worker ref's remote commit before dispatch. Use a fixed published worker tag and do not move it during the study.

## 3. Manually launch ONE trial

Choose one case:

| Case | Automatic fault/traffic setup | Expected healthy-policy response |
|---|---|---|
| `healthy` | Normal production traffic | Verify and deliver v2 |
| `build-failure` | Controlled build failure; no traffic client needed | Stop before deployment |
| `transient-test-failure` | Test attempt 1 fails transiently; normal production traffic | Retry once, then deliver if checks pass |
| `staging-persistent` | Staging request-fault mode; persistent staging errors | Block promotion; production stays v1 |
| `production-temporary` | Production request-fault mode; 75s mixed errors, then normal traffic | Reobserve and continue if health recovers within budget |
| `production-persistent` | Persistent production errors | Reobserve, restore verified v1 and verify recovery |

Run the selected mechanism. For example:

```powershell
py -3 -B bdi-cicd-framework/run_experiment.py --mechanism bdi --case production-temporary --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed 42
```

The wrapper starts a traffic client automatically, launches one controller, waits for completion and extracts metrics. No second traffic terminal or manual injection timing is required. It does not run the next experiment or reset the environment. For comparisons it uses terminal output, without the MAS GUI's keep-open delay.

Expected: traffic WAITING -> STARTED at the shared deployment pause -> phase transitions -> stop on recovery/completion. Both mechanisms use `experiment-events.jsonl`; the traffic client still supports old controller journals for historical/manual compatibility. Do not manually inject additional traffic into a scripted trial.

After recording this trial, stop any residual client, restore both environments using manual B4, and rerun B2. Then launch its paired comparator:

```powershell
py -3 -B bdi-cicd-framework/run_experiment.py --mechanism conventional --case production-temporary --release-sha "$v2Sha" --known-good "$knownGood" --confirm-compatible-rollback --seed 42
```

Expected: conventional decision events instead of MAS beliefs, the same configured fault schedule and safeguards, and its own new evidence directories. A stopped campaign returns exit code 1; unknown/startup failure returns 2. An expected fault containment result is not a successful deployment, even when it meets the experimental expectation. Equivalent outcomes are valid. Do not weaken the baseline to manufacture a BDI advantage.

If interrupted, stop the residual traffic process if any, inspect remote execution and use the shared `run_controller.py --reconcile-only` procedure before restarting. Terminating the local process does not cancel GitHub jobs. A crashed/missing traffic client marks the evidence unsuitable rather than silently proving a successful fault experiment.

## 4. Inspect automatically recorded evidence

Each trial prints its campaign path. Three sibling locations are retained:

| Location | Contents |
|---|---|
| `<campaign>/` | Controller journal/result, `experiment-events.jsonl`, snapshots/provenance, `experiment-metrics.json`; conventional trials also have `conventional-policy.json` |
| `<campaign>-experiment/` | `plan.json` with case, seed, candidate/baseline, worker, source/contract/profile hashes and comparison key; exact fault configuration and `controller-console.log` |
| `<campaign>-traffic/` | Exact traffic profile, per-request timing/outcomes, phase events and summary; omitted for build failure |

Common events include `campaign_started`, `action_started`, `action_finished`, `decision`, `observation`, `health_accepted`, `reconciliation`, `deployment_ready`, `recovery_started`, `campaign_finished`. They retain entity/attempt/execution IDs where applicable and label the mechanism. Common logging observes decisions; it does not choose actions for either controller.

`experiment-metrics.json` reports candidate delivery, restoration, production dispatch, action attempts/retries, rollback attempts, observations, reconciliation, runtime, recovery timing and traffic counts. Recovery is not candidate delivery. Retry counts come from all action-start events, not just the last result for an entity.

Timing definitions:

- Runtime: `campaign_started` to `campaign_finished`, excluding Gradle startup; includes configured pauses and execution waits.
- Candidate time: that runtime only for accepted candidate delivery.
- Recovery time: first observed production failure/unhealthy/unavailable evidence to accepted rollback health. This is not exact outage duration or latency from the external fault's start.
- Decision latency: first adverse production evidence to recovery selection.
- Summed entity duration includes adapter-observed wait/execution time; it is **not billed runner time**. Use GitHub job timestamps/billing data for actual execution cost.

Missing evidence and simulated runs are excluded by `eligible_for_comparison`. Traffic faults must actually be observed by the traffic client; unexpected traffic/transport errors are flagged. `protocol_expectation_met` evaluates the stated scenario expectation; it is not an independent proof of safety or an oracle that rules out every incorrect decision.

Human intervention is unknown by default. After each trial, optionally create `<campaign>-experiment/interventions.json` as a JSON array of your interventions (timestamps/action/reason). Use `[]` only if you confirm none occurred. Extraction then reports the count. Do not infer zero interventions merely because automation ran.

## 5. Export paired data

After both trials, substitute their printed campaign paths:

```powershell
py -3 -B bdi-cicd-framework/experiment_metrics.py "bdi-cicd-framework/runs/BDI-TRIAL" "bdi-cicd-framework/runs/CONVENTIONAL-TRIAL" --csv "bdi-cicd-framework/runs/comparison.csv"
```

This refreshes per-trial metrics and writes a CSV. Pair rows only when their `comparison_key` matches; keys deliberately exclude mechanism but include case, seed, candidate/baseline, worker, configuration, profile and local control/adapter source hashes. A key match does not prove equal database state, queue conditions or real fault exposure: inspect those separately.

Report success/restoration/containment per scenario, with repetitions and failures, rather than pooling unlike faults into a single success percentage. Build defects should be contained, not delivered. Keep live trials separate from simulation, pilot mistakes and setup incidents. Current automated metrics expose whether production was dispatched, but independent service observations are still needed to validate stronger safety claims.

## Local verification before live pilots

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --mechanism conventional --validate-only
py -3 -B bdi-cicd-framework/verify_comparison.py
node --test scripts/tests/traffic-scenario.test.mjs
```

`verify_comparison.py` runs eight simulated pairs through actual Jason and the imperative controller with a separate, explicitly generated short-budget project. It checks outcomes, recovery, action attempts, accepted health and terminal events. It never contacts GitHub or deploys. The test fixture's short waits are not the live experimental budgets.

Next live work: pilot healthy and temporary-production cases in both modes; inspect all evidence; then freeze the tested revision and begin repeated paired trials. Controlled service unavailability, infrastructure outage and deployment timeout need additional fault mechanisms and are not claimed as implemented live scenarios here.
