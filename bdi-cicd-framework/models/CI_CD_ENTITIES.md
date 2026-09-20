# Current entity contract

`01_pipeline.yaml` defines logical jobs. The agent owns their dependencies and conditional recovery; GitHub's dispatch workflow executes one explicitly selected entity. Each dispatch has a campaign ID, execution UUID, attempt and immutable source SHA.

| Entity | Worker commands / result | Agent policy |
|---|---|---|
| build | npm install/lint/build, Docker build | First normal entity |
| test | PostgreSQL fixture, migrations, application and parser tests | After build; bounded retry |
| security | Advisory production dependency audit | After test; advisory scan limitations remain |
| staging | Fake-payment Compose deployment, identity/readiness, sample traffic | After security; observe before production |
| production | Candidate source deployment, identity/readiness, sample traffic | Only after staging is healthy; evaluate production health goal |
| rollback | Known-good source deployment in normal mode, fresh identity/traffic | Conditional recovery only; one attempt; verify restored telemetry |

`02_goal.yaml` requires production/staging success, production health and a stated duration budget. `examples/staging_goal.yaml` requires only staging success/health. Rollback is never in normal required work and cannot satisfy the candidate delivery goal.

Statuses and durations come from the selected GitHub run/job. Health comes from `/ready` and run-correlated Prometheus queries configured in `01_pipeline.yaml`; error rate, latency and availability thresholds determine healthy/unhealthy/unknown. The adapter transports evidence; generic AgentSpeak chooses retry/wait/recovery/progression.

`recovery.rollback.from`, `recovery.rollback.on`, and `observe_after` define conditional recovery. `release_source: known_good` selects the receipt-validated baseline SHA. Commands remain in `.github/workflows/entity-execution.yml`; no generated shell steps are executed from pipeline YAML.

Recovery success reports `stopped/restored`; failed recovery reports `stopped/failed`; missing recovery telemetry reports `unknown/unverified`. Ambiguous remote execution triggers bounded read-only reconciliation; unresolved state blocks rollback and redispatch. See [the controller guide](../README.md).
