# Pre-canonical historical files

These files are preserved from `6eab595` for comparison. They are not runtime inputs or runnable entry points. The old manual rollback workflow is outside `.github/workflows`, so it cannot bypass receipt verification and Jason recovery selection.

The current launcher generates a campaign-local MAS, workflow model and agent. See [the current guide](../../../bdi-cicd-framework/README.md). Legacy payment YAMLs used by parser/baseline regression tests live in `bdi-cicd-framework/parser/fixtures/legacy`; they are not engineer inputs. Some old Java observer classes remain compiled to preserve regression coverage; there are no Gradle gate or baseline launch tasks.
