package harness;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import jason.asSyntax.Literal;
import jason.asSyntax.Structure;
import jason.environment.Environment;

/** Jason environment transporting generated decisions to one-entity execution and telemetry adapters. */
public final class ControllerEnvironment extends Environment {
    private static final com.fasterxml.jackson.databind.ObjectMapper JSON = new com.fasterxml.jackson.databind.ObjectMapper();
    private ControllerProjectConfig controller;
    private ProjectConfig telemetryProject;
    private EntityExecution executor;
    private StructuredEventLogger journal;
    private final Map<String, EntityExecution.Result> latest = new LinkedHashMap<>();
    private Path resultFile;
    private String scenario;
    private final Map<String, Integer> attempts = new LinkedHashMap<>();
    private final Map<String, Integer> observationRounds = new LinkedHashMap<>();
    private final Map<String, String> telemetry = new LinkedHashMap<>();

    @Override
    public void init(String[] args) {
        super.init(args);
        try {
            Path projectFile = Path.of(required("BDI_PROJECT_FILE"));
            controller = ControllerProjectConfig.load(projectFile);
            resultFile = Path.of(value("BDI_RESULT_FILE", "build/controller-result.json"));
            journal = new StructuredEventLogger(Path.of(value("BDI_JOURNAL_FILE", "build/controller-journal.jsonl")));
            scenario = System.getenv("BDI_SCENARIO");
            if (!value("BDI_KNOWN_GOOD_SHA", "").isBlank()) addPercept(Literal.parseLiteral("known_good_available"));
            if (scenario == null || scenario.isBlank()) {
                if (!controller.environments().isEmpty()) telemetryProject = ProjectConfig.load(projectFile);
                executor = new GitHubEntityExecution(controller, journal);
            } else {
                executor = new ScenarioEntityExecution(scenario);
            }
            journal.event("controller_started", null, Map.of("project", controller.project(),
                "mode", scenario == null || scenario.isBlank() ? "github" : "scenario",
                "scenario", scenario == null ? "" : scenario));
            if (Boolean.parseBoolean(value("BDI_GUI", "false"))) {
                journal.event("mas_console", null, Map.of("visible",
                    jason.runtime.MASConsoleGUI.get().getFrame().isShowing(),
                    "agent", "controller_agent", "keep_open", true));
            }
        } catch (Exception error) {
            throw new IllegalStateException("Cannot start BDI controller: " + error.getMessage(), error);
        }
    }

    @Override
    public synchronized boolean executeAction(String agentName, Structure action) {
        try {
            return switch (action.getFunctor()) {
                case "run_job" -> runJob(action);
                case "observe_telemetry" -> observeTelemetry(action);
                case "reconcile_job" -> reconcileJob(action);
                case "accept_telemetry" -> { telemetry.put(atom(action, 0), atom(action, 1)); yield true; }
                case "finish" -> finish(action);
                case "record_recovery" -> {
                    journal.event("bdi_recovery_decision", null, Map.of("source", atom(action, 0),
                        "entity", atom(action, 1), "reason", atom(action, 2),
                        "known_good_sha", value("BDI_KNOWN_GOOD_SHA", "")));
                    yield true;
                }
                default -> false;
            };
        } catch (Exception error) {
            journal.event("controller_action_error", null, Map.of("action", action.toString(),
                "error", String.valueOf(error.getMessage())));
            if (action.getFunctor().equals("run_job") && action.getArity() >= 2) {
                addPercept(Literal.parseLiteral("status(" + atom(action, 0) + "," + integer(action, 1) + ",unknown)"));
                informAgsEnvironmentChanged();
                return true;
            }
            return false;
        }
    }

    private boolean runJob(Structure action) throws Exception {
        if (action.getArity() != 2) return false;
        String entity = atom(action, 0);
        int attempt = integer(action, 1);
        attempts.put(entity, attempt);
        observationRounds.remove(entity);
        telemetry.remove(entity);
        if (!controller.jobNames().containsKey(entity)) throw new IllegalArgumentException("Unmapped entity " + entity);
        journal.event("bdi_decision", null, Map.of("decision", "run", "entity", entity,
            "attempt", attempt, "relevant_beliefs", controller.releaseSources().containsKey(entity)
                ? "recovery_trigger_known_good_and_single_attempt" : "dependencies_satisfied_and_goal_required"));
        journal.event("entity_execution_started", null, Map.of("entity", entity, "attempt", attempt));
        EntityExecution.Result result = executor.execute(entity, attempt);
        latest.put(entity, result);
        journal.event("entity_execution_finished", null, Map.of("entity", entity, "attempt", attempt,
            "execution_id", result.executionId(), "github_run_id", result.githubRunId(),
            "run_url", result.runUrl(), "status", result.status(), "duration_ms", result.durationMs()));
        if (entity.equals(System.getenv("BDI_PAUSE_AFTER_ENTITY"))) {
            long milliseconds = Long.parseLong(value("BDI_PAUSE_MILLISECONDS", "0"));
            journal.event("controller_pause", null, Map.of("after_entity", entity,
                "milliseconds", milliseconds, "successor_dispatched", false));
            if (milliseconds > 0) Thread.sleep(milliseconds);
        }
        addPercept(Literal.parseLiteral("duration(" + entity + "," + attempt + "," + result.durationMs() + ")"));
        addPercept(Literal.parseLiteral("status(" + entity + "," + attempt + "," + result.status() + ")"));
        informAgsEnvironmentChanged();
        return true;
    }

