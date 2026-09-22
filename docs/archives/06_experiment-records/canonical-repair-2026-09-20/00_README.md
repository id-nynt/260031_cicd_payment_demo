# Canonical repair validation ? 2026-09-20

All **29 Python tests**, **20 Java tests**, **20 real-Jason scenarios**, and **9 payment application tests** passed. Application lint and build also passed. No live GitHub dispatch, deployment, or database restoration was performed.

[Summary](summary.json) contains every scenario's actions and outcomes. [Evidence archive](verification-evidence.zip) contains the complete campaign input snapshots, workflow models, generated agents, MAS files, provenance manifests, journals, results, console logs, and Java test XML. All 20 campaign manifests were checked against the final runtime source hashes. The source base records the pre-commit worktree parent; file hashes identify the tested repair implementation.

Scenarios cover healthy delivery, staging-only goals, transient and exhausted retry, blocked/unavailable/delayed telemetry, production failure/unhealthy/unknown telemetry, failed/unhealthy/unverified recovery, duration violation, reconciliation success, reconciliation-confirmed failure before retry, unresolved execution, first baseline without recovery, paused progression, and a second application topology.

HTTP adapter tests cover lost acknowledgement, restart persistence, absent and ambiguous run discovery, polling failures, missing selected jobs, freshness and source-age validation. Artifact integrity and isolated generation are also checked. Payment test coverage is the repository's nine existing tests; a live PostgreSQL/GitHub integration suite was not executed here.

Only this deliberately selected evidence is retained in Git. `bdi/build` remains disposable. Earlier main-branch evidence is separately labeled under `../historical-main-dd1b5c8`.
