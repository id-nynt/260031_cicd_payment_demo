# Project contract, agent policy and execution environment

Use the [manual experiment](BDI_MANUAL_EXECUTION_GUIDE.md) for the eight human steps and [setup](BDI_SETUP.md) for tools, credentials and publication. This document describes the current implemented policy.

## Artifact lifecycle and executable files

| Stage | Inputs / component | Output and responsibility |
|---|---|---|
| 1. Engineer configuration | [01_pipeline.yaml](../bdi-cicd-framework/models/01_pipeline.yaml), [02_goal.yaml](../bdi-cicd-framework/models/02_goal.yaml) | Entities, bindings, capabilities, dependencies, budgets and goals |
| 2. Contract compilation | [generate_project.py](../bdi-cicd-framework/generate_project.py) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ [workflow_model.compile_inputs](../bdi-cicd-framework/parser/workflow_model.py) | Saved, validated [03_workflow_model.yaml](../bdi-cicd-framework/models/03_workflow_model.yaml) |
| 3. Agent generation | Saved contract + [controller_generic.asl](../bdi-cicd-framework/generator/controller_generic.asl), through `generate_agent` | Persistent [controller_agent.asl](../bdi-cicd-framework/bdi/controller_agent.asl), plus generation manifest |
| 4. Campaign launch | [run_controller.py](../bdi-cicd-framework/run_controller.py) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ [ControllerMain.java](../bdi-cicd-framework/bdi/harness/ControllerMain.java) | Validate consistency, archive exact artifacts/provenance, acquire repository lock, load Jason |
| 5. Agent environment | [controller.mas2j](../bdi-cicd-framework/bdi/controller.mas2j) binds `controller_agent` to [ControllerEnvironment.java](../bdi-cicd-framework/bdi/harness/ControllerEnvironment.java) | Execute selected actions and publish correlated observations |
| 6. External execution | [GitHubEntityExecution.java](../bdi-cicd-framework/bdi/harness/GitHubEntityExecution.java) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ [entity-execution.yml](../.github/workflows/entity-execution.yml) | Execute only the entity selected by Jason |

Generate once per input/generator revision. App commits, campaign IDs and fault-file contents do not regenerate the agent. Runtime rejects missing, stale or inconsistent persistent artifacts. Campaign directories contain execution evidence and archival copies, not campaign-specific generated agents. Agent generation reads the saved contract as its **sole project-specific input**; the generic template is framework policy.

The compiler validates exact entity/action/observation/recovery/goal agreement. Runtime reconstructs the contract from engineer inputs, verifies hashes and checks the complete deterministic agent projection. This catches altered rules as well as missing facts; updating a hash alone cannot bless an inconsistent agent.

## Read the simplified workflow model (schema 2)

`03_workflow_model.yaml` is now the readable, authoritative project contract. It starts with the BDI definition; execution bindings appear once at the end. It is generated, not another input for engineers to maintain.

| Section | Meaning and source |
|---|---|
| `workflow.entities(E)` | Normal and recovery entity names from input 01 |
| `workflow.dependencies(D)` | Ordered prerequisite edges from input 01 `needs` |
| `workflow.observable_properties(O)` | Framework-supported execution statuses, duration unit and health values |
| `workflow.recovery(R)` | Source-to-recovery mapping from input 01 |
| `goals` | Input 02 achievements, maintenance and avoidance rules, including failure goals |
| `execution` | Retry safety, maximum retries, health observation and reconciliation limits |
| `observation_schema` | Required attempt correlation, duration targets, and observation points before/after jobs |
| `recovery_policy` | Triggers, verified known-good source, no recovery retry, health verification, restored/failed result |
| `bindings` | Project name, GitHub worker/job names, environments, endpoints, metric queries and thresholds |

For example, the main definition reads like this (excerpt):

