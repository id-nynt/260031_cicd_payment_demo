# One-time setup and troubleshooting

Start with [Part A of the manual guide](BDI_MANUAL_EXECUTION_GUIDE.md#part-a---setup-and-separate-system-checks) for the complete beginner walkthrough. This page is a supplementary setup and troubleshooting reference. Preparation does not count as a v2 deployment experiment. Commands are PowerShell at the current controller checkout unless marked Linux runner.

## Tools and local app check

Use Python with PyYAML, JDK 21+, Node 22+, Git, GitHub CLI and Docker Compose. Keep the controller outside the runner's `_work` checkout.

```powershell
git status --short
git branch --show-current
py -3 --version
java -version
node --version
gh --version
docker info
py -3 -m pip install PyYAML==6.0.3
npm ci
npm run lint
npm test
npm run build
```

Optional isolated app/telemetry rehearsal: in a **separate PowerShell window**, set these values and start Compose:

```powershell
$env:COMPOSE_PROJECT_NAME = 'payment-local'
$env:APP_PORT = '3002'
$env:POSTGRES_PORT = '5434'
$env:METRICS_PORT = '9466'
$env:PROMETHEUS_PORT = '9092'
$env:CI_RUN_ID = 'local'
$env:EXPERIMENT_MODE = 'normal'
docker compose up -d --build
Invoke-RestMethod http://localhost:3002/ready
$env:PAYMENT_BASE_URL = 'http://localhost:3002'
npm run traffic:experiment -- normal 6
```

Expected: checkout at port 3002 works; Prometheus at 9092 shows `payment_service_ready{ci_run_id="local"}`. Finish with `docker compose stop`, then close that PowerShell window. This preserves volumes. Keep Docker Engine running. The live experiment starts separate staging/production stacks; it never updates the stopped port-3002 rehearsal.

## Runner and endpoints

GitHub repository Ã¢â€ â€™ Settings Ã¢â€ â€™ Actions Ã¢â€ â€™ Runners: use the existing Linux runner with labels `self-hosted`, `linux`, `payment-deploy`. No new repository or runner registration is needed because of a second Git worktree. If registration is absent, follow GitHub's New self-hosted runner instructions.

Linux runner terminal, in its actual installation directory:

```bash
cd ~/actions-runner-payment
docker info
docker compose version
./run.sh
```

Expected: runner online/idle and able to use Docker. Leave it running, or use its existing service. Check repository Environments `staging` and `production`; any required deployment approvals must be granted for the selected job to run.

The controller must reach runner services: staging readiness/Prometheus 3001/9091, production 3000/9090. `127.0.0.1` is relative to the process using it. WSL/Docker Desktop forwarding or an explicit tunnel is required if these are not the same reachable host. Edit input 01 and regenerate if addresses change. Merely changing a hostname does not expose loopback-bound Prometheus.

## Credentials and publish the updated worker

Use a fine-grained GitHub token for `id-nynt/260031_cicd_payment_demo` with **Actions: Read and write**. In GitHub: profile Settings Ã¢â€ â€™ Developer settings Ã¢â€ â€™ Personal access tokens Ã¢â€ â€™ Fine-grained tokens. Select the owner/repository and complete any required approval. [Dispatch permissions](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).

```powershell
$dispatchToken = Read-Host 'Controller token (hidden)' -AsSecureString
$env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new('', $dispatchToken).Password
Remove-Variable dispatchToken
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
$headers = @{ Authorization = "Bearer $env:GITHUB_TOKEN"; Accept = 'application/vnd.github+json'; 'X-GitHub-Api-Version' = '2026-03-10' }
Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$env:GITHUB_REPOSITORY/actions/workflows/entity-execution.yml" |
    Select-Object name, state, path
Remove-Variable headers
```

Expected: the workflow is visible and active. This GET verifies read access only; check Actions write in token settings. Do not overwrite this environment variable with an older restricted CLI token. Do not print the token.

The **updated worker must be published before using the new fault modes**. After reviewing/committing the repaired revision, publish a new immutable worker tag from it. Do not move an existing tag:

```powershell
$workerRef = 'bdi-worker-' + (Get-Date -Format yyyyMMdd-HHmmss)
git tag $workerRef
git push origin "refs/tags/$workerRef"
$env:BDI_WORKFLOW_REF = $workerRef
```

Expected: GitHub has that tag containing the updated `.github/workflows/entity-execution.yml`. The workflow file must also exist on the default branch for dispatch. This publication is performed by you through the normal review process; local validation does not publish it. Pin this worker tag for all v1/v2 comparisons. It is independent of the source being deployed.

Git push uses Git credentials, which may differ from the controller token. If push is denied, use a separate authentication terminal without `GH_TOKEN`/`GITHUB_TOKEN`, run `gh auth login --hostname github.com --git-protocol https --web --scopes workflow`, then `gh auth setup-git`. Resolve repository/token write access before retrying the same push. Do not recreate the tag or install another runner to fix 403.

## Generate the project and rehearse once

Review [input 01](../bdi-cicd-framework/models/01_pipeline.yaml) and [input 02](../bdi-cicd-framework/models/02_goal.yaml). Normal jobs are declared retry-safe for this fake-payment, source-redeployment experiment; re-evaluate that assertion before adding nonrepeatable steps or database migrations. Production job duration is limited to 30 minutes, including queue/execution/polling; health verification has its own count/time limits.

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --scenario healthy
```

Expected: persistent `03_workflow_model.yaml`, `controller_agent.asl` and `generation-manifest.json` agree; simulated Jason reaches achieved. The scenario does not touch GitHub or deploy. Generate again only when input or generator policy changes, not for each campaign, source version or fault selection. Commit the generated outputs with the configuration revision.

Before live use, clear old endpoint/pause overrides in the controller shell:

```powershell
Remove-Item Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL,Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS -ErrorAction SilentlyContinue
```

Proceed to manual phase B1 with `$env:BDI_WORKFLOW_REF`, `$env:GITHUB_REPOSITORY` and `$env:GITHUB_TOKEN` set. Keep Docker/runner running.

## Troubleshooting: stop at the actual boundary

| Symptom | Meaning and action |
|---|---|
| Existing campaign directory | Evidence is protected. Use a fresh name or omit `--artifacts-dir`. |
| MAS finished but Gradle stays at 75% | Inspect printed outcome, then close MAS Console. No jobs are pending just because the GUI is open. |
| Dispatch 401/403/404/422 | Rejected request, not uncertain execution. Fix token/repository/ref/inputs; Jason stops without blindly retrying credentials. |
| Staging/production URLs unreachable | Inspect result/journal and `docker ps -a`. If no deployment ran, old stopped containers will remain stopped. |
| Missing/stale project artifacts | Run explicit generation after reviewing inputs/policy; runtime never generates silently. |
| Job queued | Check online runner, labels and Environment approvals. |
| Unhealthy telemetry | Check correct execution ID, freshness, traffic and readiness. Persistent faults stop promotion or restore verified v1. |
| Execution unknown | Reconcile before any new deployment. Absence of a GitHub run in a bounded search does not prove rejection. |

After closing the old MAS, reconcile uncertain execution:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only
```

Expected: confirmed terminal state clears pending intent; unknown retains it. This does not resume the candidate or claim achievement. Worktrees share the controller lock. Never delete pending state to force redispatch.

For a legacy campaign that incorrectly recorded an explicit 403 as uncertain, use its **original** rejection evidence:

```powershell
py -3 -B bdi-cicd-framework/run_controller.py --reconcile-only --rejected-dispatch-evidence bdi-cicd-framework/runs/manual-20260921-000908-v1
```

This validates matching journal/receipt/pending identities, archives proof, and settles `dispatch_rejected` without a network dispatch. It is a one-time repair, not a routine command. The specific old record above was already repaired in this worktree; do not rerun it unless that record is actually pending. Historical recovery results may use the older status `failure`.

## Locally rejected Authorization header (September 2026 repair)

The campaign `manual-20260921-003920-v1` failed locally while constructing the HTTP Authorization header: its token input contained a control character. No POST was sent. Older code nevertheless left an unresolved dispatch record, blocking later campaigns. The launcher and Java adapter now reject missing/malformed credentials before creating a dispatch intent and never echo the token.

The evidence-recovery command also recognizes this exact local header-construction error, validates campaign/execution identities, archives the original journal and pending record, then settles `dispatch_rejected`. This does not reinterpret network timeouts or an absent run as proof of rejection. Use `--reconcile-only --rejected-dispatch-evidence` only with the original campaign's proof, not a later blocked campaign. This specific pending record was repaired during the fix; do not rerun the repair unless that record is actually pending.

A hidden token prompt can capture Ctrl+V as a control character in some consoles. Use the terminal's Paste action, then confirm the metadata request in manual A6 succeeds before launching. Credentials set in one PowerShell session are not automatically available in another session or to GitHub CLI.
