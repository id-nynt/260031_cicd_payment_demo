# Proposal: simplify the editable BDI models

**Design proposal, implemented 22 September 2026.** The four-source layout is now supported; see [the migration record](BDI_FOUR_SOURCE_MIGRATION.md) for verification and remaining live pilots. The assessment and execution plan below are retained as the design rationale.

## 1. What the archives establish

Reviewed [archived pipeline](../archives/01_pipeline.yaml), [archived goals](../archives/02_goal.yaml) and [archived workflow model](../archives/03_workflow_model.yaml), alongside the current compiler, artifact validator and Java runtime reader.

- The original pipeline exposes only `execution.max_retries`; health checks and monitoring appear as job steps, with their implementation delegated to scripts.
- The archive does not define observation budgets, metric queries or thresholds: their omission does not establish how those scripts would decide health, and its referenced build/deploy/monitor shell scripts are not present in the current `scripts/` directory.
- The archived goal has a 100,000 ms production limit; the current goal has 1,800,000 ms and additionally requires healthy production. Reverting these would change policy, not just simplify formatting.
- The archived generated model omits goal rules and allows observations without attempt IDs. Do not restore those omissions: the current agent needs explicit goals and correlated observations.
- The archive uses `rollback_production`; the working project uses `rollback`. Retain the current name during this relocation to avoid an unrelated mapping change.

## 2. Judgement: three sentences per model

**01_pipeline.yaml.** Keep `max_retries` as the simple retry budget from the original proposal, but move the detailed observation/retry/reconciliation settings into `config/controller_policy.yaml` and telemetry URLs/queries/freshness into `config/runtime_bindings.yaml`. Engineers should review timing and retry safety when adapting their deployment operations, and must check endpoint and metric bindings against their own application's instrumentation rather than accepting payment-service values blindly. The relocation can preserve behaviour after coordinated parser/generator/provenance changes, but deleting fields today can change defaults or fail validation.

**02_goal.yaml.** Move `telemetry_constraints` into `config/controller_policy.yaml`, retaining achievement, maintenance, avoidance and duration units in the goal file. Engineers must review acceptable error rate and latency for their application, while a supplied payment profile can preserve 0.05 and 500 ms for this experiment. Removing these thresholds now fails validation for the observed deployment model, whereas resolving the same values from the proposed profile would preserve the existing health decisions.

**03_workflow_model.yaml.** Keep the resolved `execution`, `observation_schema`, `recovery_policy` and `bindings` blocks in this generated contract, because the agent generator currently reads saved 03 as its sole project-specific input and the runtime consumes its bindings. Engineers should never edit 03 directly: they update the simple models or advanced configuration and explicitly regenerate it. Moving these blocks out of 03 is possible only with a larger contract redesign, so I recommend simplifying the editable inputs while preserving the generated schema and current runtime behaviour.

## 3. Where each extra field belongs

| Fields | Recommended editable location | Who reviews them / why |
|---|---|---|
| `max_retries` | Keep in 01 | Engineer selects the permitted additional execution attempts |
| `observation_attempts`, `observation_interval_seconds`, `observation_timeout_seconds`, `healthy_observations` | Controller policy | Engineer reviews settling time, metric window and required consecutive healthy samples |
| `retry_interval_seconds` | Controller policy | Engineer reviews safe delay before repeating an action |
| `reconciliation_attempts`, `reconciliation_interval_seconds` | Controller policy | Framework supplies bounded defaults; operator tunes for execution discovery/polling, not redispatch |
| `retry_safe` | Controller policy | Engineer explicitly identifies repeatable actions; never infer safety from job names |
| `observe_before`, `observe_after` | Controller policy, expressed as observation placement | Engineer confirms which deployments require health verification and promotion prerequisites |
| `ready_url`, `prometheus_url` | Runtime bindings | Engineer supplies endpoints reachable from the observer, which may differ between a laptop and runner |
| Four metric queries | Runtime bindings | Engineer maps actual exported metric names/labels; retain execution correlation through `{{run_id}}` |
| `max_age_seconds` | Runtime bindings | Engineer reviews exporter/scrape timing and the maximum acceptable sample age |
| Error-rate and latency thresholds | Controller policy | Engineer reviews application service-quality requirements |
| Job/environment/workflow mappings | Keep basic execution mappings in 01; derive 03 bindings | Engineer adapts them to actual GitHub jobs and deployment environments |
| `duration_required_for` | Derived from goal maintenance rules | Generator, not a separately edited list |
| `attempt_id_required: true` | Generated schema invariant | Framework requirement; do not offer an unsafe disable switch |
| Recovery triggers | Controller policy; recovery relationship remains in 01 | Engineer chooses supported triggers for an available recovery capability |
| Known-good source, no recovery retry, verified recovery, `restored`/`failed` outcomes | Validated recovery policy, expanded into 03 | Preserve current safeguards; restoration must not count as candidate delivery |

