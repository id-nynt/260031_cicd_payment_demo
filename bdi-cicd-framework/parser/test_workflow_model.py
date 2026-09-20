import copy
from pathlib import Path
import tempfile
import unittest
import yaml
from workflow_model import ModelError, compile_documents, compile_inputs, generate_agent, load_workflow, read

ROOT = Path(__file__).resolve().parents[1]

class CanonicalModelTest(unittest.TestCase):
    def setUp(self):
        self.pipeline = read(ROOT/'models/01_pipeline.yaml')
        self.goals = read(ROOT/'models/02_goal.yaml')

    def test_normal_chain_and_separate_recovery(self):
        doc, model = compile_documents(self.pipeline,self.goals)
        self.assertEqual(model.dependencies,(('build','test'),('test','security'),('security','staging'),('staging','production')))
        self.assertNotIn('rollback',doc['workflow']['jobs'])
        self.assertIn('rollback',doc['workflow']['recovery'])
        self.assertIn('production', [m.entity for m in model.maintenance if m.property=='health'])

    def test_serialized_model_alone_generates_identical_agent(self):
        doc, model = compile_documents(self.pipeline,self.goals)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); workflow=root/'03.yaml'; agent=root/'agent.asl'
            workflow.write_text(yaml.safe_dump(doc,sort_keys=False),encoding='utf-8')
            generate_agent(workflow,ROOT/'generator/controller_generic.asl',agent)
            first=agent.read_bytes()
            self.pipeline.clear(); self.goals.clear()
            generate_agent(workflow,ROOT/'generator/controller_generic.asl',agent)
            self.assertEqual(first,agent.read_bytes())
            self.assertEqual(model,load_workflow(workflow)[1])
            self.assertIn(b'require_healthy(production)',first)
            self.assertIn(b'recover_on(production',first)

    def test_corrupted_runtime_binding_is_rejected(self):
        doc,_=compile_documents(self.pipeline,self.goals)
        doc['runtime']['controller']['jobs']['build']='Different job'
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'model.yaml';p.write_text(yaml.safe_dump(doc,sort_keys=False),encoding='utf-8')
            with self.assertRaises(ModelError):load_workflow(p)

    def test_invalid_inputs_are_rejected(self):
        mutations=[lambda p:p['jobs']['test'].update(needs=['missing']),
                   lambda p:p['jobs']['test'].update(needs=['security']),
                   lambda p:p['jobs']['production'].update(needs=['rollback']),
                   lambda p:p['jobs']['build'].update(steps=[]),
                   lambda p:p['recovery']['rollback'].update(environment='staging'),
                   lambda p:p['recovery']['rollback'].update(release_source='candidate'),
                   lambda p:p['execution'].update(max_retries=True),
                   lambda p:p['telemetry']['metrics'].update(availability_query='min(unrelated)')]
        for mutate in mutations:
            p=copy.deepcopy(self.pipeline);mutate(p)
            with self.subTest(p=p),self.assertRaises(ModelError):compile_documents(p,self.goals)

    def test_health_requirement_cannot_be_silently_dropped(self):
        g=copy.deepcopy(self.goals);g['goal']['maintain(M)']=['production.duration <= 100000']
        p=copy.deepcopy(self.pipeline);p['jobs']['production'].pop('observe_after')
        with self.assertRaises(ModelError):compile_documents(p,g)

    def test_second_project_needs_no_legacy_gate_fields(self):
        doc,model=compile_inputs(ROOT/'examples/reporting_pipeline.yaml',ROOT/'examples/reporting_goal.yaml')
        self.assertEqual(model.required_entities,('package','verify','preview'))
        self.assertNotIn('promotion_gate',doc['runtime'])
        self.assertNotIn('github_job_names',doc['runtime'])

    def test_invalid_or_duplicate_goal_constraints_are_rejected(self):
        for field,value in [('maintain(M)',None),('maintain(M)',['production.duration <= 1','production.duration <= 100000']),('achieve(A)',['production.status == success']*2)]:
            g=copy.deepcopy(self.goals);g['goal'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ModelError):compile_documents(self.pipeline,g)

    def test_duplicate_yaml_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'bad.yaml';p.write_text('jobs: {}\njobs: {}\n')
            with self.assertRaises(ModelError):read(p)

if __name__=='__main__': unittest.main()
