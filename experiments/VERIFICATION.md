# Adaptive candidate repair verification — 2026-09-22

These are offline implementation checks, not experimental observations supporting the RQ.

| Check | Result |
|---|---|
| Conventional Python tests | 14 passed |
| Shared experiment/repair Python tests | 12 passed |
| Existing compiler/artifact regression suite plus configuration extension tests | 58 passed; final source-validation subset (10) passed again after validation refinements |
| New `parser/test_candidate_agent.py` | 4 generated-Jason repair scenarios passed |
| Gradle Java tests | 43 passed |
| Selected existing Jason matrix | 4 passed: negative production goal, temporary production fault, absent rollback baseline, second project |
| `npm run lint` / `npm run test:traffic` | Passed / 14 passed |
| `py -3 ci-cd-conventional/configuration.py --check-bdi-parity` | Passed |
| `py -3 ci-cd-conventional/sync_workflows.py --check` | Passed |
| `py -3 bdi-cicd-framework/run_controller.py --validate-only` | Passed |
| `git diff --check` | Passed |
| Active workflow YAML / single BDI guide PowerShell | Parsed / all 37 code blocks parsed without executing them |
| Edited documentation local links | No broken file links |

The repair tests cover wrong deployment identity, ambiguous containers, unready dependency, a changed container before mutation, post-restart identity mismatch, failed restart, fresh verification and separate repair/rollback metrics. The actual generated Jason tests demonstrate repaired candidate achievement, failed repair with verified restoration, uncertain repair without overlapping rollback, and persistent running-app degradation without restart. Conventional tests retain standalone operation without BDI and require new consecutive observations after repair.

Windows sandbox permissions prevented Python temporary-directory tests initially; the same offline tests passed outside that sandbox. No production settings were changed to accommodate the tests.

The pre-change checkpoint is **`82e07d17c106911c4316768c830994f7e52faa7e`**. It preserves the full codebase before adaptive repair. The four sources, saved-03 generation workflow, `master_goal`, normal execution loop and application functionality remain. Repair extends the source configuration, compiler, generic plans, Java adapters, shared worker and conventional gate. The existing app SHAs need no replacement; the worker/control revision does.

Local test logs are in ignored `experiments/results/verification/`: `parser-tests-final.log`, `four-sources-final.log`, `agent-repair-tests.log`, `java-tests-final.log`, `native-tests-final.log`, and `experiment-tests-final.log`. Retained regression traces are in `adaptive-regression-resumed/`. The earlier `adaptive-regression/` was interrupted when the session closed and remains incomplete; it is not counted as a passed run. Temporary integration-test projects are cleaned by the test suite. These files are implementation verification, not live study outcomes.

No workflow was published, no new control tag was created, and no live deployment was dispatched. Follow [BDI manual A4.4](../docs/execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#a44-update-only-the-control-revision-retaining-an-existing-app-pair), then B1-B3 and C1 healthy. Pilot candidate-stopped, failed repair and persistent degradation with a v1 reset between trials. GitHub workflow acceptance, artifact downloads, runner scheduling, actual Docker restart and measured Prometheus recovery still require live validation. Queue time consumes the repair budget; do not infer experimental reliability or BDI superiority from these offline tests. Both mechanisms have the same recovery capabilities and may achieve equivalent outcomes.
