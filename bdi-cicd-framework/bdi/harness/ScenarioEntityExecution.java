package harness;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Deterministic executor used only by local Jason reasoning experiments. */
public final class ScenarioEntityExecution implements EntityExecution {
    private final String scenario;
    private final Map<String, Integer> calls = new HashMap<>();

    public ScenarioEntityExecution(String scenario) { this.scenario = scenario; }

    @Override
    public Result execute(String entity, int attempt) {
        int count = calls.merge(entity, 1, Integer::sum);
        String status = "success";
        if (entity.equals("test") && scenario.equals("transient_test_failure") && count == 1) status = "failure";
        if (entity.equals("test") && scenario.equals("exhausted_test_failure")) status = "failure";
        return new Result(status, 42, "scenario-" + UUID.randomUUID(), 0,
            "scenario://" + scenario + "/" + entity + "/" + attempt);
    }
}
