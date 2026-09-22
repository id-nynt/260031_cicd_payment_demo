# Version control workflow

Use a review branch for source, configuration and documentation changes. Keep immutable application tags separate from the control revision used to run the experiments. The earlier guide's 305-file count and one-time staging list describe a completed working-tree state; they are [archived](../archives/07_superseded-developer-guides/07_ONE_TIME_VERSION_CONTROL_PLAN.md), not instructions to repeat.

## 1. Decide what belongs in the commit

| Versioned inputs and reviewed records | Ignored local products |
|---|---|
| App source/tests, Docker/Compose files, dependency lockfile | Dependencies, build output and caches |
| Controller/helper code, workflow sources and installed copies | Local environment values, virtual environments and scratch logs |
| BDI models/config plus matching generated contract, agent and manifest | `bdi-cicd-framework/runs/` |
| Conventional config and matching snapshots | `experiments/results/`, `experiments/reports/` |
| Shared scenarios, profiles, metrics and tests | Runner scratch directories `evidence/` and `downloaded/` |
| Maintained docs and deliberately reviewed historical evidence | Temporary directories and controller pending-state copies |

The root `.gitignore` and BDI's nested `.gitignore` define the rules. Ignoring a path neither backs it up nor untracks an already committed file. Do not ignore all JSON/YAML/ZIP/AgentSpeak files: these include runtime inputs, fixtures and reviewed evidence. Generated BDI contract/agent files are required by this project's validation workflow and must be committed consistently with their sources.

## 2. Review and stage deliberately

From the repository root:

```powershell
git status --short
git branch --show-current
git switch -c chore/describe-this-change
git diff --stat
```

Choose an unused branch name. Stage the files for the intended change using Source Control or explicit `git add` paths. For a documentation reorganization, stage both old and new paths together; `git add -A -- docs` does that, but first inspect all outstanding changes in that directory.

```powershell
git diff --cached --name-status -M
git diff --cached --stat
git diff --cached --check
git diff --cached
```

Git detects renames from staged content. Heavily edited files may appear as delete/add. Do not discard unrelated user changes or force-add ignored experiment results just to reduce the change count. A commit contains staged changes; a push sends commits, not the remaining working tree.

## 3. Validate the affected inputs

- Conventional workflow edits: run `py -3 ci-cd-conventional/sync_workflows.py`, review both source and installed YAML, then run it with `--check`.
- Paired policy edits: regenerate BDI explicitly, update conventional configuration/snapshots after review, and run `py -3 ci-cd-conventional/configuration.py --check-bdi-parity`.
- BDI configuration edits: run `py -3 bdi-cicd-framework/run_controller.py --validate-only` after generation.
- Code edits: run the relevant tests; `.github/workflows/validate-controller.yml` lists repository-wide validation.
- Documentation moves: check links and any test fixture paths that refer to moved material.

Stop on failures. If generation or synchronization changes a file, review and stage it before committing. Keep related changes together so a checkout of the commit remains usable.

## 4. Commit, review and publish

```powershell
git commit -m "Describe the concrete change"
git status --short
git push -u origin HEAD
```

Review the branch in a pull request and run CI before merging. For a new experiment control revision, follow the execution manual's workflow-registration and immutable-tag steps after review. Do not move existing v1/v2 or worker tags. `release_sha` selects application code independently of the control tag.

Back up full ignored result bundles separately. Publish selected research evidence only after reviewing its contents, with provenance and links to the corresponding control/app revisions. Use `git check-ignore -v PATH` to diagnose why a file is excluded.

[Resources index](00_README.md)
