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
    private ControllerProjectConfig controller;
    private ProjectConfig telemetryProject;
    private EntityExecution executor;
    private StructuredEventLogger journal;
    private final Map<String, EntityExecution.Result> latest = new LinkedHashMap<>();
    private Path resultFile;
    private String scenario;
    private final Map<String, Integer> observationRounds = new LinkedHashMap<>();

    @Override
    public void init(String[] args) {
        super.init(args);
        try {
            Path projectFile = Path.of(required("BDI_PROJECT_FILE"));
            controller = ControllerProjectConfig.load(projectFile);
            resultFile = Path.of(value("BDI_RESULT_FILE", "build/controller-result.json"));
            journal = new StructuredEventLogger(Path.of(value("BDI_JOURNAL_FILE", "build/controller-journal.jsonl")));
            scenario = System.getenv("BDI_SCENARIO");
            addPercept(Literal.parseLiteral("observation_limit(" + controller.observationAttempts() + ")"));
            addPercept(Literal.parseLiteral("observation_interval(" + controller.observationIntervalSeconds() * 1000L + ")"));
            if (scenario == null || scenario.isBlank()) {
                telemetryProject = ProjectConfig.load(projectFile);
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
                case "finish" -> finish(action);
                default -> false;
            };
        } catch (Exception error) {
            journal.event("controller_action_error", null, Map.of("action", action.toString(),
                "error", String.valueOf(error.getMessage())));
            if (action.getFunctor().equals("run_job") && action.getArity() >= 2) {
                addPercept(Literal.parseLiteral("status(" + atom(action, 0) + "," + integer(action, 1) + ",failure)"));
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
        if (!controller.jobNames().containsKey(entity)) throw new IllegalArgumentException("Unmapped entity " + entity);
        journal.event("bdi_decision", null, Map.of("decision", "run", "entity", entity,
            "attempt", attempt, "relevant_beliefs", "dependencies_satisfied_and_goal_required"));
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

    private boolean observeTelemetry(Structure action) throws Exception {
        if (action.getArity() != 1) return false;
        String entity = atom(action, 0);
        journal.event("bdi_decision", null, Map.of("decision", "observe", "entity", entity));
        String decision;
        String reason;
        int round = observationRounds.merge(entity, 1, Integer::sum);
        if (scenario != null && !scenario.isBlank()) {
            if (scenario.equals("telemetry_block")) { decision = "block"; reason = "scenario_block"; }
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
            ProjectTelemetryProvider.Assessment assessment = new ProjectTelemetryProvider(telemetryProject, environment, entity,
                    execution.executionId()).assess();
                journal.event("telemetry_observation", null, Map.of("entity", entity, "round", round,
                    "execution_id", execution.executionId(), "decision", assessment.decision(),
                    "reason", assessment.reason()));
            decision = assessment == null ? "unknown" : assessment.decision();
            reason = assessment == null ? "no_observation" : assessment.reason();
        }
        journal.event("telemetry_terminal", null, Map.of("entity", entity, "decision", decision, "reason", reason));
        addPercept(Literal.parseLiteral("telemetry_sample(" + entity + "," + round + "," + decision + ")"));
        informAgsEnvironmentChanged();
        return true;
    }

    private boolean finish(Structure action) throws Exception {
        if (action.getArity() != 1) return false;
        String outcome = atom(action, 0);
        Files.createDirectories(resultFile.toAbsolutePath().getParent());
        String json = "{\"timestamp\":\"" + Instant.now() + "\",\"outcome\":\"" + outcome
            + "\",\"project\":\"" + controller.project() + "\"}\n";
        Files.writeString(resultFile, json);
        journal.event("controller_finished", null, Map.of("outcome", outcome, "project", controller.project()));
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
