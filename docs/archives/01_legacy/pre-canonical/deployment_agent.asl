// Persistent BDI CI/CD deployment controller.
//
// This agent is the plain Jason controller for the local CI/CD prototype.
// It invokes real shell actions through CicdEnvironment and reacts to the
// resulting percepts. Prometheus telemetry is also perceived periodically by
// CicdEnvironment and can trigger reliability recovery plans while the agent
// remains alive.

controller_mode(persistent).
candidate(candidate).

!start_controller.

+environment(production, unstable)
  : release_monitoring_enabled(production)
    & status(deploy(production), passed)
    & telemetry(production, unavailable)
    & not recovery_attempted(production)
  <- .print("[deployment_agent][event] +environment(production, unstable) with telemetry unavailable");
     !pause_reobserve(network_suspected).

+environment(production, unstable)
  : release_monitoring_enabled(production)
    & status(deploy(production), passed)
    & metric(production, latency, high)
    & not metric(production, error_rate, high)
    & not recovery_attempted(production)
  <- .print("[deployment_agent][event] +environment(production, unstable) with high latency");
     !pause_reobserve(high_latency).

+environment(production, unstable)
  : release_monitoring_enabled(production)
    & status(deploy(production), passed)
    & not recovery_attempted(production)
  <- .print("[deployment_agent][event] +environment(production, unstable)");
     !recover_production(telemetry_unstable).

+!start_controller
  <- .print("[deployment_agent] started");
     .print("[deployment_agent] adopting !deliver_release(candidate)");
     !deliver_release(candidate).

// Root goal: deliver a candidate release while preserving production reliability.
+!deliver_release(Candidate)
  <- .print("[deployment_agent][goal] !deliver_release(", Candidate, ")");
     +delivery_in_progress(Candidate);
     !prepare_candidate(Candidate);
     !validate_candidate(Candidate);
     !deploy_to_staging(Candidate);
     !verify_staging;
     !deploy_to_production(Candidate);
     !verify_production;
     !observe_production_canary;
     !maintain_reliability.

// Build preparation.
+!prepare_candidate(Candidate)
  <- .print("[deployment_agent][subgoal] !prepare_candidate(", Candidate, ")");
     !run_build(Candidate).

+!run_build(Candidate)
  <- .print("[deployment_agent][plan] build candidate");
     build(Candidate);
     .wait(250);
     !handle_build_result.

+!handle_build_result
  : status(build, passed)
  <- .print("[deployment_agent][belief] status(build, passed)").

+!handle_build_result
  : status(build, failed)
  <- .print("[deployment_agent][belief] status(build, failed)");
     !fail_delivery(candidate, build_failed).

// Candidate validation.
+!validate_candidate(Candidate)
  <- .print("[deployment_agent][subgoal] !validate_candidate(", Candidate, ")");
     !run_tests(Candidate);
     !run_security_scan(Candidate).

+!run_tests(Candidate)
  <- .print("[deployment_agent][plan] test candidate");
     test(Candidate);
     .wait(250);
     !handle_test_result.

+!handle_test_result
  : status(test, passed)
  <- .print("[deployment_agent][belief] status(test, passed)").

+!handle_test_result
  : status(test, failed)
  <- .print("[deployment_agent][belief] status(test, failed)");
     !fail_delivery(candidate, test_failed).

+!run_security_scan(Candidate)
  <- .print("[deployment_agent][plan] security scan candidate");
     security_scan(Candidate);
     .wait(250);
     !handle_security_scan_result.

+!handle_security_scan_result
  : status(security_scan, passed)
  <- .print("[deployment_agent][belief] status(security_scan, passed)").

+!handle_security_scan_result
  : status(security_scan, failed)
  <- .print("[deployment_agent][belief] status(security_scan, failed)");
     !fail_delivery(candidate, security_failed).

// Staging deployment gate.
+!deploy_to_staging(Candidate)
  <- .print("[deployment_agent][subgoal] !deploy_to_staging(", Candidate, ")");
     deploy(Candidate, staging);
     .wait(250);
     !handle_staging_deploy_result.

+!handle_staging_deploy_result
  : status(deploy(staging), passed)
  <- .print("[deployment_agent][belief] status(deploy(staging), passed)").

