# Separation verification — 2026-09-22

These are offline implementation checks, not experimental observations supporting the RQ.

| Check | Result |
|---|---|
| `py -3 -m unittest discover -s ci-cd-conventional/tests -v` | 12 passed |
| `py -3 -m unittest discover -s experiments/tests -v` | 3 passed |
| `py -3 -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py' -v` | 55 passed |
| `py -3 ci-cd-conventional/configuration.py --check-bdi-parity` | Passed |
| `py -3 ci-cd-conventional/sync_workflows.py --check` | Passed |
| `py -3 bdi-cicd-framework/run_controller.py --validate-only` | Passed |
| `git diff --check` | Passed |

The conventional tests include a temporary checkout with no BDI framework, matching scenario options, worker fault scoping, retry eligibility, telemetry deadlines/freshness, receipt rejection, failed-attempt preservation, rollback classification, configuration snapshots and protocol pairing. Results tests cover delivery/restoration denominators, invalid evidence exclusion and interrupted-run collection.

Windows sandbox permissions prevented Python temporary-directory tests initially; the same offline tests passed outside that sandbox. No production settings were changed to accommodate the tests.

The root app, v1/v2 commits, generated agent, BDI execution policy and shared execution worker were not changed by this separation. Existing unrelated workspace changes were left intact.

No workflow was published, no new control tag was created, and no live deployment was dispatched. No new live experimental outcomes are claimed. Before the full repeated dataset, publish the complete revision and run paired healthy, transient-test-failure, deployment-timeout and persistent-production pilots, with a verified v1 reset between every run. Inspect raw fault exposure and GitHub failure propagation as described in the manuals. YAML is parsed and its contracts tested locally; GitHub acceptance and runner behavior remain live checkpoints.
