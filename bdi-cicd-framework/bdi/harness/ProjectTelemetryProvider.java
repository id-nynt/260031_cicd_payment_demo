package harness;

import cicd.observer.PrometheusTelemetryObserver;
import cicd.observer.TelemetrySample;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import telemetry.Observation;

/** Converts one project's URLs and thresholds into stable observations. */
public final class ProjectTelemetryProvider implements ObservationProvider {
    public record Assessment(String decision, String reason, Double errorRate,
                             Double latencyP95Ms, String readiness) { }

    private final ProjectConfig project;
    private final String environment;
    private final String entity;
    private final ProjectConfig.Environment endpoints;
    private final HttpClient client = HttpClient.newHttpClient();
    private final PrometheusTelemetryObserver prometheus;

    public ProjectTelemetryProvider(ProjectConfig project, String environment) {
        this(project, environment, environment);
    }

    public ProjectTelemetryProvider(ProjectConfig project, String environment, String entity) {
        this.project = project;
        this.environment = environment;
        this.entity = entity;
        this.endpoints = project.environment(environment);
        String runId = System.getenv().getOrDefault("BDI_TELEMETRY_RUN_ID", "local");
        if (!runId.matches("[A-Za-z0-9_.-]+")) {
            throw new IllegalArgumentException("Invalid BDI_TELEMETRY_RUN_ID");
        }
        this.prometheus = new PrometheusTelemetryObserver(client, endpoints.prometheusUrl().toString(),
            metricQuery(project, "error_rate_query", runId), metricQuery(project, "latency_p95_ms_query", runId),
            metricQuery(project, "availability_query", runId));
    }

    static String metricQuery(ProjectConfig project, String name, String runId) {
        return project.metrics().get(name).replace("{{run_id}}", runId);
    }

    public Assessment assess() {
        String readiness = ready();
        if (readiness.equals("not_ready")) {
            return new Assessment("block", "readiness_not_ready", null, null, readiness);
        }
        if (readiness.equals("unknown")) {
            return new Assessment("unknown", "readiness_unknown", null, null, readiness);
        }
        TelemetrySample sample;
        try {
            sample = prometheus.observe(environment);
        } catch (Exception ignored) {
            return new Assessment("unknown", "metrics_unavailable", null, null, readiness);
        }
        if (sample.availability() < 1) {
            return new Assessment("block", "service_unready_metric", sample.errorRate(), sample.latencyP95Ms(), readiness);
        }
        if (sample.errorRate() > project.maxErrorRate()) {
            return new Assessment("block", "high_http_error_rate", sample.errorRate(), sample.latencyP95Ms(), readiness);
        }
        if (sample.latencyP95Ms() > project.maxLatencyP95Ms()) {
            return new Assessment("block", "high_http_latency", sample.errorRate(), sample.latencyP95Ms(), readiness);
        }
        return new Assessment("allow", "healthy", sample.errorRate(), sample.latencyP95Ms(), readiness);
    }

    @Override
    public List<Observation> getObservations() {
        Assessment assessment = assess();
        Instant now = Instant.now();
        List<Observation> items = new ArrayList<>();
        items.add(new Observation(entity, "gate", assessment.decision(), now));
        items.add(new Observation(entity, "health", assessment.decision().equals("allow") ? "healthy"
            : assessment.decision().equals("block") ? "unhealthy" : "unknown", now));
        items.add(new Observation(entity, "readiness", assessment.readiness(), now));
        items.add(new Observation(entity, "data_status", assessment.errorRate() == null ? "unavailable" : "fresh", now));
        if (assessment.errorRate() != null) {
            items.add(new Observation(entity, "error_rate", assessment.errorRate(), now));
            items.add(new Observation(entity, "latency", assessment.latencyP95Ms(), now));
        }
        return items;
    }

    private String ready() {
        try {
            HttpRequest request = HttpRequest.newBuilder(endpoints.readyUrl())
                .timeout(Duration.ofSeconds(5)).GET().build();
            int status = client.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
            if (status == 200) return "ready";
            if (status == 503) return "not_ready";
            return "unknown";
        } catch (Exception ignored) {
            return "unknown";
        }
    }
}
