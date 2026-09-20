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
