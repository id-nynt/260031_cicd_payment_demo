# BDI project generation and runtime

This document explains the implementation in this repository. Use the [framework README](../../bdi-cicd-framework/README.md) to customize a project and the [manual guide](../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md) to run experiments: A is one-time setup, B prepares each run, C covers deployment scenarios, D tests a failure goal, and E/F cover evidence and recovery from mistakes.

**Jason selects actions and evaluates goals. Java executes those actions and publishes observations. GitHub Actions executes only the selected entity.** The traffic client is separate: it creates test conditions, not agent decisions.

## 1. Persistent project artifacts

| Artifact                                                                                 | Owner and purpose                                                                                                               |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| [models/01_pipeline.yaml](../../bdi-cicd-framework/models/01_pipeline.yaml)                 | Engineer input: logical jobs, dependencies, worker mappings, retry safety, recovery, observation budgets and telemetry bindings |
| [models/02_goal.yaml](../../bdi-cicd-framework/models/02_goal.yaml)                         | Engineer input: achievements, maintenance/avoidance rules, error-rate and latency thresholds                                    |
| [models/03_workflow_model.yaml](../../bdi-cicd-framework/models/03_workflow_model.yaml)     | Generated schema-2 project contract; sole project-specific input to agent generation                                            |
| [bdi/controller_agent.asl](../../bdi-cicd-framework/bdi/controller_agent.asl)               | Generated AgentSpeak beliefs/goals plus the executable generic policy                                                           |
| [models/generation-manifest.json](../../bdi-cicd-framework/models/generation-manifest.json) | Required input, generator and artifact hashes; not a disposable build file                                                      |

Inputs 01 and 02 are the configuration sources of truth. Generate explicitly once per input/generator revision and retain the generated outputs together with that revision. Do not edit 03 or the agent manually. Starting a campaign reuses these artifacts; it does not generate a new project agent.

The [commented templates](../../bdi-cicd-framework/templates/models/01_pipeline.yaml) provide forms for another app. Template 03 is an annotated reference shape, not another engineer input. Actual shell steps, services, runner labels and deployment commands remain in the GitHub worker. Input 01 does not accept embedded `steps`, `services` or `runs-on`.

## 2. From inputs to an executable campaign

| Stage                   | Implemented component                                                                                                                                                                                            | Result                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Compile configuration   | [generate_project.py](../../bdi-cicd-framework/generate_project.py), [project_artifacts.py](../../bdi-cicd-framework/project_artifacts.py), [parser/workflow_model.py](../../bdi-cicd-framework/parser/workflow_model.py) | Validate 01/02 and save 03                                                                        |
| Generate agent          | `generate_agent` reloads saved 03 and uses [controller_generic.asl](../../bdi-cicd-framework/generator/controller_generic.asl)                                                                                      | Persistent `controller_agent.asl` and generation manifest                                         |
| Start campaign          | [run_controller.py](../../bdi-cicd-framework/run_controller.py)                                                                                                                                                     | Validate artifacts, create fresh evidence directory and exact snapshots, prepare Java environment |
| Start Jason             | [ControllerMain.java](../../bdi-cicd-framework/bdi/harness/ControllerMain.java), [controller.mas2j](../../bdi-cicd-framework/bdi/controller.mas2j)                                                                     | Check campaign snapshot integrity, acquire controller lock, load the archived agent               |
| Execute agent actions   | [ControllerEnvironment.java](../../bdi-cicd-framework/bdi/harness/ControllerEnvironment.java)                                                                                                                       | Bind `run_job`, observations, reconciliation and final results to Java adapters                   |
| Execute selected entity | [GitHubEntityExecution.java](../../bdi-cicd-framework/bdi/harness/GitHubEntityExecution.java), [entity-execution.yml](../../.github/workflows/entity-execution.yml)                                                    | Dispatch/poll one entity and return its correlated result                                         |
| Measure app health      | [ProjectTelemetryProvider.java](../../bdi-cicd-framework/bdi/harness/ProjectTelemetryProvider.java), [PrometheusTelemetryObserver.java](../../bdi-cicd-framework/monitoring/observer/PrometheusTelemetryObserver.java) | Read readiness and raw metrics; the current controller's AgentSpeak plans apply thresholds        |

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

| Saved contract section              | Source and meaning                                                             | Agent/runtime use                                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `workflow.entities(E)`              | Job and recovery keys from 01                                                  | `entity(...)`, recovery entity facts; validate action targets                                            |
| `workflow.dependencies(D)`          | Prerequisite edges from each job's `needs`                                     | `depends(Entity, Requirements)`; only successful prerequisites authorize successors                      |
| `workflow.observable_properties(O)` | Framework-defined execution status, duration and health domains                | Validate supported observations; actual values arrive during execution                                   |
| `workflow.recovery(R)`              | Input 01 `recovery.<name>.from`                                                | `recovery(Source, Target)` and recovery selection                                                        |
| `goals`                             | Input 02 achievement, maintenance and avoidance rules                          | `achievement`, `max_duration`, `require_healthy`, `avoid_missing`; determine required dependency closure |
| `execution`                         | Retry/observation/reconciliation budgets and retry-safe job list               | Counter/limit facts; separate budgets for repeating actions and rechecking evidence                      |
| `observation_schema`                | Observation points and duration constraints                                    | Attempt correlation required; observe-after and observe-before capabilities                              |
| `recovery_policy`                   | Input triggers plus framework recovery safeguards                              | Known-good source, no recovery retry, mandatory health verification, restored/failed outcome             |
| `bindings`                          | Project, worker file/display names, environments, URLs, queries and thresholds | Java dispatch/telemetry configuration and generated threshold beliefs                                    |

