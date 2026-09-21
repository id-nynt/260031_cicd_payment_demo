# BDI project generation and runtime

This document explains the implementation in this repository. Use the [framework README](../bdi-cicd-framework/README.md) to customize a project and the [manual guide](BDI_MANUAL_EXECUTION_GUIDE.md) to run experiments: A is one-time setup, B prepares each run, C covers deployment scenarios, D tests a failure goal, and E/F cover evidence and recovery from mistakes.

**Jason selects actions and evaluates goals. Java executes those actions and publishes observations. GitHub Actions executes only the selected entity.** The traffic client is separate: it creates test conditions, not agent decisions.

## 1. Persistent project artifacts

| Artifact | Owner and purpose |
|---|---|
| [models/01_pipeline.yaml](../bdi-cicd-framework/models/01_pipeline.yaml) | Engineer input: logical jobs, dependencies, worker mappings, retry safety, recovery, observation budgets and telemetry bindings |
| [models/02_goal.yaml](../bdi-cicd-framework/models/02_goal.yaml) | Engineer input: achievements, maintenance/avoidance rules, error-rate and latency thresholds |
| [models/03_workflow_model.yaml](../bdi-cicd-framework/models/03_workflow_model.yaml) | Generated schema-2 project contract; sole project-specific input to agent generation |
| [bdi/controller_agent.asl](../bdi-cicd-framework/bdi/controller_agent.asl) | Generated AgentSpeak beliefs/goals plus the executable generic policy |
| [models/generation-manifest.json](../bdi-cicd-framework/models/generation-manifest.json) | Required input, generator and artifact hashes; not a disposable build file |

Inputs 01 and 02 are the configuration sources of truth. Generate explicitly once per input/generator revision and retain the generated outputs together with that revision. Do not edit 03 or the agent manually. Starting a campaign reuses these artifacts; it does not generate a new project agent.

The [commented templates](../bdi-cicd-framework/templates/models/01_pipeline.yaml) provide forms for another app. Template 03 is an annotated reference shape, not another engineer input. Actual shell steps, services, runner labels and deployment commands remain in the GitHub worker. Input 01 does not accept embedded `steps`, `services` or `runs-on`.

## 2. From inputs to an executable campaign

| Stage | Implemented component | Result |
|---|---|---|
| Compile configuration | [generate_project.py](../bdi-cicd-framework/generate_project.py), [project_artifacts.py](../bdi-cicd-framework/project_artifacts.py), [parser/workflow_model.py](../bdi-cicd-framework/parser/workflow_model.py) | Validate 01/02 and save 03 |
| Generate agent | `generate_agent` reloads saved 03 and uses [controller_generic.asl](../bdi-cicd-framework/generator/controller_generic.asl) | Persistent `controller_agent.asl` and generation manifest |
| Start campaign | [run_controller.py](../bdi-cicd-framework/run_controller.py) | Validate artifacts, create fresh evidence directory and exact snapshots, prepare Java environment |
| Start Jason | [ControllerMain.java](../bdi-cicd-framework/bdi/harness/ControllerMain.java), [controller.mas2j](../bdi-cicd-framework/bdi/controller.mas2j) | Check campaign snapshot integrity, acquire controller lock, load the archived agent |
| Execute agent actions | [ControllerEnvironment.java](../bdi-cicd-framework/bdi/harness/ControllerEnvironment.java) | Bind `run_job`, observations, reconciliation and final results to Java adapters |
| Execute selected entity | [GitHubEntityExecution.java](../bdi-cicd-framework/bdi/harness/GitHubEntityExecution.java), [entity-execution.yml](../.github/workflows/entity-execution.yml) | Dispatch/poll one entity and return its correlated result |
| Measure app health | [ProjectTelemetryProvider.java](../bdi-cicd-framework/bdi/harness/ProjectTelemetryProvider.java), [PrometheusTelemetryObserver.java](../bdi-cicd-framework/monitoring/observer/PrometheusTelemetryObserver.java) | Read readiness and raw metrics; the current controller's AgentSpeak plans apply thresholds |

`parser/model_transform.py` still provides shared model/parsing functionality. Its older CLI and `generator/bdi_generic.asl` are not the canonical generation path; the latter remains covered by compatibility tests.

From the repository root:

```powershell
# Explicit generation after configuration/generator changes.
py -3 -B bdi-cicd-framework/generate_project.py

# Read-only consistency check; no campaign or dispatch.
py -3 -B bdi-cicd-framework/run_controller.py --validate-only

# Optional real Jason execution with simulated jobs/telemetry.
py -3 -B bdi-cicd-framework/run_controller.py --gui --scenario healthy
```

