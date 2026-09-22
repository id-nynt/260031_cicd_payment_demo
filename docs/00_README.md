# Documentation reading guide

Start with the execution guidelines to run the experiments. File numbers indicate reading order within each folder; the two execution manuals are alternative routes.

**Complete RQ1 study in one document:** [06 End-to-end paired experiments](execution/guidelines/06_PAIRED_EXPERIMENTS_END_TO_END.md) combines both approaches, all scenarios, preparation/reset, evidence and final evaluation. Start there for a sequential paired study; the earlier guides remain focused references.

**BDI readers need one operational document:** [03 BDI complete manual](execution/guidelines/03_BDI_MANUAL_EXECUTION_GUIDE.md). New users start at A; users with a completed pair/baseline start at B. Pair refresh is included in A4, and baseline setup in F1. The old split guides are archived.

| Folder | Read it for |
|---|---|
| [Execution guidelines](execution/guidelines/00_README.md) | Setup, paired experiment procedure, BDI/conventional execution and result inspection |
| [Resources and plans](resources-and-plans/00_README.md) | Current study plan, one generation/runtime reference and reusable version-control workflow |
| [Archives](archives/00_README.md) | Superseded documentation, legacy snapshots, reviews and historical experiment evidence |

For the full paired experiment, use **06** alone. For background or an individual mechanism, **01 → 02**, **03** (BDI) / **04** (conventional), and **05** (results) remain available. Conventional-only readers can start at **04**.

Commands in the guides still run from the repository root unless explicitly stated otherwise. New experiment results remain in root `experiments/results/`; the records under `docs/archives/` are historical.

Only reading documents have been numbered. Raw evidence, manifests and executable/model snapshots retain their filenames and contents so recorded evidence remains intact. Historical logs may mention their original paths.

Each active guide has one purpose: 01 checks prerequisites, 02 defines the comparative protocol, 03/04 provide mechanism-specific commands, and 05 defines evidence/metrics. The resource plan links to these procedures rather than repeating them. Superseded material and the reasons for archiving it are listed in the [content-review record](archives/07_superseded-developer-guides/00_README.md).
