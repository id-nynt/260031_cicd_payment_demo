# Project contract, agent policy and execution environment

Use the [manual experiment](BDI_MANUAL_EXECUTION_GUIDE.md) for the eight human steps and [setup](BDI_SETUP.md) for tools, credentials and publication. This document describes the current implemented policy.

## Artifact lifecycle and executable files

| Stage | Inputs / component | Output and responsibility |
|---|---|---|
| 1. Engineer configuration | [01_pipeline.yaml](../bdi-cicd-framework/models/01_pipeline.yaml), [02_goal.yaml](../bdi-cicd-framework/models/02_goal.yaml) | Entities, bindings, capabilities, dependencies, budgets and goals |
| 2. Contract compilation | [generate_project.py](../bdi-cicd-framework/generate_project.py) → [workflow_model.compile_inputs](../bdi-cicd-framework/parser/workflow_model.py) | Saved, validated [03_workflow_model.yaml](../bdi-cicd-framework/models/03_workflow_model.yaml) |
| 3. Agent generation | Saved contract + [controller_generic.asl](../bdi-cicd-framework/generator/controller_generic.asl), through `generate_agent` | Persistent [controller_agent.asl](../bdi-cicd-framework/bdi/controller_agent.asl), plus generation manifest |
| 4. Campaign launch | [run_controller.py](../bdi-cicd-framework/run_controller.py) → [ControllerMain.java](../bdi-cicd-framework/bdi/harness/ControllerMain.java) | Validate consistency, archive exact artifacts/provenance, acquire repository lock, load Jason |
| 5. Agent environment | [controller.mas2j](../bdi-cicd-framework/bdi/controller.mas2j) binds `controller_agent` to [ControllerEnvironment.java](../bdi-cicd-framework/bdi/harness/ControllerEnvironment.java) | Execute selected actions and publish correlated observations |
| 6. External execution | [GitHubEntityExecution.java](../bdi-cicd-framework/bdi/harness/GitHubEntityExecution.java) → [entity-execution.yml](../.github/workflows/entity-execution.yml) | Execute only the entity selected by Jason |

Generate once per input/generator revision. App commits, campaign IDs and fault-file contents do not regenerate the agent. Runtime rejects missing, stale or inconsistent persistent artifacts. Campaign directories contain execution evidence and archival copies, not campaign-specific generated agents. Agent generation reads the saved contract as its **sole project-specific input**; the generic template is framework policy.

The compiler validates exact entity/action/observation/recovery/goal agreement. Runtime reconstructs the contract from engineer inputs, verifies hashes and checks the complete deterministic agent projection. This catches altered rules as well as missing facts; updating a hash alone cannot bless an inconsistent agent.

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
