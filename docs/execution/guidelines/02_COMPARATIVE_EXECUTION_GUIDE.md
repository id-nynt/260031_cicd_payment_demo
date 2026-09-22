# Compare BDI with conventional GitHub Actions

**Current layout:** conventional implementation and frozen configuration are in `ci-cd-conventional/`; shared catalog and metrics are in `experiments/`. Its runtime does not import BDI. Workflow installation copies are checked for drift in CI.

**Configuration lifecycle:** BDI uses its four explicit sources and generated schema-3 repair contract/agent. Conventional uses its own frozen `config.json` and snapshots. No campaign regenerates either project. After changing BDI policy, regenerate explicitly, review/update conventional snapshots and static workflow as needed, then run the parity check. Freeze one published control revision for both approaches; existing v1/v2 tags and verified receipts remain usable.

Use one payment app/repository, the same immutable v1/v2 sources and one shared deployment environment. **Conventional entry:** [ci-cd.yml](../../../.github/workflows/ci-cd.yml). **BDI entry:** `run_experiment.py --mechanism bdi`. Both use [entity-execution.yml](../../../.github/workflows/entity-execution.yml); conventional uses `needs`/conditions and a bounded telemetry script, while BDI uses Jason beliefs/plans.

Follow the [conventional manual](04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md) for publication/setup and GitHub activation; follow [BDI manual C1](03_BDI_MANUAL_EXECUTION_GUIDE.md#c6-matched-comparison-all-11-scenarios) for agent activation. Complete common setup/reset before **each** trial. Do not run both mechanisms simultaneously.

The earlier `--mechanism conventional` Java implementation remains an optional **scripted controller** for controlled policy tests. It is not the native GitHub baseline described here. Its old walkthrough is [archived](../../archives/04_manual-guides/02_COMPARISON-before-native-workflow.md).

## Shared scenarios

Both entry points use the same 13 names in [scenarios.json](../../../experiments/scenarios.json). This table defines the fault, exposure and expected safe response for **both** approaches.

| Case | Automatic injection / timing | Expected result |
|---|---|---|
| `healthy` | Normal production traffic | Deliver and verify v2 |
| `candidate-stopped` | Stop app after the production deployment job passes; database remains ready | Diagnose, restart once, verify fresh health, deliver v2 |
| `candidate-restart-fails` | Same fault, with a controlled stop immediately after restart | Repair fails; restore verified v1 without claiming v2 delivery |
| `build-failure` | Build job exits before compilation/deployment | Stop; production remains v1 |
| `test-failure` | Test job exits with persistent failure | Stop; production remains v1 |
| `transient-test-failure` | First test attempt exits as a typed transient failure; second executes tests | Retry once; deliver if checks pass |
| `service-unavailable` | After production Compose deployment, stop only its app container | Readiness check fails; restore verified v1 and verify health |
| `infrastructure-failure` | After staging deployment, stop only its PostgreSQL container | Readiness check fails; block promotion; production remains v1 |
| `deployment-timeout` | Staging job sleeps 90s before deployment, with a 1-minute job deadline; repeat fault on retry | Confirm timeout, retry once, stop before production |
| `staging-temporary` | Stage request-fault mode; 75s mixed errors, then normal traffic | Recheck; promote if health recovers within budget |
| `staging-persistent` | Stage request-fault mode; persistent mixed errors | Exhaust bounded observations; block promotion |
| `production-temporary` | Production request-fault mode; 75s mixed errors, then normal traffic | Recheck; accept v2 if health recovers within budget |
| `production-persistent` | Production request-fault mode; persistent mixed errors | Exhaust observations; restore and verify v1 |

**Scope:** build/test failures are controlled job failures, not yet independent commits with compiler/test defects. “Service unavailable” means the deployed payment service; “infrastructure failure” means its staging database, not the entire host/cloud. The timeout is a controlled pre-deployment hang. A host loss, runner loss, deployment API outage and real network partition remain additional experiments; do not report these scoped faults as proving resilience to those broader failures.

Traffic profiles use a fixed seed, bounded rates/jitter and the same request-fault headers. Temporary faults transition automatically to normal traffic; persistent faults stop when containment/recovery starts. Normally both approaches keep normal or fault traffic running during each staging/production observation window. For `candidate-stopped` and `candidate-restart-fails`, the app cannot initially serve requests: production uses the shared repair worker's 120-second payment probes after restart instead of the ordinary traffic client. Both retain the 60-second pause and normal staging traffic. Failed restart intentionally produces no successful post-repair probes. Retain operation receipts and health observations as fault/repair evidence.

**Efficient initial subset:** `healthy`, `build-failure`, `candidate-stopped`, `production-persistent`, `candidate-restart-fails`; add `production-temporary` for passive recovery. The larger catalog is optional. Predeclare the selected cases and repetitions before measuring; do not select only cases favoring one approach.

## Common setup and execution order

1. Publish one new workflow/control revision, then freeze its tag. Existing v1/v2 commits remain unchanged.
2. Start Docker Desktop and the same self-hosted Linux runner. Verify both environments are reachable.
3. Restore both environments to verified v1. Stop old traffic, settle previous remote jobs and retain database state consistently (or use a separately documented reset).
4. Pick one table case, candidate SHA, verified v1 receipt and seed 42.
5. Manually launch ONE approach. Fault setup, traffic transitions and evidence collection are automatic.
6. Save results, including unsuccessful/incomplete runs. Record interventions and verify visible app version/identity independently.
7. Restore v1; run the same case with the other approach. Alternate order in later repetitions.

Shared policy: one additional execution retry for confirmed transient failure/timeout on retry-safe jobs; no blind retry of uncertain execution; 5-second retry delay; 60-second warmup at each successful staging/production deployment; at most 36 observations/180 seconds with 5-second intervals; two consecutive healthy observations; error rate <=5%, p95 <=500ms, readiness/availability and sample freshness required. Production restoration uses the verified known-good receipt and must pass its own health gate.

The native retry DAG currently supports the payment topology, one retry and a five-second retry delay. Startup rejects incompatible contract revisions. BDI remains the configurable generated agent. BDI reads its saved contract; conventional reads its own checked-in policy and contract snapshots. Run `py -3 ci-cd-conventional/configuration.py --check-bdi-parity` before freezing a paired revision. No per-campaign generation occurs.

Candidate repair has separate limits: diagnose once on the first unhealthy/unknown production sample, allow one restart only for the matching stopped app with a ready database, run the shared 120-second probes, then require two new healthy observations and current deployment identity. The 300-second decision budget starts at diagnosis; queue/approval delays count. Adapter/worker/network timeouts can add bounded wall-clock overhead. A restart resets the observation window/count in both implementations but cannot extend the overall repair budget. Inapplicable diagnosis resumes bounded observation; failed verification/known-terminal repair failure permits verified rollback. BDI preserves unresolved execution and stops when remote operation status is uncertain. The conventional gate's script runs synchronously on the runner; runner loss remains a separate untested case.

Conventional execution uses one workflow with six jobs. Each job records mechanical attempts and fails if its selected attempt is unsuccessful. Deployment health checks are steps inside staging/production/rollback. The collector aggregates terminal metadata and receipts offline; a successful rollback restores v1 but does not establish v2 delivery. There are no reusable entity/health wrappers or report/result jobs.

## Evidence and metrics

| BDI | Native GitHub Actions |
|---|---|
| Printed local campaign directory | Run artifacts: `native-prepare`, `native-<entity>`; collected result is generated locally |
| Controller result/journal and common events | Same result/common-event schema plus GitHub job records |
| Sibling `*-experiment/plan.json` | Preparation plan, conventional config, frozen input/contract snapshots and workflow copies |
| Sibling `*-traffic/` plus `*-traffic-<other-stage>/` | Gate artifact contains profile, requests/transitions and traffic summary |
| Automatic `experiment-metrics.json` | Automatic `native-result/result/experiment-metrics.json` |

Record candidate-delivery rate separately from restoration rate, containment, retries, observations, human interventions, elapsed time and recovery time. `eligible_for_comparison` flags missing/failed traffic, incomplete evidence and non-live runs. It is a screening flag, not independent proof of fault exposure or safety. A controlled execution fault must also appear in the relevant job logs. `protocol_expectation_met` is the case expectation, not an oracle proving correctness.

Repair metrics are `repair_attempts`, `diagnoses`, `candidate_repaired`, `candidate_repair_seconds` and `repair_failures`. Count restart separately from normal job retries. `candidate_repaired` requires both executed repair and verified v2 delivery. Rollback can improve restoration rate while candidate delivery remains false. Summaries expose candidate repair rate among trials that attempted repair, with its denominator separate from rollback restoration rate.

`protocol_key` compares case, seed, candidate, baseline, worker commit, contract, policy, all four input hashes and traffic profile. Match it across the native/BDI pair. The older `comparison_key` belongs to the scripted-controller comparison; do not use it to pair native trials. A matching key cannot certify database state, queue load or actual timing.

Use the [results inspection guide](05_EXPERIMENT_RESULTS_GUIDE.md) for collection, fields, line filters and combined CSV output. New BDI results live under `experiments/results/bdi/`; downloaded native results live under `experiments/results/conventional/`. Keep all sibling experiment/traffic directories. Historical verification evidence is under `docs/archives/06_experiment-records/`.

Timing limitations: BDI action duration includes adapter-observed dispatch/poll waits; native job duration comes from GitHub job start/end. These are not identical execution-cost measures. Native recovery timing includes GitHub job scheduling. Report whole-trial elapsed time plus raw GitHub timestamps separately; do not present summed entity duration as billed runner cost. The native gate is scheduled as a separate self-hosted job, whereas BDI observes locally: measure this scheduling overhead, and retain actual traffic/observation timestamps.

## What can BDI do better?

**For the implemented matched policy, equivalent outcomes are the honest expectation.** Conventional CI/CD can retry, wait for telemetry recovery, block promotion and roll back. These capabilities are not exclusive to BDI.

- **Potential advantage:** changing goals, dependencies or available recovery capabilities may be easier to express and inspect through agent beliefs/plans. Current BDI also journals uncertain dispatch intent and reconciles it before redispatch. Test interruption/reconciliation separately before claiming a reliability advantage over the native workflow.
- **Temporary test or telemetry failure:** BDI should improve over a fail-fast pipeline with no retry/recheck. Our conventional baseline includes those protections, so expect a tie unless observations demonstrate a difference.
- **Persistent production degradation or failed deployment:** both should restore verified v1. This improves service recovery, not v2 delivery.
- **Stopped but repairable v2 process:** both have the same restart capability. BDI demonstrates diagnosis, contextual plan selection, fresh verification and resumption of its master goal; a capable conventional gate may achieve the same delivery outcome. Failed repair demonstrates bounded fallback, not proof of BDI superiority.
- **Compiler defect, consistently failing test, persistent staging failure:** neither should deliver a broken v2. Correct stopping is the desired result.
- **Host/runner/database loss with no available repair capability:** reasoning alone cannot repair it. Neither approach can promise completion without an executable recovery path.

The research conclusion must follow repeated paired results. If rates match, report that result and compare decision traceability, policy adaptation effort and overhead. Do not remove safeguards from the conventional baseline to manufacture a BDI advantage.

## Verification before live experiments

Offline checks cover workflow syntax, shared scenario/worker contracts, bounded telemetry, malformed/stale samples, pairing keys, existing Java policies/adapters and traffic scheduling. They do **not** validate real GitHub scheduling, reusable-workflow failure propagation or actual Docker recovery.

Next pilot: healthy pair, candidate-stopped pair, then failed-repair and persistent-production pairs; inspect original deployment identity, diagnosis/restart receipts, fresh verification and restoration before collecting the predeclared repeated dataset. Existing app pairs can use a newly published control revision via BDI manual A4.4. No new live comparative trials have been run as part of this implementation.


Current support scripts store a per-environment `traffic_targets` plan and validate `traffic_by_entity` evidence for gates actually reached. Before new trials, publish a reviewed control revision and use the full control-file check in [guide 06, Step 3](06_PAIRED_EXPERIMENTS_END_TO_END.md). This includes the refactored agent and metric/traffic scripts; checking only the worker YAML is insufficient. Existing app SHAs remain valid. For the complete sequential run, collection, evaluation and reset procedure, use guide 06.
