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
    def test_finalizer_preserves_and_validates_both_traffic_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); downloaded = root/'downloaded'; downloaded.mkdir()
            sha = 'a'*40
            plan = dict(case='healthy', seed=42, comparison=dict(candidate=sha, baseline='b'*40),
                        traffic_targets=native.traffic_targets('healthy', native.CATALOG['healthy']))
            native.write(downloaded/'prepare'/'plan.json', plan)
            native.write(downloaded/'prepare'/'unused.json', {})
            events = [dict(event='campaign_started', timestamp='2026-01-01T00:00:00Z')]
            for entity in ('staging', 'production'):
                identity = f'native-7-1-{entity}-1'
                native.write(downloaded/entity/'gate-result.json', dict(entity=entity, decision='allow', execution_id=identity))
                native.write(downloaded/(entity+'-traffic')/'summary.json', dict(entity=entity, scenario='healthy', seed=42,
                    execution_id=identity, release_sha=sha, stop_reason='campaign_finished', successful=3, requests=3))
                events.append(dict(event='deployment_ready', after_entity=entity, timestamp='2026-01-01T00:00:01Z'))
            (downloaded/'prepare'/'experiment-events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            jobs = [dict(name=name+' entity', conclusion='success', started_at='2026-01-01T00:00:00Z',
                         completed_at='2026-01-01T00:00:01Z') for name in ('Build','Test','Security','Staging','Production')]
            with patch.object(native, 'api', return_value={'jobs':jobs}), patch.dict('os.environ', {
                    'GITHUB_RUN_ID':'7', 'GITHUB_RUN_ATTEMPT':'1', 'GITHUB_REPOSITORY':'o/r',
                    'GITHUB_STEP_SUMMARY':str(root/'step-summary.md')}):
                result = root/'result'
                self.assertEqual(0, native.finish(result, downloaded))
            metrics = json.loads((result/'experiment-metrics.json').read_text())
            self.assertTrue(metrics['eligible_for_comparison'], metrics['validation_issues'])
            self.assertEqual(6, metrics['traffic_requests'])
            self.assertTrue((root/'result-traffic-staging/summary.json').exists())
            self.assertTrue((root/'result-traffic/summary.json').exists())

    def test_execution_wrapper_classifies_only_confirmed_injections_as_retryable(self):
        spec=importlib.util.spec_from_file_location('attempt',ROOT/'ci-cd-conventional/run-entity.py')
        attempt=importlib.util.module_from_spec(spec);spec.loader.exec_module(attempt)
        self.assertEqual('failure',attempt.status_for(75))
        self.assertEqual('failure',attempt.status_for(124))
        self.assertEqual('transient_failure',attempt.status_for(75,'transient_failure'))
        self.assertEqual('timeout',attempt.status_for(124,'deployment_timeout'))

    def test_attempt_intent_blocks_replay_before_side_effects(self):
        spec=importlib.util.spec_from_file_location('attempt',ROOT/'ci-cd-conventional/run-entity.py')
        attempt=importlib.util.module_from_spec(spec);spec.loader.exec_module(attempt)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            with patch.dict(attempt.os.environ,dict(GITHUB_RUN_ID='7',GITHUB_RUN_ATTEMPT='1',RELEASE_SHA='a'*40,GITHUB_OUTPUT=str(directory/'outputs'))),patch.object(attempt.subprocess,'Popen') as launch:
                launch.return_value.wait.return_value=0
                attempt.run('build',1,directory,directory/'evidence')
                with self.assertRaises(FileExistsError):attempt.run('build',1,directory,directory/'evidence')
                self.assertEqual(1,launch.call_count)

    def test_six_job_collector_uses_attempt_receipts_not_failed_health_job_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);download=root/'download';download.mkdir()
            native.write(download/'prepare/plan.json',dict(workflow_layout='six-jobs-v1',case='production-persistent',
                seed=42,comparison=dict(candidate='a'*40,baseline='b'*40),traffic_required=False))
            native.emit(download/'prepare/experiment-events.jsonl','campaign_started')
            jobs=[]
            for entity in ('build','test','security','staging','production','rollback'):
                identity='native-7-1-'+entity+'-1'
                native.write(download/entity/'execution/attempt-1.json',dict(entity=entity,attempt=1,status='success',
                    executionId=identity,githubRunId=7,release_sha=('b' if entity=='rollback' else 'a')*40,
                    started_at='2026-01-01T00:00:00Z',completed_at='2026-01-01T00:00:01Z',durationMs=1000))
                jobs.append(dict(name=entity.title(),conclusion='failure' if entity=='production' else 'success',completedAt='2026-01-01T00:00:02Z'))
                if entity in ('staging','production','rollback'):
                    native.write(download/entity/'health/gate-result.json',dict(entity=entity,execution_id=identity,
                        decision='block' if entity=='production' else 'allow'))
            with patch.dict(native.os.environ,dict(GITHUB_REPOSITORY='o/r',GITHUB_RUN_ID='7')),patch.object(native,'api',side_effect=AssertionError('offline')):
                self.assertEqual(1,native.finish(root/'result',download,remote={'jobs':jobs}))
            result=json.loads((root/'result/controller-result.json').read_text())
            self.assertEqual('success',result['executions']['production']['status'])
            self.assertEqual('restored',result['recovery_outcome'])
            self.assertEqual('stopped',result['outcome'])

    def test_single_workflow_has_six_jobs_with_embedded_health(self):
        for source in (ROOT/'ci-cd-conventional/workflows').glob('*.yml'):
            self.assertEqual(source.read_bytes(),(ROOT/'.github/workflows'/source.name).read_bytes())
        doc=workflow('ci-cd.yml')
        self.assertEqual({'build','test','security','staging','production','rollback'},set(doc['jobs']))
        for entity in ('staging','production','rollback'):
            self.assertTrue(any('native-experiment.py gate' in s.get('run','') for s in doc['jobs'][entity]['steps']))
        self.assertEqual(['staging'],doc['jobs']['production']['needs'])

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
        self.assertEqual(len(CASES),14)
        for job in doc['jobs'].values(): self.assertNotIn('uses',job)
        self.assertIn('known_good_sha',doc['jobs']['rollback']['if'])
        self.assertIn("needs.production.outputs.status == 'success'",doc['jobs']['rollback']['if'])
    def test_worker_faults_are_scoped_and_timeout_precedes_deployment(self):
        script=(ROOT/'scripts/execute-entity.sh').read_text()
        for entity in ('staging','production'):
            body=script.split('  '+entity+')')[1].split('    ;;')[0]
            self.assertLess(body.index('sleep 90'),body.index('docker compose up'))
            self.assertIn('docker compose stop postgres',body)
        self.assertNotIn('docker compose stop',script.split('  rollback)')[1])
    def test_native_retries_only_confirmed_transient_or_timeout_never_unknown(self):
        doc=workflow('ci-cd.yml')
        for entity in ('build','test','security','staging','production'):
            condition=next(s['if'] for s in doc['jobs'][entity]['steps'] if s.get('id')=='retry')
            self.assertIn("'transient_failure'",condition);self.assertIn("'timeout'",condition)
            self.assertNotIn("'unknown'",condition)
        self.assertFalse(any(s.get('id')=='retry' for s in doc['jobs']['rollback']['steps']))
    def test_pending_rollback_recheck_requires_consecutive_fresh_health_and_expires(self):
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        bad=dict(good,error_rate=.7)
        for sequence, expected in [([good,bad,good,good],'allow'),([dict(good,data_status='unavailable')]*20,'block')]:
            elapsed=[0];seen=[];values=iter(sequence)
            def sample(): return next(values, bad)
            def sleep(seconds): elapsed[0]+=seconds
            decision=native.reconsider(self.policy,'production',sample,lambda r,v:seen.append(v),clock=lambda:elapsed[0],sleep=sleep)
            self.assertEqual(expected,decision)
            self.assertLessEqual(elapsed[0],self.policy['rollback_reconsideration']['production']['window_seconds'])
            if expected=='allow': self.assertEqual(4,len(seen))

    def test_short_timing_observes_fault_then_two_healthy_samples(self):
        from experiments.experiment_protocol import OBSERVATION_DELAY_SECONDS
        self.assertEqual(15,OBSERVATION_DELAY_SECONDS)
        profile=json.loads((ROOT/'scripts/traffic-scenarios/temporary-errors.json').read_text())
        self.assertEqual(35,profile['phases'][0]['seconds'])
        self.assertTrue(all('[30s]' in self.doc['bindings']['metrics'][name] for name in ('error_rate_query','latency_p95_ms_query')))
        elapsed=[float(OBSERVATION_DELAY_SECONDS)];seen=[]
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        def sample():return dict(good,error_rate=.7 if elapsed[0]<65 else 0)
        def sleep(seconds):elapsed[0]+=seconds
        from unittest.mock import Mock
        repair=Mock()
        self.assertEqual('allow',native.observe(self.policy,sample,lambda r,v:seen.append((elapsed[0],v)),clock=lambda:elapsed[0],sleep=sleep,repair=repair))
        self.assertLess(seen[0][0],35)
        self.assertGreater(seen[0][1]['error_rate'],.05)
        self.assertEqual([0,0],[v['error_rate'] for _,v in seen[-2:]])
        self.assertEqual(70,elapsed[0]);repair.assert_not_called()

    def test_ready_degradation_reobserves_without_repair(self):
        policy=copy.deepcopy(self.policy);policy['execution'].update(observation_attempts=4,observation_interval_seconds=0)
        good=dict(data_status='fresh',readiness='ready',availability=1,error_rate=0,latency_p95_ms=10)
        samples=iter([dict(good,error_rate=.8),good,good])
        from unittest.mock import Mock
        repair=Mock()
        self.assertEqual('allow',native.observe(policy,lambda:next(samples),lambda *a:None,repair=repair))
        repair.assert_not_called()

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
