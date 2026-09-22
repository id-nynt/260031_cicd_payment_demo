# Four-stage agent refactor verification ? 2026-09-22

This is offline implementation evidence, not a live comparison showing BDI superiority.

## Change and preserved reference

The active generic policy now names post-observations, pre-observations, job execution and goal assessment explicitly. Matching status/duration/telemetry percepts still drive progress. The internal unsuccessful-attempt marker is `execution_failed`; source goal values and Java statuses are unchanged. `BDI_STAGE=1/2/3/4` lines are saved in the normal console log.

The four source inputs, saved workflow contract, `master_goal`, Java environment, application, shared workers and conventional policy are unchanged. The generated agent and generation manifest were regenerated only after the behavioural comparisons passed.

The original implementation is retained in [the generated-agent fixture](../bdi-cicd-framework/bdi/fixtures/controller_agent_pre_sequence.asl) and [the generic-policy fixture](../bdi-cicd-framework/bdi/fixtures/controller_generic_pre_sequence.asl). They are exact pre-refactor copies and are not used by the active generator. The pre-refactor committed implementation is `9950f0a9978a22a685fac9ae941ee56258d5c9f5`.

## Validation results

| Check | Result |
|---|---|
| Original agent, real Jason with simulated adapters | 38 scenarios passed |
| Refactored agent against the original results and journals | 38 comparisons passed |
| Compiler, artifact, input and console regression tests | 58 passed, zero failures/errors |
| Persistent artifact validation | Passed |
| Conventional configuration parity | Passed |
| Conventional workflow copies | Passed |
| Edited documentation links and Python syntax | Passed |

Comparisons check execution order, final outcome, recovery classification, accepted telemetry, achieved/unmet goals and the ordered decision trace. The matrix additionally checks health acceptance before production promotion, deployment identity correlation, a single terminal result, distinct execution IDs, bounded repair, fresh observations after repair, no restart for a persistently unhealthy running app, and visible stage order. The separate reporting project and negative-goal configurations also pass.

Representative outcomes preserved by both agent versions:

| Situation | Result |
|---|---|
| Healthy candidate or temporary unhealthy state that clears | Candidate achieved |
| Matching stopped candidate, successful restart and fresh verification | Candidate achieved, no rollback |
| Failed candidate restart | Candidate unmet, verified v1 restored |
| Uncertain restart/execution | Unknown/unresolved; no overlapping rollback |
| Deterministic test failure | Stop without retrying to manufacture success |
| Retryable failure | Bounded retry; stop or recover when exhausted/inapplicable |
| Persistent production degradation | Candidate unmet, verified v1 restored |
| Failed/unhealthy/unverified rollback | Failed or unverified recovery, never candidate achievement |

## Evidence and reproduction

Local evidence is Git-ignored; back it up separately:

- `experiments/results/verification/sequence-reference-validated/`: complete original matrix, per-case snapshots, journals, results and console logs.
- `experiments/results/verification/sequence-refactored/`: first four completed comparisons. Its later interrupted case is not counted.
- `experiments/results/verification/sequence-refactored-remaining/`: remaining 34 completed comparisons.
- `experiments/results/verification/sequence-comparison.json`: combined 38-case result index with each evidence directory.
- `experiments/results/verification/sequence-parser-tests.log`: final 58-test report.

An initial attempt lacked permission to use the Gradle cache. An intermediate comparison hit the repository controller lock because an older artifact-test mock still targeted `subprocess.run` after the launcher moved to `Popen`. The mock now intercepts the console launcher; controller comparisons were resumed sequentially. Only completed comparisons listed above count. Temporary stale-manifest failures during staging were resolved through normal regeneration; the final consistency checks passed.

To rerun the current agent's full offline matrix, use a new output directory:

```powershell
$verificationDir = 'experiments/results/verification/sequence-' + (Get-Date -Format yyyyMMdd-HHmmss)
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output $verificationDir
```

When the original evidence above is available, append `--compare experiments/results/verification/sequence-reference-validated/summary.json` to check its outcomes and decision traces. `--case` can select individual cases. Run controller matrices sequentially: the normal campaign lock remains enforced.

## Research interpretation

The refactor preserves runtime adaptation: reobserve changing health, diagnose the current deployment, select a bounded applicable restart, verify fresh correlated observations, then resume candidate delivery or select verified rollback/safe stopping. Both mechanisms retain equivalent capabilities and budgets. These offline checks establish preservation of behaviour for the tested scenarios; live paired experiments are still needed to measure reliability, resilience and overhead. Synthetic timings are not live recovery-time results.

No live deployment, GitHub dispatch, workflow publication or control tag was created. Returning users keep their app SHAs and follow [BDI manual A4.4](../docs/execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#a44-update-only-the-control-revision-retaining-an-existing-app-pair) when publishing the reviewed control revision, then B1-B3 and a healthy pilot.


## Experiment-support follow-up

Support scripts now share the per-environment traffic plan, retain client console logs, preserve both native traffic summaries, and validate profile/seed/deployment/release identity at each reached gate. Early build/test failures do not require unreached deployment traffic. Stopped-candidate production uses the existing repair probes; staging traffic remains required. The launcher records its status separately from the deployment outcome. The control-revision preflight covers the active agent, worker, shared scripts and configuration instead of checking only a small file subset.

Validation: **30 experiment/evaluation tests, 15 conventional tests and 16 loopback traffic tests passed**. The new native finalizer test verifies both environment summaries survive collection and yield valid metrics. **75 guideline PowerShell blocks parsed** without executing their commands; local guideline links, Python syntax, generated-agent consistency and conventional parity/workflow-copy checks passed. These checks required normal temporary-directory/loopback access and full PowerShell parser access outside constrained language mode. No live dispatch or deployed-app traffic occurred.

The agent policy did not need another change: the prior 38 behavioural comparisons remain applicable. The operational update is documented in [guides 03-06](../docs/execution/guidelines/00_README.md). Publish the reviewed control revision before new paired trials; retain the current app SHAs.
