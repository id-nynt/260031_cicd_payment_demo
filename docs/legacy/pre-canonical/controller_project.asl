// Generated from 03_workflow_model.yaml; do not edit.

entity(build).
entity(test).
entity(security).
entity(staging).
entity(production).
entity(rollback).
recovery_entity(rollback).

depends(build, []).
depends(test, [build]).
depends(security, [test]).
depends(staging, [security]).
depends(production, [staging]).

recovery(production, rollback).
recover_on(production, failure, rollback).
recover_on(production, telemetry_block, rollback).
recover_on(production, telemetry_unknown, rollback).
recover_on(production, maintenance_violation, rollback).
observe_after(rollback).
final_phase(production).
observe_before(production, staging).

required(build).
required(test).
required(security).
required(staging).
required(production).

achievement(production, success).
achievement(staging, success).
max_duration(production, 100000).
require_healthy(production).
avoid_missing(production, test).
avoid_missing(production, staging).

duration_unit(milliseconds).
max_retries(1).

// Controller-derived attempt counters.
attempt_count(build, 0).
attempt_count(test, 0).
attempt_count(security, 0).
attempt_count(staging, 0).
attempt_count(production, 0).
attempt_count(rollback, 0).
