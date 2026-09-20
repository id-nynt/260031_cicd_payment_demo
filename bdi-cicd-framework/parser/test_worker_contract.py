"""The worker is an executor, never a deployment pipeline controller."""
import unittest
from pathlib import Path
from workflow_model import read, compile_inputs
ROOT=Path(__file__).resolve().parents[2]
class WorkerContractTest(unittest.TestCase):
    def test_selected_entity_is_the_only_executable_job(self):
        worker=read(ROOT/'.github/workflows/entity-execution.yml')
        self.assertEqual('bdi-${{ inputs.execution_id }}',worker['run-name'])
        self.assertEqual({'workflow_dispatch'},set(worker.get('on',worker.get(True))))
        self.assertFalse((ROOT/'.github/workflows/rollback-production.yml').exists())
        pipeline=read(ROOT/'bdi-cicd-framework/models/01_pipeline.yaml')
        for name, job in (pipeline['jobs']|pipeline['recovery']).items():
            self.assertEqual(job['job_name'], worker['jobs'][name]['name'])
            self.assertEqual("inputs.entity == '"+name+"'", worker['jobs'][name]['if'])
            self.assertNotIn('needs',worker['jobs'][name])
        self.assertEqual(set(worker['jobs']),set(pipeline['jobs'])|set(pipeline['recovery']))

    def test_java_fixtures_match_canonical_compiler(self):
        framework=ROOT/'bdi-cicd-framework'
        for name,pipeline,goal in [('controller-workflow','models/01_pipeline.yaml','models/02_goal.yaml'),('reporting-workflow','examples/reporting_pipeline.yaml','examples/reporting_goal.yaml')]:
            doc,_=compile_inputs(framework/pipeline,framework/goal)
            self.assertEqual(doc,read(framework/('bdi/fixtures/'+name+'.yaml')))

    def test_payment_environment_and_telemetry_bindings_match_worker_and_service(self):
        pipeline=read(ROOT/'bdi-cicd-framework/models/01_pipeline.yaml')
        worker=read(ROOT/'.github/workflows/entity-execution.yml')
        for entity in ('staging', 'production', 'rollback'):
            binding=(pipeline['jobs']|pipeline['recovery'])[entity]
            job=worker['jobs'][entity]
            self.assertEqual(binding['environment'], job['environment'])
            self.assertEqual('${{ inputs.execution_id }}', job['env']['CI_RUN_ID'])
            endpoint=pipeline['telemetry']['environments'][binding['environment']]
            self.assertEqual(f"http://127.0.0.1:{job['env']['APP_PORT']}/ready", endpoint['ready_url'])
            self.assertEqual(f"http://127.0.0.1:{job['env']['PROMETHEUS_PORT']}", endpoint['prometheus_url'])
        service=(ROOT/'src/telemetry.ts').read_text()
        self.assertIn('ci_run_id: config.CI_RUN_ID', service)
        for metric in ('payment.http.requests','payment.http.errors','payment.http.request.duration','payment.service.ready'):
            self.assertIn(metric, service)
        compose=read(ROOT/'docker-compose.yml')['services']
        self.assertEqual('${CI_RUN_ID:-local}', compose['app']['environment']['CI_RUN_ID'])
        self.assertEqual('http://otel-collector:4318/v1/metrics', compose['app']['environment']['OTEL_EXPORTER_OTLP_METRICS_ENDPOINT'])
        self.assertEqual(['otel-collector:9464'], read(ROOT/'prometheus.yml')['scrape_configs'][0]['static_configs'][0]['targets'])
