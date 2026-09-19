# Overall Manual Payment Demo

Use this guide for the visible v1-to-v2 experiment. It supersedes the older guide's headless-only and Java-owned telemetry-wait instructions.

```text
publish the complete controller
-> deploy a healthy baseline v1
-> open the production app
-> publish candidate v2
-> start Jason MAS Console
-> watch GitHub entity runs and the agent mind
-> inject a fault at the documented pause
-> observe Jason retry, reconsider, stop, or promote
-> confirm production identity
```

The launcher `bdi-cicd-framework/run_controller.py` validates, generates, and starts Jason. Without `--scenario` it dispatches real GitHub jobs. With `--scenario` it runs simulated results through the real agent and makes no deployment.

## 0. Branches and versions: do this once

The complete recovery is on **fix/bdi-controller-runtime**, reconciled with `origin/main` at `dd1b5c8`. The older `release/bdi-demo-v2` was already merged; this repair removes its generated build/cache files from Git tracking while preserving local files. Merge the repair's reviewed PR before creating release tags. Do not continue experiments on the older release branch.

Publish the repair after authenticating, then open its PR into `main`:

```powershell
gh auth login -h github.com
git push -u origin fix/bdi-controller-runtime
```

The repair is committed locally; publication and live deployment have not been verified from this session.

Historical tags `v1.0` and `bdi-demo-v1.0.0` remain unchanged. Neither should be called the complete new console baseline. Use fresh names:

| Name | Meaning |
|---|---|
| `bdi-console-v1.0.0` | Reviewed complete controller plus known-good app |
| `demo/payment-v2` | New candidate branch created from that baseline |
| `bdi-console-v2.0.0-rc1` | Published candidate commit |

After the recovery PR is merged, in a clean checkout:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git tag -a bdi-console-v1.0.0 -m "Complete MAS console demo baseline"
git push origin bdi-console-v1.0.0
```

Do not tag before the source, generated controller, workflow, scripts, and tests are committed. `git add -p` alone does not include newly created files; explicitly add reviewed new paths and inspect `git diff --cached --stat`.

## 1. Prepare the windows

| Window | Purpose |
|---|---|
| Terminal A: controller checkout | Start a campaign; it opens MAS Console |
| MAS Console | Select `controller_agent`; see decisions, results and waiting/reconsideration |
| Browser: agent mind | Open the mind-inspector URL printed by Jason; select `controller_agent` to inspect beliefs, events and intentions |
| Browser: GitHub Actions | One named run per selected entity; observe retries and Environment approval |
| Browser: production app | `http://localhost:3000/checkout` |
| Browser: staging Prometheus | `http://localhost:9091` |
| Terminal B: operator | Watch journal, inject faults and inspect production identity |

Run the controller from a durable checkout, outside the runner's `_work` folder and outside its execution slot. A Linux self-hosted runner labelled `payment-deploy` runs deployment jobs. Docker must work for that runner account. Build/test/security use hosted runners. Keep Environment approval protections enabled.

The MAS console needs a desktop display (Windows desktop, Linux desktop, or WSLg). It is the real Jason Swing console, not a separate mock dashboard. It stays open after the final outcome so you can inspect the mind. Close it after recording evidence to release the controller lock. Closing it during a live job does not cancel that GitHub run; inspect/cancel the run before starting another campaign.

For Windows controller plus a separate Linux/WSL runner, verify that the following loopback URLs really reach the runner-hosted stack. Otherwise use protected forwarding or a project manifest with reachable endpoints; do not assume localhost crosses machines.

## 2. Quick visible local rehearsal

```powershell
py -3 bdi-cicd-framework/run_controller.py --gui --scenario telemetry_delayed
```

Expected: MAS Console opens, `controller_agent` runs build/test/security/staging, prints `BDI_DECISION=wait_reconsider`, waits five seconds, observes again, then reaches production and `BDI_CONTROLLER_RESULT=achieved`. Open the printed mind-inspector URL. This rehearsal has no GitHub deployment. Close MAS Console afterwards.

## 3. Terminal A: credentials and clean campaign settings

Use Python/PyYAML and JDK 21+. Start Docker and the existing runner service. Authenticate with `gh auth login`, then:

```powershell
$env:GITHUB_REPOSITORY='id-nynt/260031_cicd_payment_demo'
$env:GITHUB_TOKEN = gh auth token
if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication required' }
$env:BDI_WORKFLOW_REF='main'
Remove-Item Env:BDI_EXECUTION_PLAN -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_AFTER_ENTITY -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
Remove-Item Env:BDI_READY_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_PROMETHEUS_URL -ErrorAction SilentlyContinue
```

