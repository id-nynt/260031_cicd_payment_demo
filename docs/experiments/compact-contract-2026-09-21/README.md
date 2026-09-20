# Simplified workflow contract validation

Schema 2 exposes E/D/O/R, goals and policy, followed by one bindings section. Repeated jobs, goal blocks and capability action lists are replaced by validated internal derivation. Agent generation reads only the saved contract and generic framework policy. Python runtime settings and Java execution/telemetry readers consume the new schema; old persistent artifacts require explicit regeneration. Historical evidence remains untouched.

The payment agent before and after migration is byte-identical (hash in summary.json). Payment and reporting Java fixtures were regenerated. 43 Python tests, 30 Java tests and eight real Jason scenarios with simulated adapters passed. Mutation tests reject dropped correlation, unknown entities/edges, altered observation domains and weakened recovery verification. The scenario summary covers success/failure goals, health reobservation, retry, verified recovery, uncertainty and the second application.

Commands:

```powershell
py -3 -B bdi-cicd-framework/generate_project.py
py -3 -B bdi-cicd-framework/run_controller.py --validate-only
py -3 -B -m unittest discover -s bdi-cicd-framework/parser -p 'test_*.py'
bdi-cicd-framework/bdi/gradlew.bat -p bdi-cicd-framework/bdi --no-daemon test --console=plain
py -3 -B bdi-cicd-framework/verify_controller_experiment.py --output bdi-cicd-framework/bdi/build/compact-contract-validation --case healthy --case expected_staging_failure --case unmet_staging_failure --case temporary_fault --case retry --case production_unhealthy --case execution_uncertain --case second_project
```

Full local campaign evidence remains in the matrix output directory. No live dispatch, deployment, push, merge, tag movement or history rewrite was performed for this schema migration. Existing worker and application mappings are unchanged.
