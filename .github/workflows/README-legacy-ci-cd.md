# Legacy CI/CD workflow disabled

The former build → test → staging → BDI gate → production workflow was
removed from the active workflow directory. The BDI controller now dispatches
one selected entity through `entity-execution.yml`.

See `docs/BDI_LIVE_MANUAL_DEMO.md` for startup and observation instructions.
