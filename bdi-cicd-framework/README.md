# BDI-controlled CI/CD experiment

This framework generates and runs a Jason controller from three engineer-owned inputs:

- `pipeline.yaml`: logical entities, dependencies, retry bound, and telemetry observation points.
- `goal.yaml`: achievements, duration requirements, and avoidance requirements.
- The referenced project manifest: GitHub workflow/job names, environments, endpoints, metric queries, thresholds, and observation timing.

The generated agent owns progression. It selects one entity, waits for its correlated terminal result, updates its beliefs, optionally retries or observes telemetry, and then reasons again. GitHub Actions executes only the entity selected in that dispatch. The dispatch workflow contains no application-stage `needs` chain.

The older replay and promotion-gate programs remain available for comparison, but the controller launcher does not start them.

The default project inputs are now `models/01_pipeline.yaml` and `models/02_goal.yaml`. They include conditional BDI recovery and production health assessment. Rollback is an agent-selected branch, followed by verification; it never turns failed candidate delivery into an achieved goal. Start with the [current manual](../docs/BDI_LIVE_MANUAL_DEMO.md).

## Supported configuration subset

The experiment deliberately supports a small language rather than arbitrary GitHub workflow YAML.

```yaml
name: Example
project_file: project.yaml
execution:
  max_retries: 1
jobs:
  build: {}
  test: {}
  staging:
    needs: [build, test]
  production:
    needs: staging
    observe_before: staging
  restore:
    recover_from: production
    recover_on: [failure, telemetry_block, telemetry_unknown, maintenance_violation]
    observe_after: true
```

Health requirements use `entity.health == healthy` under `maintain(M)`. Recovery entities must map to `known_good` in `controller.release_sources`, have an environment mapping and observe the restored release. They cannot be normal goal targets/dependencies. Recovery is attempted once; protected deployments recover after a confirmed terminal failure rather than being retried. Embedded runner commands are rejected by the controller launcher; put commands in the worker workflow.

Goals support one or more `entity.status == success` achievements, optional `entity.duration <= integer` maintenance requirements in milliseconds, and avoidance rules of the form “do not succeed entity A when prerequisite B did not succeed.” Entity names are lowercase AgentSpeak atoms. Dependencies must be acyclic. `observe_before` must identify a direct dependency.

The parser computes the transitive work needed by every requested achievement and safety rule. It rejects unknown entities, unsupported syntax, cycles, incomplete project mappings, and malformed goals. The generated files are:

- `models/03_workflow_model.yaml` and compatibility copy `models/controller_workflow_model.yaml`: normalized model and active goal closure.
- `generator/controller_project.asl`: project beliefs.
- `bdi/controller_agent.asl`: beliefs plus the generic controller plans.
- `<campaign artifacts>/generation-manifest.json`: SHA-256 hashes of all three inputs.

`examples/reporting_*` is a second topology with `package`, `verify`, and `preview`. It uses the same parser, Java runtime, and `controller_generic.asl`.

## Prerequisites

For local reasoning scenarios, use Python 3 with PyYAML and JDK 21 or newer. Add `--gui` to open the real Jason MAS Console, with the generated `controller_agent` and a web mind inspector. The window stays open after completion; close it before the next campaign. Omit `--gui` for unattended execution.

Follow [the visible v1-to-v2 manual demo](../docs/BDI_LIVE_MANUAL_DEMO.md) for the ordered release procedure and mid-campaign fault injection. Java now returns each telemetry sample to Jason; AgentSpeak owns the bounded wait/reconsideration loop.

For a live GitHub campaign, also prepare:

1. Merge the tested controller files and `.github/workflows/entity-execution.yml` to the repository's default branch; GitHub requires a manually dispatched workflow to exist there. Use that approved branch as the workflow ref.
2. Keep the controller on a workstation, VM, or hosted process outside the self-hosted runner's disposable checkout and outside its only execution slot.
3. Register an online self-hosted runner with the `payment-deploy` label. Its account needs Docker Engine/Compose and access to the designated staging and production ports.
4. Start Docker Desktop or Docker Engine on that runner. The entity workflow creates the designated Compose stacks; do not manually start the payment stack first.
5. Configure the GitHub `staging` and `production` Environments and retain their reviewer/protection rules.
6. Export `GITHUB_REPOSITORY=owner/repository` and a `GITHUB_TOKEN` able to dispatch/read Actions. Do not store the token in YAML or a journal.
7. Choose a workflow ref containing the dispatch workflow and an immutable release SHA available in the repository.

The legacy gate deployment workflow has been removed locally. Publish and merge the repair before expecting GitHub's default branch to reflect this. Old run graphs retain their historical gate.

## One-command launcher

Run from the repository root. The default goal is production:

```powershell
py -3 .\bdi-cicd-framework\run_controller.py --gui --scenario production_unhealthy
```

For a live run, set the execution identity explicitly:

```powershell
$env:GITHUB_REPOSITORY='owner/repository'
$env:GITHUB_TOKEN = gh auth token
$env:BDI_WORKFLOW_REF='main'
$env:BDI_RELEASE_SHA='<full commit SHA>'
$env:BDI_CAMPAIGN_ID='payment-demo-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --pipeline .\bdi-cicd-framework\models\payment_pipeline.yaml `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --known-good .\baseline\controller-result.json --confirm-compatible-rollback `
  --artifacts-dir .\artifacts\payment-demo-001
```

