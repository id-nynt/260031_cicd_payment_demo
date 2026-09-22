"""Synthetic files only: no workflows, Docker, telemetry or traffic are invoked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.evaluate_study import evaluate, main


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding='utf-8-sig')


class StudyEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.trials=[dict(id='01-bdi',case='healthy',repetition=1,mechanism='bdi'),
                     dict(id='02-native',case='healthy',repetition=1,mechanism='github-actions')]
        write(self.root/'study.json',dict(repository='owner/repo',v1_sha='v1',v2_sha='v2',worker_sha='worker',seed=42,trials=self.trials))
        self.results=[];self.records=[];self.resets=[]
        for i,trial in enumerate(self.trials):
            folder=self.root/'trials'/trial['id']
            result=folder/('bdi' if i==0 else 'native/artifacts/native-result/result')
            self.results.append(result)
            reset=self.root/'resets'/trial['id']/'controller-result.json';self.resets.append(reset)
            verified={e:dict(release_sha='v1',execution_id=f'{trial["id"]}-{e}',github_run_id=i+1) for e in ('staging','production')}
            write(reset,dict(mode='github',outcome='achieved',release_sha='v1',repository='owner/repo',verified_releases=verified))
            reset_check=folder/'reset-check.json'
            write(reset_check,{e:dict(deploymentRunId=v['execution_id'],appVersion='v1',experimentMode='normal',ready=True) for e,v in verified.items()})
            write(result/'controller-result.json',dict(repository='owner/repo',outcome='achieved',executions={'build':{'executionId':str(i)}},
                verified_releases={'production':dict(release_sha='v2',execution_id=f'candidate-{i}')}))
            write(folder/'final-state.json',dict(production=dict(ready=True,health=dict(appVersion='v2',deploymentRunId=f'candidate-{i}'))))
            write(result/'experiment-metrics.json',dict(case='healthy',mechanism=trial['mechanism'],seed=42,
                release_sha='v2',known_good_sha='v1',mode='github',protocol_key='same',eligible_for_comparison=True,
                candidate_delivered=True,service_restored=False,candidate_repaired=False,retries=0,repair_attempts=0,
                rollback_attempts=0,runtime_seconds=10+i*2,recovery_seconds=None,candidate_repair_seconds=None,protocol_expectation_met=True))
            write(Path(str(result)+'-experiment')/'plan.json',dict(comparison=dict(worker_sha='worker')))
            record=folder/'record.json';self.records.append(record)
            write(record,dict(result_dir=str(result),reset_result=str(reset),reset_check=str(reset_check),
                evidence_complete=True,fault_reviewed=True,safety='verified_candidate',human_interventions=i,notes=''))
            if i:write(folder/'native/collection.json',dict(complete_download=True))

    def tearDown(self):self.temp.cleanup()

    def change(self,path,**fields):
        data=json.loads(path.read_text(encoding='utf-8-sig'));data.update(fields);write(path,data)

    def test_bom_files_matched_pairs_costs_and_explicit_denominators(self):
        rows,pairs,summary=evaluate(self.root)
        self.assertEqual(2,summary['eligible']);self.assertEqual(1,summary['matched_pairs'])
        self.assertEqual(-2,pairs[0]['runtime_seconds_bdi_minus_conventional'])
        self.assertEqual(-1,pairs[0]['human_interventions_bdi_minus_conventional'])
        self.assertEqual(1,summary['groups'][0]['delivery_denominator'])
        self.assertIsNone(summary['groups'][0]['restoration_rate'])

    def test_missing_trial_stays_in_planned_denominator(self):
        self.records[1].unlink()
        rows,pairs,summary=evaluate(self.root)
        self.assertEqual(2,summary['planned']);self.assertEqual(1,summary['recorded'])
        self.assertEqual(['not_finalised'],rows[1]['issues']);self.assertFalse(pairs[0]['matched'])

    def test_wrong_worker_incomplete_artifacts_and_unreviewed_fault_excluded(self):
        self.change(Path(str(self.results[0])+'-experiment')/'plan.json',comparison=dict(worker_sha='other'))
        self.change(self.records[0],fault_reviewed=False)
        self.change(self.root/'trials/02-native/native/collection.json',complete_download=False)
        rows,pairs,summary=evaluate(self.root)
        self.assertEqual(0,summary['eligible'])
        self.assertIn('worker_mismatch',rows[0]['issues']);self.assertIn('incomplete_native_download',rows[1]['issues'])

    def test_protocol_mismatch_prevents_pair_even_with_valid_marginal_rows(self):
        self.change(self.results[0]/'experiment-metrics.json',protocol_key='different')
        rows,pairs,summary=evaluate(self.root)
        self.assertEqual(2,summary['eligible']);self.assertFalse(pairs[0]['matched'])

    def test_unexpected_valid_failure_is_not_excluded(self):
        self.change(self.results[0]/'experiment-metrics.json',candidate_delivered=False,protocol_expectation_met=False)
        self.change(self.records[0],safety='unsafe',human_interventions=None)
        rows,pairs,summary=evaluate(self.root)
        self.assertTrue(rows[0]['eligible']);self.assertEqual(-1,pairs[0]['candidate_delivered_bdi_minus_conventional'])
        self.assertEqual(0,summary['groups'][0]['safe_rate']);self.assertIsNone(pairs[0]['human_interventions_bdi_minus_conventional'])

    def test_duplicate_download_cannot_be_counted_as_replication(self):
        write(self.results[1]/'controller-result.json',json.loads((self.results[0]/'controller-result.json').read_text(encoding='utf-8-sig')))
        rows,_,summary=evaluate(self.root)
        self.assertEqual(0,summary['eligible'])
        self.assertTrue(all('duplicate_trial_evidence' in r['issues'] for r in rows))

    def test_reusing_reset_is_rejected(self):
        write(self.resets[1],json.loads(self.resets[0].read_text(encoding='utf-8-sig')))
        rows,_,summary=evaluate(self.root)
        self.assertEqual(0,summary['eligible'])
        self.assertTrue(all('reset_reused_across_trials' in r['issues'] for r in rows))

    def test_nonfinite_cost_and_bad_reset_identity_are_excluded(self):
        self.change(self.results[0]/'experiment-metrics.json',runtime_seconds=float('nan'))
        self.change(self.root/'trials/02-native/reset-check.json',production=dict(deploymentRunId='wrong'))
        rows,_,summary=evaluate(self.root)
        self.assertEqual(0,summary['eligible']);self.assertIn('invalid_numeric_runtime_seconds',rows[0]['issues'])

    def test_safety_annotation_needs_raw_identity_evidence(self):
        self.change(self.root/'trials/01-bdi/final-state.json',production=dict(ready=True,health=dict(appVersion='v2',deploymentRunId='wrong')))
        self.change(self.records[1],safety='verified_baseline')
        rows,_,summary=evaluate(self.root)
        self.assertEqual(0,summary['eligible'])
        self.assertIn('candidate_safety_not_supported',rows[0]['issues'])
        self.assertIn('baseline_safety_not_supported',rows[1]['issues'])

    def test_cli_exports_all_reports_without_changing_evidence(self):
        before=self.records[0].read_bytes();output=self.root/'report'
        with patch.object(sys,'argv',['evaluate_study','--study',str(self.root),'--output',str(output)]),contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertEqual({'trials.csv','pairs.csv','groups.csv','summary.json'},{p.name for p in output.iterdir()})
        self.assertEqual(before,self.records[0].read_bytes())
        self.assertEqual(1,json.loads((output/'summary.json').read_text())['matched_pairs'])


if __name__=='__main__':unittest.main()
