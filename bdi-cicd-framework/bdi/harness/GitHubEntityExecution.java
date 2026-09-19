package harness;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/** Dispatches one configured entity workflow and validates the selected job's terminal result. */
public final class GitHubEntityExecution implements EntityExecution {
    private static final ObjectMapper JSON = new ObjectMapper();
    private final ControllerProjectConfig project;
    private final String repository;
    private final String token;
    private final String ref;
    private final String releaseSha;
    private String knownGoodSha = "";
    private final String campaignId;
    private final URI apiBase;
    private final HttpClient client;
    private final Duration pollInterval;
    private final Duration maxWait;
    private final StructuredEventLogger journal;
    private final ExperimentExecutionPlan experimentPlan = new ExperimentExecutionPlan();

    public GitHubEntityExecution(ControllerProjectConfig project, StructuredEventLogger journal) {
        this(project, journal, URI.create(value("GITHUB_API_URL", "https://api.github.com")),
            required("GITHUB_REPOSITORY"), required("GITHUB_TOKEN"), value("BDI_WORKFLOW_REF", "main"),
            required("BDI_RELEASE_SHA"), required("BDI_CAMPAIGN_ID"),
            Duration.ofSeconds(number("BDI_POLL_SECONDS", 5)),
            Duration.ofMinutes(number("BDI_ENTITY_TIMEOUT_MINUTES", 20)));
        knownGoodSha = value("BDI_KNOWN_GOOD_SHA", "");
    }

    GitHubEntityExecution(ControllerProjectConfig project, StructuredEventLogger journal, URI apiBase,
                          String repository, String token, String ref, String releaseSha, String campaignId,
                          Duration pollInterval, Duration maxWait) {
        if (!releaseSha.matches("(?i)[0-9a-f]{40}|[0-9a-f]{64}")) {
            throw new IllegalArgumentException("BDI_RELEASE_SHA must be a full immutable commit hash");
        }
        if (!repository.matches("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")) {
            throw new IllegalArgumentException("GITHUB_REPOSITORY must be owner/name");
        }
        this.project = project;
        this.repository = repository;
        this.token = token;
        this.ref = ref;
        this.releaseSha = releaseSha;
        this.campaignId = campaignId;
        this.apiBase = apiBase;
        this.pollInterval = pollInterval;
        this.maxWait = maxWait;
        this.journal = journal;
        client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    }

    @Override
    public Result execute(String entity, int attempt) throws Exception {
        String selectedSha = sourceFor(entity, releaseSha, knownGoodSha, project);
        String expectedJob = project.jobNames().get(entity);
        if (expectedJob == null) throw new IllegalArgumentException("Unmapped entity: " + entity);
        String executionId = UUID.randomUUID().toString();
        ExperimentExecutionPlan.Injection injection = experimentPlan.next(entity);
        String experimentMode = !"0".equals(injection.forceErrorRate()) ? "high_error_rate" : "normal";
        Instant started = Instant.now();
        journal.event("dispatch_intent", null, Map.of("campaign_id", campaignId, "entity", entity,
            "attempt", attempt, "execution_id", executionId, "release_sha", selectedSha));
        long runId = dispatch(entity, attempt, executionId, injection.failureMode(), experimentMode, selectedSha);
        String runUrl = "https://github.com/" + repository + "/actions/runs/" + runId;
        journal.event("dispatch_acknowledged", null, Map.of("campaign_id", campaignId, "entity", entity,
            "attempt", attempt, "execution_id", executionId, "github_run_id", runId, "run_url", runUrl));
        String status = awaitSelectedJob(runId, expectedJob, started.plus(maxWait));
        long duration = Duration.between(started, Instant.now()).toMillis();
        journal.event("execution_terminal", null, Map.of("campaign_id", campaignId, "entity", entity,
            "attempt", attempt, "execution_id", executionId, "github_run_id", runId,
            "run_url", runUrl, "status", status, "duration_ms", duration));
        return new Result(status, duration, executionId, runId, runUrl);
    }

    private long dispatch(String entity, int attempt, String executionId, String failureMode,
                          String experimentMode, String selectedSha) throws Exception {
        URI uri = endpoint("/repos/" + repository + "/actions/workflows/" + project.workflowFile() + "/dispatches");
        var inputs = JSON.createObjectNode();
        inputs.put("entity", entity).put("campaign_id", campaignId).put("execution_id", executionId)
            .put("attempt", String.valueOf(attempt)).put("release_sha", selectedSha)
            .put("failure_mode", failureMode).put("experiment_mode", experimentMode);
        var body = JSON.createObjectNode().put("ref", ref).put("return_run_details", true).set("inputs", inputs);
        HttpResponse<String> response = client.send(request(uri)
            .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))).build(),
            HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IOException("GitHub dispatch returned HTTP " + response.statusCode() + ": " + response.body());
        }
        long runId = JSON.readTree(response.body()).path("workflow_run_id").asLong(0);
        if (runId <= 0) throw new IOException("Dispatch response did not contain workflow_run_id");
        return runId;
    }

    private String awaitSelectedJob(long runId, String expectedJob, Instant deadline) throws Exception {
        while (Instant.now().isBefore(deadline)) {
            JsonNode run = get("/repos/" + repository + "/actions/runs/" + runId);
            if ("completed".equals(run.path("status").asText())) {
                JsonNode jobs = get("/repos/" + repository + "/actions/runs/" + runId + "/jobs?filter=latest&per_page=100").path("jobs");
                for (JsonNode job : jobs) {
                    if (expectedJob.equals(job.path("name").asText())) {
                        if (!"completed".equals(job.path("status").asText())) throw new IOException("Selected job is not terminal");
                        return normalize(job.path("conclusion").asText());
                    }
                }
                throw new IOException("Selected job was absent or skipped: " + expectedJob);
            }
            Thread.sleep(pollInterval.toMillis());
        }
        // The remote job could still be deploying. Do not permit retry/rollback over it.
        return "unknown";
    }

    static String sourceFor(String entity, String candidate, String knownGood, ControllerProjectConfig project) {
        String selected = "known_good".equals(project.releaseSources().get(entity)) ? knownGood : candidate;
        if (selected == null || !selected.matches("(?i)[0-9a-f]{40}")) {
            throw new IllegalArgumentException("Entity requires a validated immutable source: " + entity);
        }
        return selected;
    }

    private JsonNode get(String path) throws Exception {
        HttpResponse<String> response = client.send(request(endpoint(path)).GET().build(), HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IOException("GitHub API returned HTTP " + response.statusCode());
        return JSON.readTree(response.body());
    }

    private HttpRequest.Builder request(URI uri) {
        return HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(20))
            .header("Accept", "application/vnd.github+json")
            .header("Authorization", "Bearer " + token)
            .header("X-GitHub-Api-Version", "2026-03-10")
            .header("Content-Type", "application/json");
    }

    private URI endpoint(String path) { return URI.create(apiBase.toString().replaceAll("/$", "") + path); }
    private static String normalize(String value) {
        return switch (value) { case "success" -> "success"; case "cancelled" -> "cancelled";
            case "timed_out" -> "timeout"; case "skipped" -> "skipped"; default -> "failure"; };
    }
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException(name + " is required");
        return value;
    }
    private static String value(String name, String fallback) {
        String value = System.getenv(name); return value == null || value.isBlank() ? fallback : value;
    }
    private static long number(String name, long fallback) {
        try { return Long.parseLong(value(name, Long.toString(fallback))); }
        catch (NumberFormatException error) { throw new IllegalStateException(name + " must be numeric"); }
    }
}