The token requires Actions write/read access. Do not print it or store it in files. `main` must contain the dispatch workflow. Pushing a candidate makes source available; starting the controller starts the BDI campaign.

## 4. Establish v1 in production first

Do not switch the controller checkout backwards. Select the application's immutable source SHA:

```powershell
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-console-v1.0.0
$env:BDI_CAMPAIGN_ID = 'baseline-' + (Get-Date -Format yyyyMMdd-HHmmss)
$runDir = "bdi-cicd-framework/bdi/build/controller-runs/$env:BDI_CAMPAIGN_ID"
py -3 bdi-cicd-framework/run_controller.py --gui --artifacts-dir $runDir
```

Human actions: watch build, test, security, staging; approve production in GitHub if requested. Wait for `achieved`. Close MAS Console.

Open `http://localhost:3000/checkout` and make a fake payment. In Terminal B:

```powershell
$v1Health = Invoke-RestMethod http://localhost:3000/health
$v1Health
Invoke-RestMethod http://localhost:3000/ready
```

Expected: `status=ok`, `experimentMode=normal`, readiness success. Record `deploymentRunId` and the production run URL; the campaign journal links this identity to the release SHA. The app currently reports execution identity, not a literal v1/v2 version string.

## 5. Publish candidate v2

From the complete baseline:

```powershell
git switch -c demo/payment-v2 main
# Make the candidate app change, then run its checks.
npm test
npm run lint
npm run build
git add -p
git diff --cached
git commit -m "Prepare payment v2 candidate"
git push -u origin demo/payment-v2
git tag -a bdi-console-v2.0.0-rc1 -m "Payment v2 demo candidate"
git push origin bdi-console-v2.0.0-rc1
```

Use a real intentional candidate change, for example UI receipt wording. Runtime fault injection below does not require faulty application source. Keep the controller/workflow identical between versions. Do not create an empty candidate merely to claim a different version.

## 6. Healthy v2 campaign

In Terminal A:

```powershell
$env:BDI_RELEASE_SHA = git rev-list -n 1 bdi-console-v2.0.0-rc1
$env:BDI_CAMPAIGN_ID = 'v2-healthy-' + (Get-Date -Format yyyyMMdd-HHmmss)
$runDir = "bdi-cicd-framework/bdi/build/controller-runs/$env:BDI_CAMPAIGN_ID"
py -3 bdi-cicd-framework/run_controller.py --gui --artifacts-dir $runDir
```

Expected MAS sequence:

```text
BDI_DECISION=run entity=build attempt=1
BDI_BELIEF=success entity=build attempt=1
...test, security, staging...
BDI_DECISION=observe entity=staging
BDI_BELIEF=telemetry entity=staging decision=allow
BDI_DECISION=run entity=production attempt=1
BDI_CONTROLLER_RESULT=achieved
```

GitHub run titles include campaign, entity and attempt. In each run only the selected job executes. The others are skipped. On production approval, the selected job waits; the agent does not choose a successor.

Terminal B can follow the journal (replace the campaign name):

```powershell
Get-Content bdi-cicd-framework/bdi/build/controller-runs/<campaign>/controller-journal.jsonl -Wait
```

After completion, compare `/health` with `$v1Health`. The new `deploymentRunId` must match the production execution ID in the journal, whose `release_sha` must be v2. Check `/ready` and a fake payment again.

## 7. Mid-release transient test failure

Create an initially empty control file before starting. Java reloads it before each dispatch, allowing edits while the agent is paused:

```powershell
New-Item -ItemType Directory -Force bdi-cicd-framework/bdi/build/manual-control | Out-Null
Set-Content bdi-cicd-framework/bdi/build/manual-control/faults.properties '' -Encoding ascii
$env:BDI_EXECUTION_PLAN = (Resolve-Path bdi-cicd-framework/bdi/build/manual-control/faults.properties).Path
$env:BDI_CAMPAIGN_ID = 'v2-retry-' + (Get-Date -Format yyyyMMdd-HHmmss)
py -3 bdi-cicd-framework/run_controller.py --gui --pause-after build --pause-ms 60000
```

Wait for `controller_pause` with `after_entity=build`. In Terminal B, before that minute expires:

```powershell
Set-Content bdi-cicd-framework/bdi/build/manual-control/faults.properties 'test.1.failure_mode=force_failure' -Encoding ascii
```

