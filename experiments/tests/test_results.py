import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.summarize import summarize
from experiments.collect import main as collect


class ResultsTest(unittest.TestCase):
    def test_collector_preserves_missing_artifacts_and_running_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'trial'
            responses = [
                SimpleNamespace(returncode=0, stdout='{"status":"in_progress"}', stderr=''),
                SimpleNamespace(returncode=1, stdout='', stderr='logs not available'),
                SimpleNamespace(returncode=1, stdout='', stderr='no artifacts'),
            ]
            with patch('sys.argv', ['collect', '--repo', 'o/r', '--run-id', '123', '--output', str(output)]), \
                    patch('experiments.collect.subprocess.run', side_effect=responses):
                with self.assertRaises(SystemExit):
                    collect()
            record = json.loads((output/'collection.json').read_text())
            self.assertFalse(record['complete_download'])
            self.assertEqual(0, record['metrics_found'])
            self.assertEqual(3, len(record['errors']))

    def test_delivery_restoration_and_exclusion_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, fields in enumerate([
                dict(candidate_delivered=False, service_restored=True, rollback_attempts=1, eligible_for_comparison=True),
                dict(candidate_delivered=False, service_restored=False, rollback_attempts=1, eligible_for_comparison=True),
                dict(candidate_delivered=True, service_restored=False, rollback_attempts=0, eligible_for_comparison=False),
            ]):
                path = root/str(index)
                path.mkdir()
                row = dict(mechanism='github-actions', case='production-persistent', retries=0,
                           release_sha='candidate', recovery_seconds=10 if index == 0 else None,
                           protocol_key='same', **fields)
                (path/'experiment-metrics.json').write_text(json.dumps(row))
            rows, result = summarize(root, 'candidate')
            group = result['groups'][0]
            self.assertEqual((3, 2, 1), (group['recorded'], group['eligible'], group['excluded']))
            self.assertEqual(0, group['delivery_rate'])
            self.assertEqual(.5, group['restoration_rate'])
            self.assertEqual(10, group['mean_recovery_seconds'])
            self.assertFalse(result['protocol_groups'][0]['balanced'])
            self.assertEqual([], summarize(root, 'other-candidate')[0])

    def test_incomplete_download_overrides_server_eligibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'collection.json').write_text(json.dumps(dict(complete_download=False)))
            (root/'experiment-metrics.json').write_text(json.dumps(dict(
                mechanism='github-actions', case='healthy', eligible_for_comparison=True,
                candidate_delivered=True, retries=0)))
            rows, result = summarize(root)
            self.assertFalse(rows[0]['eligible_for_comparison'])
            self.assertIsNone(result['groups'][0]['delivery_rate'])
            self.assertEqual(1, len(result['incomplete_collections']))


if __name__ == '__main__':
    unittest.main()
