# Native conventional baseline: offline validation

Validated 2026-09-21. See `validation.json` for counts and source hashes. No workflow was dispatched and no app was deployed.

- Actionlint validated all three execution workflows, including local reusable-workflow interfaces. The project config recognizes the existing `payment-deploy` runner label. Shellcheck/pyflakes were not run by actionlint.
- Python tests exercise the shared 11-case catalog, execution-only worker contract, retry restrictions, telemetry deadlines/staleness, pairing identity, receipt validation and native result extraction (failed first attempt and verified rollback).
- Java tests cover existing execution adapters, reconciliation and policies. Traffic tests use local mock HTTP servers, including per-entity observation completion.
- PowerShell blocks in both manuals and the comparison guide were parsed, not executed.
- The saved project contract/agent remain consistent. No generation input or agent policy changed.

Unverified live behavior: GitHub reusable-workflow status propagation, hosted/self-hosted queue timing, real injected container outages/timeouts and native rollback. Publish a new worker revision, then pilot healthy, transient-test and timeout cases before the telemetry/recovery cases. Inspect raw step conclusions/status outputs and fault exposure; offline tests are not a live comparative result.