```yaml
workflow:
  name: Payment service release with BDI recovery
  entities(E): [build, test, security, staging, production, rollback]
  dependencies(D):
    - from: build
      to: test
    - from: test
      to: security
    - from: security
      to: staging
    - from: staging
      to: production
  recovery(R):
    - from: production
      to: rollback
goals:
  achieve(A):
    - production.status == success
    - staging.status == success
```

The full generated file includes O and the policies/bindings described above. There are no repeated goal blocks, repeated job definitions, YAML aliases or serialized lists of every framework action. The compiler derives the internal capability dictionary from this saved contract plus predefined action/observation signatures. It validates the complete generated agent against those derived capabilities and the policy template. The agent generator still reads no project-specific file other than saved 03.

`attempt_id_required` stays true: an old execution cannot satisfy a newer attempt. Execution status includes `unknown` and `dispatch_rejected` as well as normal GitHub conclusions, because those outcomes require different agent decisions. The logical entity remains `rollback` to match the existing worker. `terminal_on_success: restored` is a recovery outcome, not candidate achievement; campaign outcome remains stopped after restoration.

Python `expand_workflow` validates the compact contract and derives internal settings. Java `WorkflowRuntime` translates its bindings/policy for `ControllerProjectConfig` and `ProjectConfig`; it does not choose the next job. The payment agent generated before and after this migration is identical. GitHub workflow and app behavior do not change.

After a schema/generator update, explicitly regenerate each persistent project with its original inputs. Runtime rejects stale artifacts or schema 1 and never silently migrates them. Historical campaign snapshots remain unchanged; their JSON receipts remain usable as evidence and compatible known-good receipts. This worktree's default artifacts and both Java test fixtures have already been regenerated. For custom projects, use their `--project-dir`, `--pipeline` and `--goal` arguments as before.


## What comes from where?

| Concept | Origin |
|---|---|
| Entities E | Engineer-defined jobs/recovery in input 01, mapped to real worker job names |
| Dependencies D | `needs` in input 01; only Jason schedules successors |
| Observations O | Predefined transport schema: status, duration, reconciliation and raw telemetry; actual values come from GitHub/app/Prometheus |
| Recovery R | Engineer mapping from failed environment/entity to a known-good recovery action |
| Goals and thresholds | Input 02; achievements, maintenance, avoidance, error rate and latency |
| Retry capability | `retry_safe` on normal jobs in input 01; default false |
| Policy budgets | Input 01 execution settings, emitted as AgentSpeak facts |
| Reasoning plans | Generic `controller_generic.asl`, included in generated agent |

`generator/bdi_generic.asl` and the old `observable_properties(O)` representation are retained only for legacy compatibility coverage; they are not the active controller policy. Job implementations remain in the worker. Embedding GitHub `steps`, `services` or `runs-on` in input 01 is not supported; the parser rejects those fields. A single-source worker generator would be a separate extension.

## Agent structure: following the original reference

The active template and generated agent follow the supplied reference's named goals, section layout and phase-result events. The executable progression is:

```text
!master_goal
  -> !need_achieve(Entity, Desired)
  -> !run_pipeline
  -> !run_entity(Entity)
  -> run_job(Entity, Attempt)
  -> status(Entity, Attempt, Result)
  -> phase_result(Entity, success | fail)
     success: !maintain -> !check_avoidance -> !run_pipeline
     retryable failure within budget: !run_pipeline -> retry same entity
     other/exhausted failure: !recover -> verified recovery, or stop
  -> !check_master_goal
```

This is actual AgentSpeak control flow, not a diagram layered over a differently named `!control` loop. A successful deployed phase is health-verified before progression/achievement. Unknown execution takes a reconciliation path before a phase failure can authorize retry or recovery. The generated agent is not edited by hand.