+!handle_staging_deploy_result
  : status(deploy(staging), failed)
  <- .print("[deployment_agent][belief] status(deploy(staging), failed)");
     !defer_delivery(candidate, staging_deploy_failed).

+!verify_staging
  <- .print("[deployment_agent][subgoal] !verify_staging");
     health_check(staging);
     .wait(250);
     !handle_staging_health_result.

+!handle_staging_health_result
  : status(health_check(staging), passed) & environment(staging, stable)
  <- .print("[deployment_agent][belief] staging stable").

+!handle_staging_health_result
  <- .print("[deployment_agent][belief] staging unstable");
     !defer_delivery(candidate, staging_unstable).

// Production deployment gate.
+!deploy_to_production(Candidate)
  <- .print("[deployment_agent][subgoal] !deploy_to_production(", Candidate, ")");
     deploy(Candidate, production);
     .wait(250);
     !handle_production_deploy_result.

+!handle_production_deploy_result
  : status(deploy(production), passed)
  <- .print("[deployment_agent][belief] status(deploy(production), passed)").

+!handle_production_deploy_result
  : status(deploy(production), failed)
  <- .print("[deployment_agent][belief] status(deploy(production), failed)");
     !restore_production_reliability(deploy_failed);
     !defer_delivery(Candidate, production_deploy_failed);
     !keep_alive.

+!verify_production
  <- .print("[deployment_agent][subgoal] !verify_production");
     health_check(production);
     .wait(250);
     !handle_production_health_result.

+!handle_production_health_result
  : status(health_check(production), passed)
  <- .print("[deployment_agent][belief] status(health_check(production), passed)");
     -release_monitoring_enabled(production);
     +release_monitoring_enabled(production).

+!handle_production_health_result
  : status(health_check(production), failed)
  <- .print("[deployment_agent][belief] status(health_check(production), failed)");
     !recover_production(health_failed).

+!observe_production_canary
  <- .print("[deployment_agent][subgoal] !observe_production_canary");
     .print("[deployment_agent][decision] observe_production_canary");
     record_decision(observe_production_canary);
     observe(production, canary);
     !handle_production_canary_observation.

+!handle_production_canary_observation
  : delivery_failed(Candidate, Reason)
  <- .print("[deployment_agent][belief] canary completed after delivery already failed: ", Reason).

+!handle_production_canary_observation
  : delivery_deferred(Candidate, Reason)
  <- .print("[deployment_agent][belief] canary completed after delivery already deferred: ", Reason).

+!handle_production_canary_observation
  : observation(production, canary, stable) & environment(production, stable)
  <- .print("[deployment_agent][belief] production stable after canary observation").

+!handle_production_canary_observation
  : telemetry(production, unavailable)
  <- .print("[deployment_agent][belief] telemetry unavailable during canary observation");
     !pause_reobserve(network_suspected).

+!handle_production_canary_observation
  : metric(production, latency, high) & not metric(production, error_rate, high)
  <- .print("[deployment_agent][belief] high latency during canary observation");
     !pause_reobserve(high_latency).

+!handle_production_canary_observation
  : metric(production, error_rate, high)
    & candidate(Candidate)
  <- .print("[deployment_agent][belief] high error rate during canary observation");
     !restore_production_reliability(candidate_unsafe);
     !fail_delivery(Candidate, candidate_unsafe).

+!handle_production_canary_observation
  : observation(production, canary, unstable)
    & candidate(Candidate)
  <- .print("[deployment_agent][belief] production unstable after canary observation");
     !restore_production_reliability(telemetry_unstable);
     !fail_delivery(Candidate, telemetry_unstable).

+!handle_production_canary_observation
  <- .print("[deployment_agent][belief] production canary observation inconclusive");
     .print("[deployment_agent][decision] reliability_unknown");
     record_decision(reliability_unknown);
     !defer_delivery(candidate, reliability_unknown).

// Reliability goal.
+!maintain_reliability
  : environment(production, stable)
    & candidate(Candidate)
    & not delivery_failed(Candidate, _)
    & not delivery_deferred(Candidate, _)
  <- .print("[deployment_agent][goal] !maintain_reliability");
     -release_monitoring_enabled(production);
     +release_monitoring_enabled(production);
     !succeed_delivery(Candidate).