These concepts also exist in conventional CI/CD as scripts, health gates, retry conditions and settings; these exact YAML keys are framework-specific. Our native comparator already consumes the resolved contract, so it should receive the same effective settings after relocation. Configuration must not secretly move decision-making into Java: Jason still selects actions/rechecks/recovery, while Java executes and measures.

**Pre-migration warning (resolved by explicit required settings):** `parser/workflow_model.py` defaults omitted `observation_attempts` to **18**, not the current **36**, and omitted `retry_safe` to **false**. Other omitted timing fields also resolve through compiler defaults, while telemetry bindings and thresholds are required for observed entities. A migration must preserve explicit resolved values rather than rely on omission.

## 4. Proposed files ? examples only

This changes the input arrangement from two engineer files to **two primary files plus two advanced configuration files**; the extra information is relocated, not eliminated. Use the fixed project-relative paths below initially, with one authoritative location per setting and errors for conflicting duplicates. Ship documented payment defaults, but require a different application to review its mappings and safety assertions.

### models/01_pipeline.yaml ? structure and execution mappings

```yaml
name: Payment service release with BDI recovery
project: payment-service
workflow_file: entity-execution.yml
execution:
  max_retries: 1
jobs:
  build:
    job_name: Build entity
  test:
    needs: build
    job_name: Test entity
  security:
    needs: test
    job_name: Security entity
  staging:
    needs: security
    job_name: Staging entity
    environment: staging
  production:
    needs: staging
    job_name: Production entity
    environment: production
recovery:
  rollback:
    from: production
    job_name: Rollback entity
    environment: production
```

Actual commands remain in the selected-entity GitHub worker. Supporting the archive's complete `runs-on`/`steps`/`on` structure as a directly executable input would be a separate feature; this proposal does not pretend that arbitrary shell steps can be translated into health/retry semantics automatically.

### models/02_goal.yaml ? intended outcomes

```yaml
goal:
  achieve(A):
    - production.status == success
    - staging.status == success
  maintain(M):
    - production.duration <= 1800000
    - production.health == healthy
  duration_unit: milliseconds
  avoid(V):
    - condition: production.status == success
      when: test.status != success
    - condition: production.status == success
      when: staging.status != success
```

This retains the current goals, rather than silently restoring the archive's shorter duration limit or removing its newer health requirement. A successful execution and accepted health remain separate observations; candidate achievement requires all applicable goals and verification rules.

### config/controller_policy.yaml ? advanced decision settings

```yaml
execution:
  observation_attempts: 36
  observation_interval_seconds: 5
  observation_timeout_seconds: 180
  healthy_observations: 2
  retry_interval_seconds: 5
  reconciliation_attempts: 3
  reconciliation_interval_seconds: 5
  retry_safe: [build, test, security, staging, production]
observation:
  before:
    production: staging
  after: [staging, production, rollback]
recovery_policy:
  rollback:
    run_after: [failure, telemetry_block, telemetry_unknown, maintenance_violation]
    release_source: known_good
    retryable: false
    verify_health: true
    terminal_on_success: restored
    terminal_on_failure: failed
telemetry_constraints:
  error_rate_high_gt: 0.05
  latency_p95_ms_high_gt: 500
```

