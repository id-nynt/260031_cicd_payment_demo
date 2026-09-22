"""Four-source ownership, migration equivalence and fail-closed configuration tests."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from project_artifacts import generate, validate, ModelError
from workflow_model import read, compile_sources, compile_inputs, generate_agent
ARCHIVE=ROOT.parent/'docs/archives/03_model-inputs-before-four-source'

class FourSourcesTest(unittest.TestCase):
    def setUp(self):
        self.sources=[read(ROOT/p) for p in ['models/01_pipeline.yaml','models/02_goal.yaml','config/controller_policy.yaml','config/runtime_bindings.yaml']]
    def test_contract_and_agent_equivalence(self):
        doc,_=compile_sources(*self.sources)
        legacy=deepcopy(doc);legacy['schema_version']=2;legacy.pop('candidate_repair');legacy['bindings'].pop('diagnostics')
        self.assertEqual(read(ARCHIVE/'payment-resolved.yaml'),legacy)
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp)/'03.yaml';a=Path(tmp)/'agent.asl'
            w.write_text(yaml.safe_dump(doc,sort_keys=False),encoding='utf-8')
            generate_agent(w,ROOT/'generator/controller_generic.asl',a)
            # Git may materialize CRLF on Windows; compare the exact normalized agent body.
            self.assertIn('!master_goal.',a.read_text(encoding='utf-8'))
            self.assertIn('repair_enabled(production).',a.read_text(encoding='utf-8'))
            self.assertIn((ROOT/'generator/controller_generic.asl').read_text(encoding='utf-8'),a.read_text(encoding='utf-8'))
        self.assertEqual(read(ARCHIVE/'reporting-resolved.yaml'),compile_inputs(ROOT/'examples/reporting_pipeline.yaml',ROOT/'examples/reporting_goal.yaml')[0])

    def test_repair_configuration_is_bounded_and_explicit(self):
        from workflow_model import expand_workflow
        doc,model=compile_sources(*self.sources)
        expanded,roundtrip=expand_workflow(doc)
        self.assertEqual(model,roundtrip)
        self.assertEqual(1,expanded['runtime']['candidate_repair']['production']['max_attempts'])
        self.assertNotIn('restart_production',model.entities)
        mutations=[lambda s:s[2]['candidate_repair']['production'].update(max_attempts=True),
            lambda s:s[2]['candidate_repair']['production'].update(max_attempts=2),
            lambda s:s[2]['candidate_repair']['production'].update(deadline_seconds=1),
            lambda s:s[0]['candidate_repair']['production'].update(restart_job_name='Production entity'),
            lambda s:s[3]['diagnostics'].clear(),
            lambda s:s[3]['diagnostics']['production'].update(app_service='postgres')]
        for mutate in mutations:
            sources=deepcopy(self.sources);mutate(sources)
            with self.subTest(mutation=mutate),self.assertRaises(ModelError):compile_sources(*sources)
    def test_missing_policy_fields_never_fall_back(self):
        for name in self.sources[2]['execution']:
            sources=deepcopy(self.sources);sources[2]['execution'].pop(name)
            with self.subTest(name=name),self.assertRaises(ModelError):compile_sources(*sources)
        self.assertEqual(36,compile_sources(*self.sources)[0]['execution']['observation_attempts'])
        self.sources[2]['execution']['observation_attempts']=37
        self.assertEqual(37,compile_sources(*self.sources)[0]['execution']['observation_attempts'])
    def test_conflicting_sources_and_bad_references_rejected(self):
        mutations=[lambda s:s[0]['execution'].update(observation_attempts=36),
            lambda s:s[0]['jobs']['build'].update(retry_safe=True),
            lambda s:s[0].update(telemetry=s[3]['telemetry']),
            lambda s:s[1].update(telemetry_constraints=s[2]['telemetry_constraints']),
            lambda s:s[2]['execution']['retry_safe'].append('missing'),
            lambda s:s[2]['execution']['retry_safe'].append('rollback'),
            lambda s:s[2]['execution']['retry_safe'].append('build'),
            lambda s:s[2]['observation']['after'].append('missing'),
            lambda s:s[2]['observation']['before'].update(production='build'),
            lambda s:s[2]['recovery_policy']['rollback'].update(retryable=True),
            lambda s:s[2]['recovery_policy']['rollback'].update(verify_health=False),
            lambda s:s[2]['recovery_policy']['rollback'].update(terminal_on_success='achieved'),
            lambda s:s[0]['recovery']['rollback'].update(environment='staging'),
            lambda s:s[3]['telemetry']['metrics'].update(availability_query='uncorrelated'),
            lambda s:s[2]['telemetry_constraints'].update(error_rate_high_gt=2)]
        for mutate in mutations:
            sources=deepcopy(self.sources);mutate(sources)
            with self.subTest(mutation=mutate),self.assertRaises(ModelError):compile_sources(*sources)
    def test_explicit_empty_retry_allowlist_and_changed_threshold_are_reflected(self):
        self.sources[2]['execution']['retry_safe']=[]
        self.sources[2]['telemetry_constraints']['error_rate_high_gt']=0.01
        doc,_=compile_sources(*self.sources)
        self.assertEqual([],doc['execution']['retry_safe'])
        self.assertEqual(.01,doc['bindings']['thresholds']['error_rate_high_gt'])
    def test_configuration_hashes_and_legacy_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=[]
            for name,data in zip(['pipeline','goal','policy','bindings'],self.sources):
                p=root/(name+'.yaml');p.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8');paths.append(p)
            _,_,manifest=generate(root,*paths)
            record=validate(root)[2]
            self.assertEqual({'pipeline','goal','policy','bindings'},set(record['inputs']))
            for p in paths[2:]:
                data=p.read_bytes();p.write_bytes(data+b'\n# changed\n')
                with self.assertRaisesRegex(ModelError,'generate_project.py'):validate(root)
                p.unlink()
                with self.assertRaisesRegex(ModelError,'generate_project.py'):validate(root)
                p.write_bytes(data)
            import json
            record['schema_version']=1;manifest.write_text(json.dumps(record),encoding='utf-8')
            with self.assertRaisesRegex(ModelError,'generate_project.py'):validate(root)
    def test_failure_goals_still_compile(self):
        for entity in ['staging','production']:
            sources=deepcopy(self.sources);sources[1]={'goal':{'achieve(A)':[entity+'.status == failure']}}
            doc,_=compile_sources(*sources)
            self.assertEqual([entity+'.status == failure'],doc['goals']['achieve(A)'])
    def test_templates_use_explicit_profiles_and_match_reference(self):
        doc,_=compile_inputs(ROOT/'templates/models/01_pipeline.yaml',ROOT/'templates/models/02_goal.yaml')
        self.assertEqual(doc,read(ROOT/'templates/models/03_workflow_model.yaml'))
        self.assertEqual([],doc['execution']['retry_safe'])

    def test_cli_defaults_are_relative_to_selected_project(self):
        from unittest.mock import patch
        import generate_project
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,data in zip(['models/01_pipeline.yaml','models/02_goal.yaml','config/controller_policy.yaml','config/runtime_bindings.yaml'],self.sources):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8')
            with patch.object(sys,'argv',['generate_project.py','--project-dir',str(root)]):
                generate_project.main()
            doc,_,record,_=validate(root)
            self.assertEqual(compile_sources(*self.sources)[0],doc)
            self.assertEqual('config/controller_policy.yaml',record['inputs']['policy']['path'])

    def test_duplicate_policy_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'policy.yaml';p.write_text('execution: {}\nexecution: {}\n')
            with self.assertRaises(ModelError):read(p)

if __name__=='__main__':unittest.main()