For another project, generation accepts `--project-dir`, `--pipeline` and `--goal`; subsequent launches use that `--project-dir`. Specify both input paths when generating a separate project. Runtime rejects stale/missing/inconsistent artifacts with a regeneration message; it never silently migrates or regenerates them.

App-only commits, fault-file changes and traffic-profile changes do not require regeneration. Changes to input bindings, goals, generator code or the generic policy do. A runtime-only implementation change is distinct from a project-generation change.

## 3. Mapping the workflow model to agent beliefs

| Saved contract section | Source and meaning | Agent/runtime use |
|---|---|---|
| `workflow.entities(E)` | Job and recovery keys from 01 | `entity(...)`, recovery entity facts; validate action targets |
| `workflow.dependencies(D)` | Prerequisite edges from each job's `needs` | `depends(Entity, Requirements)`; only successful prerequisites authorize successors |
| `workflow.observable_properties(O)` | Framework-defined execution status, duration and health domains | Validate supported observations; actual values arrive during execution |
| `workflow.recovery(R)` | Input 01 `recovery.<name>.from` | `recovery(Source, Target)` and recovery selection |
| `goals` | Input 02 achievement, maintenance and avoidance rules | `achievement`, `max_duration`, `require_healthy`, `avoid_missing`; determine required dependency closure |
| `execution` | Retry/observation/reconciliation budgets and retry-safe job list | Counter/limit facts; separate budgets for repeating actions and rechecking evidence |
| `observation_schema` | Observation points and duration constraints | Attempt correlation required; observe-after and observe-before capabilities |
| `recovery_policy` | Input triggers plus framework recovery safeguards | Known-good source, no recovery retry, mandatory health verification, restored/failed outcome |
| `bindings` | Project, worker file/display names, environments, URLs, queries and thresholds | Java dispatch/telemetry configuration and generated threshold beliefs |

The current payment topology is:

```text
build -> test -> security -> staging -> production
production -- conditional verified recovery --> rollback
```

Rollback is conditional, not a successful-path dependency. Input 01 enables health observation after staging, production and rollback, and requires accepted staging health before production. Input 02 requires staging and production success, production health, production duration <= 1,800,000 ms, and forbids production success without test/staging success.

O includes execution statuses `success`, `failure`, `transient_failure`, `dispatch_rejected`, `cancelled`, `timeout`, `skipped`, `unknown`; duration is milliseconds; health values are `healthy`, `unhealthy`, `unknown`. The framework adds distinctions that GitHub job conclusions alone do not provide. These are not free-form app-defined properties.

The compact YAML does not duplicate its capability dictionary. `expand_workflow` derives and validates entities, permitted action targets, observation signatures, recovery pairs and goal rules from saved 03. [WorkflowRuntime.java](../bdi-cicd-framework/bdi/harness/WorkflowRuntime.java) adapts that contract for `ControllerProjectConfig` and `ProjectConfig`; it does not schedule jobs.

Validation recompiles 01/02, compares the saved contract, verifies hashes, and compares the complete generated agent against its deterministic projection plus generic policy. It detects added/missing entities, altered actions, observations, recovery or goal rules. Changing only the agent hash cannot make an inconsistent agent valid. This is consistency checking, not a cryptographic trust boundary against a deliberately replaced generator.

## 4. How the agent pursues goals

Static beliefs describe the project: entities, dependencies, required jobs, achievement predicates, recovery mappings, thresholds and limits. Runtime beliefs track attempts, running/terminal work, phase results, observations and workflow state. Java publishes attempt-qualified `status`, `duration`, `reconciled` and round-qualified `telemetry_measurement` percepts. The execution UUID additionally correlates GitHub and deployed-app measurements.

The active generic plans use this progression:

```text
!master_goal -> !need_achieve(Entity, Desired) -> !run_pipeline
  -> !run_entity(Entity) -> run_job(Entity, Attempt)
  -> correlated status/duration -> phase_result(Entity, success | failure)
  -> maintenance, avoidance and required health checks
  -> next eligible entity, retry, reobserve, reconcile, recover or stop
  -> !check_master_goal -> achieved / stopped / unknown
```

`phase_result(Entity, success)` alone is not verified delivery. Required health must also be accepted before progression/achievement. MAS exposes `workflow_active`, `workflow_started`, `workflow_stopped`, `workflow_completed` and `master_goal_achieved` as the corresponding plans run. The console/journal preserve decisions; the mind inspector shows current beliefs, which can change quickly.

