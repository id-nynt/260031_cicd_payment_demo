# Payment execution workflows

- `entity-execution.yml`: shared executor; BDI dispatches one selected entity, or the conventional workflow calls it. Its optional report job only reports confirmed execution status.
- `ci-cd.yml`: manually activated conventional GitHub Actions pipeline with bounded retry, telemetry gates and verified rollback. No Jason process.
- `conventional-entity.yml`: reusable execution/retry steps for that pipeline.
- `validate-controller.yml`: application/controller checks; no deployment.

Start with the [conventional manual](../../docs/CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md) or [BDI manual](../../docs/BDI_MANUAL_EXECUTION_GUIDE.md). Use the same worker revision for paired experiments. The former BDI-gate chain is archived under `docs/archive/pre-policy-refactor/ci-cd-before-native.yml.txt`; it is not the conventional baseline.
