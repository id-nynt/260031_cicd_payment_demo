"""Offline checks for ledger schema and dispatch ambiguity; never launch a trial."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'))
from record_trial import make_record
from dispatch_trial import select_run


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


class AutomationTest(unittest.TestCase):
    def test_run_selection_rejects_ambiguity_and_wrong_revision(self):
        run=dict(headSha='worker',displayTitle='title',createdAt='2026-09-22T10:00:00Z',databaseId=1)
        self.assertEqual(run,select_run([run],'worker','title','2026-09-22T10:00:00Z'))
        self.assertIsNone(select_run([run],'other','title','2026-09-22T10:00:00Z'))
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            select_run([run,dict(run,databaseId=2)],'worker','title','2026-09-22T10:00:00Z')

    def test_forced_test_failure_records_exposure_without_traffic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'trials/t';result=folder/'bdi'
            write(root/'study.json',dict(v1_sha='v1',v2_sha='v2',trials=[dict(id='t',mechanism='bdi',case='test-failure')]))
            write(root/'reset.json',dict(verified_releases={'production':{'execution_id':'reset'}}))
            write(folder/'started.json',dict(reset_result=str(root/'reset.json'),reset_check=str(folder/'reset-check.json')))
            write(result/'controller-result.json',dict(outcome='stopped',executions={'test':{'status':'failure'}}))
            (folder/'result-path.txt').write_text(str(result))
            (result/'experiment-events.jsonl').write_text(json.dumps(dict(event='execution_configuration',entity='test',failure_mode='force_failure'))+'\n')
            write(folder/'final-state.json',dict(production=dict(ready=True,health=dict(appVersion='v1',deploymentRunId='reset'))))
            write(folder/'remote-collection.json',dict(complete=True))
            record=make_record(root,'t')
            self.assertTrue(record['fault_reviewed']);self.assertEqual('verified_baseline',record['safety'])
            self.assertIn('result_dir',record);self.assertIn('reset_result',record);self.assertIn('reset_check',record)
            self.assertIsNone(record['human_interventions'])
            (result/'experiment-events.jsonl').write_text('')
            self.assertFalse(make_record(root,'t')['fault_reviewed'])
            write(folder/'final-state.json',dict(production=dict(ready=True,health=dict(appVersion='v1',deploymentRunId='other'))))
            self.assertEqual('unverified',make_record(root,'t')['safety'])


if __name__=='__main__':unittest.main()