The current payment topology is:

```text
build -> test -> security -> staging -> production
production -- conditional verified recovery --> rollback
```

Rollback is conditional, not a successful-path dependency. Input 01 enables health observation after staging, production and rollback, and requires accepted staging health before production. Input 02 requires staging and production success, production health, production duration <= 1,800,000 ms, and forbids production success without test/staging success.

O includes execution statuses `success`, `failure`, `transient_failure`, `dispatch_rejected`, `cancelled`, `timeout`, `skipped`, `unknown`; duration is milliseconds; health values are `healthy`, `unhealthy`, `unknown`. The framework adds distinctions that GitHub job conclusions alone do not provide. These are not free-form app-defined properties.

The compact YAML does not duplicate its capability dictionary. `expand_workflow` derives and validates entities, permitted action targets, observation signatures, recovery pairs and goal rules from saved 03. [WorkflowRuntime.java](../../bdi-cicd-framework/bdi/harness/WorkflowRuntime.java) adapts that contract for `ControllerProjectConfig` and `ProjectConfig`; it does not schedule jobs.

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

| Evidence                                            | Decision under ordinary success goals                                         |
| --------------------------------------------------- | ----------------------------------------------------------------------------- |
| Successful job                                      | Check maintenance and required health, then continue                          |
| Confirmed `transient_failure` or terminal `timeout` | Retry only if retry-safe, within budget and not recovery                      |
| Ordinary failure, cancelled or skipped              | Stop or select configured recovery; no blind retry                            |
| Dispatch rejected                                   | Stop with rejection evidence; no speculative deployment recovery              |
| Execution unknown                                   | Read-only reconciliation of the same execution; no redispatch while uncertain |
| Unhealthy or unavailable measurements               | Bounded reobservation; do not advance                                         |
| Enough consecutive healthy samples                  | Accept health before the deadline and continue                                |
| Persistent staging health failure/uncertainty       | Stop promotion; production remains unchanged                                  |
| Persistent production health failure/uncertainty    | Recover once from verified known-good source, then verify recovery            |

Current input values: one additional execution retry with a five-second delay; up to 36 observations five seconds apart within 180 seconds; two consecutive healthy samples; three reconciliation attempts five seconds apart. A bad/unavailable measurement resets the healthy count. The observation deadline starts with the first observation request and includes measurement time. Two healthy measurements can finish early: 180 seconds is a maximum, not a compulsory wait. Overlapping two-minute metric windows are not independent statistical samples.

The adapter recognizes controlled transient failure only if the exact **Controlled transient failure** step failed. A locally expired polling wait is uncertain, not a confirmed remote timeout eligible for retry. The current Java entity polling limit defaults to 20 minutes; that is separate from the 30-minute production duration maintenance limit and the three-minute health observation limit.

### Success and failure goals

`achieve(A)` supports `entity.status == success` and `entity.status == failure`. A failure goal requires an actual exact `failure`; rejected dispatch, uncertainty, timeout and controlled `transient_failure` do not satisfy it. The goal does not cause fault injection. An unexpected success is not repeatedly executed to manufacture a failure.

A matching failure satisfies that entity's requested outcome without normal retry/automatic recovery. Dependencies still require success, and separately declared maintenance/avoidance rules still apply. Contradictory goals can therefore finish unmet. Use [staging_failure_goal.yaml](../../bdi-cicd-framework/examples/staging_failure_goal.yaml) for the isolated negative experiment in manual D1.

Results include `requested_goals`, `achieved_goals`, `unmet_goals` and `goal_message`. Negative-goal campaigns have `negative_goal_experiment: true` and no `verified_releases`; they cannot certify a rollback baseline. An explicitly expected production failure may happen after the app changed and finish without automatic rollback; restore manually afterward. Unmet pursuit prints **Attempted but failed to achieve goals.**

## 5. Live dispatch, interruption and recovery

For live execution set `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, `BDI_WORKFLOW_REF` and `BDI_RELEASE_SHA` in the controller terminal. The token needs repository access and Actions write. The worker ref selects published workflow code; the full immutable release SHA selects published app source. An unpublished local commit cannot be checked out by GitHub. A push publishes code; launching the controller starts this campaign.

## 6. Payment telemetry and controllable traffic

The [app config](../../src/config.ts), [instrumentation](../../src/telemetry.ts), [Compose file](../../docker-compose.yml), [OTel collector](../../otel-collector.yaml) and [Prometheus configuration](../../prometheus.yml) define/export the actual metrics. The worker supplies host ports and `CI_RUN_ID=execution_id`. Input 01 tells the controller where and how to read them; it does not create app endpoints.

| Environment              | App  | Prometheus | Collector metrics | Database |
| ------------------------ | ---- | ---------- | ----------------- | -------- |
| Staging                  | 3001 | 9091       | 9465              | 5433     |
| Production/recovery      | 3000 | 9090       | 9464              | 5432     |
| Optional local rehearsal | 3002 | 9092       | 9466              | 5434     |

`/ready` reports readiness via HTTP 200/503. `/health` reports `deploymentRunId` and `experimentMode`; the ID is an execution UUID, not a source SHA.
