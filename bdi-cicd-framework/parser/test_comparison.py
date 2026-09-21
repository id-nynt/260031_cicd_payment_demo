"""Test conventional contract guardrails and metrics without GitHub or deployment."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_artifacts import validate, ModelError
from run_controller import conventional_policy
from experiment_metrics import extract

class ComparisonTest(unittest.TestCase):
    def test_payment_contract_and_rejection_of_other_goals(self):
        doc=validate(ROOT)[0]
        self.assertEqual(conventional_policy(doc)['max_production_ms'],1800000)
        bad=copy.deepcopy(doc);bad['goals']['achieve(A)']=['staging.status == failure']
        with self.assertRaises(ModelError): conventional_policy(bad)
        bad=copy.deepcopy(doc);bad['observation_schema']['before']={}
        with self.assertRaises(ModelError): conventional_policy(bad)

    def test_metrics_count_all_attempts_not_only_last_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign=Path(tmp)/'trial';campaign.mkdir()
            companion=Path(str(campaign)+'-experiment');companion.mkdir()
            (companion/'plan.json').write_text(json.dumps({'case':'transient-test-failure','comparison_key':'same','traffic_required':False}))
            (campaign/'generation-manifest.json').write_text(json.dumps({'mechanism':'conventional'}))
            result={'mode':'github','outcome':'achieved','release_sha':'abc','verified_releases':{'production':{'release_sha':'abc','execution_id':'id'}}}
            (campaign/'controller-result.json').write_text(json.dumps(result))
            events=[{'event':'campaign_started','timestamp':'2026-01-01T00:00:00Z'},
                {'event':'action_started','entity':'test','attempt':1}, {'event':'action_started','entity':'test','attempt':2},
                {'event':'action_started','entity':'production','attempt':1},
                {'event':'campaign_finished','timestamp':'2026-01-01T00:00:10Z'}]
            (campaign/'experiment-events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
            row=extract(campaign)
            self.assertEqual(row['retries'],1);self.assertEqual(row['action_attempts'],3)
            self.assertTrue(row['candidate_delivered']);self.assertEqual(row['runtime_seconds'],10)
            self.assertIsNone(row['human_interventions'])
            result['mode']='scenario'
            (campaign/'controller-result.json').write_text(json.dumps(result))
            simulated=extract(campaign)
            self.assertFalse(simulated['candidate_delivered'])
            self.assertFalse(simulated['eligible_for_comparison'])
            result['mode']='github'

            result.update(outcome='stopped',recovery_outcome='restored',telemetry={'rollback':'allow'})
            (campaign/'controller-result.json').write_text(json.dumps(result))
            row=extract(campaign);self.assertFalse(row['candidate_delivered']);self.assertTrue(row['service_restored'])

    def test_incomplete_and_simulated_trials_are_not_research_successes(self):
        with tempfile.TemporaryDirectory() as tmp:
            row=extract(tmp)
            self.assertFalse(row['eligible_for_comparison'])
            self.assertIn('incomplete_campaign',row['validation_issues'])
            self.assertFalse(row['candidate_delivered'])

if __name__ == '__main__': unittest.main()