| Reference feature | Current equivalent / necessary adaptation |
|---|---|
| `!master_goal`, `!need_achieve`, `!run_pipeline`, `!run_entity` | Preserved named goals |
| `+phase_result(Entity, success/fail)` | Preserved event-based normal/recovery handling |
| `retry_allowed` and attempt counters | Preserved, with explicit retry safety and typed failure eligibility |
| `!maintain`, `!check_avoidance`, `!recover`, `!check_master_goal` | Preserved named responsibilities |
| `workflow_started/stopped/completed`, `master_goal_achieved` | Visible lifecycle beliefs; recovery ends stopped rather than achieved |
| `run_job(Entity)` and unqualified status | `run_job(Entity, Attempt)` and attempt-qualified observations match the current Java environment and reject stale results |
| Global `run_sequence` | Per-entity attempt count plus environment execution UUID; no redundant second attempt identity |
| Final phase success | Every configured achievement, duration/safety condition and required health observation must pass |
| `rollback_production` | Current configured logical name is `rollback`, matching the worker; selection still comes from `recovery(production, rollback)` |

The reference's uncorrelated runtime `status(Entity, fail)` handler is not restored: raw telemetry remains correlated and interpreted by Jason, and the campaign is not an always-running monitoring service. Existing budgets, thresholds and immutable known-good recovery protections remain unchanged by this structural adaptation.

## Decision policy

Jason owns dependencies, retries, delays, reobservation, stop, recovery and achievement. Java transports data and performs actions; GitHub does not choose the next job.

| Observation | Jason's decision |
|---|---|
| Successful normal job | Check duration, then required health before proceeding |
| `transient_failure` or confirmed terminal `timeout` | Retry only if `retry_safe`, retry count remains and entity is not recovery |
| Ordinary `failure`, cancelled or skipped | No blind retry; stop or use configured recovery |
| `dispatch_rejected` | Stop with configuration/authentication evidence; no automatic recovery for an unaccepted deployment |
| `unknown` execution | Reconcile the same execution before any redispatch; stop unresolved if budget expires |
| Unhealthy/unavailable telemetry | Reobserve within count/time limits; do not advance |
| Consecutive healthy samples | Accept health if required count is reached before deadline |
| Persistent bad staging | Stop, leaving production unchanged |
| Persistent bad production | Select verified v1 recovery once, then verify restored health |

`max_retries=1` means two total executions at most. The existence of recovery no longer excludes production from retry: explicit retry safety and result classification decide. Ordinary failing tests/compilation/security results remain deterministic. The adapter recognizes a controlled transient fault only when the exact `Controlled transient failure` step actually failed, not when it is skipped or merely requested. Unclassified failures are not guessed to be transient.

Current payment policy: five-second retry delay; 36 observations; five seconds between observations; 180-second observation deadline; two consecutive healthy samples; three reconciliation attempts. The observation clock starts with the first request, includes measurement time and uses monotonic elapsed time. A bad/unavailable sample resets the healthy count. A healthy sample after the deadline cannot achieve delivery. These are separate budgets; observation does not increment execution attempts. Repeated Prometheus queries may overlap in their two-minute metric window and are not independent statistical samples.

The production job duration goal is 1,800,000 ms (30 minutes) instead of the old 100 seconds, allowing hosted/runner queue and deployment time. Health verification is independently bounded. Engineer-selected budgets remain fixed across experiment comparisons.

Before every dispatch, intent is persisted. Explicit HTTP 401/403/404/422 responses are rejected requests; ambiguous responses, server errors, missing jobs and polling failures remain uncertain. A remote completed timed-out job differs from a local polling timeout: only the former is terminal and potentially retryable.

Recovery uses an achieved live receipt matching repository/project/environment and an immutable release SHA. It rebuilds that source; it does not restore database contents or an attested image. Recovery itself is not retried. Verified restoration finishes `stopped/restored`, never candidate achievement. The agent ends with the campaign; no automatic v2 restart after rollback and no permanent post-campaign monitoring are implemented.

## Payment telemetry and controllable traffic

