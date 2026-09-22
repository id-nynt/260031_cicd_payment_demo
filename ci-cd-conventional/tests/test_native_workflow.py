"""Offline contract, telemetry and evidence tests for the native GitHub baseline."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
import subprocess
import shutil
import sys
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native',ROOT/'ci-cd-conventional/native-experiment.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)

def workflow(name):return yaml.safe_load((ROOT/'.github/workflows'/name).read_text())

class NativeWorkflowTest(unittest.TestCase):
    def test_installed_sources_and_reusable_health_inputs(self):
        for source in (ROOT/'ci-cd-conventional/workflows').glob('*.yml'):
            self.assertEqual(source.read_bytes(), (ROOT/'.github/workflows'/source.name).read_bytes())
        doc = workflow('ci-cd.yml')
        for entity in ['staging', 'production', 'rollback']:
            job = doc['jobs'][entity+'_health']
            callee = workflow(Path(job['uses']).name)
            self.assertEqual(set(callee['on']['workflow_call']['inputs']), set(job['with']))
            self.assertEqual(entity, job['with']['entity'])
            self.assertIn('always()', job['if'])
        self.assertEqual(['staging_health'], doc['jobs']['production']['needs'])

    def test_runs_without_bdi_framework(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ['ci-cd-conventional', 'experiments']:
                shutil.copytree(ROOT/folder, root/folder,
                    ignore=shutil.ignore_patterns('results', 'reports', '.tmp', '__pycache__'))
            self.assertFalse((root/'bdi-cicd-framework').exists())
            for command in [['configuration.py'], ['native-experiment.py', '--help']]:
                run = subprocess.run([sys.executable, str(root/'ci-cd-conventional'/command[0]), *command[1:]],
                    capture_output=True, text=True, cwd=root)
                self.assertEqual(0, run.returncode, run.stderr)

    def setUp(self):
        self.doc,_,self.policy=native.configuration()
    def test_same_scenarios_and_manual_only_trigger(self):
        CASES = json.loads((ROOT/'experiments/scenarios.json').read_text())
        doc=workflow('ci-cd.yml')
        self.assertEqual({'workflow_dispatch'},set(doc['on']))
        self.assertEqual(set(CASES),set(doc['on']['workflow_dispatch']['inputs']['scenario']['options']))
        self.assertEqual(len(CASES),13)
        for name in ['build','test','security','staging','production','rollback']:
            self.assertEqual('./.github/workflows/conventional-entity.yml',doc['jobs'][name]['uses'])
        self.assertEqual(['staging_health'],doc['jobs']['production']['needs'])
        self.assertIn('known_good_sha',doc['jobs']['rollback']['if'])
        self.assertIn("needs.production.outputs.status == 'success'",doc['jobs']['rollback']['if'])
    def test_worker_faults_are_scoped_and_timeout_precedes_deployment(self):
        worker=workflow('entity-execution.yml')
        for entity in ['staging','production']:
            steps=worker['jobs'][entity]['steps']
            fault=next(i for i,s in enumerate(steps) if s.get('name')=='Controlled deployment timeout before side effects')
            deploy=next(i for i,s in enumerate(steps) if s.get('run')=='docker compose up -d --build')
            self.assertLess(fault,deploy)
            self.assertTrue(any(s.get('run')=='docker compose stop postgres' for s in steps))
            self.assertTrue(any(s.get('run')=='docker compose stop app' for s in steps))
        self.assertFalse(any('docker compose stop' in s.get('run','') for s in worker['jobs']['rollback']['steps']))
    def test_native_retries_only_confirmed_transient_or_timeout_never_unknown(self):
        condition=workflow('conventional-entity.yml')['jobs']['wait']['if']
        self.assertIn("'transient_failure'",condition);self.assertIn("'timeout'",condition)
        self.assertNotIn("'unknown'",condition);self.assertIn("inputs.entity != 'rollback'",condition)
    def test_gate_rechecks_transient_and_rejects_persistent_or_missing(self):
        policy=copy.deepcopy(self.policy);policy['execution'].update(observation_attempts=4,observation_interval_seconds=0,healthy_observations=2)
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        bad=dict(good,error_rate=.8);unknown=dict(good,data_status='unavailable')
        for values,expected in [([bad,good,good],'allow'),([bad]*4,'block'),([unknown]*4,'unknown'),([good,bad,good,bad],'block')]:
            samples=iter(values);seen=[]
            self.assertEqual(expected,native.observe(policy,lambda:next(samples),lambda r,v:seen.append(v)))
            self.assertLessEqual(len(seen),4)
    def test_gate_deadline_is_enforced_even_when_sample_returns_healthy_late(self):
        elapsed=[0];policy=copy.deepcopy(self.policy);policy['execution']['observation_timeout_seconds']=1
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        def sample():elapsed[0]=2;return good
        self.assertEqual('unknown',native.observe(policy,sample,lambda *a:None,clock=lambda:elapsed[0]))

    def test_repair_once_requires_two_new_healthy_samples_and_a_deadline(self):
        policy=copy.deepcopy(self.policy);policy['execution'].update(observation_attempts=6,observation_interval_seconds=0)
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        bad=dict(good,readiness='unknown');calls=[];observations=[]
        samples=iter([good,bad,good,good])
        def repair():calls.append(1);return 'executed'
        self.assertEqual('allow',native.observe(policy,lambda:next(samples),lambda r,v:observations.append(v),repair=repair))
        self.assertEqual(1,len(calls));self.assertEqual(4,len(observations))
        for status in ('failed','unknown','exhausted'):
            self.assertEqual('block',native.observe(policy,lambda:bad,lambda *a:None,repair=lambda:status))
        self.assertEqual('unknown',native.observe(policy,lambda:good,lambda *a:None,deadline_limit=lambda:0))

    def test_repair_health_cannot_accept_another_deployment(self):
        self.assertEqual('unavailable',native.measure(self.doc['bindings'],'production','v2',
            get=lambda url:{'deploymentRunId':'v1'},verify_identity=True)['data_status'])
    def test_nonfinite_stale_and_future_telemetry_never_pass(self):
        binding=self.doc['bindings']
        for value,stamp in [('NaN',time.time()),('0',time.time()-60),('0',time.time()+60)]:
            def get(url):return {} if url.endswith('/ready') else {'status':'success','data':{'result':[{'value':[stamp,value]}]}}
            self.assertEqual('unavailable',native.measure(binding,'production','id',get)['data_status'])
    def test_protocol_key_distinguishes_fault_seed_and_worker(self):
        from experiments.experiment_protocol import protocol_key
        args=['healthy',42,'a','b','c','d',self.policy,'p']
        key=protocol_key(*args)
        for i,value in [(0,'production-temporary'),(1,43),(4,'new-worker')]:
            changed=args.copy();changed[i]=value;self.assertNotEqual(key,protocol_key(*changed))
    def test_native_evidence_preserves_failed_attempt_and_verified_restoration(self):
        for recovering in [False, True]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);download=root/'downloaded';download.mkdir()
                native.write(download/'plan.json',dict(case='production-persistent' if recovering else 'transient-test-failure',
                    seed=42,comparison=dict(candidate='a'*40,baseline='b'*40),traffic_required=False))
                native.emit(download/'experiment-events.jsonl','campaign_started')
                jobs=[]
                names={'build':'Build entity','test':'Test entity','security':'Security entity','staging':'Staging entity','production':'Production entity','rollback':'Rollback entity'}
                for i,entity in enumerate(list(names) if recovering else list(names)[:-1]):
                    if entity=='test':
                        jobs.append(dict(name='test / first / Test entity',started_at='2026-01-01T00:00:00Z',completed_at='2026-01-01T00:00:01Z',
                            conclusion='success',steps=[dict(name='Controlled transient failure',conclusion='failure')]))
                    jobs.append(dict(name=f'{entity} / {"retry" if entity=="test" else "first"} / {names[entity]}',
                        started_at=f'2026-01-01T00:00:{i+2:02}Z',completed_at=f'2026-01-01T00:00:{i+3:02}Z',conclusion='success',steps=[]))
                    if entity in ['staging','production','rollback']:
                        native.write(download/entity/'gate-result.json',dict(entity=entity,decision='block' if recovering and entity=='production' else 'allow',execution_id=entity,release_sha='a'*40))
                env=dict(GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_REPOSITORY='o/r',GITHUB_STEP_SUMMARY=str(root/'summary.md'))
                with patch.dict(native.os.environ,env),patch.object(native,'api',return_value={'jobs':jobs}):
                    native.finish(root/'result',download)
                result=json.loads((root/'result/controller-result.json').read_text())
                metrics=json.loads((root/'result/experiment-metrics.json').read_text())
                self.assertEqual(1,metrics['retries'])
                self.assertEqual(not recovering,metrics['candidate_delivered'])
                self.assertEqual('restored' if recovering else 'not_attempted',result['recovery_outcome'])
                events=[json.loads(line) for line in (root/'result/experiment-events.jsonl').read_text().splitlines()]
                self.assertTrue(any(e.get('status')=='transient_failure' for e in events))

    def test_native_preparation_preserves_four_sources_and_pairing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            env=dict(RELEASE_SHA='a'*40,SCENARIO='healthy',SEED='42',BASELINE='true',
                GITHUB_REPOSITORY='o/r',GITHUB_SHA='b'*40,GITHUB_OUTPUT=str(root/'outputs'))
            with patch.dict(native.os.environ,env),patch.object(native,'api',return_value={'sha':'a'*40}):
                native.prepare(root/'evidence')
            plan=json.loads((root/'evidence/plan.json').read_text())
            self.assertEqual({'pipeline','goal','policy','bindings'},set(plan['configuration_inputs']))
            for name,entry in plan['configuration_inputs'].items():
                self.assertEqual(entry['sha256'],native.digest(root/'evidence'/(name+'.input.yaml')))
            from experiments.experiment_protocol import protocol_key
            hashes={k:v['sha256'] for k,v in plan['configuration_inputs'].items()}
            profile=native.digest(ROOT/'scripts/traffic-scenarios/healthy.json')
            self.assertEqual(plan['protocol_key'],protocol_key('healthy',42,'a'*40,'','b'*40,
                native.digest(ROOT/'ci-cd-conventional/snapshots/contract.yaml'),self.policy,
                {'selected':profile,'healthy':profile},hashes))

    def test_preparation_rejects_unverified_rollback_receipt(self):
        env=dict(RELEASE_SHA='a'*40,SCENARIO='healthy',SEED='42',BASELINE='false',CONFIRM_ROLLBACK='true',KNOWN_GOOD_RECEIPT='{}',GITHUB_REPOSITORY='o/r')
        with tempfile.TemporaryDirectory() as tmp,patch.dict(native.os.environ,env),patch.object(native,'api',return_value={'sha':'a'*40}):
            with self.assertRaises(ValueError):native.prepare(Path(tmp)/'evidence')

if __name__=='__main__':unittest.main()
