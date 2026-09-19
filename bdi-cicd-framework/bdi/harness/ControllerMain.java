package harness;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import jason.infra.local.RunLocalMAS;

/** Acquires a campaign lock, starts the generated Jason controller, and maps its final outcome to an exit code. */
public final class ControllerMain {
    private static final ObjectMapper JSON = new ObjectMapper();
    private ControllerMain() { }

    public static void main(String[] args) throws Exception {
        Path lockPath = Path.of(value("BDI_LOCK_FILE", "build/controller.lock")).toAbsolutePath();
        Files.createDirectories(lockPath.getParent());
        try (FileChannel channel = FileChannel.open(lockPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = channel.tryLock()) {
            if (lock == null) throw new IllegalStateException("Another controller holds " + lockPath);
            Path result = Path.of(value("BDI_RESULT_FILE", "build/controller-result.json"));
            Files.deleteIfExists(result);
            boolean gui = Boolean.parseBoolean(value("BDI_GUI", "false"));
            if (gui && java.awt.GraphicsEnvironment.isHeadless()) {
                throw new IllegalStateException("--gui requires a desktop display; use a desktop terminal or omit --gui");
            }
            RunLocalMAS.main(new String[]{"controller.mas2j", "--log-conf",
                gui ? "logging-gui.properties" : "logging.properties"});
            if (!Files.exists(result)) throw new IllegalStateException("Controller stopped without a result");
            String outcome = JSON.readTree(Files.readString(result)).path("outcome").asText("unknown");
            if (outcome.equals("achieved")) return;
            System.exit(outcome.equals("stopped") ? 1 : 2);
        }
    }

    private static String value(String name, String fallback) {
        String value = System.getenv(name); return value == null || value.isBlank() ? fallback : value;
    }
}
