# Four-source migration verification - 22 September 2026

All offline checks passed: 65 Python tests, 40 Java tests (unchanged Gradle test task up-to-date), 14 traffic tests, 35 actual Jason simulations and eight paired simulations (16 runs). Actionlint passed all four workflows; 40 PowerShell documentation blocks parsed successfully without execution.

- [Validation and configuration hashes](validation.json) identify the four inputs, generator sources and persistent outputs checked.
- [Jason scenarios](jason-scenarios.json) cover retries, observation budgets, reconciliation, recovery, failure goals and the reporting application.
- [Paired simulations](paired-simulations.json) compare Jason with the procedural Java comparator using simulated execution adapters; all eight pairs agree.

Payment and reporting contracts equal their archived pre-migration contracts. The payment agent is byte-identical. Missing/stale profiles, invalid settings and provenance mismatches are covered by tests.

These results do not represent live native GitHub Actions or Docker deployments, and do not demonstrate BDI superiority. Live paired healthy, transient and rollback pilots remain required before freezing the experiment revision; follow the [migration record](../../07_superseded-developer-guides/04_FOUR_SOURCE_MIGRATION_RECORD.md).

Full local simulation evidence remains under the ignored `bdi-cicd-framework/bdi/build/four-source-jason-20260922/` and `four-source-comparison-20260922/` directories. Historical campaign evidence was preserved.
