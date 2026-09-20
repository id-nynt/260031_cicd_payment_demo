> Historical file inventory. Superseded operating guides are now in `docs/archive/pre-policy-refactor`; see the current manual and setup reference for execution.

# Project file audit: active, legacy and cleanup candidates

Audit date: 20 September 2026. Scope: this payment-repair worktree, its tracked source/tests/docs, configured launch paths, and observed local generated directories. No files were deleted or moved. The user's uncommitted additions to `NOTE.md` were preserved.

**Conclusion:** there are removable local build products and several legacy implementation families outside the canonical runtime. Some apparent duplicates are required project artifacts, regression fixtures or experiment evidence. Do not perform a blanket removal of `legacy`, `build`, `runs`, `monitoring` or old-looking Java files.

## 1. How the classification was checked

- Inspected [build.gradle](../bdi-cicd-framework/bdi/build.gradle), [controller.mas2j](../bdi-cicd-framework/bdi/controller.mas2j), the Python entry points, application imports, npm scripts and both active GitHub workflows.
- Compared Java type-name references starting from `ControllerMain` / `ControllerEnvironment`, and separately from the current Java tests. Inspected representative legacy entry points and shared classes directly.
- Checked tracked references to old templates/scripts and inspected parser/baseline regression tests.
- Checked ignored local output directories and confirmed `node_modules`, `dist`, framework `runs`, and framework `bdi/build` are not tracked source.

The Java reference analysis is a conservative source-level inventory, not a whole-program proof of dead code. It includes referenced types in compatibility methods even when those methods are not called by the current controller. External/manual consumers of old entry points are outside this audit. Gradle currently compiles all Java source under `bdi`, `monitoring` and `actions`, including legacy code.

## 2. Regenerable local output

These directories were present in this worktree. They are not required as versioned source.

| Location | Classification | Treatment |
|---|---|---|
| `node_modules/` | Installed npm dependencies | Can be recreated with `npm ci`; removing it interrupts local npm commands until reinstall |
| `dist/` | TypeScript compilation output | Can be recreated with `npm run build`; used by local `npm start`; Docker builds its own output from source |
| `bdi-cicd-framework/bdi/.gradle/` | Local Gradle cache/state | Regenerable while no build is active |
| `bdi-cicd-framework/__pycache__/`, `parser/__pycache__/` | Python bytecode caches | Regenerable |
| `bdi-cicd-framework/bdi/build/` | **Mixed:** compiled Java/test output plus local campaign verification evidence | Preserve needed campaign directories, journals/results and test evidence before cleaning build output |
| `bdi-cicd-framework/runs/` | **Experiment data**, including receipts, snapshots, fault files and sometimes separately generated example projects | Not a disposable cache; archive deliberately, retain trusted receipts and project artifacts still used by experiments |

Existing `bdi/build/` contains lifecycle verification and manual agent-check campaigns from this work. A Gradle clean can remove those even though the source is reproducible. Git ignore status means “not versioned,” not “safe to discard.” No deletion commands are proposed here because evidence retention needs to be decided first.

## 3. High-confidence redundant or retired pieces

| Exact location | Evidence | Recommendation |
|---|---|---|
| Old `paymentPage` export within [src/ui.ts](../src/ui.ts) | [src/app.ts](../src/app.ts) imports only `checkoutPage` and `receiptPage` from this module; it imports the active payment page from [src/payment-page.ts](../src/payment-page.ts). The UI test also imports the latter. | Candidate to remove the unused **export block only** in a focused cleanup. Keep `src/ui.ts`: its checkout and receipt exports are active. |
| [scripts/check-gate-telemetry.mjs](../scripts/check-gate-telemetry.mjs) | References found in historical `BDI_EXPERIMENT.md`; neither current workflow nor npm scripts invokes it. | Legacy gate diagnostic; archive/remove if the old manual diagnostic is no longer wanted. Keep the active traffic and telemetry-display helpers. |
| [bdi/CicdEnvironment.java](../bdi-cicd-framework/bdi/CicdEnvironment.java) | Legacy environment using shell actions, budgets and Java-side classification; current MAS names `harness.ControllerEnvironment`. | Candidate to archive with its legacy dependency family, after deciding compatibility support. |
| [harness/ProjectGateMain.java](../bdi-cicd-framework/bdi/harness/ProjectGateMain.java) | Launches `gate.mas2j`, which is archived; there is no current Gradle gate launch task. | Retired entry point, not a supported way to run this experiment. |
| [harness/ProjectBaselineProbe.java](../bdi-cicd-framework/bdi/harness/ProjectBaselineProbe.java) | Standalone older probe, not selected by the canonical launcher or current tests. | Candidate to archive if the old probe is no longer used manually. |