### Decision policy and current limits

| Evidence | Decision under ordinary success goals |
|---|---|
| Successful job | Check maintenance and required health, then continue |
| Confirmed `transient_failure` or terminal `timeout` | Retry only if retry-safe, within budget and not recovery |
| Ordinary failure, cancelled or skipped | Stop or select configured recovery; no blind retry |
| Dispatch rejected | Stop with rejection evidence; no speculative deployment recovery |
| Execution unknown | Read-only reconciliation of the same execution; no redispatch while uncertain |
| Unhealthy or unavailable measurements | Bounded reobservation; do not advance |
| Enough consecutive healthy samples | Accept health before the deadline and continue |
| Persistent staging health failure/uncertainty | Stop promotion; production remains unchanged |
| Persistent production health failure/uncertainty | Recover once from verified known-good source, then verify recovery |

Current input values: one additional execution retry with a five-second delay; up to 36 observations five seconds apart within 180 seconds; two consecutive healthy samples; three reconciliation attempts five seconds apart. A bad/unavailable measurement resets the healthy count. The observation deadline starts with the first observation request and includes measurement time. Two healthy measurements can finish early: 180 seconds is a maximum, not a compulsory wait. Overlapping two-minute metric windows are not independent statistical samples.

The adapter recognizes controlled transient failure only if the exact **Controlled transient failure** step failed. A locally expired polling wait is uncertain, not a confirmed remote timeout eligible for retry. The current Java entity polling limit defaults to 20 minutes; that is separate from the 30-minute production duration maintenance limit and the three-minute health observation limit.

### Success and failure goals

`achieve(A)` supports `entity.status == success` and `entity.status == failure`. A failure goal requires an actual exact `failure`; rejected dispatch, uncertainty, timeout and controlled `transient_failure` do not satisfy it. The goal does not cause fault injection. An unexpected success is not repeatedly executed to manufacture a failure.

A matching failure satisfies that entity's requested outcome without normal retry/automatic recovery. Dependencies still require success, and separately declared maintenance/avoidance rules still apply. Contradictory goals can therefore finish unmet. Use [staging_failure_goal.yaml](../bdi-cicd-framework/examples/staging_failure_goal.yaml) for the isolated negative experiment in manual D1.

Results include `requested_goals`, `achieved_goals`, `unmet_goals` and `goal_message`. Negative-goal campaigns have `negative_goal_experiment: true` and no `verified_releases`; they cannot certify a rollback baseline. An explicitly expected production failure may happen after the app changed and finish without automatic rollback; restore manually afterward. Unmet pursuit prints **Attempted but failed to achieve goals.**

## 5. Live dispatch, interruption and recovery

