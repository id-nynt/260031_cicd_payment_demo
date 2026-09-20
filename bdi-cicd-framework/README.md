# BDI CI/CD controller

Engineer inputs are **models/01_pipeline.yaml** and **models/02_goal.yaml**. The payment example supplies job bindings, endpoints and PromQL in the pipeline input; recovery actions have their own mapping. Goals supply achievements, safety constraints and telemetry thresholds. No separate project manifest is read by the controller.

Read [how generation and runtime connect](../docs/BDI_GENERATION_AND_RUNTIME.md) for the origin of E/D/O/R, predefined versus project-specific rules, the active agent/environment, telemetry configuration sources, and the assessment of embedding GitHub job steps. Follow the [manual experiment walkthrough](../docs/BDI_MANUAL_EXECUTION_GUIDE.md) one step at a time for local startup, version tags, baseline/v2 campaigns and recovery.

Achievement goals support `entity.status == success` and `entity.status == failure`. Failure goals are explicit negative experiments: a matching executed failure satisfies the goal; rejected dispatch or uncertain execution does not. Unmet campaigns report ?Attempted but failed to achieve goals.? Negative experiments never create verified release receipts. See the [manual failure-goal experiment](../docs/BDI_MANUAL_EXECUTION_GUIDE.md#optional-experiment-require-staging-to-fail).

## Project generation and campaign execution

```text
Explicit project generation (once per configuration revision):
models/01_pipeline.yaml + models/02_goal.yaml
  -> generate_project.py -> validate and save models/03_workflow_model.yaml
  -> reload saved contract -> generate_agent + generator/controller_generic.asl
  -> bdi/controller_agent.asl + models/generation-manifest.json

Each campaign (no generation):
run_controller.py -> validate persistent inputs/contract/agent/generator hashes
  -> archive exact artifacts and provenance in runs/<campaign>/
  -> harness.ControllerMain -> harness.ControllerEnvironment -> Jason
  -> Java executes selected action -> entity-execution.yml runs selected entity only
  -> correlated observation -> Jason selects next action / retry / recovery / stop
```

`generate_project.py` is the only supported project generation entry point. Run it explicitly after changing either engineer input, the compiler, generation code or generic policy. Commit the generated contract, agent and generation manifest together with that revision. Generation reads the saved, validated workflow model as its sole project-specific input; it does not read the engineer inputs again when emitting AgentSpeak.

`run_controller.py` validates existing artifacts without writing them. Missing, stale or inconsistent artifacts fail before Java starts, with a regeneration command. `--validate-only` performs the same check without creating a campaign. `--project-dir` selects a different generated project. Input options belong to generation, not campaign startup; the old `--generate-only` launch option is removed.

The schema 2 workflow contract leads with entities (E), dependencies (D), observations (O), recovery (R) and goals, followed by execution/observation/recovery policies and one bindings section. The framework derives its capability dictionary from that saved contract rather than repeating action lists and goals in YAML. Validation reconstructs the contract from engineer inputs, checks its derived capabilities, then compares the complete agent with its deterministic contract projection and generic executable policy. Thus extra/missing entities, changed action calls, dropped observations/recovery, changed goal constraints and altered goal rules are rejected, even if someone updates the agent hash. This is consistency validation, not a signature or proof that arbitrary replacement generator code is correct.

`bdi/controller.mas2j` is a framework launch template. Each campaign loads an exact archival copy of the persistent agent in an isolated MAS directory; copying does not regenerate it. Java checks the snapshot hashes immediately before launch. The Gradle `runController` task is an internal launcher used with the campaign environment, not a replacement for Python's project validation.

Normal work is `build -> test -> security -> staging -> production`. Recovery is conditional and never a successful-path dependency. Jason limits retries, reobservation and reconciliation. Confirmed retryable failures use the configured retry budget only for retry-safe entities, including production. Deterministic failures stop or recover; unhealthy/unavailable telemetry is reobserved within a separate count/time budget. Two consecutive healthy observations are required for payment verification; recovery is attempted once. The worker contains no `needs` pipeline and cannot choose a successor. Build/test/security use hosted workers; deployment uses the existing self-hosted Linux `payment-deploy` runner and local Docker Compose.

The [manual guide](../docs/BDI_MANUAL_EXECUTION_GUIDE.md) separates setup and local checks (Part A) from the eight live v1-to-v2 experiment phases (Part B), with commands and visible checkpoints. [Setup details](../docs/BDI_SETUP.md) provide additional authentication and troubleshooting reference. [Policy details](../docs/BDI_GENERATION_AND_RUNTIME.md) distinguish execution retry, health observation and reconciliation. Superseded guidance is in [docs/archive/pre-policy-refactor](../docs/archive/pre-policy-refactor/README.md).

## Local verification (no deployment)

Requires Python 3.12 with PyYAML, JDK 21+, and the supplied Gradle wrapper. From the repository root (use `py -3 -B` instead of `python` on Windows if necessary):

```sh
python bdi-cicd-framework/generate_project.py
python bdi-cicd-framework/run_controller.py --validate-only
python bdi-cicd-framework/run_controller.py --scenario healthy
python bdi-cicd-framework/verify_controller_experiment.py
python -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
cd bdi-cicd-framework/bdi
bash ./gradlew --no-daemon test
```

On Windows run `gradlew.bat`. `--gui` opens Jason's console and retains the final mind until closed. `examples/reporting_pipeline.yaml` and `reporting_goal.yaml` exercise another topology through the same compiler, agent and runtime. This example is a simulated application contract; it does not claim a live reporting deployment.

## Telemetry and recovery

The payment application exports OTLP HTTP metrics to the OTel collector; Prometheus scrapes its exporter. Each worker sets `CI_RUN_ID` to the controller execution UUID. Canonical PromQL binds that identity. Java reads readiness and raw metrics, checks finite values and sample/source freshness, and publishes entity/attempt/round measurements. AgentSpeak applies the configured error/latency thresholds and decides whether to reobserve or continue. Production and recovery both require an accepted post-deployment observation. HTTP/job success alone cannot achieve deployment goals.

For live use, configure `GITHUB_REPOSITORY`, `GITHUB_TOKEN` (Actions write), `BDI_WORKFLOW_REF` (approved branch/tag with the worker), and `BDI_RELEASE_SHA` (full immutable candidate SHA). The worker must already be available for dispatch. Start the controller outside the runner checkout and its execution slot. Keep endpoint overrides consistent with the intended deployment. See the [GitHub dispatch API contract](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event), version 2026-03-10.

An initial live baseline requires explicit `--baseline`; it has no rollback source. Subsequent runs use `--known-good <trusted-achieved-live-controller-result.json> --confirm-compatible-rollback`. Receipts must verify the same project, repository and recovery environment at a full commit SHA. The compatibility flag confirms the retained database schema/data can be used by that revision. Rollback rebuilds this verified source and verifies its new execution identity and telemetry. A restored environment yields `stopped/restored`, never successful candidate delivery. Receipt files are trusted operator evidence, not cryptographically signed attestations.

## Uncertain execution

Before each POST, Java atomically persists execution intent in the common Git directory (`bdi-execution-pending.json`). All worktrees share a controller lock. A lost acknowledgement, timeout, missing selected job or polling failure becomes unknown. Jason requests bounded read-only reconciliation. Java searches the exact `bdi-<execution UUID>` run name and checks the selected job. Absence or ambiguity never authorizes another dispatch. Unresolved state blocks later campaigns, including after a restart.

After a stopped process, `python bdi-cicd-framework/run_controller.py --reconcile-only` performs only remote reads and records a reconciliation result. It never resumes the old campaign or declares candidate achievement. Confirmed terminal status clears the pending marker; unknown preserves it. If the run cannot be found in the bounded search (500 recent dispatches), investigate it manually; do not erase the marker to force a retry. Repository-local locking does not coordinate independent clones or other deployment tools.

## Artifacts and file responsibilities

| Location | Responsibility |
|---|---|
| `models/01_pipeline.yaml`, `02_goal.yaml` | Canonical engineer inputs |
| `models/03_workflow_model.yaml`, `bdi/controller_agent.asl` | Persistent generated project contract and agent |
| `models/generation-manifest.json` | Input, generator and artifact hashes; paths relative to project directory |
| `parser/workflow_model.py`, `model_transform.py` | Canonical compiler plus reused syntax/model machinery |
| `generator/controller_generic.asl` | Generic Jason control policy |
| `bdi/controller.mas2j`, `harness/Controller*`, `GitHubEntityExecution`, telemetry adapters | Runtime source and bindings |
| `runs/<campaign>/` | Execution journal/result, MAS, provenance and exact archival snapshots of existing artifacts |
| `bdi/fixtures/*workflow.yaml` | Generated Java test fixtures, checked against the compiler |
| `parser/fixtures/legacy/` | Compatibility fixtures, never live inputs |
| `examples/` | Second-application and staging-goal examples; legacy project manifests are in parser fixtures |
| `../docs/legacy/pre-canonical/` | Archived agents/models and manual rollback workflow |
| `../docs/experiments/` | Deliberately retained historical and repair validation evidence |
| `bdi/build`, `.gradle`, `bin`, `__pycache__` | Disposable output, not evidence |

Follow the [manual experiment walkthrough](../docs/BDI_MANUAL_EXECUTION_GUIDE.md) for actions, commands and checkpoints. Every campaign directory must be new. Provenance identifies persistent artifact paths and the generation-manifest hash, and includes input snapshots/hashes, workflow/agent/MAS/template hashes, source file hashes and source commit; scenario receipts are explicitly labeled and rejected for live rollback. Preserve a campaign as evidence deliberately; Gradle's verification output is disposable. The old `config/` Gradle scripts are archived. Non-controller Java classes remain compatibility material, not supported launch paths. Do not invoke the old `model_transform.py` CLI for canonical input generation.

## Limits

No live GitHub, runner, Docker deployment or rollback is part of repair verification. The workflow rebuilds source rather than promoting an immutable image digest, and never restores a database. Telemetry proves bounded sampled health, not indefinite service correctness. Security auditing blocks high/critical production dependency advisories. Independent clones need shared external coordination before concurrent live control. The second application verifies generic generation/reasoning, not a second production integration.