The unused `paymentPage` export is duplicated functionality rather than an identical byte-for-byte copy. Do not remove `src/payment-page.ts`; it is the active implementation and is tested.

## 4. Legacy Java families outside the current launch/test reference paths

The following names are outside the conservative reference closure from both canonical entry points and current Java tests. They form connected older implementations, so review/remove them together rather than deleting individual shared dependencies arbitrarily.

### Old harness adapters and environments

All paths below are under `bdi-cicd-framework/bdi/harness/`:

```text
BeliefAdapter.java
CompositeObservationProvider.java
CorrelationRegistry.java
EnvironmentFactory.java
GitHubActionsWorkflowExecutor.java
GitHubEnvironment.java
JasonBeliefAdapter.java
MockEnvironment.java
MockObservationProvider.java
MockWorkflowExecutor.java
MultiTelemetryObservationProvider.java
ObservationEnvironment.java
ObservedRunExecutor.java
ProjectBaselineProbe.java
ProjectGateEnvironment.java
ProjectGateMain.java
ProjectRunEnvironment.java
ScenarioEnvironment.java
ScenarioObservationProvider.java
ScenarioWorkflowExecutor.java
TelemetryObservationProvider.java
WorkflowExecutor.java
```

These are legacy/compatibility candidates, not active campaign launchers. In particular, `GitHubActionsWorkflowExecutor` is not the active `GitHubEntityExecution`, and `ScenarioWorkflowExecutor` is not the active `ScenarioEntityExecution`.

### Old shell execution, budgets and classification

```text
bdi-cicd-framework/bdi/CicdEnvironment.java
bdi-cicd-framework/actions/action/CicdAction.java
bdi-cicd-framework/actions/action/ShellActionExecutor.java
bdi-cicd-framework/actions/budget/AttemptBudget.java
bdi-cicd-framework/actions/budget/InMemoryAttemptBudget.java
bdi-cicd-framework/actions/policy/ActionPolicy.java
bdi-cicd-framework/actions/policy/AllowlistedActionPolicy.java
bdi-cicd-framework/monitoring/TelemetryAdapter.java
bdi-cicd-framework/monitoring/audit/AuditSink.java
bdi-cicd-framework/monitoring/audit/ConsoleFileAuditSink.java
bdi-cicd-framework/monitoring/classifier/TelemetryClassification.java
bdi-cicd-framework/monitoring/classifier/TelemetryClassifier.java
bdi-cicd-framework/monitoring/classifier/TelemetryThresholds.java
```

Current Jason policy owns retry/reobservation/recovery and threshold classification; it does not select these older shell-policy/classifier components. The retained standalone telemetry README describes part of this older path. Archiving these families would reduce confusion, but it is a separate source cleanup requiring compilation and regression verification.

## 5. Legacy material that still has test or shared-code users

| Location | Why it is still needed |
|---|---|
| [generator/bdi_generic.asl](../bdi-cicd-framework/generator/bdi_generic.asl) | Inactive for the canonical agent, but `test_model_transform.test_deterministic_output` reads it. Deleting it breaks compatibility tests. |
| [parser/model_transform.py](../bdi-cicd-framework/parser/model_transform.py) | Mixed active/legacy file: canonical compilation uses `parse_model`, model structures and `project_beliefs`. Only its old CLI/serializer is retired from the active path. Do not delete the file. |
| [parser/fixtures/legacy/](../bdi-cicd-framework/parser/fixtures/legacy/) | Parser tests read old pipeline/goals; Java `PaymentBaselineTest` reads `payment_project.yaml`. Do not delete the directory wholesale. Not every retained fixture is claimed to have a direct current consumer. |
| [harness/GitHubRunObserver.java](../bdi-cicd-framework/bdi/harness/GitHubRunObserver.java), [GateEvidence.java](../bdi-cicd-framework/bdi/harness/GateEvidence.java) | Outside the canonical live controller, but explicitly used by `PaymentBaselineTest`. |
| [bdi/fixtures/payment-jobs-success.json](../bdi-cicd-framework/bdi/fixtures/payment-jobs-success.json), [payment-jobs-pre-promotion.json](../bdi-cicd-framework/bdi/fixtures/payment-jobs-pre-promotion.json) | Used by those baseline compatibility tests. |
| `ProjectConfig.java`, `ProjectTelemetryProvider.java` | Both contain compatibility features but are also used for current telemetry. Keep; any removal must be method-level and evidence-based. |
| `ObservationProvider.java`, `monitoring/Observation.java`, `CorrelationContext.java` | Shared type dependencies reachable through current telemetry/logging classes, even where individual compatibility methods are inactive. |

## 6. Intentionally archived history and older guidance