Retries, telemetry rechecks and uncertain-execution reconciliation remain separate budgets. Missing/invalid telemetry is insufficient verification evidence, not proof that the application is broken; retain the current bounded decision policy while making that distinction visible in observations.

### config/runtime_bindings.yaml ? application monitoring integration

```yaml
telemetry:
  environments:
    staging:
      ready_url: http://127.0.0.1:3001/ready
      prometheus_url: http://127.0.0.1:9091
    production:
      ready_url: http://127.0.0.1:3000/ready
      prometheus_url: http://127.0.0.1:9090
  metrics:
    error_rate_query: >-
      (sum(rate(payment_http_errors_total{ci_run_id="{{run_id}}",route="/payments",status_code=~"5.."}[2m]))
      or vector(0)) / clamp_min(sum(rate(payment_http_requests_total{ci_run_id="{{run_id}}",route="/payments"}[2m])), 0.001)
    latency_p95_ms_query: >-
      histogram_quantile(0.95, sum by (le) (rate(payment_http_request_duration_milliseconds_bucket{ci_run_id="{{run_id}}",route="/payments"}[2m])))
    availability_query: min(payment_service_ready{ci_run_id="{{run_id}}"})
    sample_age_seconds_query: time() - max(timestamp(payment_service_ready{ci_run_id="{{run_id}}"}))
  max_age_seconds: 30
```

These are monitoring connections, not instructions to change the application's listening ports. Keep credentials out of these tracked files; changing URLs/queries changes project configuration and therefore requires explicit regeneration.

### models/03_workflow_model.yaml ? generated, fully resolved contract

**Recommended output: the same schema and resolved values as the current 03.** The new compiler would merge the four sources before saving this file; its header/provenance should name all four sources, while the agent generator still reads only saved 03 and the generic template.

<details>
<summary>Proposed generated file contents (expand to inspect)</summary>

```yaml
# Generated from models/01_pipeline.yaml, models/02_goal.yaml,
# config/controller_policy.yaml and config/runtime_bindings.yaml; do not edit.
schema_version: 2
workflow:
  name: Payment service release with BDI recovery
  entities(E):
  - build
  - test
  - security
  - staging
  - production
  - rollback
  dependencies(D):
  - from: build
    to: test
  - from: test
    to: security
  - from: security
    to: staging
  - from: staging
    to: production
  observable_properties(O):
    status:
      values:
      - success
      - failure
      - transient_failure
      - dispatch_rejected
      - cancelled
      - timeout
      - skipped
      - unknown
    duration:
      unit: milliseconds
    health:
      values:
      - healthy
      - unhealthy
      - unknown
  recovery(R):
  - from: production
    to: rollback
goals:
  achieve(A):
  - production.status == success
  - staging.status == success
  maintain(M):
  - production.duration <= 1800000
  - production.health == healthy
  duration_unit: milliseconds
  avoid(V):
  - condition: production.status == success
    when: test.status != success
  - condition: production.status == success
    when: staging.status != success
execution:
  max_retries: 1
  observation_attempts: 36
  observation_interval_seconds: 5
  reconciliation_attempts: 3
  reconciliation_interval_seconds: 5
  retry_interval_seconds: 5
  observation_timeout_seconds: 180
  healthy_observations: 2
  retry_safe:
  - build
  - test
  - security
  - staging
  - production
observation_schema:
  attempt_id_required: true
  duration_required_for:
  - production
  before:
    production: staging
  after:
  - staging
  - production
  - rollback
recovery_policy:
  rollback:
    run_after:
    - failure
    - telemetry_block
    - telemetry_unknown
    - maintenance_violation
    release_source: known_good
    retryable: false
    verify_health: true
    terminal_on_success: restored
    terminal_on_failure: failed
bindings:
  project: payment-service
  controller:
    workflow_file: entity-execution.yml
    jobs:
      build: Build entity
      test: Test entity
      security: Security entity
      staging: Staging entity
      production: Production entity
      rollback: Rollback entity
    environments:
      staging: staging
      production: production
      rollback: production
  environments:
    staging:
      ready_url: http://127.0.0.1:3001/ready
      prometheus_url: http://127.0.0.1:9091
    production:
      ready_url: http://127.0.0.1:3000/ready
      prometheus_url: http://127.0.0.1:9090
  metrics:
    error_rate_query: (sum(rate(payment_http_errors_total{ci_run_id="{{run_id}}",route="/payments",status_code=~"5.."}[2m]))
      or vector(0)) / clamp_min(sum(rate(payment_http_requests_total{ci_run_id="{{run_id}}",route="/payments"}[2m])),
      0.001)
    latency_p95_ms_query: histogram_quantile(0.95, sum by (le) (rate(payment_http_request_duration_milliseconds_bucket{ci_run_id="{{run_id}}",route="/payments"}[2m])))
    availability_query: min(payment_service_ready{ci_run_id="{{run_id}}"})
    sample_age_seconds_query: time() - max(timestamp(payment_service_ready{ci_run_id="{{run_id}}"}))
  max_age_seconds: 30
  thresholds:
    error_rate_high_gt: 0.05
    latency_p95_ms_high_gt: 500
```

