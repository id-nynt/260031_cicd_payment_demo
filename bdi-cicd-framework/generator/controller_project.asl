// Generated from 03_workflow_model.yaml; do not edit.

entity(build).
entity(test).
entity(security).
entity(staging).
entity(production).

depends(build, []).
depends(test, []).
depends(security, [build, test]).
depends(staging, [build, test, security]).
depends(production, [staging]).

final_phase(production).
observe_before(production, staging).

required(build).
required(test).
required(security).
required(staging).
required(production).

achievement(production, success).
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
