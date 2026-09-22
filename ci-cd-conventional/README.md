# Conventional CI/CD experiment

Start with [the standalone manual](../docs/execution/guidelines/04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md).

The root payment application is shared unchanged: `src/`, `tests/`, `package*.json`, Dockerfile and Compose. Both approaches select the same published application SHA; v1/v2 retain their existing functionality and UI differences. No duplicated app can drift from its counterpart.

| File | Responsibility |
|---|---|
| `workflows/ci-cd.yml` | Explicit build → test → security → staging → production DAG, plus preparation, health, recovery and result jobs |
| `workflows/conventional-entity.yml` | One bounded retry for confirmed transient failure/timeout; shared execution worker |
| `workflows/conventional-health.yml` | Runner-side traffic and bounded telemetry observations |
| `native-experiment.py` | Preparation, telemetry checks and result serialization; does not choose the next stage |
| `config.json`, `snapshots/` | Frozen conventional policy, endpoints and provenance; no runtime BDI imports |
| `configuration.py` | Standalone validation; optional BDI parity check for matched studies |
| `sync_workflows.py` | Install/check exact YAML copies in `.github/workflows/` |
| `tests/` | Offline conventional gate, retry, receipt and evidence tests |

GitHub only discovers workflows in `.github/workflows/`, so both source files and installation copies are committed. Edit the sources here, run `py -3 ci-cd-conventional/sync_workflows.py`, and commit both. CI rejects drift. See [GitHub's reusable workflow documentation](https://docs.github.com/en/enterprise-cloud%40latest/actions/how-tos/reuse-automations/reuse-workflows).

`.github/workflows/entity-execution.yml` is the shared mechanical worker for both approaches. Its historical display name is **BDI Entity Execution**, but calling it does not start an agent. It runs the same npm commands, security audit, Docker deployments and injected faults for either orchestrator. Jason/Java/generation is not required for conventional execution. The YAML keeps health and rollback support explicit because a realistic conventional baseline should include those protections.

To run this as a checkout without the BDI framework, retain this folder, `.github/workflows/`, `experiments/`, `scripts/` and the root app/Compose files. Do not enable the BDI validation workflow in that separate repository. For this paired study, keep one repository so both approaches use the same application commits and worker revision.

When changing the study policy, review BDI's generated contract and refresh `config.json` and the five snapshots together. `configuration.py --check-bdi-parity` verifies exact policy, bindings, contract and source hashes. Do not merely update hashes to silence a mismatch; a changed retry topology also requires changes to the static YAML.

No live result is shipped as evidence for this revision. Local unit tests are validation of the implementation, not RQ outcomes.

The production health gate diagnoses the first unhealthy/unknown sample using the shared `scripts/candidate-repair.py`. A matching stopped candidate with a ready database permits one restart, followed by 120 seconds of payment probes and two fresh health observations. The 300-second decision budget includes diagnosis/repair/verification. A running app with request errors is reobserved; a failed repair or failed verification makes the gate fail so the YAML selects verified rollback. This is a conventional scripted recovery policy with the same capabilities as BDI, not a fail-fast baseline. The normal five jobs remain visible in the YAML.

The shared catalog adds `candidate-stopped` and `candidate-restart-fails` (13 available cases). For these two, production's normal traffic client is replaced by the shared repair probes; staging traffic and the 60-second production pause remain. Gate artifacts retain `diagnose-receipt.json` and `restart-receipt.json`. Metrics distinguish repaired v2 delivery from restored v1. The legacy Java conventional simulator does not implement this repair policy and is not the live comparator.
