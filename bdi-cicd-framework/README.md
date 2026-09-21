# Adapt the BDI CI/CD framework to your project

This framework uses a Jason BDI agent to pursue deployment goals. You describe the available jobs, their dependencies, observations and recovery actions. The agent selects work, checks results and decides whether to continue, retry, recheck health, recover or stop.

**Jason decides; Java executes and observes; GitHub Actions runs only the selected job.** Starting the controller starts a campaign immediately. The agent ends when that campaign finishes; it is not a permanent production monitor.

## 1. Understand the configuration

| File | Role | Who edits it? |
|---|---|---|
| [models/01_pipeline.yaml](models/01_pipeline.yaml) | Available entities, dependencies, GitHub job mappings, telemetry and execution budgets | Engineer |
| [models/02_goal.yaml](models/02_goal.yaml) | Desired results, maintenance/avoidance constraints and health thresholds | Engineer |
| [models/03_workflow_model.yaml](models/03_workflow_model.yaml) | Validated project contract and runtime bindings | Generator |
| [bdi/controller_agent.asl](bdi/controller_agent.asl) | Executable project agent: generated beliefs/goals plus generic reasoning plans | Generator |
| `models/generation-manifest.json` | Input, generator and artifact hashes | Generator |

Inputs **01 and 02 are the configuration sources of truth**. The saved 03 is the agent generator's sole project-specific input. Generate once per configuration or generator revision, then reuse the persistent artifacts for campaigns. Commit inputs, generated contract, agent and manifest together. Campaign startup rejects missing, stale or inconsistent artifacts; it never regenerates them.

### How the model becomes an agent

| Model concept | Where its definition comes from |
|---|---|
| **E: entities** | Keys under `jobs` and `recovery` in 01; each maps to a real worker job |
| **D: dependencies** | Each job's `needs` in 01; prerequisites must succeed |
| **O: observable properties** | Framework-defined status, duration and health vocabulary; actual observations come from GitHub, readiness and Prometheus |
| **R: recovery** | Each recovery entry's `from` entity and recovery action in 01 |
| **Goals** | `achieve(A)`, `maintain(M)` and `avoid(V)` in 02 |

The generator emits static beliefs for entities, dependencies, capabilities, budgets and goal predicates. During execution the agent receives attempt-correlated status, duration and telemetry beliefs, and tracks attempts and workflow state. Its `!master_goal` pursues the declared achievements through the plans in [generator/controller_generic.asl](generator/controller_generic.asl). The older `bdi_generic.asl` is not the active policy.

```text
01 + 02 -> generate_project.py / parser/workflow_model.py -> saved 03
saved 03 + controller_generic.asl -> bdi/controller_agent.asl + manifest
run_controller.py -> ControllerMain -> ControllerEnvironment -> Jason
Jason action -> Java GitHub adapter -> selected worker job -> correlated observations
```

The current policy retries only eligible transient failures/timeouts on retry-safe jobs within budget. Ordinary failures stop or recover. Bad telemetry causes bounded reobservation; enough consecutive healthy samples allow progress. Unknown execution must be reconciled before redispatch. Recovery uses a verified known-good release and verifies its health; restoration never counts as candidate delivery.

`entity.status == failure` is supported for negative experiments. It requires an actual matching failure, does not manufacture one, and produces no known-good release receipt. Goals remain subject to dependencies and constraints; impossible goals end unmet.

## 2. Fill the two inputs

Use the commented [01 template](templates/models/01_pipeline.yaml) and [02 template](templates/models/02_goal.yaml). The [03 reference shape](templates/models/03_workflow_model.yaml) explains generated sections; **do not fill or copy it as an input**. These are YAML forms checked against the existing parser, not a separate JSON Schema implementation.

From the repository root, copy only 01 and 02 to `bdi-cicd-framework/models/` when replacing the payment example, then edit them. Keep a separate project directory if you need to retain both configurations.

- **01:** replace project/name placeholders; rename/add/remove jobs; map exact GitHub job display names; set dependencies, environments, observation points, recovery and retry safety.
- **01 telemetry:** replace hosts, ports, metric names and route filters with values your app actually exports. Addresses must be reachable from the controller. Keep `{{run_id}}` in queries so previous releases cannot satisfy current health checks.
- **02:** select achievements and constraints using the same entity names. Choose meaningful duration limits, error fractions and p95 latency limits. The template values are examples.

**Expected:** your two inputs describe your app, with no remaining `YOUR_*`, `your-app` or `your_app_*` placeholders. Unknown fields and unsupported goals are rejected during generation.

### Connect your actual worker and application

The input YAML does not implement shell commands or create runners. Adapt [.github/workflows/entity-execution.yml](../.github/workflows/entity-execution.yml) to build, test and deploy your app:

