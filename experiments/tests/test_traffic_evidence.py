"""Offline evidence checks; no deployment, GitHub, Docker or real payment calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.experiment_metrics import extract
from experiments.experiment_protocol import traffic_targets
from experiments.control_revision import control_files, verify_control_revision

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / 'experiments/scenarios.json').read_text())


class TrafficEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'trial'
        self.directory.mkdir()
        self.companion = Path(str(self.directory) + '-experiment')
        self.companion.mkdir()
        self.plan = dict(case='healthy', seed=42, traffic_targets=traffic_targets('healthy', CATALOG['healthy']))
        self.result = dict(mode='github', outcome='achieved', release_sha='v2', executions={
            e: dict(status='success', executionId=e+'-id') for e in ('staging', 'production')})
        self.events = [dict(event='campaign_started', timestamp='2026-01-01T00:00:00Z'),
                       *[dict(event='deployment_ready', after_entity=e, timestamp='2026-01-01T00:00:01Z')
                         for e in ('staging', 'production')],
                       dict(event='campaign_finished', timestamp='2026-01-01T00:00:02Z')]
        for e, target in self.plan['traffic_targets'].items():
            folder = Path(str(self.directory) + target['summary_suffix'])
            folder.mkdir()
            (folder/'summary.json').write_text(json.dumps(dict(entity=e, scenario='healthy', seed=42,
                execution_id=e+'-id', release_sha='v2', stop_reason='campaign_finished',
                requests=3, successful=3, injected_errors=0)))

    def metrics(self):
        (self.companion/'plan.json').write_text(json.dumps(self.plan))
        (self.directory/'controller-result.json').write_text(json.dumps(self.result))
        (self.directory/'experiment-events.jsonl').write_text('\n'.join(json.dumps(e) for e in self.events))
        return extract(self.directory)

    def test_healthy_includes_both_environments(self):
        row = self.metrics()
        self.assertTrue(row['eligible_for_comparison'], row['validation_issues'])
        self.assertEqual(6, row['traffic_requests'])
        self.assertEqual({'staging', 'production'}, set(row['traffic_by_entity']))

    def test_missing_staging_traffic_cannot_hide_behind_healthy_production(self):
        Path(str(self.directory)+'-traffic-staging/summary.json').unlink()
        self.assertIn('staging:traffic_failed_or_incomplete', self.metrics()['validation_issues'])

    def test_wrong_identity_or_seed_is_excluded(self):
        path = Path(str(self.directory)+'-traffic/summary.json')
        summary = json.loads(path.read_text()); summary.update(execution_id='previous-release', seed=999)
        path.write_text(json.dumps(summary))
        issues = self.metrics()['validation_issues']
        self.assertIn('production:traffic_identity_mismatch', issues)
        self.assertIn('production:traffic_configuration_mismatch', issues)

    def test_early_failure_does_not_require_unreached_deployment_traffic(self):
        self.plan.update(case='build-failure', traffic_targets=traffic_targets('build-failure', CATALOG['build-failure']))
        self.events = [self.events[0], self.events[-1]]
        self.result.update(outcome='stopped', executions={'build': {'status': 'failure'}})
        for p in Path(self.temp.name).glob('*traffic*/summary.json'): p.unlink()
        row = self.metrics()
        self.assertTrue(row['eligible_for_comparison'], row['validation_issues'])
        self.assertFalse(any(t['required'] for t in row['traffic_by_entity'].values()))

    def test_fault_scenario_without_fault_exposure_is_excluded(self):
        self.plan.update(case='production-persistent', traffic_targets=traffic_targets('production-persistent', CATALOG['production-persistent']))
        self.assertIn('production:no_injected_traffic_observed', self.metrics()['validation_issues'])

    def test_repair_uses_staging_traffic_and_separate_production_probes(self):
        for case in ('candidate-stopped', 'candidate-restart-fails'):
            self.assertEqual({'staging'}, set(traffic_targets(case, CATALOG[case])))

    def test_control_revision_covers_active_agent_and_traffic(self):
        paths = {p.relative_to(ROOT).as_posix() for p in control_files()}
        self.assertTrue({'bdi-cicd-framework/bdi/controller_agent.asl',
                         'bdi-cicd-framework/generator/controller_generic.asl',
                         'experiments/experiment_metrics.py', 'scripts/run-traffic-scenario.mjs'} <= paths)

    def test_control_revision_rejects_changed_file_without_dispatch(self):
        path = Path(self.temp.name)/'control.txt'; path.write_text('new')
        with patch('experiments.control_revision.control_files', return_value=[path]), \
             patch('experiments.control_revision.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='old')) as run:
            with self.assertRaisesRegex(ValueError, 'NEW control tag'):
                verify_control_revision('a'*40, root=Path(self.temp.name))
            self.assertEqual(['git','show'], run.call_args.args[0][:2])


if __name__ == '__main__': unittest.main()
