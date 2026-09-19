# BDI controller experiment results

## MAS Console update ? 20 September 2026

The following sections below this update preserve the earlier experiment record; their uncommitted/branch status and source hashes describe that earlier run.

Current repair branch: `fix/bdi-controller-runtime`, reconciled with `origin/main` (`dd1b5c8`). Existing tags are unchanged. The previously merged build/cache artifacts are removed from Git tracking, with local files retained. Publish this repair through a reviewed PR; follow [the current live manual](BDI_LIVE_MANUAL_DEMO.md) before tagging a new baseline.

Verified in this update:

- Python parser/generator: 13 tests passed.
- Java: 10 tests passed, including changing/removing injected faults between dispatches.
- Actual Jason GUI delayed-telemetry campaign: native Swing `isShowing=true`; `build,test,security,staging`; first observation unknown, AgentSpeak wait approximately five seconds, second observation allow; production selected; final `achieved`. The MAS process remained open for inspection.
- Actual Jason missing-telemetry campaign: 18 unknown samples, bounded AgentSpeak reconsideration, final `unknown`; production execution count zero. Expected and actual sequences matched.
- GUI evidence: `bdi/build/mas-gui-final/`; unknown evidence: `bdi/build/mas-unknown-final/`. Each has generation manifest, journal and result. These are local scenario runs, with UUID execution identities and `scenario://` URLs, not GitHub run URLs. No live telemetry or deployment success is claimed.
- Saved GitHub credentials remain invalid (`gh auth status`). Remote publication, runner availability, Environment approvals and live v1-to-v2 execution remain unverified. New baseline/candidate tags have deliberately not been created before review.

The generic AgentSpeak plans now own waiting/reconsideration; Java supplies one telemetry sample per request. The worker produces staging traffic without deciding promotion. Use `--gui` to open MAS Console, then close it after inspecting the final beliefs. Headless runs still stop automatically.

Updated source hashes (SHA-256 of local files at verification):

| File | SHA-256 |
|---|---|
| `bdi-cicd-framework/run_controller.py` | `ff377423fb3de9dbcc1be1d2f0433cc20ac217686c500cc9c012a7b498ef90a9` |
| `bdi-cicd-framework/generator/controller_generic.asl` | `0bf64e744de6f5348593fd4ee01d6985c37f0547a5ec82d7e635ab00b0912191` |
| `bdi-cicd-framework/bdi/harness/ControllerEnvironment.java` | `75294d8378820c2a2c59b423858980d3e7927fccc5b24e04f2089490ef65637f` |
| `.github/workflows/entity-execution.yml` | `cbbcd259517ab44f4d46f71a1f05033a595073fc2e0954f96b4fc90deac44358` |

Experiment date: 19 September 2026. Local branch: `experiment-v2`. Starting commit: `f658daf6c2f30d2f1d157c3237ff569f15a2bc77`. The implementation was tested in the working tree; it has not been committed or published, so that starting commit does not contain the controller.

## Result

The local experiment verifies that a generated Jason agent can control and decide CI/CD progression for the supported model. The agent, rather than a GitHub `needs` chain, selected each entity; it used correlated results and telemetry beliefs to retry, stop, wait, or continue. Goal changes altered required work: the staging goal never selected production, while the production goal did.

This is local reasoning and adapter evidence. It is not a successful live deployment claim. No GitHub run URLs exist for these local scenarios; their journals deliberately use `scenario://...` and GitHub run ID `0`.

## Configuration identity

