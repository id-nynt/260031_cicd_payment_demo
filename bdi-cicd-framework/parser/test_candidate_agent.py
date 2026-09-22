"""End-to-end generated Jason reasoning, with simulated adapters only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from project_artifacts import generate

class CandidateAgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.project=Path(cls.temp.name)/'project'
        for relative in ['models/01_pipeline.yaml','models/02_goal.yaml','config/controller_policy.yaml','config/runtime_bindings.yaml']:
            path=cls.project/relative;path.parent.mkdir(parents=True,exist_ok=True)
            doc=yaml.safe_load((ROOT/relative).read_text())
            if relative=='config/controller_policy.yaml':
                doc['execution'].update(observation_attempts=4,observation_interval_seconds=1,observation_timeout_seconds=15)
            path.write_text(yaml.safe_dump(doc,sort_keys=False),encoding='utf-8')
        generate(cls.project,cls.project/'models/01_pipeline.yaml',cls.project/'models/02_goal.yaml')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def run_case(self,case,outcome,recovery):
        directory=Path(self.temp.name)/case
        run=subprocess.run([sys.executable,str(ROOT/'run_controller.py'),'--project-dir',str(self.project),
            '--scenario',case,'--artifacts-dir',str(directory)],capture_output=True,text=True,timeout=120)
        self.assertTrue((directory/'controller-result.json').exists(),run.stdout[-3000:]+run.stderr[-3000:])
        result=json.loads((directory/'controller-result.json').read_text())
        self.assertEqual((outcome,recovery),(result['outcome'],result['recovery_outcome']),run.stdout[-3000:]+run.stderr[-3000:])
        self.assertEqual('scenario',result['mode'])
        events=[json.loads(line) for line in (directory/'controller-journal.jsonl').read_text().splitlines()]
        self.assertFalse(any(e['event']=='controller_action_error' for e in events))
        return result,events

    def test_repair_preserves_candidate_and_resumes_master_goal(self):
        result,events=self.run_case('candidate_stopped','achieved','not_needed')
        self.assertEqual('success',result['executions']['production']['status'])
        self.assertNotIn('rollback',result['executions'])
        self.assertEqual(1,sum(e['event']=='repair_started' for e in events))
        self.assertTrue(any(e.get('decision')=='repair_verified' for e in events))
        original=result['executions']['production']['execution_id'] if 'execution_id' in result['executions']['production'] else result['executions']['production']['executionId']
        self.assertTrue(all(e['execution_id']==original for e in events if e['event']=='telemetry_measurement' and e['entity']=='production'))

    def test_failed_repair_restores_without_achieving_candidate(self):
        result,events=self.run_case('candidate_restart_fails','stopped','restored')
        self.assertEqual('allow',result['telemetry']['rollback'])
        self.assertEqual(1,sum(e['event']=='repair_started' for e in events))
        self.assertFalse(any(e.get('decision')=='repair_verified' for e in events))

    def test_uncertain_repair_stops_without_overlapping_rollback(self):
        result,events=self.run_case('candidate_repair_unknown','unknown','unresolved')
        self.assertNotIn('rollback',result['executions'])
        self.assertEqual(1,sum(e['event']=='repair_started' for e in events))

    def test_persistent_running_fault_does_not_select_restart(self):
        result,events=self.run_case('production_unhealthy','stopped','restored')
        self.assertFalse(any(e['event']=='repair_started' for e in events))
        self.assertEqual(0,sum(e['event']=='diagnosis_started' for e in events))

if __name__=='__main__':unittest.main()
