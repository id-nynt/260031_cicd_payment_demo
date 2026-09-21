# Four-source migration: implementation record

The proposal in [BDI_MODEL_SIMPLIFICATION_PROPOSAL.md](BDI_MODEL_SIMPLIFICATION_PROPOSAL.md) is implemented. The payment policy has been relocated, not changed; the generated AgentSpeak file is byte-identical to its pre-migration version.

## Files engineers edit

| File | Responsibility |
|---|---|
| `bdi-cicd-framework/models/01_pipeline.yaml` | Entities, dependencies, exact worker job names, deployment environments, recovery relationship, `max_retries` |
| `bdi-cicd-framework/models/02_goal.yaml` | Achievement, maintenance and avoidance goals |
| `bdi-cicd-framework/config/controller_policy.yaml` | Required explicit budgets, retry-safe allowlist, observation placement, recovery safeguards and telemetry thresholds |
| `bdi-cicd-framework/config/runtime_bindings.yaml` | Actual readiness/Prometheus URLs, correlated metric queries and freshness |

The policy explicitly retains 36 observation attempts, five-second intervals, a 180-second observation deadline, two consecutive healthy samples and the existing retry/reconciliation budgets. Missing required settings now fail validation; there is no fallback to 18 observations or an omitted retry-safety field. An explicit `retry_safe: []` is valid and disables execution retries; the payment allowlist retains its previous entities.

A setting belongs to one source. Old inline policy/telemetry fields in 01/02 are rejected rather than silently overriding the new files. Unknown entities, invalid budgets, uncorrelated queries, invalid thresholds and weakened recovery safeguards fail validation. Omitting a job from the explicit retry allowlist means it is not safe to retry, not that the parser should guess its safety.

## Generation and runtime

From the repository root, after changing any source or generator:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
```

The default command resolves `models/` and `config/` under `--project-dir`. Custom paths use `--pipeline`, `--goal`, `--policy` and `--bindings`; all four source paths/hashes are recorded in generation manifest schema 2.

The saved **workflow remains schema 2** with the same resolved contract values. The generator reloads saved 03 as its sole project-specific input to agent generation; the generic AgentSpeak policy and Java decision/execution boundary are unchanged. YAML ordering/header changes are serialization/provenance differences, not new policy.

Runtime validates four-source consistency and never regenerates. BDI campaign snapshots include `01_pipeline.input.yaml`, `02_goal.input.yaml`, `controller_policy.input.yaml` and `runtime_bindings.input.yaml`, plus the resolved contract/agent and generation manifest. Native preparation preserves `pipeline.input.yaml`, `goal.input.yaml`, `policy.input.yaml` and `bindings.input.yaml`, plus its resolved contract and manifest.

BDI/native pairing keys now include the four normalized input hashes. The native implementation uses the same newline-normalized digest as BDI, avoiding Windows/Linux line-ending mismatches. Unsupported conventional topology/policy configurations remain rejected.

The reporting example has its own explicit `examples/config/` files; no payment policy is implicitly loaded into it. Supported failure-goal examples use the payment policy when explicitly generated with that configuration. Templates now include both models and both advanced configuration files; their retry allowlist intentionally starts empty for engineer review.

## Preservation and verification

Pre-migration masters and generated artifacts are retained in [the archive](archive/model-inputs-before-four-source/README.md). Historical campaign evidence was not changed. The payment agent SHA-256 remains `13053a85e5c7746429c720ca13fc9aa95c77af7acb1ab43fcf9c9b6a10b97a43`.

- Migration tests compare both payment and reporting resolved contracts with archived originals and compare the complete payment agent body (normalizing Git checkout line endings). The current generated file also matches the archived original byte-for-byte.
- Failure tests cover missing/stale profiles, conflicting fields, duplicate YAML keys, invalid references/thresholds, retry safety and recovery invariants; runtime snapshot tests verify campaign reuse without regeneration.
- Native preparation tests verify four-source snapshots and the common pairing key without contacting GitHub.
- Passed: 65 Python tests, 40 Java tests (unchanged task up-to-date), 14 traffic tests, 35 actual Jason simulations and eight paired simulations; four workflows passed Actionlint and 40 documentation PowerShell blocks passed syntax checks. See the [verification record](experiments/four-source-migration-2026-09-22/README.md).

## Next: manual live pilots, not automatic deployment

The persistent project artifacts have already been regenerated for this migration; no extra generation is needed unless you edit a source again. This development task does not publish workflows, deploy the app or freeze a release tag.

1. Publish the complete migrated control revision through your normal review process, then select the same newly published worker revision for both approaches; do not move existing v1/v2 tags.
2. Follow [conventional setup steps 1-4](CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md) and the BDI manual to start Docker/runner, load credentials and restore both environments to verified v1.
3. Pilot `healthy`, `transient-test-failure` and `production-persistent` for **both** mechanisms using the same v2, known-good receipt and seed; use [BDI C6](BDI_MANUAL_EXECUTION_GUIDE.md#c6-matched-comparison-all-11-scenarios) and [conventional step 5](CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md#5-choose-one-scenario-and-launch-the-conventional-pipeline).
4. Reset v1 between every trial, inspect actual fault exposure and all four source snapshots, compare `protocol_key`, and distinguish v2 delivery from verified v1 restoration.
5. Freeze the experiment revision only after these live pilots pass; offline simulations do not establish live GitHub/Docker success.
