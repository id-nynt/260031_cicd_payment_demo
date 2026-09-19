// Generic goal-directed controller. All entity names and policy facts are generated.
workflow_active.
holds([]).
holds([Head | Tail]) :- phase_result(Head, success) & holds(Tail).
achievement_unsatisfied(E, V) :- achievement(E, V) & not phase_result(E, V).
required_unsatisfied(E) :- required(E) & not phase_result(E, success).
health_unsatisfied(E) :- required(E) & require_healthy(E) & not telemetry(E, allow).
health_unsatisfied(E) :- required(E) & observe_after(E) & not telemetry(E, allow).
all_goals_satisfied :- not achievement_unsatisfied(_, _) & not required_unsatisfied(_) & not health_unsatisfied(_).
avoidance_violation(E) :- avoid_missing(E, R) & not phase_result(R, success).
safe_to_execute(E) :- not avoidance_violation(E).
verify_after(E) :- require_healthy(E).
verify_after(E) :- observe_after(E).
ready_to_execute(E) :- not observe_before(E, _).
ready_to_execute(E) :- observe_before(E, S) & telemetry(S, allow).
nextentity(E) :- workflow_active & required(E) & entity(E) & depends(E, Requirements)
    & holds(Requirements) & safe_to_execute(E) & not running(_)
    & not phase_result(E, success) & not terminal(E, _).
retry_allowed(E) :- max_retries(Max) & attempt_count(E, Attempts) & Attempts <= Max
    & not recovery(E, _) & not recovery_entity(E).

!control.

// Post-deployment verification takes priority over achieving the delivery goal.
+!control : workflow_active & required(E) & phase_result(E, success)
    & verify_after(E) & telemetry(E, block)
 <- !failed(E, telemetry_block, stopped).
+!control : workflow_active & required(E) & phase_result(E, success)
    & verify_after(E) & telemetry(E, unknown)
 <- !failed(E, telemetry_unknown, unknown).
+!control : workflow_active & required(E) & phase_result(E, success)
    & verify_after(E) & not telemetry(E, _) & not observing(E)
 <- +observing(E); .print("BDI_DECISION=observe entity=", E); observe_telemetry(E).
+!control : workflow_active & all_goals_satisfied
 <- !end(achieved, not_needed).
+!control : nextentity(E) & observe_before(E, S) & telemetry(S, block)
 <- !failed(S, telemetry_block, stopped).
+!control : nextentity(E) & observe_before(E, S) & telemetry(S, unknown)
 <- !failed(S, telemetry_unknown, unknown).
+!control : nextentity(E) & observe_before(E, S) & not telemetry(S, _) & not observing(S)
 <- +observing(S); .print("BDI_DECISION=observe entity=", S); observe_telemetry(S).
+!control : nextentity(E) & ready_to_execute(E) & not observing(_)
 <- !run_entity(E).
+!control : workflow_active & not running(_) & not observing(_) & not nextentity(_)
 <- .print("BDI_STOP=no_safe_progress"); !end(unknown, not_needed).

+!run_entity(E) : attempt_count(E, Previous)
 <- Attempt = Previous + 1; -attempt_count(E, Previous); +attempt_count(E, Attempt);
    +running(E); +run_attempt(E, Attempt);
    .print("BDI_DECISION=run entity=", E, " attempt=", Attempt);
    run_job(E, Attempt).

+status(E, A, success) : running(E) & run_attempt(E, A) & not max_duration(E, _)
 <- -running(E); -run_attempt(E, A); !accepted(E).
+status(E, A, success) : running(E) & run_attempt(E, A)
    & max_duration(E, Max) & duration(E, A, Time) & Time <= Max
 <- -running(E); -run_attempt(E, A); !accepted(E).
+status(E, A, success) : running(E) & run_attempt(E, A)
    & max_duration(E, Max) & duration(E, A, Time) & Time > Max
 <- -running(E); -run_attempt(E, A); !failed(E, maintenance_violation, stopped).

+!accepted(E) : recovery_active(_, E)
 <- +phase_result(E, success); +observing(E);
    .print("BDI_DECISION=verify_recovery entity=", E); observe_telemetry(E).
+!accepted(E) : workflow_active
 <- +phase_result(E, success); .print("BDI_BELIEF=success entity=", E); !control.

// Unknown execution may still be running remotely. Never retry or recover over it.
+status(E, A, unknown) : running(E) & run_attempt(E, A)
 <- -running(E); -run_attempt(E, A);
    .print("BDI_STOP=execution_uncertain entity=", E); !end(unknown, unresolved).
+status(E, A, Result) : running(E) & run_attempt(E, A) & Result \== success & Result \== unknown
    & retry_allowed(E)
 <- -running(E); -run_attempt(E, A);
    .print("BDI_DECISION=retry entity=", E, " after=", Result); !control.
+status(E, A, Result) : running(E) & run_attempt(E, A) & Result \== success & Result \== unknown
    & not retry_allowed(E)
 <- -running(E); -run_attempt(E, A); !failed(E, failure, stopped).

// Recovery is conditional, single-attempt, and cannot satisfy the candidate goal.
+!failed(E, Reason, Outcome) : recovery_active(_, E)
 <- .print("BDI_RECOVERY=failed entity=", E, " reason=", Reason); !end(stopped, failed).
+!failed(E, Reason, Outcome) : workflow_active & recover_on(E, Reason, R)
    & known_good_available & safe_to_execute(R) & not recovery_attempted(E)
 <- -workflow_active; +terminal(E, Reason); +recovery_attempted(E); +recovery_active(E, R);
    .print("BDI_DECISION=rollback source=", E, " entity=", R, " reason=", Reason);
    record_recovery(E, R, Reason); !run_entity(R).
+!failed(E, Reason, Outcome) : workflow_active
 <- +terminal(E, Reason); .print("BDI_STOP=", Reason, " entity=", E);
    !end(Outcome, not_attempted).

+telemetry_sample(E, Round, unknown) : observing(E) & observation_limit(Max) & Round < Max
    & observation_interval(Delay)
 <- .print("BDI_DECISION=wait_reconsider entity=", E, " round=", Round);
    .wait(Delay); observe_telemetry(E).
+telemetry_sample(E, Round, unknown) : observing(E) & observation_limit(Max) & Round >= Max
 <- -observing(E); +telemetry(E, unknown); !observed(E, unknown).
+telemetry_sample(E, Round, Decision) : observing(E) & Decision \== unknown
 <- -observing(E); +telemetry(E, Decision); !observed(E, Decision).
+!observed(E, allow) : recovery_active(_, E)
 <- .print("BDI_RECOVERY=restored entity=", E); !end(stopped, restored).
+!observed(E, block) : recovery_active(_, E)
 <- .print("BDI_RECOVERY=unhealthy entity=", E); !end(stopped, failed).
+!observed(E, unknown) : recovery_active(_, E)
 <- .print("BDI_RECOVERY=unverified entity=", E); !end(unknown, unverified).
+!observed(E, Decision) : workflow_active
 <- .print("BDI_BELIEF=telemetry entity=", E, " decision=", Decision); !control.

+!end(Outcome, Recovery)
 <- -workflow_active; +controller_result(Outcome); +recovery_result(Recovery);
    .print("BDI_CONTROLLER_RESULT=", Outcome, " recovery=", Recovery);
    finish(Outcome, Recovery).
