# Explicit CI/CD decision policy validation — 2026-09-21

This validates the follow-up to `04e0ec2`: typed failures, declared retry safety, separate retry/observation/reconciliation budgets, bounded consecutive-health verification, request-controlled app faults and the revised manual. Earlier repair history and evidence remain unchanged.

Implementation commit: `14c4df0`.

## Results

- 39 Python tests passed: compiler/contract, artifact lifecycle, invalid budgets, explicit retry safety, worker/input/environment bindings and selected-entity-only execution.
- 26 Java tests passed: correlated dispatch, rejected requests, durable uncertainty/reconciliation, legacy rejection recovery and classification only from the actually failed transient worker step.
- 11 payment tests passed, including an HTTP 503 request-fault test and mode isolation; TypeScript lint/build passed.
- 28 actual Jason scenarios passed using simulated adapters, including temporary staging/production degradation, consecutive-health reset under flapping, observation deadline, deterministic failure without retry, dispatch rejection without retry, safe production retry, unsafe production recovery, exhausted retries, uncertainty, verified rollback and reporting-service topology.
- Saved persistent payment-agent smoke test uses real configured timing with simulated adapters; its result and manifest are retained in `persistent-smoke/`.
- `npm audit --omit=dev --json` reported zero production vulnerabilities at validation time. The updated worker blocks on high/critical production advisories.
- Active guide links resolve; every PowerShell block in the manual/setup document parses; `git diff --check` passes.

## Commands used

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
# From bdi-cicd-framework/bdi:
.\gradlew.bat --no-daemon test
# From repository root:
npm run lint
npm test
npm run build
npm audit --omit=dev --json
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/policy-refactor-validation
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/policy-refactor-unsafe --case production_retry_unsafe
py -3 -B bdi-cicd-framework/run_controller.py --scenario healthy --artifacts-dir bdi-cicd-framework/bdi/build/policy-persistent-smoke
```

The first scenario matrix ran 27 cases; the additional unsafe-production case was then added and tested separately. The suite now contains all 28. Use a new output directory if repeating validation. This automated local regression suite is for implementation verification; the live walkthrough remains manual.

`scenario-summary.json` retains all outcomes. Representative journals, results and manifests retain exact executed snapshots/source hashes. They were captured during implementation atop `04e0ec2`, before the final commits; source hashes, not that base commit alone, identify the tested code. `java-summary.json` records final test totals. Full local logs are under the named build directories.

## Live boundary

No live GitHub workflow, container deployment, rollback, push, merge or tag movement was performed. App HTTP tests use a mocked repository; they do not prove a live PostgreSQL/Compose/Prometheus deployment. Worker syntax and mappings are tested locally; the operator must publish the updated worker and v2 source, repair/confirm credentials and execute the manual scenarios. The existing v1 source has the same dependency manifests, but live v1 health must still be established by an achieved receipt.

Observation samples can overlap in the two-minute Prometheus window; two consecutive healthy readings are a policy threshold, not a statistical independence claim. Source rollback retains the database. The agent ends with the campaign. The reporting application is simulated coverage, not a live deployment claim.
