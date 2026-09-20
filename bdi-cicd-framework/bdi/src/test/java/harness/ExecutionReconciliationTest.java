package harness;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class ExecutionReconciliationTest {
    @TempDir Path directory;
    private static final ObjectMapper JSON = new ObjectMapper();

    private GitHubEntityExecution adapter(HttpServer server) throws Exception {
        return new GitHubEntityExecution(ControllerProjectConfig.load(Path.of("fixtures/controller-workflow.yaml")),
            new StructuredEventLogger(null), URI.create("http://127.0.0.1:"+server.getAddress().getPort()),
            "example/repository", "test-token", "main", "a".repeat(40), "campaign-test", Duration.ofMillis(1), Duration.ofMillis(100));
    }
    private static void respond(HttpExchange exchange, int code, String body) throws java.io.IOException {
        byte[] bytes=body.getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(code,bytes.length);
        exchange.getResponseBody().write(bytes);exchange.close();
    }

    @Test void lostAcknowledgementIsFoundByExecutionIdentityWithoutAnotherPost() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        var posts=new AtomicInteger();var id=new AtomicReference<String>();
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/dispatches",e->{
            posts.incrementAndGet();id.set(JSON.readTree(e.getRequestBody()).path("inputs").path("execution_id").asText());
            respond(e,503,"lost acknowledgement");
        });
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/runs",e->
            respond(e,200,"{\"workflow_runs\":[{\"id\":321,\"display_title\":\"bdi-"+id.get()+"\"}]}"));
        server.createContext("/repos/example/repository/actions/runs/321/jobs",e->respond(e,200,
            "{\"jobs\":[{\"name\":\"Build entity\",\"status\":\"completed\",\"conclusion\":\"success\"}]}"));
        server.createContext("/repos/example/repository/actions/runs/321",e->respond(e,200,"{\"status\":\"completed\"}"));
        server.start();
        try {
            Path state=directory.resolve("pending.json");var first=adapter(server);first.useStateFile(state);
            assertEquals("unknown",first.execute("build",1).status());assertTrue(Files.exists(state));
            // Simulate restart: unresolved durable state prevents a fresh POST.
            var restarted=adapter(server);restarted.useStateFile(state);
            assertEquals("unknown",restarted.execute("build",2).status());
            assertEquals("success",restarted.reconcile("build",1).status());
            assertEquals(1,posts.get());assertFalse(Files.exists(state));
        } finally {server.stop(0);}
    }

    @Test void absentDiscoveryNeverAuthorizesRedispatch() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);var posts=new AtomicInteger();
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/dispatches",e->{posts.incrementAndGet();respond(e,503,"unknown");});
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/runs",e->respond(e,200,"{\"workflow_runs\":[]}"));
        server.start();
        try {
            var adapter=adapter(server);adapter.useStateFile(directory.resolve("pending.json"));
            assertEquals("unknown",adapter.execute("build",1).status());
            assertEquals("unknown",adapter.reconcile("build",1).status());
            assertEquals("unknown",adapter.execute("build",2).status());
            assertEquals(1,posts.get());
        } finally {server.stop(0);}
    }

    @Test void pollingFailureRetainsAcknowledgedRunForReconciliation() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);var polls=new AtomicInteger();var posts=new AtomicInteger();
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/dispatches",e->{posts.incrementAndGet();respond(e,200,"{\"workflow_run_id\":12}");});
        server.createContext("/repos/example/repository/actions/runs/12/jobs",e->respond(e,200,
            "{\"jobs\":[{\"name\":\"Build entity\",\"status\":\"completed\",\"conclusion\":\"failure\"}]}"));
        server.createContext("/repos/example/repository/actions/runs/12",e->{if(polls.incrementAndGet()==1) respond(e,503,"unavailable");else respond(e,200,"{\"status\":\"completed\"}");});
        server.start();
        try {
            var adapter=adapter(server);adapter.useStateFile(directory.resolve("pending.json"));
            assertEquals("unknown",adapter.execute("build",1).status());
            assertEquals("failure",adapter.reconcile("build",1).status());
            assertEquals(1,posts.get());
        } finally {server.stop(0);}
    }

    @Test void ambiguousExecutionIdentityRemainsUnresolved() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        var posts=new AtomicInteger();var id=new AtomicReference<String>();
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/dispatches",e->{
            posts.incrementAndGet();id.set(JSON.readTree(e.getRequestBody()).path("inputs").path("execution_id").asText());
            respond(e,503,"lost acknowledgement");
        });
        server.createContext("/repos/example/repository/actions/workflows/entity-execution.yml/runs",e->{
            var body=JSON.createObjectNode();var runs=body.putArray("workflow_runs");
            runs.addObject().put("id",1).put("display_title","bdi-"+id.get());
            runs.addObject().put("id",2).put("display_title","bdi-"+id.get());
            respond(e,200,body.toString());
        });
        server.start();
        try {
            var adapter=adapter(server);Path state=directory.resolve("ambiguous.json");adapter.useStateFile(state);
            assertEquals("unknown",adapter.execute("build",1).status());
            assertEquals("unknown",adapter.reconcile("build",1).status());
            assertEquals("unknown",adapter.execute("build",2).status());
            assertEquals(1,posts.get());assertTrue(Files.exists(state));
        } finally {server.stop(0);}
    }
}
