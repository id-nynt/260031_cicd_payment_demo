package harness;

import jason.infra.local.RunLocalMAS;

/** Starts the Jason gate and fails closed if no plan produces a decision. */
public final class ProjectGateMain {
    private ProjectGateMain() { }

    public static void main(String[] args) {
        long timeoutSeconds = 90;
        try {
            timeoutSeconds = Long.parseLong(System.getenv().getOrDefault("BDI_GATE_TIMEOUT_SECONDS", "90"));
            if (timeoutSeconds < 1 || timeoutSeconds > 3600) throw new NumberFormatException("out of range");
        } catch (NumberFormatException error) {
            System.err.println("BDI_GATE_RESULT=unknown reason=invalid_timeout");
            System.exit(2);
        }
        long timeoutMs = timeoutSeconds * 1000;
        Thread watchdog = new Thread(() -> {
            try {
                Thread.sleep(timeoutMs);
                System.err.println("BDI_GATE_RESULT=unknown reason=timeout");
                System.exit(2);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }, "bdi-gate-watchdog");
        watchdog.setDaemon(false);
        watchdog.start();
        try {
            RunLocalMAS.main(new String[]{"gate.mas2j", "--log-conf", "logging.properties"});
        } catch (Exception error) {
            System.err.println("BDI_GATE_RESULT=unknown reason=jason_startup_error");
            error.printStackTrace(System.err);
            System.exit(2);
        }
    }
}