Expected GitHub: test attempt 1 fails at Controlled experiment failure; a separate test attempt 2 succeeds. Expected MAS: `BDI_DECISION=retry entity=test after=failure`, followed by attempt 2 and normal progression. The fault changes the job result; Jason selects retry.

For exhaustion, put `test.failure_mode=force_failure` in the file. Expected: two failed test runs, `stopped`, and no staging/production run. Production remains whatever revision was deployed before this campaign.

## 8. High-error staging: keep healthy v1 in production

First rerun step 4 if production currently has v2. Record v1 `/health`. Then select v2 SHA again. Clear the fault file, start a new GUI campaign with `--pause-after security --pause-ms 60000`. At `after_entity=security`, Terminal B writes:

```powershell
Set-Content bdi-cicd-framework/bdi/build/manual-control/faults.properties 'staging.force_error_rate=1' -Encoding ascii
```

The staging worker deploys v2 in high-error mode and sends real fake-payment traffic. Open staging Prometheus, use the run-specific query from `models/payment_project.yaml` (replace `{{run_id}}` with staging execution ID).

Expected: HTTP 503 samples, error ratio above 0.05, Java observation reason `high_http_error_rate`, MAS `telemetry(staging,block)` and `stopped`. There must be no production dispatch. Production `/health` must retain the original v1 execution ID. This demonstrates avoiding promotion; it does not perform rollback.

## 9. Missing telemetry, then reconsideration

Clear the fault file. Start healthy v2 with `--gui --pause-after staging --pause-ms 60000`. Wait until `controller_pause` says `after_entity=staging`; this is after staging deployment/traffic, before Jason's telemetry observation.

In a terminal **on the Docker deployment host**:

```powershell
docker compose -p payment-staging stop prometheus
```

After the pause, MAS should show `BDI_DECISION=wait_reconsider entity=staging round=1`. No production run starts. After one or two rounds:

```powershell
docker compose -p payment-staging start prometheus
```

Expected: subsequent samples become available and Jason proceeds after `allow`. Keep the interruption short so the two-minute request window remains populated. If samples have expired, send healthy traffic again with `PAYMENT_BASE_URL=http://localhost:3001` and `node scripts/generate-experiment-traffic.mjs normal 12`.

If Prometheus stays stopped, after 18 observations Jason records exhausted unknown and finishes `unknown`, with no production run. Restart Prometheus after the demonstration. No volumes are removed. The 5-second interval excludes HTTP query time, so total wall time can exceed 90 seconds.

## 10. Return to v1 / redo a campaign

Close the finished MAS window, clear the fault file, unset pause settings, select the v1 SHA, and repeat step 4 with a NEW campaign ID. This redeploys the pinned known-good source through the same checks. It does not reset Git, move tags, or delete the database. Source rollback across incompatible migrations requires a separate database recovery plan.

To repeat the same candidate experiment, keep the same SHA and use a new campaign ID. Do not erase old journals; they are evidence.

## Evidence checklist

- Every dispatched entity has a preceding BDI decision.
- Retries have a distinct GitHub run URL and execution UUID.
- At the pause, no successor workflow exists yet.
- `telemetry_sample(staging,Round,unknown)` leads to a visible AgentSpeak wait/reconsider plan.
- Only `allow` permits production; block/unknown leave the old production identity intact.
- `controller_result(achieved|stopped|unknown)` remains inspectable in the GUI at the end.

There is no production canary/automatic rollback policy in this project. Do not copy `/pay`, port 8002, `deployment_agent`, or rollback expectations from the reference project's guide. This app uses `/payments`, ports 3000/3001, and `controller_agent`.

The old `ci-cd.yml` needs-chain and `bdi-gate` workflow is disabled and moved
to documentation. It must not be re-enabled during the experiment. If a
candidate must be reverted, use the separate `Manual production rollback`
workflow with the previously recorded immutable v1 commit SHA, a new
`rollback_run_id`, and the confirmation value `ROLLBACK`. GitHub's production
Environment approval remains required. This is an operator-selected rollback;
the BDI controller does not invent a release SHA or roll back automatically.

To exercise rollback, first record the v1 `release_sha` and production
`deploymentRunId` from the baseline campaign. After a v2 campaign has reached
production, open GitHub Actions → `Manual production rollback` → Run workflow,
enter the v1 SHA and a value such as `rollback-<timestamp>`, type `ROLLBACK`,
approve the production Environment, and verify `/health` reports that new
rollback identity. Record the workflow URL beside the campaign journal.
