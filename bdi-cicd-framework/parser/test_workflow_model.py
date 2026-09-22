import copy
from pathlib import Path
import tempfile
import unittest
import yaml
from workflow_model import ModelError, compile_documents, compile_inputs, generate_agent, load_workflow, read, expand_workflow, resolve_documents

ROOT = Path(__file__).resolve().parents[1]

class CanonicalModelTest(unittest.TestCase):
    def setUp(self):
        # These tests exercise the unchanged schema-2 core; repair extension has separate tests.
        pipeline=read(ROOT/'models/01_pipeline.yaml');pipeline.pop('candidate_repair',None)
        policy=read(ROOT/'config/controller_policy.yaml');policy.pop('candidate_repair',None)
        bindings=read(ROOT/'config/runtime_bindings.yaml');bindings.pop('diagnostics',None)
        self.pipeline,self.goals = resolve_documents(pipeline,read(ROOT/'models/02_goal.yaml'),policy,bindings)

    def test_normal_chain_and_separate_recovery(self):
        doc, model = compile_documents(self.pipeline,self.goals)
        self.assertEqual(model.dependencies,(('build','test'),('test','security'),('security','staging'),('staging','production')))
        self.assertIn('rollback',doc['workflow']['entities(E)'])
        self.assertIn({'from': 'production', 'to': 'rollback'},doc['workflow']['recovery(R)'])
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
        doc['bindings']['controller']['jobs']['unmapped']='Different job'
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
                   lambda p:p['jobs']['production'].update(retry_safe='yes'),
                   lambda p:p['execution'].update(healthy_observations=121),
                   lambda p:p['execution'].update(observation_attempts=1,healthy_observations=2),
                   lambda p:p['execution'].update(observation_timeout_seconds=0),
                   lambda p:p['telemetry']['metrics'].update(availability_query='min(unrelated)')]
        for mutate in mutations:
            p=copy.deepcopy(self.pipeline);mutate(p)
            with self.subTest(p=p),self.assertRaises(ModelError):compile_documents(p,self.goals)

    def test_retry_safety_is_explicit_and_contract_preserves_budgets(self):
        self.pipeline['jobs']['production'].pop('retry_safe')
        with self.assertRaises(ModelError):compile_documents(self.pipeline,self.goals)
        self.pipeline['jobs']['production']['retry_safe']=False
        doc,_=compile_documents(self.pipeline,self.goals)
        self.assertNotIn('production',doc['execution']['retry_safe'])
        self.assertIn('test',doc['execution']['retry_safe'])
        self.assertEqual(2,doc['execution']['healthy_observations'])
        self.assertIn('elapsed_ms',expand_workflow(doc)[0]['capabilities']['observations']['telemetry_measurement'])

    def test_health_requirement_cannot_be_silently_dropped(self):
        g=copy.deepcopy(self.goals);g['goal']['maintain(M)']=['production.duration <= 100000']
        p=copy.deepcopy(self.pipeline);p['jobs']['production'].pop('observe_after')
        with self.assertRaises(ModelError):compile_documents(p,g)

    def test_second_project_needs_no_legacy_gate_fields(self):
        doc,model=compile_inputs(ROOT/'examples/reporting_pipeline.yaml',ROOT/'examples/reporting_goal.yaml')
        self.assertEqual(model.required_entities,('package','verify','preview'))
        self.assertNotIn('promotion_gate',doc['bindings'])
        self.assertNotIn('github_job_names',doc['bindings'])

    def test_invalid_or_duplicate_goal_constraints_are_rejected(self):
        for field,value in [('maintain(M)',None),('maintain(M)',['production.duration <= 1','production.duration <= 100000']),('achieve(A)',['production.status == success']*2)]:
            g=copy.deepcopy(self.goals);g['goal'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ModelError):compile_documents(self.pipeline,g)

    def test_duplicate_yaml_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'bad.yaml';p.write_text('jobs: {}\njobs: {}\n')
            with self.assertRaises(ModelError):read(p)

    def test_failure_goal_round_trip_and_agent_fact(self):
        goals = {'goal': {'achieve(A)': ['staging.status == failure']}, 'telemetry_constraints': self.goals['telemetry_constraints']}
        doc, model = compile_documents(self.pipeline, goals)
        self.assertEqual(model.achievements[0].value, 'failure')
        self.assertNotIn('production', model.required_entities)
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory)/'workflow.yaml'
            agent = Path(directory)/'agent.asl'
            workflow.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
            generate_agent(workflow, ROOT/'generator/controller_generic.asl', agent)
            self.assertEqual(load_workflow(workflow)[1], model)
            self.assertIn('achievement(staging, failure).', agent.read_text())

    def test_compact_contract_rejects_weakened_or_inconsistent_fields(self):
        document, _ = compile_documents(self.pipeline, self.goals)
        mutations = [
            lambda d: d['observation_schema'].update(attempt_id_required=False),
            lambda d: d['observation_schema'].update(attempt_id_required=1),
            lambda d: d['workflow']['observable_properties(O)']['status']['values'].remove('unknown'),
            lambda d: d['workflow']['dependencies(D)'].append({'from': 'missing', 'to': 'test'}),
            lambda d: d['recovery_policy']['rollback'].update(verify_health=False),
            lambda d: d['recovery_policy']['rollback'].update(retryable=True),
            lambda d: d['recovery_policy']['rollback'].update(terminal_on_success='achieved'),
            lambda d: d['observation_schema']['after'].remove('rollback'),
            lambda d: d.update(schema_version=1),
        ]
        for mutate in mutations:
            doc = copy.deepcopy(document)
            mutate(doc)
            with self.subTest(doc=doc), self.assertRaises(ModelError):
                expand_workflow(doc)

    def test_compact_contract_has_single_goals_and_binding_sections(self):
        doc, _ = compile_documents(self.pipeline, self.goals)
        self.assertNotIn('capabilities', doc)
        self.assertNotIn('runtime', doc)
        self.assertNotIn('jobs', doc['workflow'])
        self.assertEqual(self.goals['goal'], doc['goals'])
        self.assertNotIn('observation_attempts', doc['bindings']['controller'])
        self.assertEqual(self.pipeline['execution']['observation_attempts'],
                         expand_workflow(doc)[0]['runtime']['controller']['observation_attempts'])

if __name__=='__main__': unittest.main()
