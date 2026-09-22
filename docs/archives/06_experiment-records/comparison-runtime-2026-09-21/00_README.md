# Comparative runtime validation (local only)

The imperative conventional controller uses the same selected-entity GitHub executor, telemetry reader, lock and pending-state handling as BDI. Its procedural policy supports the payment success-goal contract and rejects unsupported contracts. Both publish common experiment events; the traffic client can follow either mechanism.

`paired-simulation-summary.json` records eight paired runs: healthy, transient retry, retry exhaustion, production failure/recovery, unresolved execution, staging telemetry block, transient production telemetry and persistent production telemetry. Actual Jason and the imperative loop agree on outcomes, recovery, action order/attempts, accepted telemetry and exit status. External execution and measurements were simulated with shortened test budgets; this is not live comparative evidence or a superiority claim.

`validation-summary.json` records final local test totals and relevant source hashes. Full logs and campaign snapshots are retained locally under `bdi-cicd-framework/bdi/build/comparison-preflight-20260921` and `bdi-cicd-framework/runs/comparative-*-tests*.log`. The new trial launcher was also exercised in prepare-only mode against the retained live v1 receipt; it wrote a plan without launching a controller or traffic. Source hashes describe the final files; paired runs' manifests retain their own execution-time source hashes.

Validation commands:

```powershell
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
bdi-cicd-framework/bdi/gradlew.bat -p bdi-cicd-framework/bdi --no-daemon test --console=plain
node --test scripts/tests/traffic-scenario.test.mjs
py -3 -B bdi-cicd-framework/verify_comparison.py --output bdi-cicd-framework/bdi/build/comparison-preflight-20260921
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B bdi-cicd-framework/run_controller.py --mechanism conventional --validate-only
```

Use a fresh output directory to repeat the paired simulation. Documentation command blocks were syntax-checked without executing their deployment commands. No live GitHub dispatch, payments, deployment, push or tag mutation was performed. Existing unrelated local edits/deletions were left untouched. Native GitHub DAG comparison, live infrastructure/timeout injection and repeated research trials remain outside this implementation's verified boundary.
