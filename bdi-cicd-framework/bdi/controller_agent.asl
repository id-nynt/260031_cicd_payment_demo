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

// Generic goal-directed CI/CD controller. Project facts are generated above.

workflow_active.

holds([]).
holds([Head | Tail]) :- phase_result(Head, success) & holds(Tail).

achievement_unsatisfied(Entity, Desired) :-
    achievement(Entity, Desired) & not phase_result(Entity, Desired).
all_achievements_satisfied :- not achievement_unsatisfied(_, _).

avoidance_violation(Entity) :-
    avoid_missing(Entity, Required) & not phase_result(Required, success).
safe_to_execute(Entity) :- not avoidance_violation(Entity).

ready_to_execute(Entity) :- not observe_before(Entity, _).
ready_to_execute(Entity) :- observe_before(Entity, Source) & telemetry(Source, allow).

nextentity(Entity) :-
    workflow_active
    & required(Entity)
    & entity(Entity)
    & depends(Entity, Requirements)
    & holds(Requirements)
    & safe_to_execute(Entity)
    & not running(_)
    & not phase_result(Entity, success)
    & not terminal(Entity, _).

retry_allowed(Entity) :-
    max_retries(Max)
    & attempt_count(Entity, Attempts)
    & Attempts <= Max.

!control.

+!control
    : all_achievements_satisfied & workflow_active
    <- -workflow_active;
       +controller_result(achieved);
       .print("BDI_CONTROLLER_RESULT=achieved");
       finish(achieved).

+!control
    : nextentity(Entity)
      & observe_before(Entity, Source)
      & telemetry(Source, block)
    <- -workflow_active;
       +controller_result(stopped);
       .print("BDI_CONTROLLER_RESULT=stopped reason=telemetry_block entity=", Source);
       finish(stopped).

+!control
    : nextentity(Entity)
      & observe_before(Entity, Source)
      & telemetry(Source, unknown)
    <- -workflow_active;
       +controller_result(unknown);
       .print("BDI_CONTROLLER_RESULT=unknown reason=telemetry_unavailable entity=", Source);
       finish(unknown).

+!control
    : nextentity(Entity)
      & observe_before(Entity, Source)
      & not telemetry(Source, allow)
      & not telemetry(Source, block)
      & not telemetry(Source, unknown)
      & not observing(Source)
    <- +observing(Source);
       .print("BDI_DECISION=observe entity=", Source);
       observe_telemetry(Source).

+!control
    : nextentity(Entity) & ready_to_execute(Entity)
    <- !run_entity(Entity).

+!control
    : workflow_active & not running(_) & not nextentity(_)
    <- -workflow_active;
       +controller_result(unknown);
       .print("BDI_CONTROLLER_RESULT=unknown reason=no_safe_progress");
       finish(unknown).

+!run_entity(Entity)
    : attempt_count(Entity, Previous)
    <- Attempt = Previous + 1;
       -attempt_count(Entity, Previous);
       +attempt_count(Entity, Attempt);
       +running(Entity);
       +run_attempt(Entity, Attempt);
       .print("BDI_DECISION=run entity=", Entity, " attempt=", Attempt);
       run_job(Entity, Attempt).

+status(Entity, Attempt, success)
    : running(Entity)
      & run_attempt(Entity, Attempt)
      & not max_duration(Entity, _)
    <- -running(Entity);
       -run_attempt(Entity, Attempt);
       +phase_result(Entity, success);
       .print("BDI_BELIEF=success entity=", Entity, " attempt=", Attempt);
       !control.

+status(Entity, Attempt, success)
    : running(Entity)
      & run_attempt(Entity, Attempt)
      & max_duration(Entity, Maximum)
      & duration(Entity, Attempt, Time)
      & Time <= Maximum
    <- -running(Entity);
       -run_attempt(Entity, Attempt);
       +phase_result(Entity, success);
       .print("BDI_BELIEF=success entity=", Entity, " attempt=", Attempt);
       !control.

+status(Entity, Attempt, success)
    : running(Entity)
      & run_attempt(Entity, Attempt)
      & max_duration(Entity, Maximum)
      & duration(Entity, Attempt, Time)
      & Time > Maximum
    <- -running(Entity);
       -run_attempt(Entity, Attempt);
       +terminal(Entity, maintenance_violation);
       -workflow_active;
       +controller_result(stopped);
       .print("BDI_CONTROLLER_RESULT=stopped reason=duration entity=", Entity);
       finish(stopped).

+status(Entity, Attempt, Result)
    : running(Entity)
      & run_attempt(Entity, Attempt)
      & Result \== success
      & retry_allowed(Entity)
    <- -running(Entity);
       -run_attempt(Entity, Attempt);
       .print("BDI_DECISION=retry entity=", Entity, " after=", Result);
       !control.

+status(Entity, Attempt, Result)
    : running(Entity)
      & run_attempt(Entity, Attempt)
      & Result \== success
      & not retry_allowed(Entity)
    <- -running(Entity);
       -run_attempt(Entity, Attempt);
       +terminal(Entity, Result);
       -workflow_active;
       +controller_result(stopped);
       .print("BDI_CONTROLLER_RESULT=stopped reason=execution_", Result, " entity=", Entity);
       finish(stopped).

+telemetry(Source, Decision)
    : observing(Source)
    <- -observing(Source);
       .print("BDI_BELIEF=telemetry entity=", Source, " decision=", Decision);
       !control.