For the first healthy v1 only, replace `--known-good ... --confirm-compatible-rollback` with `--baseline`. A live receipt must verify the same project, repository, environment and immutable SHA; simulated receipts cannot enable live rollback. Recovery rebuilds compatible source and preserves volumes; there is no database recovery or image-digest guarantee.

The launcher validates the inputs and exact job mapping, generates the model and agent, takes an exclusive repository-wide controller lock, and starts Jason. A campaign journal records decisions, attempts, execution IDs, GitHub run IDs/URLs, telemetry observations, and the final outcome. Exit status is 0 for `achieved`, 1 for `stopped`, and 2 for `unknown` or a startup failure.

Each normal dispatch pins checkout to `BDI_RELEASE_SHA`; a recovery dispatch pins it to the SHA validated from the known-good receipt. The adapter accepts only the returned GitHub run ID and configured selected-job name. Missing jobs or uncertain API results stop as unknown without a competing deployment. Each UUID identifies both execution and telemetry.

To inject live experiment faults without changing Java or AgentSpeak, point `BDI_EXECUTION_PLAN` to a Java properties file:

```properties
test.1.failure_mode=force_failure
test.2.failure_mode=none
staging.force_error_rate=1
```

Use separate campaigns for faults. `production.force_error_rate=1` exercises BDI recovery after unhealthy deployment; `production.failure_mode=force_failure` fails after deployment; `rollback.failure_mode=force_failure` tests recovery failure. Retry count comes from the pipeline; metric thresholds and wait bounds come from the manifest.

## Local actual-Jason scenarios

These commands use deterministic entity/telemetry adapters but start the generated Jason interpreter and generic plans. Their `scenario://` URLs and run ID 0 identify local evidence; they are not live GitHub evidence.

```powershell
# Healthy production goal
py -3 .\bdi-cicd-framework\run_controller.py --scenario healthy

# Staging goal: production must be absent
py -3 .\bdi-cicd-framework\run_controller.py `
  --goal .\bdi-cicd-framework\models\payment_goal_staging.yaml --scenario healthy

# Retry succeeds, then retry exhaustion stops
py -3 .\bdi-cicd-framework\run_controller.py --scenario transient_test_failure
py -3 .\bdi-cicd-framework\run_controller.py --scenario exhausted_test_failure

# Telemetry outcomes
py -3 .\bdi-cicd-framework\run_controller.py --scenario telemetry_block
py -3 .\bdi-cicd-framework\run_controller.py --scenario telemetry_unknown
py -3 .\bdi-cicd-framework\run_controller.py --scenario telemetry_delayed

# Visible proof that no successor starts while the controller is paused
py -3 .\bdi-cicd-framework\run_controller.py --scenario healthy `
  --pause-after security --pause-ms 5000

# Same framework, different topology
py -3 .\bdi-cicd-framework\run_controller.py `
  --pipeline .\bdi-cicd-framework\examples\reporting_pipeline.yaml `
  --goal .\bdi-cicd-framework\examples\reporting_goal.yaml --scenario healthy
```

## Verification

`py -3 bdi-cicd-framework/verify_controller_experiment.py` checks 16 real-Jason local scenarios and writes a JSON summary, manifests, journals and console logs. These use simulated execution/telemetry, with a copied three-observation/zero-delay test manifest.

```powershell
py -3 -m unittest discover -s .\bdi-cicd-framework\parser -p 'test_*.py' -v
Set-Location .\bdi-cicd-framework\bdi
.\gradlew.bat --no-daemon test
Set-Location ..\..
npm test
npm run lint
npm run build
git diff --check
```

Parser tests cover validation, deterministic generation, goal closure, the second project, and the independent dispatch workflow. Java tests cover project mapping, scenario retry behavior, telemetry components inherited from the baseline, and the GitHub adapter against a local HTTP server including the exact run/job correlation path.

## Runtime behavior and limits

Before every entity, AgentSpeak checks the active goal closure, successful dependencies, avoidance requirements, terminal state, and the single-in-flight belief. Failures are retried only within `max_retries`. Before configured promotion work, it waits for run-correlated readiness and Prometheus observations. A confirmed threshold violation produces `stopped`; exhausted observations or missing data produce `unknown`; all requested achievements and maintenance conditions produce `achieved`.

GitHub Environment approval can leave an entity waiting. The controller dispatches no successor. Uncertain execution stops as unknown. Configured terminal failure or post-deployment telemetry problems activate BDI recovery using the verified baseline; recovery itself is observed before reporting restored. Outcomes remain achieved/stopped/unknown, with a separate recovery_outcome. The manual rollback workflow is an emergency operator tool and must not run alongside a controller.

The current GitHub adapter reads up to 100 latest jobs in one run and assumes a non-matrix selected job. The controller journal is local JSON Lines rather than a durable multi-host database. The source commit is immutable per campaign, while each deployment still rebuilds that source rather than promoting one binary image. Live credentials, runner labels, Environment rules, and network reachability remain external prerequisites.

See [the architecture audit and plan](../docs/BDI_ARCHITECTURE_AUDIT_AND_PLAN.md) and [the experiment results](../docs/BDI_CONTROLLER_EXPERIMENT_RESULTS.md).

For repository-specific versioning, ports, prerequisites, live startup, observation, retry, and rollback procedures, use the [manual execution guide](../docs/BDI_MANUAL_EXECUTION_GUIDE.md).
