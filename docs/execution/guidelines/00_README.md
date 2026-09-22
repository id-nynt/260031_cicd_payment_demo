# Execution guidelines

**Limited time: start with [07 Compact five-scenario study](07_COMPACT_FIVE_SCENARIO_EXPERIMENTS.md).** It runs only healthy, test failure, temporary production degradation, persistent production degradation and stopped-candidate repair for both approaches (10 candidate runs by default), with result collection, reset and evaluation.

**For the complete paired study, start with [06 End-to-end paired experiments](06_PAIRED_EXPERIMENTS_END_TO_END.md).** It combines setup, all 13 scenarios, both approaches, reset, evidence collection and evaluation in one sequential procedure. The documents below remain focused references; do not run their procedures in addition to 06.

**Returning after the agent/support-script update:** retain the existing v1/v2 app pair, but publish a new reviewed control tag before new trials. With tools already installed, begin at **06 Step 2**, then Step 3's full control-revision check. For BDI-only work use **03 A4.4**, then B1-B3. Earlier experiment evidence remains separate; do not mix control revisions in one matched study.

**For BDI, use one document: [03 BDI complete manual](03_BDI_MANUAL_EXECUTION_GUIDE.md).** New users start at A; existing users with a saved pair/baseline start at B. Choose one C scenario, finalise in D, reset in E. Baseline and troubleshooting are in F.

1. [Environment checklist](01_ENVIRONMENT_CHECKLIST.md): shared prerequisites for either approach.
2. [Comparative protocol](02_COMPARATIVE_EXECUTION_GUIDE.md): study design, shared cases and limitations.
3. [BDI complete manual](03_BDI_MANUAL_EXECUTION_GUIDE.md): all BDI operational steps, including initial setup and pair creation.
4. [Conventional manual](04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md): independent GitHub Actions execution.
5. [Results inspection](05_EXPERIMENT_RESULTS_GUIDE.md): shared evidence interpretation and comparison reports.
6. [End-to-end paired experiments](06_PAIRED_EXPERIMENTS_END_TO_END.md): one operational document for the entire RQ1 study, with a predeclared schedule and offline paired evaluator.

7. [Compact five-scenario study](07_COMPACT_FIVE_SCENARIO_EXPERIMENTS.md): the requested reduced experiment set, with a separate study pointer.

The former 06 refresh and 07 optional BDI guides are [archived](../../archives/08_consolidated-bdi-guides/00_README.md); their maintained instructions are now inside 03.

[All documentation](../../00_README.md)
