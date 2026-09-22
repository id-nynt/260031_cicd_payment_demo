# Research experiment plan

**RQ:** Does BDI-based execution improve the reliability and resilience of CI/CD pipelines compared with conventional CI/CD execution?

The study compares the same payment application and execution worker under two orchestrators: Jason BDI and a native GitHub Actions dependency graph. The conventional baseline retains bounded retries, health checks and rollback. A BDI advantage must be measured; equal outcomes are a valid result.

## 1. Freeze the experiment inputs

Select one reviewed control revision, immutable v1/v2 application SHAs, a verified v1 receipt, configuration, traffic profiles and seed. Run configuration parity checks before collecting paired trials. Source rebuilds are used; this is not immutable-image promotion.

The app version label lives in `src/release.ts` and is compiled from each selected application commit. After updating the app, use the [version-pair refresh procedure](../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#a4-create-or-refresh-the-version-pair) to freeze a new v1/v2 pair and establish a fresh receipt. Historical tags do not acquire the new heading automatically.

The [comparative protocol](../execution/guidelines/02_COMPARATIVE_EXECUTION_GUIDE.md) is the authoritative document for the 11 scenarios, implemented failure scope, shared policy and timing limits. Do not maintain another scenario table here. `experiments/scenarios.json` is the executable catalog.

## 2. Run pilots before the repeated dataset

Pilot healthy delivery, transient test failure, deployment timeout and persistent production failure for both mechanisms. Confirm actual fault exposure, bounded retry/recheck behavior and restoration evidence. Investigate unexpected results without silently dropping them or changing safeguards for one approach only.

Offline tests verify implementation contracts. Historical simulation reports and the separation verification record do not establish that the newly selected published revision works on the current runner. Preserve a live pilot record for that revision.

## 3. Predeclare and execute the study

Before the measured series, record the repetition count, mechanism order, seed schedule, inclusion/exclusion rules, runtime boundaries and treatment of incomplete runs. Alternate mechanism order across repetitions. Run one trial at a time and restore both environments to verified v1 between every trial.

Use [BDI manual C6](../execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md#c6-matched-comparison-all-11-scenarios) and the [conventional manual](../execution/guidelines/04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md). Manual fault injection and negative-goal demonstrations are useful for debugging, but are separate experiments unless explicitly incorporated into the study design.

## 4. Review evidence and compare

The [results guide](../execution/guidelines/05_EXPERIMENT_RESULTS_GUIDE.md) owns evidence locations, metric definitions, extraction and reporting commands. Keep delivery rate, v1 restoration rate, safe stopping, retry counts, recovery time and interventions distinct. Retain unsuccessful and incomplete trials with reasons.

Match planned inputs using `protocol_key`, then check actual fault exposure, reset identity, database state, queue/approval waits and repetition notes. A matching key alone does not establish equal conditions. Record software/control versions and infrastructure used with the final dataset.

## 5. Interpret within the implemented scope

Controlled job exits are not genuine compiler/test defects. Stopping the payment container is not an outage of a deployment API. Stopping staging PostgreSQL is not host loss. The timeout fault occurs before deployment side effects. Future extensions can test broader failures, adaptive policies or interrupted dispatch, but they need explicit implementations and matched baselines.

Do not conclude that BDI improves reliability solely because a trace contains agent decisions. Report the observed rates and timing, their uncertainty and exclusions; distinguish recovery of service from successful delivery of the candidate.

[Resources index](00_README.md) · [Original historical plan](../archives/07_superseded-developer-guides/01_ORIGINAL_EXPERIMENT_PLAN.md)
