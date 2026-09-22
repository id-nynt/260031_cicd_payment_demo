# Documentation reading guide

Start with the execution guidelines to run the experiments. File numbers indicate reading order within each folder; the two execution manuals are alternative routes.

**Already completed the old setup?** Start at [Refresh the version pair, step 1](execution/guidelines/06_REFRESH_VERSION_PAIR.md#1-review-and-publish-the-new-v1-source) for the app's new visible version label. Create fresh v1/v2 source tags and a new live v1 receipt, then resume the BDI/conventional trial steps. Existing tools, credentials and runner registration can be reused.

| Folder | Read it for |
|---|---|
| [Execution guidelines](execution/guidelines/00_README.md) | Setup, paired experiment procedure, BDI/conventional execution and result inspection |
| [Resources and plans](resources-and-plans/00_README.md) | Current study plan, one generation/runtime reference and reusable version-control workflow |
| [Archives](archives/00_README.md) | Superseded documentation, legacy snapshots, reviews and historical experiment evidence |

For a first paired experiment, read guidelines **01 → 02**, follow **03** for BDI or **04** for conventional, then use **05** to inspect the results. The conventional manual includes its own setup, so conventional-only readers can start at **04**.

Commands in the guides still run from the repository root unless explicitly stated otherwise. New experiment results remain in root `experiments/results/`; the records under `docs/archives/` are historical.

Only reading documents have been numbered. Raw evidence, manifests and executable/model snapshots retain their filenames and contents so recorded evidence remains intact. Historical logs may mention their original paths.

Each active guide has one purpose: 01 checks prerequisites, 02 defines the comparative protocol, 03/04 provide mechanism-specific commands, and 05 defines evidence/metrics. The resource plan links to these procedures rather than repeating them. Superseded material and the reasons for archiving it are listed in the [content-review record](archives/07_superseded-developer-guides/00_README.md).