- Retain the dispatch interface (`entity`, `campaign_id`, `execution_id`, `attempt`, `release_sha`, `failure_mode`, `experiment_mode`) and `run-name: bdi-${{ inputs.execution_id }}` for correlation.
- Match entity choices and job display names to 01. Gate each job with `if: inputs.entity == '<entity>'`; let Jason order jobs rather than a worker `needs` chain.
- Check out the supplied `release_sha`. Keep actual `steps`, `services`, runner labels and deployment commands in this worker, not input 01.
- Supply the execution UUID to the deployed app (the example uses `CI_RUN_ID`). Expose readiness (HTTP 200 when ready, 503 when not ready) and export metrics labeled with that execution identity. See the [telemetry integration details](../docs/BDI_GENERATION_AND_RUNTIME.md#payment-telemetry-and-controllable-traffic) and existing adapters before replacing the app's telemetry.
- Implement recovery using the supplied known-good SHA. Confirm database compatibility; source rollback does not undo database changes.

Publish the worker and candidate source before live use. Make the dispatch workflow available on the repository default branch and select an existing published worker ref. Deployment runner labels must match the worker and the runner must stay online. Build/test jobs may use hosted runners while deployment jobs use your self-hosted runner.

## 3. Generate and validate

Requires Python with PyYAML, JDK 21+ and the supplied Gradle wrapper. Run from the repository root; on Windows use `py -3 -B` in place of `python`.

```sh
python bdi-cicd-framework/generate_project.py
python bdi-cicd-framework/run_controller.py --validate-only
```

**Expected:** generation prints the contract, agent and manifest paths; validation prints `Project artifacts are consistent`. No GitHub jobs or deployments run.

For a separate configuration, always supply both input paths during generation:

```sh
python bdi-cicd-framework/generate_project.py --project-dir projects/my-app --pipeline projects/my-app/models/01_pipeline.yaml --goal projects/my-app/models/02_goal.yaml
python bdi-cicd-framework/run_controller.py --project-dir projects/my-app --validate-only
```

Use the same `--project-dir` on subsequent commands for that configuration.

## 4. Optionally test without deployment

```sh
python bdi-cicd-framework/run_controller.py --scenario healthy --gui
python -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
```

**Expected:** the simulation opens MAS Console and shows decisions and a final outcome; success goals compatible with the healthy scenario should be achieved. Tests check the compiler and artifact contracts. Simulation does not prove that your real worker, runner or telemetry works. The [reporting example](examples/reporting_pipeline.yaml) demonstrates another topology; it is not a deployed application.

## 5. Start a real deployment

In the controller terminal, configure these values before launch:

| Environment variable | Value |
|---|---|
| `GITHUB_REPOSITORY` | Your `owner/repository` |
| `GITHUB_TOKEN` | A token with repository access and Actions write; keep it secret |
| `BDI_WORKFLOW_REF` | Published worker branch/tag matching input 01 |
| `BDI_RELEASE_SHA` | Full 40-character **published application commit**, not an unpublished local HEAD |

Remove leftover scenario/fault settings such as `BDI_EXECUTION_PLAN` for an ordinary deployment. Keep Docker, the deployment runner and required monitoring services running. Run the controller outside the runner's checkout/job slot.

For the first healthy baseline, which has no earlier rollback receipt:

```sh
python bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir bdi-cicd-framework/runs/my-first-baseline
```

**Expected:** MAS Console shows selected jobs; GitHub runs one selected entity per dispatch. Deployment goals succeed only after required health checks. Inspect `controller-result.json`: require `mode: github`, `outcome: achieved`, the intended release SHA and verified environment receipts before treating it as known-good.

For the next release, set `BDI_RELEASE_SHA` to its published SHA and run:

```sh
python bdi-cicd-framework/run_controller.py --gui --known-good bdi-cicd-framework/runs/my-first-baseline/controller-result.json --confirm-compatible-rollback --artifacts-dir bdi-cicd-framework/runs/my-next-release
```

Only confirm compatible rollback when the retained database is compatible with the baseline. Each campaign directory must be new; omit `--artifacts-dir` to get an automatic unique directory. Keep the successful baseline receipt for later campaigns.

**Expected:** the agent delivers and verifies the candidate, or stops with evidence (and verifies recovery if selected). Read `controller-journal.jsonl` for decisions and `controller-result.json` for the final outcome. Campaign directories also preserve artifact snapshots and provenance. Once finished, close MAS Console to release the foreground Gradle command; deployed containers remain running.

If interrupted, close the old console and run `python bdi-cicd-framework/run_controller.py --reconcile-only` with the same project and GitHub configuration. It checks the old remote execution, without resuming or dispatching. Do not delete pending records or start overlapping campaigns to bypass uncertainty.

For the payment demo's detailed setup, traffic experiments and v1 restoration, follow the [manual guide](../docs/BDI_MANUAL_EXECUTION_GUIDE.md). For supported policy, telemetry contracts and implementation details, read [generation and runtime](../docs/BDI_GENERATION_AND_RUNTIME.md).