    private boolean reconcileJob(Structure action) throws Exception {
        if (action.getArity() != 3) return false;
        String entity = atom(action, 0);
        int attempt = integer(action, 1), round = integer(action, 2);
        EntityExecution.Result result;
        try { result = executor.reconcile(entity, attempt); }
        catch (Exception error) { result = new EntityExecution.Result("unknown", 0, "unresolved", 0, ""); }
        latest.put(entity, result);
        removePerceptsByUnif(Literal.parseLiteral("duration(" + entity + "," + attempt + ",_)"));
        journal.event("bdi_reconciliation", null, Map.of("entity", entity, "attempt", attempt, "round", round,
            "execution_id", result.executionId(), "github_run_id", result.githubRunId(), "status", result.status()));
        addPercept(Literal.parseLiteral("duration(" + entity + "," + attempt + "," + result.durationMs() + ")"));
        addPercept(Literal.parseLiteral("reconciled(" + entity + "," + attempt + "," + round + "," + result.status() + ")"));
        informAgsEnvironmentChanged();
        return true;
    }

    private boolean observeTelemetry(Structure action) throws Exception {
        if (action.getArity() != 1) return false;
        String entity = atom(action, 0);
        journal.event("bdi_decision", null, Map.of("decision", "observe", "entity", entity));
        String decision;
        String reason;
        int round = observationRounds.merge(entity, 1, Integer::sum);
        ProjectTelemetryProvider.Measurement measurement;
        if (scenario != null && !scenario.isBlank()) {
            boolean recovery = controller.releaseSources().containsKey(entity);
            boolean protectedEntity = !recovery && controller.releaseSources().keySet().stream()
                .anyMatch(r -> controller.environments().get(r).equals(controller.environments().get(entity)));
            if (scenario.equals("rollback_unhealthy") && recovery) { decision = "block"; reason = "scenario_recovery_unhealthy"; }
            else if (scenario.equals("rollback_unknown") && recovery) { decision = "unknown"; reason = "scenario_recovery_unavailable"; }
            else if (scenario.equals("production_unknown") && protectedEntity) { decision = "unknown"; reason = "scenario_production_unavailable"; }
            else if (protectedEntity && java.util.Set.of("production_unhealthy", "rollback_failure", "rollback_unknown", "rollback_unhealthy").contains(scenario)) {
                decision = "block"; reason = "scenario_production_unhealthy";
            }
            else if (scenario.equals("telemetry_block")) { decision = "block"; reason = "scenario_block"; }
            else if (scenario.equals("telemetry_unknown") || (scenario.equals("telemetry_delayed") && round == 1)) {
                decision = "unknown"; reason = "scenario_wait";
            }
            else {
                decision = "allow"; reason = "scenario_healthy";
            }
        } else {
            EntityExecution.Result execution = latest.get(entity);
            String environment = controller.environments().get(entity);
            if (execution == null || environment == null) throw new IllegalStateException("No deployment identity/environment for " + entity);
            measurement = new ProjectTelemetryProvider(telemetryProject, environment, entity, execution.executionId()).measure();
            return publishMeasurement(entity, round, measurement, execution.executionId());
        }
        measurement = decision.equals("unknown")
            ? new ProjectTelemetryProvider.Measurement("unavailable", "unknown", 0, 0, 0)
            : new ProjectTelemetryProvider.Measurement("fresh", "ready", decision.equals("block") ? 1 : 0, 20, 1);
        return publishMeasurement(entity, round, measurement, latest.get(entity).executionId());
    }

