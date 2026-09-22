# Returning users: start a new v1/v2 experiment pair

**Start here if the old tools, authentication, Docker and runner setup are already complete.** The app now displays a release banner immediately, so the old application commits cannot serve as the new labelled pair. You need new immutable application tags and a fresh live v1 receipt; you do not need to reinstall the tools or register another runner.

`src/release.ts` is the single source of the experiment version. This checkout starts as **v1**. Checkout, payment and receipt pages display **Payment Service v1**; their browser titles, `/health.appVersion`, `/config.appVersion` and the startup log use the same value. Changing the source constant to `v2` in a separate commit changes all those surfaces. An environment variable cannot relabel an old app. `package.json`'s package version is separate from this experiment label.

The label is a convenient visual check, not a unique release identifier. Keep the full source SHA, verified deployment receipt and `deploymentRunId` as the authoritative provenance. An already open browser tab must be refreshed after deployment.

## 1. Review and publish the new v1 source

Review and commit the app changes, tests, current docs and intended control/workflow changes on your review branch. Merge/register the workflows on the default branch through your normal process. Do not tag the old v1 SHA: it does not contain the new banner.

At the reviewed **v1 commit** in a clean checkout, run from the repository root:

```powershell
$ErrorActionPreference = 'Stop'
$series = Get-Date -Format yyyyMMdd-HHmmss
$v1Tag = "experiment-$series-v1"
$v2Tag = "experiment-$series-v2"
$workerRef = "comparison-worker-$series"
$env:GITHUB_REPOSITORY = 'id-nynt/260031_cicd_payment_demo'
if (git status --porcelain) { throw 'Review and commit intended changes before freezing v1' }
$v1Sha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve v1 source' }
$releaseSource = git show "${v1Sha}:src/release.ts"
if ($LASTEXITCODE -ne 0 -or ($releaseSource -join "`n") -notmatch "APP_VERSION[^=]*= 'v1';") {
  throw 'The selected commit must contain APP_VERSION v1'
}
npm run lint
if ($LASTEXITCODE -ne 0) { throw 'Typecheck failed' }
npm test
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
git tag $v1Tag $v1Sha
if ($LASTEXITCODE -ne 0) { throw 'Use a new tag name; never move an old tag' }
git push origin "refs/tags/$v1Tag"
if ($LASTEXITCODE -ne 0) { throw 'Resolve publication before continuing' }
```

Keep this PowerShell window open until step 3 saves the selections. The existing `v1` tag, prior v2 tag and old receipts remain historical records; do not overwrite them.

## 2. Create the new v2 candidate with one source change

Create a candidate branch from the new v1 commit:

```powershell
git switch -c "experiment/$series-v2" $v1Sha
if ($LASTEXITCODE -ne 0) { throw 'Choose a fresh candidate branch' }
```

In `src/release.ts`, change only this declaration:

```typescript
export const APP_VERSION: 'v1' | 'v2' = 'v2';
```

The banner, browser titles, receipt title, APIs and startup log will now say v2. Payment behavior, database schema, faults and telemetry stay the same for a controlled comparison. Then:

```powershell
npm run lint
if ($LASTEXITCODE -ne 0) { throw 'Typecheck failed' }
npm test
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
git add -- src/release.ts
git diff --cached
# Confirm the staged diff contains only the intended v1-to-v2 declaration change.
git commit -m "Mark experiment candidate as v2"
if ($LASTEXITCODE -ne 0) { throw 'Candidate commit failed' }
$v2Sha = (git rev-parse HEAD).Trim()
git diff $v1Sha $v2Sha -- src
git tag $v2Tag $v2Sha
if ($LASTEXITCODE -ne 0) { throw 'Candidate tag failed' }
git tag $workerRef $v2Sha
if ($LASTEXITCODE -ne 0) { throw 'Control tag failed' }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw 'Candidate branch publication failed' }
git push origin "refs/tags/$v2Tag" "refs/tags/$workerRef"
if ($LASTEXITCODE -ne 0) { throw 'Tag publication failed' }
```

The control tag selects the reviewed workflow code. Both mechanisms use this same tag, while `release_sha` separately selects v1 or v2. The app's source label change does not require BDI agent regeneration. Do not merge further app changes into this pair during the measured series.

## 3. Save the selected pair and check existing infrastructure

```powershell
py -3 ci-cd-conventional/sync_workflows.py --check
if ($LASTEXITCODE -ne 0) { throw 'Workflow copies differ' }
py -3 ci-cd-conventional/configuration.py --check-bdi-parity
if ($LASTEXITCODE -ne 0) { throw 'Paired configurations differ' }
py -3 bdi-cicd-framework/run_controller.py --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Resolve generated-project consistency' }
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Restore existing GitHub authentication' }
New-Item -ItemType Directory -Force experiments/results/release-pairs | Out-Null
$pairFile = [System.IO.Path]::GetFullPath("experiments/results/release-pairs/$series.json")
if (Test-Path $pairFile) { throw 'Do not overwrite an earlier release pair' }
$pair = [pscustomobject]@{
  series = $series; repository = $env:GITHUB_REPOSITORY
  v1_tag = $v1Tag; v1_sha = $v1Sha; v2_tag = $v2Tag; v2_sha = $v2Sha
  worker_ref = $workerRef; known_good_receipt = $null
}
$pair | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
$pairFile
```

Save the printed path. This selection record is local experiment evidence, so it is Git-ignored and needs a backup. Start Docker Desktop and your **existing** Linux runner if stopped; verify it is online and can use Docker. Stop old traffic and settle any previous remote execution. If BDI has an unresolved execution, follow manual F3 before launching anything else.

## 4. Deploy the NEW v1 and save a fresh baseline receipt

This is preparation, not a measured v2 trial. An old successful receipt is not a receipt for the newly labelled v1 commit. The following establishes the baseline with your existing BDI setup; the conventional manual's step 3 can alternatively establish it, using this pair's v1 SHA and worker tag.

If you reopened PowerShell, first set `$pairFile` to the exact saved path printed in step 3. The block below reloads its selections.

```powershell
if ([string]::IsNullOrWhiteSpace($pairFile)) { throw 'Set $pairFile to the saved release-pair JSON path from step 3' }
$pair = Get-Content -LiteralPath $pairFile -Raw | ConvertFrom-Json
Remove-Item Env:GH_TOKEN,Env:GITHUB_TOKEN,Env:GITHUB_API_URL -ErrorAction SilentlyContinue
Remove-Item Env:BDI_EXECUTION_PLAN,Env:BDI_SCENARIO,Env:BDI_READY_URL,Env:BDI_PROMETHEUS_URL,Env:BDI_PAUSE_AFTER_ENTITY,Env:BDI_PAUSE_MILLISECONDS,Env:BDI_POLL_SECONDS,Env:BDI_ENTITY_TIMEOUT_MINUTES -ErrorAction SilentlyContinue
$env:GITHUB_REPOSITORY = $pair.repository
$env:GITHUB_TOKEN = gh auth token --hostname github.com
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'Restore GitHub authentication' }
$env:BDI_WORKFLOW_REF = $pair.worker_ref
$env:BDI_RELEASE_SHA = $pair.v1_sha
$baselineDir = 'bdi-cicd-framework/runs/' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '-labelled-v1'
$baselineDir
py -3 -B bdi-cicd-framework/run_controller.py --gui --baseline --artifacts-dir "$baselineDir"
```

Wait for `achieved`; capture the MAS output and close the completed console to return to PowerShell. Then verify both the receipt and the deployed app:

```powershell
$baseline = Get-Content "$baselineDir/controller-result.json" -Raw | ConvertFrom-Json
if ($baseline.mode -ne 'github' -or $baseline.outcome -ne 'achieved' -or $baseline.release_sha -ne $pair.v1_sha) {
  throw 'New v1 was not verified; inspect evidence before continuing'
}
foreach ($environment in @('staging','production')) {
  $port = if ($environment -eq 'staging') { 3001 } else { 3000 }
  $verified = $baseline.verified_releases.$environment
  $health = Invoke-RestMethod "http://127.0.0.1:$port/health"
  Invoke-RestMethod "http://127.0.0.1:$port/ready"
  if ($verified.release_sha -ne $pair.v1_sha -or -not $verified.github_run_id -or
      $health.appVersion -ne 'v1' -or $health.deploymentRunId -ne $verified.execution_id) {
    throw "Wrong or unverified baseline in $environment"
  }
}
$knownGood = (Resolve-Path "$baselineDir/controller-result.json").Path
$pair.known_good_receipt = $knownGood
$pair | ConvertTo-Json | Set-Content -LiteralPath $pairFile -Encoding utf8
$knownGood
```

Refresh `http://localhost:3001/checkout` and `http://localhost:3000/checkout`: both must immediately show **Payment Service v1**, without making a payment. Container startup logs also contain `Payment Service v1 started`. Back up the baseline directory and pair file together. If using a conventional baseline instead, set `known_good_receipt` to its newly downloaded result and perform the same version/identity checks before saving the pair.

## 5. Start the measured experiments

You now have three distinct saved items: the **v1 source tag/SHA**, the **v2 source tag/SHA**, and the **new v1 live receipt**. The receipt is not a Git tag and the heading is not proof of deployment success on its own.

For BDI, use manual **B1–B4**, loading this pair file in **B2**, then **C6** with `healthy` first. For conventional, load the pair in manual **step 2**, restore v1 with **step 4**, then launch `healthy` in **step 5**. The counterpart must use the same pair file, case and seed. Restore v1 between every trial.

Successful v2 delivery: both relevant receipt/health checks pass and production shows **v2**. Verified rollback: production shows **v1** and `recovery_outcome=restored`; it is not successful v2 delivery. Archive all result/traffic folders following the [results guide](05_EXPERIMENT_RESULTS_GUIDE.md), including unsuccessful trials.

After the healthy pair, follow the [pilot sequence and shared scenarios](02_COMPARATIVE_EXECUTION_GUIDE.md). Do not repeat tool installation or runner registration unless the prerequisite checks fail.

[Guidelines index](00_README.md)
