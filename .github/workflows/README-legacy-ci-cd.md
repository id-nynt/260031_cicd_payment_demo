# Workflow entry points

- `ci-cd.yml`: conventional workflow_dispatch entry point with exactly six jobs; source in `ci-cd-conventional/workflows/ci-cd.yml`.
- `entity-execution.yml`: BDI-selected mechanical entity or diagnostic/repair operation; no conventional wrapper/report job.
- `validate-controller.yml`: development validation on push/PR.

The old `conventional-entity.yml` and `conventional-health.yml` wrappers were removed. Both current approaches use `scripts/execute-entity.sh`; experiment results are collected with `experiments/collect.py`. Follow guide 07 for a newly published control revision.
