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
    & retry_safe(E) & not recovery_entity(E).
retryable_result(transient_failure).
retryable_result(timeout).

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
    -phase_result(E, _); -telemetry(E, _); -healthy_count(E, _); +healthy_count(E, 0);
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

// Reconcile the same remote execution before any retry or recovery can be selected.
+status(E, A, unknown) : running(E) & run_attempt(E, A)
 <- .print("BDI_DECISION=reconcile entity=", E); reconcile_job(E, A, 1).
+reconciled(E, A, Round, unknown) : running(E) & run_attempt(E, A)
    & reconciliation_limit(Max) & Round < Max & reconciliation_interval(Delay)
 <- .wait(Delay); Next = Round + 1; reconcile_job(E, A, Next).
+reconciled(E, A, Round, unknown) : running(E) & run_attempt(E, A)
    & reconciliation_limit(Max) & Round >= Max
 <- -running(E); -run_attempt(E, A);
    .print("BDI_STOP=execution_uncertain entity=", E); !end(unknown, unresolved).
+reconciled(E, A, Round, Result) : running(E) & run_attempt(E, A) & Result \== unknown
 <- +status(E, A, Result).
+status(E, A, Result) : running(E) & run_attempt(E, A) & Result \== success & Result \== unknown
    & retryable_result(Result) & retry_allowed(E) & retry_interval(Delay)
 <- -running(E); -run_attempt(E, A);
    .print("BDI_DECISION=retry entity=", E, " after=", Result); record_decision(E, retry, A); .wait(Delay); !control.
+status(E, A, dispatch_rejected) : running(E) & run_attempt(E, A)
 <- -running(E); -run_attempt(E, A); !failed(E, dispatch_rejected, stopped).
+status(E, A, Result) : running(E) & run_attempt(E, A) & Result \== success & Result \== unknown
    & Result \== dispatch_rejected & (not retryable_result(Result) | not retry_allowed(E))
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

// Measurements are data. These AgentSpeak rules apply engineer-defined constraints.
+telemetry_measurement(E, A, Round, unavailable, _, _, _, _, Time) : observing(E) & attempt_count(E, A)
 <- +telemetry_sample(E, A, Round, unknown, Time).
+telemetry_measurement(E, A, Round, fresh, not_ready, _, _, _, Time) : observing(E) & attempt_count(E, A)
 <- +telemetry_sample(E, A, Round, block, Time).
+telemetry_measurement(E, A, Round, fresh, ready, Error, Latency, Availability, Time)
    : observing(E) & attempt_count(E, A) & error_rate_limit(MaxError) & latency_limit(MaxLatency)
      & (Error > MaxError | Latency > MaxLatency | Availability < 1)
 <- +telemetry_sample(E, A, Round, block, Time).
+telemetry_measurement(E, A, Round, fresh, ready, Error, Latency, Availability, Time)
    : observing(E) & attempt_count(E, A) & error_rate_limit(MaxError) & latency_limit(MaxLatency)
      & Error <= MaxError & Latency <= MaxLatency & Availability >= 1
 <- +telemetry_sample(E, A, Round, allow, Time).

observation_open(Round, Time) :- observation_limit(Max) & Round < Max & observation_timeout(Deadline) & Time < Deadline.
+telemetry_sample(E, A, Round, allow, Time) : observing(E) & attempt_count(E, A)
    & healthy_count(E, Count) & healthy_observations(Need) & Count + 1 >= Need & observation_timeout(Deadline) & Time <= Deadline
 <- !accept_sample(E, allow).
+telemetry_sample(E, A, Round, allow, Time) : observing(E) & attempt_count(E, A)
    & healthy_count(E, Count) & healthy_observations(Need) & Count + 1 < Need & observation_open(Round, Time)
 <- -healthy_count(E, Count); Next = Count + 1; +healthy_count(E, Next); !reobserve(E, Round).
+telemetry_sample(E, A, Round, allow, Time) : observing(E) & attempt_count(E, A)
    & healthy_count(E, Count) & healthy_observations(Need) & observation_timeout(Deadline)
    & (Count + 1 < Need | Time > Deadline) & not observation_open(Round, Time)
 <- !accept_sample(E, unknown).
+telemetry_sample(E, A, Round, Decision, Time) : observing(E) & attempt_count(E, A)
    & Decision \== allow & observation_open(Round, Time)
 <- -healthy_count(E, _); +healthy_count(E, 0); !reobserve(E, Round).
+telemetry_sample(E, A, Round, Decision, Time) : observing(E) & attempt_count(E, A)
    & Decision \== allow & not observation_open(Round, Time)
 <- !accept_sample(E, Decision).
+!reobserve(E, Round) : observation_interval(Delay)
 <- .print("BDI_DECISION=wait_reconsider entity=", E, " round=", Round);
    record_decision(E, reobserve, Round); .wait(Delay); observe_telemetry(E).
+!accept_sample(E, Decision)
 <- -observing(E); accept_telemetry(E, Decision); +telemetry(E, Decision); !observed(E, Decision).
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
