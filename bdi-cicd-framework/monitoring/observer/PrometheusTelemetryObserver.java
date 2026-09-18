package cicd.observer;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Reads normalized HTTP error rate, p95 latency and readiness from one environment's Prometheus. */
public final class PrometheusTelemetryObserver implements TelemetryObserver {
    private static final ObjectMapper JSON = new ObjectMapper();
    private final HttpClient client;
    private final String baseUrl;
    private final String errorRateQuery;
    private final String latencyP95MsQuery;
    private final String availabilityQuery;

    /** Compatibility for the older payment-only environment; new projects pass manifest queries. */
    @Deprecated
    public PrometheusTelemetryObserver(HttpClient client, String baseUrl) {
        this(client, baseUrl,
            "(sum(rate(payment_http_errors_total{route=\"/payments\",status_code=~\"5..\"}[2m])) or vector(0)) / clamp_min(sum(rate(payment_http_requests_total{route=\"/payments\"}[2m])), 0.001)",
            "histogram_quantile(0.95, sum by (le) (rate(payment_http_request_duration_milliseconds_bucket{route=\"/payments\"}[2m])))",
            "min(payment_service_ready)");
    }

    public PrometheusTelemetryObserver(HttpClient client, String baseUrl, String errorRateQuery,
                                       String latencyP95MsQuery, String availabilityQuery) {
        this.client = client;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.errorRateQuery = errorRateQuery;
        this.latencyP95MsQuery = latencyP95MsQuery;
        this.availabilityQuery = availabilityQuery;
    }

    @Override
    public TelemetrySample observe(String environment) throws IOException, InterruptedException {
        return new TelemetrySample(
            query(errorRateQuery),
            query(latencyP95MsQuery),
            query(availabilityQuery));
    }

    private double query(String query) throws IOException, InterruptedException {
        String encoded = URLEncoder.encode(query, StandardCharsets.UTF_8);
        URI uri = URI.create(baseUrl + "/api/v1/query?query=" + encoded);
        HttpRequest request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(10)).GET().build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("HTTP " + response.statusCode());
        }
        return firstValue(response.body());
    }

    public static double firstValue(String body) throws IOException {
        JsonNode root = JSON.readTree(body);
        if (!"success".equals(root.path("status").asText())) {
            throw new IOException("Prometheus query was not successful");
        }
        JsonNode results = root.path("data").path("result");
        if (!results.isArray() || results.isEmpty() || !results.get(0).path("value").isArray()
            || results.get(0).path("value").size() < 2) {
            throw new IOException("Prometheus query returned no sample");
        }
        try {
            double value = Double.parseDouble(results.get(0).path("value").get(1).asText());
            if (!Double.isFinite(value)) throw new IOException("Prometheus query returned a non-finite sample");
            return value;
        } catch (NumberFormatException exception) {
            throw new IOException("Prometheus query returned a non-numeric sample", exception);
        }
    }
}