| Location | Classification / treatment |
|---|---|
| [docs/legacy/pre-canonical/](legacy/pre-canonical/) | Intentional archive: old agents, `gate.mas2j`, `project.mas2j`, alternate Gradle files and manual rollback workflow. Preserve for the research comparison; not executable configuration. |
| [docs/experiments/](experiments/) | Retained historical and current verification evidence. Preserve. |
| [BDI_EXPERIMENT.md](archive/pre-policy-refactor/BDI_EXPERIMENT.md), [BDI_ARCHITECTURE_AUDIT_AND_PLAN.md](archive/pre-policy-refactor/BDI_ARCHITECTURE_AUDIT_AND_PLAN.md), [BDI_CONTROLLER_EXPERIMENT_RESULTS.md](archive/pre-policy-refactor/BDI_CONTROLLER_EXPERIMENT_RESULTS.md) | Earlier experiment/audit/results material. Useful history, not current operating instructions. The architecture audit's opening update still describes launcher generation and should be read as historical. |
| [00_PLAN.md](00_PLAN.md), [PROJECT.md](../PROJECT.md) | Earlier planning/design material. Candidates to label/archive more clearly; not runtime dependencies. |
| [BDI_LIVE_MANUAL_DEMO.md](archive/pre-policy-refactor/BDI_LIVE_MANUAL_DEMO.md) | Short redirect to the current manual. Small intentional compatibility document, not harmful duplication. |
| [.github/workflows/README-legacy-ci-cd.md](../.github/workflows/README-legacy-ci-cd.md) | Markdown pointer explaining current selected-entity workflows; despite its name it is not an active workflow or an old YAML pipeline. |
| [NOTE.md](NOTE.md) | User notes/style reference with uncommitted additions. Preserve; do not classify personal research notes as generated clutter. |

The archive README also contains an old sentence about generating workflow/agent per campaign. The authoritative lifecycle is now in [BDI_GENERATION_AND_RUNTIME.md](BDI_GENERATION_AND_RUNTIME.md). This audit records the stale guidance without rewriting the historical archive.

## 7. Generated or similar-looking files that must stay

- Persistent project artifacts: `models/01_pipeline.yaml`, `02_goal.yaml`, `03_workflow_model.yaml`, `models/generation-manifest.json`, `bdi/controller_agent.asl`. Generated does not mean disposable: runtime requires them and does not silently regenerate them.
- Active framework: `generate_project.py`, `project_artifacts.py`, `parser/workflow_model.py`, reused `parser/model_transform.py`, `generator/controller_generic.asl`, `run_controller.py`, `bdi/controller.mas2j`, `build.gradle`, `settings.gradle`, Gradle wrappers/JAR and logging configuration.
- Current Java path: `ControllerMain`, `ControllerEnvironment`, `ControllerProjectConfig`, `EntityExecution`, `GitHubEntityExecution`, `ScenarioEntityExecution`, `ExperimentExecutionPlan`, `ProjectConfig`, `ProjectTelemetryProvider`, `StructuredEventLogger` and their shared observation/logging dependencies. Keep `monitoring/observer/PrometheusTelemetryObserver`, `TelemetryObserver`, `TelemetrySample`.
- Canonical fixture copies `bdi/fixtures/controller-workflow.yaml` and `reporting-workflow.yaml`: used by Java tests and checked against Python compilation; they are deliberate test fixtures, not competing runtime artifacts.
- `examples/reporting_pipeline.yaml`, `reporting_goal.yaml`, `staging_goal.yaml`, `verify_controller_experiment.py` and tests: second-application/goal coverage and developer regression verification. The manual does not need the full automated matrix, but that does not make it unneeded for development.
- App source, SQL migrations, `package-lock.json`, Docker/Compose, OTel and Prometheus configuration, current worker/validation workflows, active traffic helpers and `show-telemetry.mjs`.
- `.git`/common Git metadata, controller pending-execution state and live lock files: coordination/history, never reset by a cleanup sweep. Do not delete local secrets/configuration as if they were build output.

Campaign copies of agents/contracts are deliberate archival snapshots identifying the executed project revision. They are not separate generated project definitions to consolidate away.

## 8. Suggested cleanup order, if requested later

1. Preserve experiment evidence/receipts and identify which local builds are no longer needed.
2. Remove only regenerable local caches/build products selected for cleanup.
3. Remove the unused payment-page export in a focused app change; run UI tests, lint and build.
4. Archive the unused gate diagnostic and disconnected Java families together; update source sets/documentation as needed, compile, run Python/Java tests and verify Jason behavior.
5. Keep compatibility tests/templates/fixtures unless deliberately retiring that coverage in a separate reviewed change.

This is an inventory and recommendation, not a deletion approval or claim that every legacy class is globally unused.