For live execution set `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, `BDI_WORKFLOW_REF` and `BDI_RELEASE_SHA` in the controller terminal. The token needs repository access and Actions write. The worker ref selects published workflow code; the full immutable release SHA selects published app source. An unpublished local commit cannot be checked out by GitHub. A push publishes code; launching the controller starts this campaign.

The worker accepts entity/campaign/execution/attempt/release and experiment inputs, names runs `bdi-<execution UUID>`, and gates each job by `inputs.entity`. Build/test/security use hosted runners. Staging, production and rollback use the self-hosted Linux `payment-deploy` runner, which must remain online. Other jobs in the same dispatch are skipped. Environment approval and queue waiting are infrastructure conditions, not agent decisions.

Before POST, Java persists execution intent in `bdi-execution-pending.json` in the common Git directory. Linked worktrees share pending state and the controller lock. Explicit HTTP 401/403/404/422 dispatch responses are rejection evidence; ambiguous responses, lost acknowledgements, missing selected jobs and polling failures remain uncertain. Reconciliation checks the exact execution/run and selected job. Missing or ambiguous evidence never authorizes redispatch.

After interruption, close the stopped console and use the configured controller terminal:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

This settles confirmed terminal execution but never resumes the campaign or claims delivery. Unknown preserves pending state. Investigate remote jobs/access/runner status instead of deleting the marker. Repository-local locks do not coordinate unrelated clones or external deployment tools.

An initial successful live `--baseline` campaign has no previous recovery source. Subsequent campaigns use `--known-good <v1-controller-result.json> --confirm-compatible-rollback`. The receipt must be achieved/live and match the project, repository, source SHA and required verified recovery environment. It is trusted operator evidence, not a signed attestation.

Recovery rebuilds verified source, observes the restored execution identity and verifies health. It does not restore database history or promote an immutable image digest. The compatibility flag confirms that source rollback can use retained database state. Restoration ends `stopped / restored`, never candidate achievement. Current automatic rollback restores production only; manual B4 redeploys v1 through the whole pipeline to reset both environments.

<a id="payment-telemetry-and-controllable-traffic"></a>

## 6. Payment telemetry and controllable traffic

The [app config](../src/config.ts), [instrumentation](../src/telemetry.ts), [Compose file](../docker-compose.yml), [OTel collector](../otel-collector.yaml) and [Prometheus configuration](../prometheus.yml) define/export the actual metrics. The worker supplies host ports and `CI_RUN_ID=execution_id`. Input 01 tells the controller where and how to read them; it does not create app endpoints.

| Environment | App | Prometheus | Collector metrics | Database |
|---|---|---|---|---|
| Staging | 3001 | 9091 | 9465 | 5433 |
| Production/recovery | 3000 | 9090 | 9464 | 5432 |
| Optional local rehearsal | 3002 | 9092 | 9466 | 5434 |

`/ready` reports readiness via HTTP 200/503. `/health` reports `deploymentRunId` and `experimentMode`; the ID is an execution UUID, not a source SHA. Campaign receipts map execution IDs to source revisions.

Input 01 filters PromQL with `ci_run_id="{{run_id}}"`. It derives error fraction from `payment_http_errors_total` / `payment_http_requests_total`, p95 milliseconds from `payment_http_request_duration_milliseconds_bucket`, and readiness/sample age from `payment_service_ready`. Request metrics use a two-minute window. Source sample age is limited to 30 seconds. Input 02 rejects error fractions above 0.05 and p95 above 500 ms. The adapter rejects missing, stale or nonfinite measurements; Jason decides what those observations mean for the campaign.

### No traffic is not proof of a broken app

An idle app can be ready while recent request latency is undefined. The current `ProjectTelemetryProvider.measure()` catches measurement errors and reports `data_status: unavailable`, with numeric zero placeholders. Those zeros are not accepted healthy measurements. The journal does not identify the individual failed metric, and this observation does not distinguish insufficient request samples from every transport/query failure.

This campaign verifies a new release's payment path. If that evidence remains insufficient, input 01's `telemetry_unknown` recovery trigger permits production rollback. The meaning is **candidate not verified**, not **application proved unhealthy**. Normal synthetic requests maintain verification evidence even without real users. No continuing agent runs after campaign completion, so later user inactivity does not cause automatic rollback.

An idle-aware policy could separately represent insufficient request samples, exporter/transport failure and readiness, then request bounded synthetic probes. That distinction is not implemented in the current agent contract. Do not silently replace undefined latency with zero or disable freshness/correlation checks.

### Fault configuration and pause signal

[ExperimentExecutionPlan.java](../bdi-cicd-framework/bdi/harness/ExperimentExecutionPlan.java) reloads `BDI_EXECUTION_PLAN` before each dispatch. Example properties:

```properties
test.1.failure_mode=transient_failure
security.failure_mode=force_failure
production.experiment_mode=request_faults
```

Attempt-qualified entries override entity defaults. These settings change the selected worker action's conditions, never its successor or the desired goal. Use one scenario's intended entries at a time. Production `force_failure` occurs after its deployment command; staging's controlled deterministic failure occurs before deployment.

[request_faults](../src/experiment.ts) makes fake-payment requests carrying `X-Experiment-Fault: error` return intentional HTTP 503. Normal requests remain normal, subject to app/database health. Merely selecting the mode sends no traffic. The published controller worker supports `normal`, `high_error_rate` and `request_faults`; application support for `high_latency` does not make it a supported live controller dispatch mode.

`--pause-after production --pause-ms 60000` (or staging) pauses Java after the selected GitHub job finishes, before its result reaches the agent for subsequent health observation. The signal is `controller_pause` with `after_entity` in **controller-journal.jsonl**, not the `controller_agent` log tab. It resumes automatically after 60 seconds.

### Scenario-driven and manual traffic

[run-traffic-scenario.mjs](../scripts/run-traffic-scenario.mjs) runs locally alongside BDI. Arm it before the controller launch using the exact new campaign directory; it can wait before that directory exists. It waits for a fresh pause, verifies the current app's execution ID, and requires request-fault mode for error profiles. It never dispatches GitHub jobs or publishes telemetry beliefs.

| Profiles | Purpose |
|---|---|
| `healthy`, `fluctuating`, `burst` | Normal payments with steady or varied request spacing/load |
| `temporary-errors` | 75 seconds of mixed errors, then continuing normal traffic |
| `persistent-errors` | Mixed errors until the agent recovers/finishes or the client reaches its cap |
| `intermittent-errors` | Two error periods separated by normal traffic |
| `idle` | No client payments; worker-generated samples may still permit early verification |
| `staging-temporary-errors` | Staging faults clear; promotion can proceed after verification |
| `staging-persistent-errors` | Staging remains unhealthy; promotion should stop, leaving production unchanged |

The two staging profiles default to port 3001 and reject a conflicting entity override. Default production profiles use port 3000. Profiles are [editable JSON](../scripts/traffic-scenarios/README.md): phase durations, request rates, fault fraction, jitter and seed. Rates are sequential targets, not guaranteed throughput; one request is in flight. A seed repeats random choices, not external timing or BDI outcomes. Built-in profiles last at most 600 active seconds and can end earlier with the campaign. This is an experiment client, not a capacity benchmark or a generic adapter for arbitrary apps.

The runner stops on campaign completion, recovery selection, changed deployment identity, limits or error. An already in-flight request may finish as recovery begins. It saves `profile.json`, `traffic.jsonl` and `summary.json` in a unique sibling `<campaign>-traffic-*` directory. Traffic outcome is separate from the controller outcome. No publication or agent regeneration is needed to use these local scripts against the existing worker.

Use manual **C0** for production profiles and **C0-S** for the two staging cases. Manual C3/C4 retain [generate-experiment-traffic.mjs](../scripts/generate-experiment-traffic.mjs): invoke it directly with `node ... inject_error 6 --continuous`, then switch to `node ... normal 6 --continuous`. Repeated batches without a returned PowerShell prompt confirm continuous operation. Normal traffic must continue while old errors leave the metric window; the earlier Windows npm invocation did not forward `--continuous`.

## 7. Evidence, validation and boundaries

Each new campaign directory contains journal/result, MAS configuration, exact input/contract/agent snapshots and provenance. `project-generation-manifest.json` is the copied persistent manifest; the campaign's `generation-manifest.json` records campaign provenance. Archival copies are not regenerated agents. Preserve verified v1 receipts, pending execution evidence and historical experiments; caches/build output are different from evidence.

The current MAS may stay open after `Campaign finished`; Gradle at 75% then means the GUI remains open, not that more jobs will run. Close the finished console to release the foreground command. Containers remain running. Starting existing containers only resumes their existing revision; it does not establish a new verified baseline.

Useful local checks (no live deployment):

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
node --test scripts/tests/traffic-scenario.test.mjs
```

