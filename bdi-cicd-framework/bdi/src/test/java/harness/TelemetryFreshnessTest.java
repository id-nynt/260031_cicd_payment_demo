package harness;
import cicd.observer.PrometheusTelemetryObserver;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class TelemetryFreshnessTest {
    private String sample(long timestamp) { return "{\"status\":\"success\",\"data\":{\"result\":[{\"value\":["+timestamp+",\"0.02\"]}]}}"; }
    @Test void acceptsFreshAndRejectsOldOrFutureSamples() throws Exception {
        assertEquals(.02, PrometheusTelemetryObserver.firstValue(sample(995),1000,30));
        assertThrows(java.io.IOException.class, () -> PrometheusTelemetryObserver.firstValue(sample(900),1000,30));
        assertThrows(java.io.IOException.class, () -> PrometheusTelemetryObserver.firstValue(sample(1100),1000,30));
    }

    @Test void freshQueryTimestampDoesNotHideStaleSourceMetrics() throws Exception {
        var server = com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress("127.0.0.1",0),0);
        var age = new java.util.concurrent.atomic.AtomicInteger(2);
        server.createContext("/api/v1/query", exchange -> {
            String query = java.net.URLDecoder.decode(exchange.getRequestURI().getRawQuery(), java.nio.charset.StandardCharsets.UTF_8);
            String value = query.contains("source_age") ? Integer.toString(age.get()) : "1";
            byte[] body = ("{\"status\":\"success\",\"data\":{\"result\":[{\"value\":["
                +java.time.Instant.now().getEpochSecond()+",\""+value+"\"]}]}}").getBytes(java.nio.charset.StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        server.start();
        try {
            var observer = new PrometheusTelemetryObserver(java.net.http.HttpClient.newHttpClient(),
                "http://127.0.0.1:"+server.getAddress().getPort(),"errors","latency","available",30,"source_age");
            assertEquals(1,observer.observe("preview").availability());
            age.set(120);
            assertThrows(java.io.IOException.class, () -> observer.observe("preview"));
        } finally {server.stop(0);}
    }

    @Test void canonicalRuntimeNeedsNoLegacyPromotionGate() throws Exception {
        var config=ProjectConfig.load(java.nio.file.Path.of("fixtures/controller-workflow.yaml"));
        assertNull(config.promotionGate());
        assertTrue(config.jobs().isEmpty());
        assertEquals(30,config.maxAgeSeconds());
        assertEquals(.05,config.maxErrorRate());
        assertTrue(ProjectTelemetryProvider.metricQuery(config,"sample_age_seconds_query","execution-123").contains("execution-123"));
        assertDoesNotThrow(()->new ProjectTelemetryProvider(config,"production","production","execution-123"));
    }
}
