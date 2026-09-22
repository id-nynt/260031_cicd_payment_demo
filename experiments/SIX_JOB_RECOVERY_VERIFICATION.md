# Six-job workflow and recovery revision: offline verification

This is implementation validation, not an RQ1 experiment result. No GitHub workflow, live traffic, deployment or reset was launched during this refactor. Existing study evidence was not amended.

## Changes

- Conventional execution has six jobs in one source YAML, installed into `.github/workflows/ci-cd.yml`. Mechanical attempts are shared with BDI through `scripts/execute-entity.sh`; native attempt receipts distinguish deployment outcome from health-gate outcome.
- Health gates are deployment-job steps. Preparation is in build. `collect.py` aggregates conventional results locally from completed workflow metadata and receipts, preserving the previous result-directory contract. Missing evidence fails collection.
- BDI keeps its four configuration sources, generation workflow, master goal and event-driven percept handlers. Ready-but-degraded observations reobserve; unavailable services can diagnose/restart once. Both mechanisms retain existing observation and repair budgets.
- Docker discovery explicitly intersects project/service labels and excludes one-off containers; missing/ambiguous matches remain failures. Deployment identity is verified before any restart. PostgreSQL readiness uses the configured database/user.
- Diagnostic jobs have static names. The obsolete report and conventional wrapper jobs were removed.
- Dispatch intent prevents blind redispatch; recording derives the required ledger schema from saved evidence. Final-reset completion is reported separately from evidence eligibility.

## Checks

- 62 parser/contract/agent tests passed, including real Jason reasoning with simulated adapters for candidate restart, failed restart, uncertain repair, and persistent degradation.
- 19 conventional tests passed, including six-job structure, bounded retry classification, transient reobservation and offline receipt aggregation.
- 33 experiment/evidence tests passed, including container ambiguity, record schema/fault exposure, dispatch ambiguity and final reset requirements.
- Three additional offline Jason scenarios passed: healthy, deterministic test failure and temporary production degradation. Evidence: `experiments/results/verification/six-job-observation-validated/summary.json` (ignored local verification output).
- Generated-artifact consistency, conventional configuration parity and installed workflow synchronization passed.
- Shared shell syntax and guide PowerShell syntax were checked without executing the guide.

The initial failing simulation encoded a stopped candidate as a ready app with request errors. The simulation was corrected to publish not-ready observations, and repair tests passed afterward. The earlier `six-job-recovery-offline` directory is incomplete diagnostic output, not a passing run or a live trial.

## Remaining live verification

Review/commit/publish the new control revision and follow guide 07 to create a new study. Do not mix the old six-trial pilot with changed control logic. Only a live paired run can establish runner/Docker integration and comparative outcomes; unit tests cannot establish BDI superiority.
