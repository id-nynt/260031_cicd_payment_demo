"""Exercise GUI forwarding without starting Java, traffic or remote jobs."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'bdi-cicd-framework'))
import run_experiment


class ExperimentGuiTest(unittest.TestCase):
    def test_display_mode_is_forwarded_and_recorded(self):
        for gui in (False, True):
            with self.subTest(gui=gui), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                campaign = Path(temp) / 'trial'
                sha = 'a' * 40
                argv = ['run_experiment.py', '--mechanism', 'bdi', '--case', 'healthy',
                        '--release-sha', sha, '--known-good', str(Path(temp) / 'receipt.json'),
                        '--confirm-compatible-rollback', '--artifacts-dir', str(campaign)]
                if gui:
                    argv.append('--gui')
                stack.enter_context(patch.object(sys, 'argv', argv))
                stack.enter_context(patch.dict(run_experiment.os.environ, {
                    'GITHUB_REPOSITORY': 'example/payment', 'GITHUB_TOKEN': 'fake-token',
                    'BDI_WORKFLOW_REF': 'test-worker'}, clear=True))
                replacements = {
                    'validate': ({}, None, {'inputs': {}}, None),
                    'conventional_policy': {'thresholds': {}}, 'runtime_settings': {},
                    'known_good_sha': 'b' * 40, 'validate_live_environment': None,
                    'verify_control_revision': {}, 'digest': 'digest',
                    'traffic_targets': {}, 'protocol_key': 'protocol',
                }
                for name, value in replacements.items():
                    stack.enter_context(patch.object(run_experiment, name, return_value=value))
                stack.enter_context(patch.object(run_experiment.urllib.request, 'urlopen',
                    side_effect=lambda *a, **k: io.BytesIO(json.dumps({'sha': sha}).encode())))
                process = Mock(stdout=[], returncode=0, pid=123)
                process.poll.return_value = 0
                launch = stack.enter_context(patch.object(run_experiment.subprocess, 'Popen', return_value=process))
                stack.enter_context(redirect_stdout(io.StringIO()))
                self.assertEqual(run_experiment.main(), 0)
                launch.assert_called_once()
                command = launch.call_args.args[0]
                self.assertEqual('--gui' in command, gui)
                self.assertIn('--pause-after', command)
                companion = Path(str(campaign) + '-experiment')
                self.assertEqual(json.loads((companion / 'plan.json').read_text())['gui'], gui)
                self.assertTrue((companion / 'controller-console.log').exists())
                self.assertTrue((companion / 'launch-status.json').exists())


if __name__ == '__main__':
    unittest.main()
