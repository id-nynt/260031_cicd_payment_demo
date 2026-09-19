package harness;

public interface EntityExecution {
    record Result(String status, long durationMs, String executionId, long githubRunId, String runUrl) { }
    Result execute(String entity, int attempt) throws Exception;
}