| Input | SHA-256 |
|---|---|
| `models/payment_pipeline.yaml` | `0C98EF10D0F9AA9DC9130ABED58E91711692AC6AC6E2A10C81C4BFA38B40663A` |
| `models/payment_goal_production.yaml` | `A77166ECC5B539C9E61D60236B1618FED946AA964CB51A3308F61F5FC695CB79` |
| `models/payment_goal_staging.yaml` | `D1846B21199D2EBFCBD78272894400E565E55CAB4D11E17E6EA7130DF517AE95` |
| `models/payment_project.yaml` | `A78FAFAB8B94F3A0A8CE2A92876DCEF2F1A060D2B6A8D08A6E2EC54624143AD5` |
| `generator/controller_generic.asl` | `E1CC555F392AA6F1675997372CD6FAAD8805986DC69830ACD79C1B4778B2D9F4` |
| `.github/workflows/entity-execution.yml` | `AE59A5D17FAAF61FDCEA361BAC831555B0D9FA643357510FB304E0046C7240F5` |
| `run_controller.py` | `392AF55CA6D1A81BD7D4C1309C754F9F4EF3C0CE541AA237EDE100E9E44BE40D` |
| `ControllerEnvironment.java` | `1A92D9256CDDB941F95A7BB003EFA364DDA378D5888BCDCABD324FE0E27A85F0` |
| `GitHubEntityExecution.java` | `4CE79913B2CE6B3B4F5D48FCA37037F005DE646253CFB22021BF045E68CA565E` |

Every run also writes `generation-manifest.json` beside its journal with absolute input paths, hashes, achievement entities, and required entity closure. The selected application source is immutable within a campaign through `BDI_RELEASE_SHA`; local scenarios recorded the starting Git commit above while executing current generated framework files.

## Local scenario matrix

All action sequences below were read from `entity_execution_started` journal events. Each execution has a distinct UUID in its journal. Expected and actual sequences matched.

| Scenario | Expected action sequence | Actual action sequence and observations | Outcome |
|---|---|---|---|
| Healthy production | `build, test, security, staging, observe staging, production` | `build#1, test#1, security#1, staging#1`; telemetry `allow`; `production#1` | `achieved` |
| Staging-only goal | `build, test, security, staging`; no production | `build#1, test#1, security#1, staging#1`; production count `0` | `achieved` |
| Transient test failure | test fails once, one retry, then normal progression | `build#1, test#1 failure, test#2 success, security#1, staging#1`; telemetry `allow`; `production#1` | `achieved` |
| Retry exhaustion | test fails twice; no successor | `build#1, test#1 failure, test#2 failure`; security/staging/production absent | `stopped` |
| High-error staging | reach staging, block on telemetry; no production | `build#1, test#1, security#1, staging#1`; telemetry `block`; production absent | `stopped` |
| Missing telemetry | reach staging, remain fail-closed; no production | `build#1, test#1, security#1, staging#1`; telemetry `unknown`; production absent | `unknown` |
| Delayed telemetry | observe unknown, reconsider allow, then production | `build#1, test#1, security#1, staging#1`; telemetry `unknown, allow`; `production#1` | `achieved` |
| Controller pause | pause after security; no successor during pause | Journal records `controller_pause`, `milliseconds:750`, `successor_dispatched:false`; staging decision occurs about 0.78 seconds later | `achieved` |
| Second topology | `package, verify, preview` using unchanged runtime/policy | `package#1, verify#1, preview#1` | `achieved` |

Artifacts are under `bdi-cicd-framework/bdi/build/controller-runs/` and are intentionally build output. Each directory contains:

- `generation-manifest.json` with input hashes and goal closure;
- `controller-journal.jsonl` with decisions, relevant beliefs, attempts, execution identities, result status, telemetry, and outcome;
- `controller-result.json` with `achieved`, `stopped`, or `unknown`.

The repository-wide controller lock is kept under `bdi/build`, outside individual campaign directories, so two local campaigns cannot control the same deployment targets concurrently.

The pause establishes the control boundary directly: after the selected security action returned, no staging workflow existed in flight during the pause. Only the next Jason reasoning cycle emitted the staging action.

## Automated checks

| Check | Result |
|---|---|
| Python parser/generator suite | 13 tests passed, including goal closure, second topology, deterministic output, strict validation, and dispatch-only workflow structure |
| Java/Gradle suite | 9 tests passed, including controller configuration, retry scenario adapter, existing telemetry/observer tests, and local HTTP GitHub API adapter tests |
| GitHub adapter correlation | Mock dispatch returned run `321`; adapter accepted only exact job `Build entity`, preserved source SHA, and journaled dispatch acknowledgement |
| Payment Vitest suite | 3 files / 9 tests passed |
| TypeScript lint | Passed |
| TypeScript build | Passed |