+!maintain_reliability
  : delivery_failed(Candidate, Reason)
  <- .print("[deployment_agent][goal] !maintain_reliability skipped because delivery already failed: ", Reason).

+!maintain_reliability
  : delivery_deferred(Candidate, Reason)
  <- .print("[deployment_agent][goal] !maintain_reliability skipped because delivery already deferred: ", Reason).

+!maintain_reliability
  : environment(production, unstable) & candidate(Candidate)
  <- .print("[deployment_agent][goal] !maintain_reliability");
     !restore_production_reliability(production_unstable);
     !fail_delivery(Candidate, production_unstable);
     !keep_alive.

+!maintain_reliability
  <- .print("[deployment_agent][goal] !maintain_reliability");
     .print("[deployment_agent][decision] reliability_unknown");
     record_decision(reliability_unknown);
     !defer_delivery(candidate, reliability_unknown).

+!recover_production(Reason)
  <- .print("[deployment_agent][goal] !recover_production(", Reason, ")");
     !restore_production_reliability(Reason);
     !handle_recovery_delivery_outcome(Reason).

+!restore_production_reliability(Reason)
  <- .print("[deployment_agent][goal] !restore_production_reliability(", Reason, ")");
     -release_monitoring_enabled(production);
     record_decision(recovery_reason, Reason);
     +recovery_attempted(production);
     +recovery_reason(Reason);
     rollback(production);
     .wait(250);
     !handle_reliability_restore_result(Reason).

+!handle_reliability_restore_result(Reason)
  : status(rollback(production), passed)
  <- .print("[deployment_agent][belief] production reliability restored");
     record_decision(production_reliability_restored, Reason);
     +production_reliability_restored;
     +production_reliability_restored(Reason).

+!handle_reliability_restore_result(Reason)
  : status(rollback(production), failed)
  <- .print("[deployment_agent][belief] production reliability restore failed");
     .print("[deployment_agent][decision] manual_intervention_required");
     record_decision(manual_intervention_required, rollback_failed);
     +decision(manual_intervention_required);
     +manual_reason(rollback_failed);
     !keep_alive.

+!handle_recovery_delivery_outcome(Reason)
  : recovery_reason(health_failed)
  <- !handle_rollback_result.

+!handle_recovery_delivery_outcome(Reason)
  : candidate(Candidate)
  <- !fail_delivery(Candidate, Reason).

+!handle_rollback_result
  : status(rollback(production), passed)
    & recovery_reason(health_failed)
    & candidate(Candidate)
    & not production_retry_attempted(Candidate)
  <- .print("[deployment_agent][belief] status(rollback(production), passed)");
     .print("[deployment_agent][decision] rollback_then_retry_production");
     record_decision(rollback_then_retry_production, health_failed);
     +decision(rollback_then_retry_production);
     +production_retry_attempted(Candidate);
     !verify_recovered_production_before_retry(Candidate, health_failed).

+!handle_rollback_result
  : status(rollback(production), passed)
  <- .print("[deployment_agent][belief] status(rollback(production), passed)");
     .print("[deployment_agent][decision] rollback_production");
     record_decision(rollback_production);
     +decision(rollback_production);
     !keep_alive.

+!handle_rollback_result
  : status(rollback(production), failed)
  <- .print("[deployment_agent][belief] status(rollback(production), failed)");
     .print("[deployment_agent][decision] manual_intervention_required");
     record_decision(manual_intervention_required, rollback_failed);
     +decision(manual_intervention_required);
     !keep_alive.

+!verify_recovered_production_before_retry(Candidate, Reason)
  <- .print("[deployment_agent][subgoal] !verify_recovered_production_before_retry(", Candidate, ", ", Reason, ")");
     health_check(production);
     .wait(250);
     !handle_recovered_production_before_retry(Candidate, Reason).

+!handle_recovered_production_before_retry(Candidate, Reason)
  : status(health_check(production), passed) & environment(production, stable)
  <- .print("[deployment_agent][belief] recovered production stable before retry");
     .print("[deployment_agent][decision] continue_deploy_candidate");
     record_decision(continue_deploy_candidate, Reason);
     +decision(continue_deploy_candidate);
     !deploy_to_production(Candidate);
     !verify_production;
     !observe_production_canary;
     !maintain_reliability.

