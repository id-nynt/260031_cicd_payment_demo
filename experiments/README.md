# Shared experiment protocol and evidence

- [BDI manual](../docs/execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md): Jason orchestrates the pipeline.
- [Conventional manual](../docs/execution/guidelines/04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md): GitHub Actions orchestrates the pipeline.
- [Scenario definitions and study limitations](../docs/execution/guidelines/02_COMPARATIVE_EXECUTION_GUIDE.md).
- [Results inspection and comparison](../docs/execution/guidelines/05_EXPERIMENT_RESULTS_GUIDE.md).

`scenarios.json` is the canonical 11-case catalog (`healthy` means normal). Both launch paths use it. Shared traffic implementation/profiles remain in root `scripts/run-traffic-scenario.mjs` and `scripts/traffic-scenarios/`; it reads normalized campaign events from either source. The BDI controller observes locally; the conventional health job observes on the deployment runner. Neither traffic client makes orchestration decisions.

`experiment_protocol.py` defines matching-input hashes. `experiment_metrics.py` extracts the same measurements for either approach. BDI's old module paths forward to these shared modules for compatibility.

New evidence is organized as:

```text
results/bdi/<trial>/                         # result, events, journal, snapshots
results/bdi/<trial>-experiment/              # plan, console, fault settings
results/bdi/<trial>-traffic*/                # requests, phase transitions, summary
results/conventional/<github-run-id>/        # all artifacts, GitHub logs and metadata
reports/<analysis-id>/                      # CSV and grouped JSON
```

Results and reports are ignored by Git to avoid accidentally publishing experiment data. Back up complete directories deliberately. Do not reuse/delete failed trial folders. Historical evidence remains where it was recorded.

Run all 11 cases for both mechanisms with the same candidate/baseline/worker/policy/seed, restore v1 between every run, and alternate execution order across repetitions. Predeclare a repetition count and retain exclusions and interrupted runs. The paired policy may produce equal outcomes; superiority is a research question, not an expected assertion built into the scripts.
