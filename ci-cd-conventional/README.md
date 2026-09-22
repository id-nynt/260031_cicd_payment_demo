# Conventional CI/CD experiment

Start with [the standalone manual](../docs/execution/guidelines/04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md).

The root payment application is shared unchanged: `src/`, `tests/`, `package*.json`, Dockerfile and Compose. Both approaches select the same published application SHA; v1/v2 retain their existing functionality and UI differences. No duplicated app can drift from its counterpart.

| File | Responsibility |
|---|---|
| `workflows/ci-cd.yml` | One workflow, six jobs: build ? test ? security ? staging ? production ? conditional rollback |
| `run-entity.py` | One mechanical attempt and immutable receipt; YAML selects a single bounded retry |
| `native-experiment.py` | Preparation, bounded health/repair gates and offline result aggregation |
| `config.json`, `snapshots/` | Reviewed policy and bindings, checked against BDI for paired studies |
| `sync_workflows.py` | Install the one source workflow into GitHub's required directory |

Edit `workflows/ci-cd.yml`, then run `python ci-cd-conventional/sync_workflows.py`. Its installed copy is `.github/workflows/ci-cd.yml`; this is one executable workflow, not two competing pipelines. The old reusable entity/health wrappers are removed. GitHub job dependencies control progression; failed entity status fails its job. Deployment gates run inside staging/production/rollback jobs. Preparation runs inside build. Each job uploads its evidence even on failure.

Both approaches call `scripts/execute-entity.sh` from the immutable app checkout while loading worker scripts from the frozen control revision. This preserves the same npm commands, audit, Docker operations and injected faults. Conventional execution does not call the BDI worker or start Jason. The BDI worker retains separate, statically named Diagnose candidate and Restart candidate jobs; the obsolete report job is removed.

After a terminal workflow, `experiments/collect.py` downloads artifacts and assembles `artifacts/native-result/result/` locally. It uses per-attempt receipts rather than treating a failed production health gate as a failed deployment command. Missing receipts remain collection errors. There is no result job; a successful rollback does not turn the failed candidate delivery into success.

To run this as a checkout without the BDI framework, retain this folder, `.github/workflows/`, `experiments/`, `scripts/` and the root app/Compose files. Do not enable the BDI validation workflow in that separate repository. For this paired study, keep one repository so both approaches use the same application commits and worker revision.

When changing the study policy, review BDI's generated contract and refresh `config.json` and the five snapshots together. `configuration.py --check-bdi-parity` verifies exact policy, bindings, contract and source hashes. Do not merely update hashes to silence a mismatch; a changed retry topology also requires changes to the static YAML.

No live result is shipped as evidence for this revision. Local unit tests are validation of the implementation, not RQ outcomes.

The production health gate diagnoses an unavailable/not-ready service using the shared `scripts/candidate-repair.py`. A matching stopped candidate with a ready database permits one restart, followed by 120 seconds of payment probes and two fresh health observations. The 300-second decision budget includes diagnosis/repair/verification. A running app with request errors is reobserved; a failed repair or failed verification makes the gate fail so the YAML selects verified rollback. This is a conventional scripted recovery policy with the same capabilities as BDI, not a fail-fast baseline. All six jobs remain visible in the YAML. Ready services with request errors reobserve within the common observation budget without early diagnosis; the two-minute metric window must recover before two consecutive healthy samples can pass.

The shared catalog adds `candidate-stopped` and `candidate-restart-fails` (13 available cases). For these two, production's normal traffic client is replaced by the shared repair probes; staging traffic and the 60-second production pause remain. Gate artifacts retain `diagnose-receipt.json` and `restart-receipt.json`. Metrics distinguish repaired v2 delivery from restored v1. The legacy Java conventional simulator does not implement this repair policy and is not the live comparator.
