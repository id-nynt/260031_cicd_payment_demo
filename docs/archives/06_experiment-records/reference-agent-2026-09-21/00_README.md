# Reference-style agent and failure-goal validation

The generic AgentSpeak policy follows the supplied reference structure: `!master_goal` ? `!need_achieve` ? `!run_pipeline` ? `!run_entity` ? `phase_result`, with named maintenance, avoidance, recovery and goal-assessment plans.

The compiler now accepts success and failure achievement goals. Agent plans accept an exact, correlated requested failure without retrying it or treating it as candidate delivery. Java result reporting receives the desired status and negative-goal campaigns produce no verified release receipts. Dependencies, retry safety, health verification for successful deployment, uncertain-execution reconciliation and normal verified recovery remain enforced.

Validation commands (all local, no GitHub dispatch):

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
bdi-cicd-framework/bdi/gradlew.bat -p bdi-cicd-framework/bdi test --console=plain
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/failure-goal-validation-3
```

The scenario runner executes actual Jason with simulated execution and telemetry adapters. It checks entity order, retries, completion, recovery, one terminal result, master-goal messages and lifecycle beliefs. Negative-goal cases additionally check receipt exclusion. Full local journals and logs remain in the output directories; compact results and the persistent generation manifest are retained here. Scenario release SHAs identify the pre-commit checkout; generator hashes identify the tested policy.

No deployment, push, merge, tag movement or history rewrite was performed. The real worker mapping was inspected and existing HTTP/telemetry adapter tests were run; live credentials, runner availability and remote dispatch still require the manual experiment. See the [walkthrough](../../../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#optional-experiment-require-staging-to-fail).

Results: **40 Python tests, 26 Java tests, and 35 Jason scenarios passed**. `scenario-summary.json` contains the 32-case matrix; `edge-summary.json` contains the three follow-up cases, added after the main matrix started, with the same policy/environment revision:

```powershell
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/failure-goal-edge-validation --case unreachable_goals --case negative_execution_uncertain --case negative_retry_unmet
```

The follow-up cases confirm that contradictory dependency goals stop unmet, unresolved execution stays unknown, and a transient failure followed by success does not satisfy an exact failure goal. The initial fixture run exposed missing telemetry thresholds and an unregistered simulated scenario; both were corrected before the passing runs. Persistent artifact consistency and `git diff --check` also passed.