    private boolean publishMeasurement(String entity, int round, ProjectTelemetryProvider.Measurement m, String executionId) {
        int attempt = attempts.getOrDefault(entity, 0);
        journal.event("telemetry_measurement", null, Map.of("entity", entity, "attempt", attempt, "round", round,
            "execution_id", executionId, "data_status", m.dataStatus(), "readiness", m.readiness(),
            "error_rate", m.errorRate(), "latency_p95_ms", m.latencyP95Ms(), "availability", m.availability()));
        addPercept(Literal.parseLiteral("telemetry_measurement(" + entity + "," + attempt + "," + round + ","
            + m.dataStatus() + "," + m.readiness() + "," + m.errorRate() + "," + m.latencyP95Ms() + "," + m.availability() + ")"));
        informAgsEnvironmentChanged();
        return true;
    }

    private boolean finish(Structure action) throws Exception {
        if (action.getArity() != 2) return false;
        String outcome = atom(action, 0);
        String recoveryOutcome = atom(action, 1);
        Files.createDirectories(resultFile.toAbsolutePath().getParent());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("campaign_id", value("BDI_CAMPAIGN_ID", ""));
        result.put("generation_manifest", value("BDI_MANIFEST_FILE", ""));
        result.put("timestamp", Instant.now().toString());
        result.put("outcome", outcome);
        result.put("recovery_outcome", recoveryOutcome);
        result.put("project", controller.project());
        result.put("mode", scenario == null || scenario.isBlank() ? "github" : "scenario");
        result.put("repository", value("GITHUB_REPOSITORY", ""));
        result.put("release_sha", value("BDI_RELEASE_SHA", ""));
        result.put("known_good_sha", value("BDI_KNOWN_GOOD_SHA", ""));
        result.put("telemetry", telemetry);
        result.put("executions", latest);
        var requested = JSON.readTree(value("BDI_GOALS", "[]"));
        var healthGoals = JSON.readTree(value("BDI_HEALTH_GOALS", "[]"));
        java.util.List<String> achieved = new java.util.ArrayList<>();
        java.util.List<String> unmet = new java.util.ArrayList<>();
        for (var goal : requested) {
            String entity = goal.asText();
            boolean healthyRequired = controller.environments().containsKey(entity);
            for (var health : healthGoals) if (health.asText().equals(entity)) healthyRequired = true;
            boolean satisfied = latest.containsKey(entity) && latest.get(entity).status().equals("success")
                && (!healthyRequired || "allow".equals(telemetry.get(entity)));
            // Restoring another revision never satisfies delivery of this candidate.
            if (!recoveryOutcome.equals("not_needed") && controller.environments().containsKey(entity)
                && controller.releaseSources().keySet().stream().anyMatch(r -> latest.containsKey(r)
                    && controller.environments().get(r).equals(controller.environments().get(entity)))) satisfied = false;
            (satisfied ? achieved : unmet).add(entity);
        }
        result.put("achieved_goals", achieved);
        result.put("unmet_goals", unmet);
        Map<String, Object> verified = new LinkedHashMap<>();
        if (outcome.equals("achieved")) for (var entry : latest.entrySet()) {
            if (entry.getValue().status().equals("success") && "allow".equals(telemetry.get(entry.getKey()))) {
                verified.put(entry.getKey(), Map.of("release_sha", value("BDI_RELEASE_SHA", ""),
                    "github_run_id", entry.getValue().githubRunId(), "execution_id", entry.getValue().executionId(),
                    "environment", controller.environments().get(entry.getKey())));
            }
        }
        result.put("verified_releases", verified);
        Files.writeString(resultFile, JSON.writerWithDefaultPrettyPrinter().writeValueAsString(result) + "\n");
        journal.event("controller_finished", null, Map.of("outcome", outcome, "recovery_outcome", recoveryOutcome, "project", controller.project()));
        if (Boolean.parseBoolean(value("BDI_GUI", "false"))) {
            java.util.logging.Logger.getLogger(getClass().getName()).info(
                "Campaign finished. Inspect controller_agent beliefs; close MAS Console to exit. No further jobs will run.");
            return true;
        }
        Thread shutdown = new Thread(() -> {
            try { getEnvironmentInfraTier().getRuntimeServices().stopMAS(); }
            catch (Exception ignored) { stop(); }
        }, "controller-shutdown");
        shutdown.setDaemon(true);
        shutdown.start();
        return true;
    }

    private static String atom(Structure action, int index) {
        String value = action.getTerm(index).toString();
        if (!value.matches("[a-z_][a-z0-9_]*")) throw new IllegalArgumentException("Expected atom: " + value);
        return value;
    }
    private static int integer(Structure action, int index) { return Integer.parseInt(action.getTerm(index).toString()); }
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException(name + " is required");
        return value;
    }
    private static String value(String name, String fallback) {
        String value = System.getenv(name); return value == null || value.isBlank() ? fallback : value;
    }
}