</details>

This deliberately retains runtime detail in the generated artifact: a shorter display is not worth losing a complete, inspectable project contract. Java and native GitHub helpers continue reading resolved 03; neither should independently reload profiles and silently override it.

## 5. Migration execution plan (see migration record for completion)

- **Create the two proposed configuration files:** relocate the existing values exactly; keep original files until migration validation succeeds, and preserve historical evidence.
- **Update input parsing:** extend `parser/workflow_model.py` to resolve the four sources into the existing normalized project model; validate entity references, defaults, conflicts, metric correlation and recovery invariants before generation; adapt `parser/model_transform.py` only where its normalized interface requires it.
- **Update generation:** extend `generate_project.py` and `project_artifacts.py` to locate/record the additional inputs, save 03, reload/validate it, then generate the agent solely from that saved contract; preserve `generator/controller_generic.asl` decision policy unless a separate behaviour change is intended.
- **Update consistency/provenance:** hash all four inputs and relevant generator sources in `generation-manifest.json`, include the resolved configuration in campaign provenance, and reject missing/stale profiles with an explicit regeneration instruction; do not regenerate at campaign startup.
- **Check runtime consumers:** retain 03 schema 2 so `WorkflowRuntime.java`, project configuration readers and agent/environment interfaces need no policy rewrite; adjust launcher/snapshot handling where it currently assumes exactly two inputs.
- **Keep the comparison fair:** update `run_controller.py`, `run_experiment.py`, native `scripts/native-experiment.py` and pairing/provenance handling as needed; both approaches must consume the same resolved policy, with unsupported conventional configurations still rejected.
- **Test migration equivalence:** compare old and relocated-input compiled contracts and generated agent bodies; allow only intentional provenance/header differences, and verify the payment and second-application fixtures plus supported failure goals.
- **Test failure handling:** missing profiles, unknown entities, duplicate/conflicting settings, stale artifacts, altered thresholds, unsafe retries and mismatched recovery bindings must fail clearly; confirm correlated observations, bounded retries/rechecks, known-good recovery and restoration distinct from delivery.
- **Run existing validation suites:** parser/generator tests, Java adapter/policy tests, actual Jason simulations, traffic tests and workflow checks; update templates and manuals to the new four-source lifecycle.
- **Explicitly regenerate once and pilot:** after the migration passes offline checks, regenerate the persistent artifacts, then run paired healthy, transient and rollback pilots before freezing a new experiment revision; no automatic deployment is part of this proposal.

**Implementation status:** see the linked migration record. **Effect of a correctly implemented migration:** a simpler editing surface with the same effective policy, but new artifact hashes/provenance requiring one explicit regeneration and revalidation.
