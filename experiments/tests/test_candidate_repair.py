"""Repair safety checks without Docker, GitHub or live payment requests."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('repair',ROOT/'scripts/candidate-repair.py')
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)


class CandidateRepairTest(unittest.TestCase):
    def setUp(self):
        self.stopped=dict(container_id='container-v2',deployment_execution_id='deploy-v2',app_state='stopped',dependency_ready=True)

    def call(self,action='restart',failure=False):
        return repair.operate(action,'payment-production','app','postgres','deploy-v2','http://local',1,failure)

    def test_mismatched_release_is_rejected_before_dependency_or_mutation(self):
        app={'Config':{'Env':['CI_RUN_ID=other-release']},'State':{'Running':False},'Id':'wrong'}
        with patch.object(repair,'container',return_value=app) as lookup,patch.object(repair,'docker') as docker:
            with self.assertRaisesRegex(ValueError,'identity mismatch'):self.call()
            self.assertEqual(1,lookup.call_count)
            docker.assert_not_called()

    def test_diagnosis_never_mutates(self):
        with patch.object(repair,'inspect_target',return_value=self.stopped),patch.object(repair,'docker') as docker:
            self.assertEqual('observed',self.call('diagnose')['status'])
            docker.assert_not_called()

    def test_running_or_unready_dependency_never_restarted(self):
        for value in [dict(self.stopped,app_state='running'),dict(self.stopped,dependency_ready=False)]:
            with self.subTest(value=value),patch.object(repair,'inspect_target',return_value=value),patch.object(repair,'docker') as docker:
                self.assertEqual('not_applicable',self.call()['status']);docker.assert_not_called()

    def test_container_changed_between_diagnosis_and_action(self):
        with patch.object(repair,'inspect_target',side_effect=[self.stopped,dict(self.stopped,container_id='new')]),patch.object(repair,'docker') as docker:
            self.assertEqual('not_applicable',self.call()['status']);docker.assert_not_called()

    def test_container_selection_intersects_exact_labels(self):
        def item(id,service,project='payment-production',oneoff='False'):
            return dict(Id=id,Config=dict(Labels={'com.docker.compose.project':project,'com.docker.compose.service':service,'com.docker.compose.oneoff':oneoff}))
        items=[item('app','app'),item('db','postgres'),item('other','app','payment-staging'),item('oneoff','app',oneoff='True')]
        with patch.object(repair,'docker',side_effect=['app db other oneoff',json.dumps(items)]):
            self.assertEqual('app',repair.container('payment-production','app')['Id'])
        with patch.object(repair,'docker',side_effect=['a b',json.dumps([item('a','app'),item('b','app')])]):
            with self.assertRaisesRegex(ValueError,'exact_matches=2'):repair.container('payment-production','app')
        with patch.object(repair,'docker',return_value=''):
            with self.assertRaisesRegex(ValueError,'project=payment-production, service=app, exact_matches=0'):repair.container('payment-production','app')

    @staticmethod
    def app_item(identity, run_id, **state):
        return dict(Id=identity, Name='/'+identity, Config=dict(Env=[] if run_id is None else ['CI_RUN_ID='+run_id],
            Labels={'com.docker.compose.project':'payment-production','com.docker.compose.service':'app'}),
            State=dict(Running=False,Status='exited',**state))

    def test_expected_identity_excludes_stale_app_but_duplicate_identity_is_rejected(self):
        candidate=self.app_item('candidate','deploy-v2')
        stale=self.app_item('stale',None)
        old=self.app_item('old','deploy-v1')
        for items, count in [([candidate,stale,old],1),([stale,old],0),([candidate,dict(candidate,Id='duplicate')],2)]:
            with self.subTest(count=count), patch.object(repair,'docker',side_effect=['ids',json.dumps(items)]):
                if count==1:
                    self.assertEqual('candidate',repair.container('payment-production','app','deploy-v2')['Id'])
                else:
                    with self.assertRaisesRegex(ValueError,'exact_matches='+str(count)):
                        repair.container('payment-production','app','deploy-v2')

    def test_diagnosis_with_stale_app_and_ready_dependency(self):
        candidate=self.app_item('candidate','deploy-v2')
        stale=self.app_item('stale',None)
        dep=dict(Id='database',State=dict(Running=True),Config=dict(Env=[]))
        with patch.object(repair,'candidates',side_effect=[[stale,candidate],[dep]]), patch.object(repair.subprocess,'run') as ready:
            ready.return_value.returncode=0
            result=self.call('diagnose')
        self.assertEqual('observed',result['status'])
        self.assertEqual('candidate',result['before']['container_id'])
        self.assertTrue(result['before']['dependency_ready'])

    def test_preflight_reports_stale_container_without_mutating(self):
        candidate=self.app_item('candidate','deploy-v2');candidate['State']['Running']=True
        stale=self.app_item('stale',None)
        dep=dict(Id='database',State=dict(Running=True))
        for apps, status in [([candidate],'observed'),([candidate,stale],'unknown'),([candidate,dict(candidate,Id='other')],'unknown')]:
            with patch.object(repair,'candidates',side_effect=[apps,[dep]]),patch.object(repair,'docker') as docker:
                result=repair.preflight('payment-production','app','postgres','deploy-v2')
                self.assertEqual(status,result['status']);docker.assert_not_called()
        self.assertIn('expected_app_count_not_one',result['issues'])

    def test_stop_confirmation_requires_exact_exited_candidate(self):
        candidate=self.app_item('candidate','deploy-v2')
        with patch.object(repair,'container',return_value=candidate):
            result=repair.verify_stopped('payment-production','app','deploy-v2')
            self.assertEqual('fault_injected',result['event'])
            self.assertEqual('deploy-v2',result['deployment_execution_id'])
            candidate['State']['Running']=True
            with self.assertRaisesRegex(ValueError,'not confirmed'):
                repair.verify_stopped('payment-production','app','deploy-v2')

    def test_controlled_restart_failure_is_retained(self):
        with patch.object(repair,'inspect_target',return_value=self.stopped),patch.object(repair,'docker') as docker:
            result=self.call(failure=True)
            self.assertEqual('failed',result['status'])
            self.assertEqual([('start','container-v2'),('stop','container-v2')],[c.args for c in docker.call_args_list])

    def test_replacement_during_probe_is_rejected(self):
        with patch.object(repair,'inspect_target',return_value=self.stopped),patch.object(repair,'docker'), \
                patch.object(repair.time,'monotonic',return_value=0), \
                patch.object(repair.urllib.request,'urlopen',return_value=io.StringIO(json.dumps({'deploymentRunId':'other'}))):
            with self.assertRaisesRegex(ValueError,'changed during'):self.call()

    def test_executed_restart_is_not_itself_a_health_acceptance(self):
        response=io.StringIO('{}');response.status=201
        with patch.object(repair,'inspect_target',return_value=self.stopped),patch.object(repair,'docker') as docker, \
                patch.object(repair.time,'monotonic',side_effect=[0,0,2]),patch.object(repair.time,'sleep'), \
                patch.object(repair.urllib.request,'urlopen',side_effect=[io.StringIO('{"deploymentRunId":"deploy-v2"}'),response]):
            result=self.call()
            self.assertEqual('executed',result['status']);self.assertEqual(1,result['probe_successes'])
            self.assertNotIn('healthy',result);docker.assert_called_once_with('start','container-v2')


if __name__=='__main__':unittest.main()