Python tests cover model/worker/artifact contracts; the traffic tests use temporary mock HTTP servers and journals. Java tests reside under `bdi/src/test/java`; [verify_controller_experiment.py](../bdi-cicd-framework/verify_controller_experiment.py) exercises generated agents through Jason scenarios. The [reporting example](../bdi-cicd-framework/examples/reporting_pipeline.yaml) preserves second-application topology coverage, but does not claim a live reporting deployment. These checks are not proof that current remote permissions, runner availability or live telemetry work; verify those with the manual guide.

Security auditing blocks high/critical production dependency advisories. Source rebuilds are not immutable-image promotion; database rollback, distributed controller coordination, continuous post-campaign monitoring and automatic v2 resumption after rollback are not implemented.


## Comparative execution extension

The [comparative guide](BDI_COMPARATIVE_EXECUTION_GUIDE.md) introduces `run_controller.py --mechanism conventional`: an imperative payment pipeline in `ConventionalPolicy` / `ConventionalMain`, using the same execution and raw telemetry adapters without starting Jason. It validates the supported success-goal contract and retains a hashed conventional policy snapshot. This is a scripted control-plane comparator, not a separate native GitHub Actions DAG.

Both mechanisms publish the same `experiment-events.jsonl` schema through `StructuredEventLogger`. `run_experiment.py` launches one operator-selected trial, coordinates the matching traffic profile and fault file, retains a comparison plan and calls `experiment_metrics.py` at completion. Shared deployment-ready, observation, recovery and completion events align traffic timing without depending on AgentSpeak log messages. Normal manual launches still work and the old journal remains available.

These are runtime/instrumentation additions: engineer inputs and the persistent agent are unchanged. Local paired simulation checks validate parity for matched policy cases; they do not establish superiority in live reliability/resilience. Live paired pilots and a frozen experimental revision remain necessary.
