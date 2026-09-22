# Environment checklist

Use this to check readiness for either approach. The [BDI manual](03_BDI_MANUAL_EXECUTION_GUIDE.md) and [conventional manual](04_CONVENTIONAL_MANUAL_EXECUTION_GUIDE.md) own their complete setup/reset/launch commands; this page does not maintain another copy of those procedures.

## Shared prerequisites

| Check | Ready when |
|---|---|
| Checkout | You are in the repository root; the local control code corresponds to the published control revision selected for the study |
| Application | Both approaches select the same immutable v1/v2 source SHAs; neither uses local HEAD as an accidental candidate |
| Tools | Git, GitHub CLI, Python with PyYAML, Node 22 and Docker Compose are available where the relevant commands run |
| Deployment runner | The dedicated Linux runner is online with `self-hosted`, `linux`, `payment-deploy` labels and can use Docker |
| Environments | GitHub staging/production environment configuration is ready; any approval waits are recorded |
| Published controls | The workflows exist on the default branch; a reviewed immutable control tag contains the current workflow/helper files |
| Baseline | A live successful v1 receipt exists, or the selected manual's first-baseline procedure will establish it |
| Reset | Both environments have been restored to v1 before each measured trial, with reset evidence retained |
| Exclusive use | No earlier controller, workflow or traffic generator is still operating on these environments |

For BDI also install JDK 21+ and validate the saved generated project. The conventional runtime does not need Java, Jason or BDI generation.

## Network and telemetry

| Environment | App readiness | Prometheus |
|---|---|---|
| Staging | `http://127.0.0.1:3001/ready` | `http://127.0.0.1:9091` |
| Production | `http://127.0.0.1:3000/ready` | `http://127.0.0.1:9090` |
| Optional isolated local rehearsal | `http://127.0.0.1:3002/ready` | `http://127.0.0.1:9092` |

`127.0.0.1` means the machine/network namespace of the reader. BDI observes from the controller; conventional observes from the deployment runner. Check reachability from both locations. Do not assume a remote controller can access a runner's loopback address.

BDI endpoint/query changes belong in `bdi-cicd-framework/config/runtime_bindings.yaml`, followed by explicit generation and validation. Conventional uses its reviewed `ci-cd-conventional/config.json` and snapshots. Verify configuration parity before a paired study. Do not put telemetry addresses into model 01 or edit generated 03 directly.

## Choose the next instruction

- Study design and fault scope: [comparative protocol](02_COMPARATIVE_EXECUTION_GUIDE.md).
- BDI setup, baseline, reset and paired trial: manual **A** and manual 03 A4/F1 when needed, then **A-F** (C1 for paired trials).
- Conventional setup, baseline, reset and trial: conventional manual **1–5**.
- Missing/stale BDI artifacts: [generation and runtime](../../resources-and-plans/02_BDI_GENERATION_AND_RUNTIME.md).
- Interrupted BDI execution: manual **F3**; reconcile before another trial and retain pending evidence.
- Interpreting outcomes: [results inspection](05_EXPERIMENT_RESULTS_GUIDE.md).

Past credential-repair incident commands are archived, not part of normal setup. Authentication and workflow publication are covered by the selected execution manual.
