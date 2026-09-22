"""The worker is an executor, never a deployment pipeline controller."""
import unittest
from pathlib import Path
from workflow_model import read, compile_inputs
ROOT=Path(__file__).resolve().parents[2]
class WorkerContractTest(unittest.TestCase):
    def test_fault_controls_and_security_gate_match_the_runtime(self):
        worker=read(ROOT/'.github/workflows/entity-execution.yml')
        for name in ('build','test','security','staging','production'):
            steps=worker['jobs'][name]['steps']
            transient=next(s for s in steps if s.get('name')=='Controlled transient failure')
            self.assertEqual("inputs.failure_mode == 'transient_failure'", transient['if'])
            self.assertEqual('exit 1',transient['run'])
        security=next(s for s in worker['jobs']['security']['steps'] if 'execute-entity.sh' in s.get('run',''))
        self.assertIn('npm audit --omit=dev --audit-level=high',(ROOT/'scripts/execute-entity.sh').read_text())
        self.assertFalse(security.get('continue-on-error',False))
        inputs=worker.get('on',worker.get(True))['workflow_dispatch']['inputs']
        self.assertIn('request_faults',inputs['experiment_mode']['options'])
        self.assertIn('transient_failure',inputs['failure_mode']['options'])
    def test_selected_entity_is_the_only_executable_job(self):
        worker=read(ROOT/'.github/workflows/entity-execution.yml')
        self.assertEqual('bdi-${{ inputs.execution_id }}',worker['run-name'])
        self.assertEqual({'workflow_dispatch','workflow_call'},set(worker.get('on',worker.get(True))))
        self.assertFalse((ROOT/'.github/workflows/rollback-production.yml').exists())
        pipeline=read(ROOT/'bdi-cicd-framework/models/01_pipeline.yaml')
        for name, job in (pipeline['jobs']|pipeline['recovery']).items():
            self.assertEqual(job['job_name'], worker['jobs'][name]['name'])
            self.assertEqual("inputs.entity == '"+name+"'", worker['jobs'][name]['if'])
            self.assertNotIn('needs',worker['jobs'][name])
        self.assertEqual(set(worker['jobs'])-{'diagnose_candidate','restart_candidate'},set(pipeline['jobs'])|set(pipeline['recovery']))
        self.assertNotIn('report',worker['jobs'])
        self.assertEqual('Diagnose candidate',worker['jobs']['diagnose_candidate']['name'])
        self.assertEqual('Restart candidate',worker['jobs']['restart_candidate']['name'])
        self.assertNotIn('report_only',worker['on']['workflow_dispatch']['inputs'])
        for name in pipeline['jobs']:
            self.assertNotIn('continue-on-error',worker['jobs'][name])

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
            endpoint=read(ROOT/'bdi-cicd-framework/config/runtime_bindings.yaml')['telemetry']['environments'][binding['environment']]
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
