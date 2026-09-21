# Campaign-linked traffic profiles

Run from the repository root with Node 22+. Use [manual guide C0](../../docs/BDI_MANUAL_EXECUTION_GUIDE.md#c0-scenario-driven-traffic-recommended-for-repeatable-timing) for complete controller setup. Keep the original `generate-experiment-traffic.mjs` for manual traffic.

```powershell
node scripts/run-traffic-scenario.mjs --campaign bdi-cicd-framework/runs/YOUR-NEW-CAMPAIGN --scenario temporary-errors --seed 42
```

Arm this command before starting the controller with the same campaign path and `--pause-after production --pause-ms 60000`. It waits for the journal, validates the deployed execution UUID, and sends fake payments only after the pause begins. Error profiles require `production.experiment_mode=request_faults` in the controller's fault file. It cannot create deployments, inject latency, or change BDI decisions.

Profiles: `healthy`, `fluctuating`, `burst`, `temporary-errors`, `persistent-errors`, `intermittent-errors`, `idle`, `staging-temporary-errors`, `staging-persistent-errors`. Each is a JSON file in this directory. Choose `--profile <file>` instead of `--scenario` for a custom profile:

```json
{
  "name": "my-temporary-fault",
  "seed": 42,
  "jitter": 0.25,
  "phases": [
    { "seconds": 75, "requests_per_second": 4, "error_fraction": 0.7 },
    { "seconds": 525, "requests_per_second": 4, "error_fraction": 0 }
  ]
}
```

- Durations are seconds from the start of each traffic phase, not controller startup. Total duration may not exceed one hour.
- Rates are sequential request targets (0..10/s), not guaranteed throughput; response time and checks reduce throughput. Only one payment is in flight. At most 10,000 payments are attempted.
- Jitter (0..0.5) varies request spacing. Error fraction (0..1) chooses a fault header with that probability. A fixed seed repeats the sequence of choices; real timing/outcomes are not deterministic.
- A zero-rate phase sends no payments. Readiness and request latency are different signals: no requests does not establish either failed or successful payment behavior.
- This is a fake-payment adapter for this app. Other applications need equivalent request payloads, execution identity and explicit fault support. Use separate load-test infrastructure for capacity testing.

Optional arguments: `--entity staging` (default URL becomes port 3001), `--url <app-origin>`, `--wait-seconds 1800`, `--output <new-evidence-directory>`. The default entity is production/port 3000. Existing output directories are rejected. No GitHub credentials are needed by this client.

Console checkpoints: WAITING, STARTED, PHASE, ACTIVE every five seconds, STOPPED. Ctrl+C saves a final summary. It stops on recovery, campaign completion, changed execution identity, duration/request cap or an error. It refuses expired pauses. An already in-flight request can finish while recovery begins; this client cannot atomically coordinate with deployment.

A unique sibling directory `<campaign>-traffic-*` contains the exact `profile.json`, `traffic.jsonl` (phase events, request outcomes and latency), and `summary.json` (counts, execution identity and stop reason). Preserve it with campaign evidence. A traffic stop is not a BDI success; inspect the controller result. Later phases may never run if the campaign finishes early.

Local regression checks, with mock HTTP responses and no real payments/deployments:

```powershell
node --test scripts/tests/traffic-scenario.test.mjs
```

## Staging failure cases

Use manual guide **C0-S** for ready-to-copy setup and launch commands. Both staging profiles declare `"entity": "staging"`; the CLI defaults to port 3001 and rejects an entity override that disagrees with the profile.

```powershell
node scripts/run-traffic-scenario.mjs --campaign YOUR-NEW-CAMPAIGN --scenario staging-temporary-errors
# For a separate campaign after resetting both environments:
node scripts/run-traffic-scenario.mjs --campaign YOUR-NEXT-CAMPAIGN --scenario staging-persistent-errors
```

Configure `staging.experiment_mode=request_faults` in the fault file and launch BDI with `--pause-after staging --pause-ms 60000`. Temporary errors last 75 seconds, then normal traffic supports recovery and promotion. Persistent errors should block promotion under the default policy, leaving production at v1; there is no staging recovery mapping. Restore staging as well as production before repeating.