The adapter is polling-based and single-flight. It generates one execution UUID per attempt, dispatches one workflow, accepts the run ID returned for that dispatch, then accepts only the exact configured selected-job name from that run. An absent or skipped selected job fails. Because no external event can insert a result belief and each terminal result is consumed synchronously once, stale runs and duplicate results cannot advance this controller.

## Live readiness check and exact blockers

The prepared source branch is `experiment-v2`; the intended reviewed workflow ref is the repository's default branch, `main`, because a `workflow_dispatch` workflow must exist on the default branch. The target is repository `id-nynt/260031_cicd_payment_demo`, GitHub Environments `staging` and `production`, and a self-hosted runner labelled `payment-deploy`. The designated stacks are `payment-staging` on application/Prometheus ports `3001/9091` and `payment-production` on `3000/9090`. Fake payments are configured in both.

Live execution was not started for these concrete reasons:

- `gh auth status` reports the saved token for account `id-nynt` as invalid. Repository workflow availability, Environment rules, runner online status, and run dispatch therefore could not be queried.
- Docker Compose v2.39.2 is installed and `docker compose config --quiet` validates the project manifest, but `docker info` fails with `Access is denied` on the Docker Desktop Linux engine pipe. `docker ps` returned no containers. No running stack or live Prometheus target could be verified.
- The new workflow and controller are only in the local working tree. GitHub cannot dispatch `.github/workflows/entity-execution.yml` until the changes are committed, reviewed, and pushed to the selected workflow ref.

Required recovery steps before a live campaign:

1. Re-authenticate GitHub CLI or provide a valid Actions dispatch/read token.
2. Review and commit this working tree on `experiment-v2`, open the normal review, and merge it to `main`. Use the resulting approved full commit SHA as `BDI_RELEASE_SHA`.
3. Confirm `entity-execution.yml` is visible on `main`, both GitHub Environments retain their protections, and an online runner has the `payment-deploy` label.
4. Start Docker Desktop/Engine on the runner and confirm Compose, curl, ports, and Prometheus reachability.
5. Run the controller from a separate host/process, not the sole self-hosted runner workspace, and record the returned GitHub URLs in a new results section.

Do not enable `legacy_deployment=true` during a controller campaign. The legacy deployment jobs otherwise remain manual and disabled, avoiding a parallel deployment race.

## Live demo commands

After those prerequisites are satisfied:

```powershell
$env:GITHUB_REPOSITORY='id-nynt/260031_cicd_payment_demo'
$env:GITHUB_TOKEN='<valid Actions dispatch/read token>'
$env:BDI_WORKFLOW_REF='main'
$env:BDI_RELEASE_SHA='<approved full commit SHA>'
$env:BDI_CAMPAIGN_ID='payment-healthy-001'
py -3 .\bdi-cicd-framework\run_controller.py `
  --goal .\bdi-cicd-framework\models\payment_goal_production.yaml `
  --artifacts-dir .\artifacts\payment-healthy-001
```

Create a properties file for a retry campaign:

```properties
test.1.failure_mode=force_failure
test.2.failure_mode=none
```

Set `BDI_EXECUTION_PLAN` to that file and use a new campaign/artifact directory. For exhaustion, force both test attempts. For high-error staging, set `staging.force_error_rate=1`. Run the staging goal separately and verify that no production run URL appears. For delayed/missing live telemetry, use an isolated demo stack or temporarily pause only the demo Prometheus/collector path; do not delete its persistent data. Repeat the core healthy, retry, and telemetry-block campaigns three times if runner time permits.

## Remaining limitations

- Live Actions, runner, Environment approval, deployment, fake-payment traffic, and Prometheus behavior remain unverified in this session.
- A workflow dispatch waiting for Environment review occupies the selected workflow while the controller waits; this is intentional and no successor is dispatched.
- The GitHub adapter handles at most 100 latest non-matrix jobs per run and uses a local JSONL journal rather than a durable service.
- Deployments rebuild the pinned source SHA. They do not promote one content-addressed image artifact.
- Readiness plus run-filtered Prometheus samples provide correlation, but independent scrape timestamp/target-health validation is limited to what the configured queries return.
- Autonomous production rollback is excluded until the project defines a real known-good artifact, selection rule, and tested recovery strategy.
