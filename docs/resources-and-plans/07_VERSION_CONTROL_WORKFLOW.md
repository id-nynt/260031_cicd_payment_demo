# Version control for the CI/CD experiment

Do not push everything blindly. At the time of this review, Git reported 305 working-tree entries, including 262 under `docs/`. Many are the old and new paths of the same documentation/evidence files. Staging both sides allows Git to report renames; ignore rules should not conceal those moves.

## 1. What belongs in Git

| Commit after review | Keep local; back up evidence separately |
|---|---|
| App source, tests, Docker/Compose and dependency lockfile | `node_modules/`, root `dist/`, coverage, Python/Gradle caches |
| Both approaches' code, tests, scenario catalog and shared metrics | New BDI campaigns in `bdi-cicd-framework/runs/` |
| Conventional config, snapshots, workflow sources AND installed `.github/workflows/` copies | New paired trials in `experiments/results/` and analysis in `experiments/reports/` |
| BDI generated contract, generation manifest and generated agent, kept consistent with their sources | Local `.env*` values, virtual environments, scratch/log files |
| Reorganized docs and already-reviewed historical evidence under `docs/archives/` | Runner scratch directories `evidence/` and `downloaded/` |

The generated BDI contract and agent are required checked-in inputs for the current runtime; do not ignore all generated files. JSON, YAML, XML, ZIP and AgentSpeak files can be legitimate archived evidence or test fixtures. Do not ignore them by extension.

`.gitignore` does not untrack files already committed. No `git rm --cached` or deletion is needed for the current reorganization. Ignoring new results does not delete them or provide a backup. Deliberately curate and inspect any new evidence you later publish in `docs/archives/`.

## 2. Create a review branch

Run from the repository root. The current checkout was on `experiment/manual-20260921-055936-v2`; use a new branch for these control/documentation changes without moving application tags:

```powershell
git status --short
git switch -c chore/separate-cicd-experiments-docs
```

If that branch already exists, choose a fresh name. Switching with `-c` carries the current uncommitted changes to the new branch. Do not reset, clean or discard them to reduce the Source Control count.

## 3. Commit the ignore policy first

```powershell
git add -- .gitignore
git diff --cached -- .gitignore
git diff --cached --name-status
# Commit only after checking that no unrelated files were already staged.
git commit -m "Define ignore rules for CI/CD experiment artifacts"
```

## 4. Stage the coupled implementation and documentation changes

The new manuals link to the new conventional implementation, and one parser test loads a relocated archived fixture. Keep those changes together for a coherent checkout. Use this explicit path list instead of `git add .`:

```powershell
git add -A -- docs ci-cd-conventional experiments
git add -A -- .github/workflows/ci-cd.yml .github/workflows/conventional-health.yml .github/workflows/validate-controller.yml .github/workflows/README-legacy-ci-cd.md
git add -A -- README.md bdi-cicd-framework/README.md scripts/traffic-scenarios/README.md
git add -A -- bdi-cicd-framework/experiment_metrics.py bdi-cicd-framework/experiment_protocol.py bdi-cicd-framework/run_experiment.py
git add -A -- bdi-cicd-framework/parser/test_native_workflow.py bdi-cicd-framework/parser/test_four_sources.py
git add -A -- scripts/native-experiment.py scripts/experiment-scenarios.json
git diff --cached --stat
git diff --cached --name-status -M
git diff --cached --check
```

`-A -- docs` stages old deletions and their new paths together. `R...` entries indicate detected renames; heavily edited documents may still appear as delete/add. Review both. The explicit deleted native test and scenario catalog have replacements in `ci-cd-conventional/tests/` and `experiments/scenarios.json`.

Review the staged content in Source Control or `git diff --cached`. In particular, `docs/resources-and-plans/06_WORKING_NOTES.md` preserves earlier user edits as well as the move; it is not necessarily a pure rename.

Leave the following earlier changes out until you decide they are intentional:

- Top-level `archives/01_pipeline.yaml`, `archives/02_goal.yaml`, `archives/03_workflow_model.yaml`.
- Deleted `bdi-cicd-framework/bdi/harness/ProjectGateEnvironment.java` and `ProjectGateMain.java`.
- Deleted `bdi-cicd-framework/models/CI_CD_ENTITIES.md`.

These were already present before the separation work. They are neither newly generated rubbish nor changes that `.gitignore` should hide. Review them separately; do not discard them automatically.

## 5. Validate, commit, then push the branch

```powershell
py -3 ci-cd-conventional/sync_workflows.py --check
py -3 ci-cd-conventional/configuration.py --check-bdi-parity
py -3 bdi-cicd-framework/run_controller.py --validate-only
py -3 -m unittest discover -s ci-cd-conventional/tests -v
py -3 -m unittest discover -s experiments/tests -v
py -3 -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py' -v
```

Stop and resolve any failed check before committing. If a check modifies a file you intend to commit, review and stage that specific file again.

```powershell
git diff --cached --check
git diff --cached --name-status -M
git commit -m "Separate CI/CD experiments and organize execution documentation"
git status --short
git push -u origin chore/separate-cicd-experiments-docs
```

Open a pull request, review the changes and let GitHub validation run before merging. Pushing sends commits, not unstaged working-tree files, so deliberately excluded changes remain local.

After merging/registering the workflows on the default branch, create a new immutable control tag at the reviewed commit as described in the execution manuals. Keep existing v1/v2 application tags unchanged. The control revision selects the orchestration code; `release_sha` still selects the application version for each trial.

## 6. Before future commits

Use `git status --short`, inspect the staged diff, and commit source/config/docs changes separately from deliberately curated research evidence. Use `git check-ignore -v PATH` to find the matching rule when a file is missing from Source Control. Never use `git add -f` merely to make ignored local results appear without reviewing what they contain.

[Resources and plans](00_README.md) · [Execution guidelines](../execution/guidelines/00_README.md)