+!handle_recovered_production_before_retry(Candidate, Reason)
  <- .print("[deployment_agent][belief] recovered production not stable before retry");
     .print("[deployment_agent][decision] manual_intervention_required");
     record_decision(manual_intervention_required, Reason);
     +decision(manual_intervention_required);
     +manual_reason(Reason);
     !keep_alive.

+!pause_reobserve(Reason)
  <- .print("[deployment_agent][goal] !pause_reobserve(", Reason, ")");
     record_decision(pause_reobserve, Reason);
     +decision(pause_reobserve);
     +reobserve_reason(Reason);
     .wait(35000);
     !handle_reobserve_result(Reason).

+!handle_reobserve_result(Reason)
  : environment(production, stable) & candidate(Candidate)
  <- .print("[deployment_agent][belief] production stable after reobserve");
     record_decision(reobserve_recovered, Reason);
     +decision(reobserve_recovered);
     !succeed_delivery(Candidate).

+!handle_reobserve_result(Reason)
  : telemetry(production, unavailable) & candidate(Candidate)
  <- .print("[deployment_agent][belief] telemetry unavailable after reobserve");
     .print("[deployment_agent][decision] manual_intervention_required");
     record_decision(manual_intervention_required, Reason);
     +decision(manual_intervention_required);
     +manual_reason(Reason);
     !defer_delivery(Candidate, Reason).

+!handle_reobserve_result(Reason)
  : telemetry(production, unavailable)
  <- .print("[deployment_agent][belief] telemetry unavailable after reobserve");
     .print("[deployment_agent][decision] manual_intervention_required");
     record_decision(manual_intervention_required, Reason);
     +decision(manual_intervention_required);
     +manual_reason(Reason);
     !keep_alive.

+!handle_reobserve_result(Reason)
  : environment(production, unstable) & candidate(Candidate)
  <- .print("[deployment_agent][belief] production still unstable after reobserve");
     !restore_production_reliability(Reason);
     !fail_delivery(Candidate, Reason).

+!succeed_delivery(Candidate)
  : delivery_failed(Candidate, Reason)
  <- .print("[deployment_agent][outcome] delivery success skipped because delivery already failed: ", Reason);
     !keep_alive.

+!succeed_delivery(Candidate)
  : delivery_deferred(Candidate, Reason)
  <- .print("[deployment_agent][outcome] delivery success skipped because delivery already deferred: ", Reason);
     !keep_alive.

+!succeed_delivery(Candidate)
  <- .print("[deployment_agent][outcome] delivery_succeeded(", Candidate, ")");
     .print("[deployment_agent][decision] delivery_succeeded");
     record_decision(delivery_succeeded, Candidate);
     record_decision(release_complete);
     -delivery_in_progress(Candidate);
     +delivery_succeeded(Candidate);
     +decision(delivery_succeeded);
     +decision(release_complete);
     .print("[deployment_agent] release complete");
     !keep_alive.

+!fail_delivery(Candidate, Reason)
  <- .print("[deployment_agent][outcome] delivery_failed(", Candidate, ", ", Reason, ")");
     .print("[deployment_agent][decision] delivery_failed");
     record_decision(delivery_failed, Reason);
     -delivery_in_progress(Candidate);
     +delivery_failed(Candidate, Reason);
     +decision(delivery_failed);
     +delivery_failure_reason(Reason);
     !keep_alive.

+!defer_delivery(Candidate, Reason)
  <- .print("[deployment_agent][outcome] delivery_deferred(", Candidate, ", ", Reason, ")");
     .print("[deployment_agent][decision] delivery_deferred");
     record_decision(delivery_deferred, Reason);
     -delivery_in_progress(Candidate);
     +delivery_deferred(Candidate, Reason);
     +decision(delivery_deferred);
     +delivery_defer_reason(Reason);
     !keep_alive.

+!stop_release(Reason)
  <- .print("[deployment_agent][decision] stop_pipeline");
     .print("[deployment_agent][reason] ", Reason);
     record_decision(stop_pipeline, Reason);
     +decision(stop_pipeline);
     +stop_reason(Reason);
     !keep_alive.

// Keep the MAS alive for future dynamic perception phases.
+!keep_alive
  <- .wait(5000);
     .print("[deployment_agent] alive: waiting for real perceptions/actions");
     !keep_alive.
