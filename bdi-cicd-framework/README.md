# BDI CI/CD controller

Engineer inputs are **models/01_pipeline.yaml** and **models/02_goal.yaml**. The payment example supplies job bindings, endpoints and PromQL in the pipeline input; recovery actions have their own mapping. Goals supply achievements, safety constraints and telemetry thresholds. No separate project manifest is read by the controller.

## Active path

```text
01_pipeline.yaml + 02_goal.yaml
  -> parser/workflow_model.py: compile_inputs
  -> runs/<campaign>/03_workflow_model.yaml
  -> reload and validate -> generate_agent + generator/controller_generic.asl
  -> runs/<campaign>/controller_agent.asl + controller.mas2j
  -> harness.ControllerMain -> harness.ControllerEnvironment -> Jason
  -> run_job(entity, attempt) -> GitHubEntityExecution
  -> entity-execution.yml -> selected job only -> correlated terminal observation
  -> Jason chooses next job / retry / observation / recovery / stop
```

`run_controller.py` is the entry point. `bdi/controller.mas2j` is a framework template copied into each campaign and loads `controller_agent` with `harness.ControllerEnvironment`. The Gradle `runController` task runs in that campaign directory. Only the saved intermediate model and generic policy are inputs to AgentSpeak generation. Java reads runtime bindings from the same intermediate model.

Normal work is `build -> test -> security -> staging -> production`. Recovery is conditional and never a successful-path dependency. Jason limits retries, reobservation and reconciliation. A protected deployment goes to its configured recovery action after confirmed failure; recovery is attempted once. The worker contains no `needs` pipeline and cannot choose a successor. Build/test/security use hosted workers; deployment uses the existing self-hosted Linux `payment-deploy` runner and local Docker Compose.

## Local verification (no deployment)

Requires Python 3.12 with PyYAML, JDK 21+, and the supplied Gradle wrapper. From the repository root (use `py -3 -B` instead of `python` on Windows if necessary):

```sh
python bdi-cicd-framework/run_controller.py --generate-only
python bdi-cicd-framework/run_controller.py --scenario healthy
python bdi-cicd-framework/verify_controller_experiment.py
python -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
cd bdi-cicd-framework/bdi
bash ./gradlew --no-daemon test
```

On Windows run `gradlew.bat`. `--gui` opens Jason's console and retains the final mind until closed. `examples/reporting_pipeline.yaml` and `reporting_goal.yaml` exercise another topology through the same compiler, agent and runtime. This example is a simulated application contract; it does not claim a live reporting deployment.

## Telemetry and recovery

The unchanged payment application exports OTLP HTTP metrics to the OTel collector; Prometheus scrapes its exporter. Each worker sets `CI_RUN_ID` to the controller execution UUID. Canonical PromQL binds that identity. Java reads readiness and raw metrics, checks finite values and sample/source freshness, and publishes entity/attempt/round measurements. AgentSpeak applies the configured error/latency thresholds and decides whether to reobserve or continue. Production and recovery both require an accepted post-deployment observation. HTTP/job success alone cannot achieve deployment goals.

For live use, configure `GITHUB_REPOSITORY`, `GITHUB_TOKEN` (Actions write), `BDI_WORKFLOW_REF` (approved branch/tag with the worker), and `BDI_RELEASE_SHA` (full immutable candidate SHA). The worker must already be available for dispatch. Start the controller outside the runner checkout and its execution slot. Keep endpoint overrides consistent with the intended deployment. See the [GitHub dispatch API contract](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event), version 2026-03-10.

An initial live baseline requires explicit `--baseline`; it has no rollback source. Subsequent runs use `--known-good <trusted-achieved-live-controller-result.json> --confirm-compatible-rollback`. Receipts must verify the same project, repository and recovery environment at a full commit SHA. The compatibility flag confirms the retained database schema/data can be used by that revision. Rollback rebuilds this verified source and verifies its new execution identity and telemetry. A restored environment yields `stopped/restored`, never successful candidate delivery. Receipt files are trusted operator evidence, not cryptographically signed attestations.

## Uncertain execution

Before each POST, Java atomically persists execution intent in the common Git directory (`bdi-execution-pending.json`). All worktrees share a controller lock. A lost acknowledgement, timeout, missing selected job or polling failure becomes unknown. Jason requests bounded read-only reconciliation. Java searches the exact `bdi-<execution UUID>` run name and checks the selected job. Absence or ambiguity never authorizes another dispatch. Unresolved state blocks later campaigns, including after a restart.

After a stopped process, `python bdi-cicd-framework/run_controller.py --reconcile-only` performs only remote reads and records a reconciliation result. It never resumes the old campaign or declares candidate achievement. Confirmed terminal status clears the pending marker; unknown preserves it. If the run cannot be found in the bounded search (500 recent dispatches), investigate it manually; do not erase the marker to force a retry. Repository-local locking does not coordinate independent clones or other deployment tools.

## Artifacts and file responsibilities

| Location | Responsibility |
|---|---|
| `models/01_pipeline.yaml`, `02_goal.yaml` | Canonical engineer inputs |
| `parser/workflow_model.py`, `model_transform.py` | Canonical compiler plus reused syntax/model machinery |
| `generator/controller_generic.asl` | Generic Jason control policy |
| `bdi/controller.mas2j`, `harness/Controller*`, `GitHubEntityExecution`, telemetry adapters | Runtime source and bindings |
| `runs/<campaign>/` | Isolated input snapshots, validated workflow, agent, MAS, hashes, journal and result |
| `bdi/fixtures/*workflow.yaml` | Generated Java test fixtures, checked against the compiler |
| `parser/fixtures/legacy/` | Compatibility fixtures, never live inputs |
| `examples/` | Second-application and staging-goal examples; legacy project manifests are in parser fixtures |
| `../docs/legacy/pre-canonical/` | Archived agents/models and manual rollback workflow |
| `../docs/experiments/` | Deliberately retained historical and repair validation evidence |
| `bdi/build`, `.gradle`, `bin`, `__pycache__` | Disposable output, not evidence |

Every campaign directory must be new. Provenance includes input snapshots/hashes, workflow/agent/MAS/template hashes, source file hashes and source commit; scenario receipts are explicitly labeled and rejected for live rollback. Preserve a campaign as evidence deliberately; Gradle's verification output is disposable. The old `config/` Gradle scripts are archived. Non-controller Java classes remain compatibility material, not supported launch paths. Do not invoke the old `model_transform.py` CLI for canonical input generation.

## Limits

No live GitHub, runner, Docker deployment or rollback is part of repair verification. The workflow rebuilds source rather than promoting an immutable image digest, and never restores a database. Telemetry proves bounded sampled health, not indefinite service correctness. Security auditing retains the demonstration's advisory behavior. Independent clones need shared external coordination before concurrent live control. The second application verifies generic generation/reasoning, not a second production integration.