The app's [config](../src/config.ts), [telemetry](../src/telemetry.ts), [Compose file](../docker-compose.yml), [collector](../otel-collector.yaml) and [Prometheus config](../prometheus.yml) define/export the endpoints and metrics. The worker supplies host ports and `CI_RUN_ID=execution_id`; input 01 describes where the controller reads them.

| Environment | App | Prometheus | Collector metrics | Database |
|---|---|---|---|---|
| Staging | 3001 | 9091 | 9465 | 5433 |
| Production/recovery | 3000 | 9090 | 9464 | 5432 |
| Optional local rehearsal | 3002 | 9092 | 9466 | 5434 |

App HTTP metrics become `payment_http_requests_total`, `payment_http_errors_total` and `payment_http_request_duration_milliseconds_bucket`; readiness is `payment_service_ready`. Input 01 PromQL filters by execution UUID, computes the error ratio and p95 over two minutes, and checks sample age (maximum 30 seconds). Java rejects nonfinite/missing/stale data and publishes raw values. Jason applies the configured limits. Historical or unrelated traffic cannot establish candidate health.

`EXPERIMENT_MODE=request_faults` is an explicit fake-payment experiment capability. Only requests carrying `X-Experiment-Fault: error` return intentional HTTP 503; normal requests succeed, subject to ordinary app/database health. Normal app mode ignores that header. The traffic script's `inject_error` option sends the header and requires request-fault mode; `--continuous` sends batches until Ctrl+C. Stopping error traffic removes the injected cause, but the metric window needs time and new normal traffic to clear. Existing fixed `high_error_rate` mode remains available for deterministic persistent-fault experiments.

`BDI_EXECUTION_PLAN` points to a manually edited properties file, reloaded before each dispatch. Examples: `test.1.failure_mode=transient_failure`, `security.failure_mode=force_failure`, `production.experiment_mode=request_faults`. Attempt-qualified entries override entity defaults. No fault option can satisfy goals or select the next entity; it only changes the selected action's experimental behavior.

The security job now blocks on high/critical production dependency advisories. Tests cover the worker/input/Compose/telemetry mappings. The reporting example remains a second topology tested through generated contracts and Jason simulation; no live reporting application is claimed.

## Success and failure achievement goals

`achieve(A)` accepts `entity.status == success` and `entity.status == failure`. The compiler preserves the desired value in the saved workflow contract and generates `achievement(entity, value)` facts. Jason evaluates every declared achievement, dependency and maintenance constraint. A matching failure completes that entity's goal without retry or automatic recovery; downstream jobs still require successful dependencies. Contradictory or unreachable goals therefore end unmet rather than bypassing dependencies. An unexpected success is not repeatedly dispatched merely to try to create a failure.

Only the exact observed execution status `failure` satisfies a failure goal. `dispatch_rejected`, `unknown`, `timeout`, `cancelled`, `skipped` and the experimental `transient_failure` classification do not. Existing bounded retry rules still apply to eligible transient failures/timeouts. The agent never fabricates a failure or selects fault injection from the desired goal alone.

Java receives both entity and desired status, records `requested_goals`, `achieved_goals`, `unmet_goals` and `goal_message`, and retains attempt-correlated real GitHub execution evidence. A failure-goal campaign has `negative_goal_experiment: true` and emits no `verified_releases`, even when its experiment goals are achieved. Use a normal success-goal campaign to establish a known-good deployment. Failed goal pursuit prints **Attempted but failed to achieve goals.**; unresolved execution remains `unknown`, while a confirmed unmet outcome is `stopped`.

A failure goal does not remove separately declared maintenance goals. For a staging-only failure experiment, use the provided `examples/staging_failure_goal.yaml`; retaining production success/health goals would also require production and can make the combined goals unreachable. The simplified schema 2 contract preserves these semantics and is the executable contract, not a separate summary.

For an explicitly requested production failure, matching the goal ends the experiment without automatic rollback. The worker can fail after changing production; use the manual restoration phase afterward. Ordinary production-success campaigns retain their existing verified recovery policy.
