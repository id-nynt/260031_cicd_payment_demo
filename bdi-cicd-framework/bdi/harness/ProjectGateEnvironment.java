package harness;

import java.nio.file.Path;
import java.util.Map;
import jason.asSyntax.Literal;
import jason.environment.Environment;

/** Read-only, periodically refreshed facts for the one-shot AgentSpeak gate. */
public final class ProjectGateEnvironment extends Environment {
    private volatile boolean running;
    private Thread observer;
    private Literal workflowPercept;
    private Literal telemetryPercept;
    private Literal roundPercept;

    @Override
    public void init(String[] args) {
        super.init(args);
        running = true;
        observer = new Thread(this::collect, "bdi-gate-observer");
        observer.setDaemon(true);
        observer.start();
    }

    private void collect() {
        ProjectConfig project;
        try {
            project = ProjectConfig.load(Path.of(value("BDI_PROJECT_FILE", "../models/payment_project.yaml")));
        } catch (Exception error) {
            System.err.println("BDI_GATE_OBSERVATION_ERROR=config: " + error.getMessage());
            publish(new GateEvidence("unknown", "unknown", "invalid_config"), 1);
            return;
        }
        addPercept(Literal.parseLiteral("promotion_goal(" + project.promotionGate().before() + ")"));
        int round = 1;
        while (running) {
            GateEvidence evidence = observe(project);
            publish(evidence, round++);
            try {
                Thread.sleep(5000);
            } catch (InterruptedException stopped) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    private GateEvidence observe(ProjectConfig project) {
        Map<String, GitHubRunObserver.Job> jobs = Map.of();
        try {
            String fixtureName = System.getenv("BDI_GITHUB_JOBS_FIXTURE");
            Path fixture = fixtureName == null || fixtureName.isBlank() ? null : Path.of(fixtureName);
            long runId = Long.parseLong(value("BDI_GITHUB_RUN_ID", value("GITHUB_RUN_ID", "0")));
            if ("true".equalsIgnoreCase(System.getenv("GITHUB_ACTIONS"))) {
                if (fixture != null) throw new IllegalStateException("GitHub job fixtures are forbidden in Actions");
                if (!String.valueOf(runId).equals(System.getenv("GITHUB_RUN_ID"))) {
                    throw new IllegalStateException("Gate run ID does not match this Actions run");
                }
            }
            GitHubRunObserver github = new GitHubRunObserver(project, System.getenv("GITHUB_REPOSITORY"),
                runId, System.getenv("GITHUB_TOKEN"), fixture);
            jobs = github.observe();
        } catch (Exception error) {
            System.err.println("BDI_GATE_OBSERVATION_ERROR=workflow: " + error.getMessage());
        }
        ProjectTelemetryProvider.Assessment telemetry;
        try {
            String target = value("BDI_TARGET_ENV", project.promotionGate().observe());
            telemetry = new ProjectTelemetryProvider(project, target).assess();
        } catch (Exception error) {
            System.err.println("BDI_GATE_OBSERVATION_ERROR=telemetry: " + error.getMessage());
            telemetry = new ProjectTelemetryProvider.Assessment("unknown", "observation_error", null, null, "unknown");
        }
        return GateEvidence.from(project, jobs, telemetry);
    }

    private void publish(GateEvidence evidence, int round) {
        System.out.println("BDI_GATE_INPUT round=" + round + " workflow=" + evidence.workflow()
            + " telemetry=" + evidence.telemetry() + " reason=" + evidence.reason());
        workflowPercept = replace(workflowPercept, "workflow_state(" + evidence.workflow() + ")");
        telemetryPercept = replace(telemetryPercept, "telemetry_state(" + evidence.telemetry() + ")");
        roundPercept = replace(roundPercept, "evidence_round(" + round + ")");
    }

    private Literal replace(Literal previous, String text) {
        if (previous != null) removePercept(previous);
        Literal next = Literal.parseLiteral(text);
        addPercept(next);
        return next;
    }

    @Override
    public void stop() {
        running = false;
        if (observer != null) observer.interrupt();
        super.stop();
    }

    private static String value(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value;
    }
}
