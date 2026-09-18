# Payment-service BDI promotion experiment

This is the executable companion to `00_PLAN.md`. The current experiment demonstrates **pre-production adaptation**: the goal is to promote a healthy release, while preserving the existing production deployment if staging is unhealthy. It does not perform a post-production rollback or move real money.

## Decision path

```text
Build + Test -> Security -> Deploy staging -> Generate fake payments
                                              -> OpenTelemetry -> Collector -> Prometheus
GitHub job results + staging telemetry -> Jason BDI gate -> allow -> Deploy production
                                               |            -> block -> Production skipped
                                               +-> unknown -> wait/reobserve; timeout fails closed
```

The gate reads the current Actions run using a job-scoped `GITHUB_TOKEN` with `actions: read`, and reads staging's loopback `/ready` and Prometheus endpoints on the same self-hosted runner. Job names and queries are in `bdi-cicd-framework/models/payment_project.yaml`. Staging and the gate share a run label (`run_id`-`attempt`) so measurements from an earlier deployment cannot make this run look healthy. The AgentSpeak goal and plans are in `bdi-cicd-framework/bdi/gate_agent.asl`. The gateway reobserves every five seconds until Jason returns `allow`/`block`; if evidence remains unavailable for 90 seconds, it returns `unknown` and fails.

## What has been verified locally

- Payment build and app tests pass. Parser and Java tests pass.
- Healthy isolated Compose app: fresh run-labeled payments produced finite Prometheus metrics; Jason changed from `telemetry_state(unknown)` to `telemetry_state(allow)` and exited successfully.
- High-error isolated Compose app: injected HTTP 503s produced a high error rate; Jason changed from `unknown` to `block` and exited nonzero.
- Missing telemetry: Jason remains waiting and the watchdog exits nonzero as `unknown`.
- The isolated app was restored to `normal` mode after testing.

These are **local integration results using a saved GitHub Jobs API fixture**. They do not prove that a live GitHub Actions run has passed. A live run must be observed before marking Phase 8 complete.

## Prepare the runner and repository

1. Confirm the self-hosted runner is online and can run Bash, Docker Compose, and `curl`.
2. Confirm the runner can reach `127.0.0.1:3001/ready` and `127.0.0.1:9091/-/ready` after staging deploys. Staging, gate, and production must use the same Docker host; if you have multiple self-hosted runners, use a shared runner label or move telemetry to a reachable host.
3. Confirm the runner has outbound access for the official Java setup action, the pinned Gradle wrapper, Maven Central, and the GitHub Actions API. No Stripe keys are needed.
4. Review all changes with `git status` and `git diff`. The copied `bdi-cicd-framework/` is currently untracked; it **must be committed** or the workflow checkout will not contain the gate. Do not accidentally stage unrelated edits in `docs/00_PLAN.md`.
5. Put the workflow on `main` through your normal review/merge process. A push to `main` automatically runs the normal path and may deploy production; use a protected `production` GitHub Environment if approval is required.

This workspace is currently on `experiment-v2`, not `main`. One safe way to publish only this experiment (leaving the unrelated local edit to `docs/00_PLAN.md` alone) is:

```powershell
git status --short
git add .dockerignore .github/workflows/ci-cd.yml README.md docker-compose.yml `
  src/app.ts src/config.ts src/telemetry.ts `
  tests/config.test.ts tests/experiment.test.ts `
  scripts/check-gate-telemetry.mjs docs/BDI_EXPERIMENT.md bdi-cicd-framework/
git diff --cached --stat
git commit -m "Integrate BDI staging-to-production gate"
git push -u origin experiment-v2
```

Review the staged framework files before committing; `bdi/bin/`, build output, and Gradle caches are ignored. Open and merge a pull request into `main` through your normal policy. The merge's push runs the healthy path automatically; then trigger the high-error run below. Do not run `git add .` if you want to leave `docs/00_PLAN.md` out of the commit.

## Run the two live experiments

Sign in on your own machine with `gh auth login`; do not paste an access token into a chat or commit it. Once the workflow is on `main`:

```powershell
gh workflow run ci-cd.yml --ref main -f experiment_mode=normal
gh run list --workflow ci-cd.yml --limit 5
gh run view <NORMAL_RUN_ID> --json jobs --jq '.jobs[] | {name, conclusion}'
```

Expected: `build`, `test`, `security`, `deploy-staging`, `bdi-gate`, and `deploy-production` succeed. In the `BDI gate` job summary/log, find `BDI_GATE_INPUT ... telemetry=allow` and `BDI_GATE_RESULT=allow`. From the runner, `curl http://127.0.0.1:3000/health` should include `deploymentRunId` for that healthy run and `experimentMode=normal`.

Then run the controlled staging fault:

```powershell
gh workflow run ci-cd.yml --ref main -f experiment_mode=high_error_rate
gh run list --workflow ci-cd.yml --limit 5
gh run view <ERROR_RUN_ID> --json jobs --jq '.jobs[] | {name, conclusion}'
```

Expected: staging succeeds because its traffic generator **expects** injected HTTP 503s and waits for fresh metrics. `BDI gate` logs `telemetry=block reason=high_http_error_rate`, prints `BDI_GATE_RESULT=block`, and fails. GitHub marks `deploy-production` **skipped** because it needs the gate. `curl http://127.0.0.1:3000/health` should still report the previous healthy `deploymentRunId`. The overall high-error workflow run is expected to be red: that is a successful safety experiment, not a broken payment app.

Use the Actions run URLs, gate job summary, Prometheus query results, and the two `/health` responses as your evidence. The run-specific metric selector is `ci_run_id="<RUN_ID>-<ATTEMPT>"`; for example, query `sum(rate(payment_http_errors_total{ci_run_id="123456-1",route="/payments",status_code="503"}[2m]))` in staging Prometheus at `http://127.0.0.1:9091` on the runner.

## If a run fails unexpectedly

- Staging traffic check fails: inspect its payment responses and `scripts/check-gate-telemetry.mjs` output. The script retries traffic until the current run has two useful Prometheus samples.
- Gate reports `workflow=unknown`: check `actions: read`, `GITHUB_RUN_ID`, repository name, and GitHub API reachability. The checked-in fixture must **not** be set in CI.
- Gate reports `telemetry=unknown`: check runner-to-staging reachability, matching `CI_RUN_ID`/`BDI_TELEMETRY_RUN_ID`, Prometheus target health, and the 90-second watchdog.
- Gradle cannot start: verify the checked-in `gradlew`, wrapper JAR, Java setup, and outbound Gradle/Maven access.
- More than one self-hosted runner: `127.0.0.1` may point to a different machine. Pin the jobs to the same runner or expose staging telemetry safely.

The earlier plan's rollback example is **not** this experiment's safety mechanism. Here, production is never changed on a bad staging run. A later post-deployment rollback experiment would need a separate, explicitly scoped recovery action, a preserved known-good image/database strategy, and rollback tests.
