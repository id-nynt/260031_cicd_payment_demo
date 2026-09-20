# Selected-entity execution

`entity-execution.yml` is the only deployment worker; Jason selects every entity, including rollback. `validate-controller.yml` runs checks and simulated scenarios without deployment. The former gate chain and manual rollback bypass are inactive; historical files are in `docs/legacy/pre-canonical`.

Start with [the controller guide](../../bdi-cicd-framework/README.md).
