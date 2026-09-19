# BDI-controlled CI/CD experiment

This framework generates and runs a Jason controller from three engineer-owned inputs:

- `pipeline.yaml`: logical entities, dependencies, retry bound, and telemetry observation points.
- `goal.yaml`: achievements, duration requirements, and avoidance requirements.
- The referenced project manifest: GitHub workflow/job names, environments, endpoints, metric queries, thresholds, and observation timing.

The generated agent owns progression. It selects one entity, waits for its correlated terminal result, updates its beliefs, optionally retries or observes telemetry, and then reasons again. GitHub Actions executes only the entity selected in that dispatch. The dispatch workflow contains no application-stage `needs` chain.

The older replay and promotion-gate programs remain available for comparison, but the controller launcher does not start them.

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
```

Goals support one or more `entity.status == success` achievements, optional `entity.duration <= integer` maintenance requirements in milliseconds, and avoidance rules of the form “do not succeed entity A when prerequisite B did not succeed.” Entity names are lowercase AgentSpeak atoms. Dependencies must be acyclic. `observe_before` must identify a direct dependency.

The parser computes the transitive work needed by every requested achievement and safety rule. It rejects unknown entities, unsupported syntax, cycles, incomplete project mappings, and malformed goals. The generated files are:

- `models/controller_workflow_model.yaml`: normalized supported model and active goal closure.
- `generator/controller_project.asl`: project beliefs.
- `bdi/controller_agent.asl`: beliefs plus the generic controller plans.
- `<campaign artifacts>/generation-manifest.json`: SHA-256 hashes of all three inputs.

`examples/reporting_*` is a second topology with `package`, `verify`, and `preview`. It uses the same parser, Java runtime, and `controller_generic.asl`.

## Prerequisites

For local reasoning scenarios, open a terminal and have Python 3 with PyYAML, JDK 21 or newer, and network access for the first Gradle dependency download. Jason is started headlessly by the launcher; do not start a Jason GUI.

For a live GitHub campaign, also prepare:

1. Merge the tested controller files and `.github/workflows/entity-execution.yml` to the repository's default branch; GitHub requires a manually dispatched workflow to exist there. Use that approved branch as the workflow ref.
2. Keep the controller on a workstation, VM, or hosted process outside the self-hosted runner's disposable checkout and outside its only execution slot.
3. Register an online self-hosted runner with the `payment-deploy` label. Its account needs Docker Engine/Compose and access to the designated staging and production ports.
4. Start Docker Desktop or Docker Engine on that runner. The entity workflow creates the designated Compose stacks; do not manually start the payment stack first.
5. Configure the GitHub `staging` and `production` Environments and retain their reviewer/protection rules.
6. Export `GITHUB_REPOSITORY=owner/repository` and a `GITHUB_TOKEN` able to dispatch/read Actions. Do not store the token in YAML or a journal.
7. Choose a workflow ref containing the dispatch workflow and an immutable release SHA available in the repository.

The legacy deployment chain is disabled by default. It runs only through a manual `workflow_dispatch` with `legacy_deployment=true`, which prevents a push-triggered legacy deployment from racing a controller campaign.

## One-command launcher

Run from the repository root. The default goal is production:

```powershell
py -3 .\bdi-cicd-framework\run_controller.py
```

For a live run, set the execution identity explicitly:

```powershell
$env:GITHUB_REPOSITORY='owner/repository'
$env:GITHUB_TOKEN='<Actions dispatch/read token>'
$env:BDI_WORKFLOW_REF='main'
$env:BDI_RELEASE_SHA='<full commit SHA>'
$env:BDI_CAMPAIGN_ID='payment-demo-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --pipeline .\bdi-cicd-framework\models\payment_pipeline.yaml `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --artifacts-dir .\artifacts\payment-demo-001
```

The launcher validates the inputs and exact job mapping, generates the model and agent, takes an exclusive repository-wide controller lock, and starts Jason. A campaign journal records decisions, attempts, execution IDs, GitHub run IDs/URLs, telemetry observations, and the final outcome. Exit status is 0 for `achieved`, 1 for `stopped`, and 2 for `unknown` or a startup failure.

Each dispatch pins `actions/checkout` to `BDI_RELEASE_SHA`. The adapter accepts only the returned GitHub run ID and exact configured selected-job name. Results from other runs or jobs cannot update beliefs; the synchronous single-in-flight controller consumes one terminal result once. Missing/skipped selected jobs are failures. A UUID execution ID labels the deployment and telemetry, and telemetry is queried with that exact ID.

To inject live experiment faults without changing Java or AgentSpeak, point `BDI_EXECUTION_PLAN` to a Java properties file:

```properties
test.1.failure_mode=force_failure
test.2.failure_mode=none
staging.force_error_rate=1
```

Use separate campaigns for retry and high-error demonstrations. Supported dispatch inputs are `failure_mode=none|force_failure` and normal/high-error staging traffic. Retry count comes from `pipeline.yaml`; thresholds, queries, endpoints, and telemetry wait bounds come from the project manifest.

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

GitHub Environment approval can leave an entity workflow waiting. The controller treats it as the selected entity still in flight and dispatches no successor. Timeouts stop the campaign. Autonomous production rollback is outside this bounded experiment because the repository has no promoted immutable artifact, known-good release selection, or validated recovery policy.

The current GitHub adapter reads up to 100 latest jobs in one run and assumes a non-matrix selected job. The controller journal is local JSON Lines rather than a durable multi-host database. The source commit is immutable per campaign, while each deployment still rebuilds that source rather than promoting one binary image. Live credentials, runner labels, Environment rules, and network reachability remain external prerequisites.

See [the architecture audit and plan](../docs/BDI_ARCHITECTURE_AUDIT_AND_PLAN.md) and [the experiment results](../docs/BDI_CONTROLLER_EXPERIMENT_RESULTS.md).

For repository-specific versioning, ports, prerequisites, live startup, observation, retry, and rollback procedures, use the [manual execution guide](../docs/BDI_MANUAL_EXECUTION_GUIDE.md).
