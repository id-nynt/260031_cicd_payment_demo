# Repair base review

Worktree: `260031_payment-repair`, branch `repair/bdi-canonical-controller`.
Base: `6eab595256c2fd1ceb3479b39f1211328ef53f28`, eight commits beyond main `dd1b5c8`.
No merge, reset, branch deletion, tag movement or history rewrite was performed.

| Commit | Review and treatment |
|---|---|
| 5e2b757 | Retain restored controller and optional GUI; replace shared generated agent startup with campaign-local MAS. |
| 1bcd861 | Retain source reconciliation and build-output untracking. |
| 6a89ad5 | Retain artifact hygiene; preserve selected historical evidence in docs/experiments. |
| 745d1df | Retain CI/deployment separation; retire the separate manual rollback workflow after the atomic recovery path is verified. |
| 0b8eaff | Preserve source/database compatibility guidance in the new operations guide. |
| f73c406 | Retain single-attempt known-good recovery, production health verification, and Jason observation budgets. Replace recovery-as-job input, Java classification, and stop-only uncertainty handling. |
| a97dd83 | Retain Bash invocation for non-executable Unix wrapper. |
| 6eab595 | Retain CI upload of verification evidence. |

The base was not treated as complete: it bypassed the intermediate model, duplicated
outputs, required legacy project fields, and did not reconcile uncertain dispatches.
The reviewed source changes were inspected together with the commit sequence and
workflow changes; historical reports were not treated as validation of new code.

## Implemented control boundaries

- `run_controller.main` compiles the two canonical inputs, serializes the complete workflow, calls `workflow_model.generate_agent` (which reloads through `load_workflow`), and starts the copied MAS in an exclusive campaign directory.
- `controller_generic.asl` owns `nextentity`, `retry_allowed`, `+reconciled`, numerical telemetry classification, bounded reobservation, `!failed` recovery selection and `!end`. Java transports those selected actions.
- `GitHubEntityExecution.execute` persists intent before POST; `reconcilePending` searches an exact execution identity, polls only its selected job and keeps uncertain state. A subsequent campaign cannot dispatch while this state exists.
- `ProjectTelemetryProvider.measure` returns raw data; `PrometheusTelemetryObserver` rejects nonfinite, missing, ambiguous and stale samples. PromQL includes execution identity. `ControllerEnvironment.publishMeasurement` correlates entity, attempt and observation round in an isolated MAS and journals the execution UUID.
- `known_good_sha` accepts only a trusted successful live receipt for the same project/repository/environment. `sourceFor` prevents recovery from using the candidate. Jason verifies both candidate production and recovery; `finish` records recovered delivery as unmet.
- `ControllerMain.verifyCampaign` checks the generated model/agent/MAS hashes before startup. `--reconcile-only` reads remote state without starting Jason or dispatching work.

## Repository preservation

The original main worktree remains at `dd1b5c8` with its pre-existing ten tracked modifications and untracked Python cache. Repair work is confined to the sibling worktree. The eight reviewed commits remain ancestors of the repair branch. Existing branches and tags were not moved; nothing was deployed or pushed.

Old YAMLs used by regression tests were moved into `parser/fixtures/legacy`. Java controller tests now consume canonical workflow fixtures, which Python checks against the two inputs. Old agents, duplicate outputs, manual rollback workflow and alternate Gradle configuration were archived in `docs/legacy/pre-canonical`. Only disposable tracked Gradle caches/reports were removed; prior scenario evidence is summarized separately under `docs/experiments/historical-main-dd1b5c8` and the full originals remain in Git history.

## Remaining boundaries

The reporting topology has been verified locally through the real Jason runtime with a simulated executor; it is not a deployed second service. No live GitHub dispatch, runner, Docker or database rollback was performed. Deployment still rebuilds a verified source commit rather than restoring an attested immutable image. Receipts are trusted operator files. The lock coordinates worktrees sharing one Git repository, not independent clones or external deployment tools. Existing security auditing remains advisory; npm installation reported five existing dependency vulnerabilities (three moderate, one high, one critical). The payment application's code and dependencies were not changed by this repair.

## Validation

Passed: 29 Python tests, 20 Java tests, 20 actual Jason scenarios using simulated adapters, and all 9 payment tests plus lint/build. Full retained evidence and scope are in [the validation record](experiments/canonical-repair-2026-09-20/README.md). All scenario source hashes match the final runtime implementation.
