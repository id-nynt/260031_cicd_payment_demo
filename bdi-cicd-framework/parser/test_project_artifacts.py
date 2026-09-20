import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import yaml
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import project_artifacts as artifacts
import run_controller
from workflow_model import ModelError, validate_agent


class ProjectArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pipeline = self.root / 'pipeline.yaml'
        self.goal = self.root / 'goal.yaml'
        shutil.copyfile(ROOT / 'models/01_pipeline.yaml', self.pipeline)
        shutil.copyfile(ROOT / 'models/02_goal.yaml', self.goal)
        self.workflow, self.agent, self.manifest = artifacts.generate(self.root, self.pipeline, self.goal)

    def test_missing_stale_and_modified_artifacts_fail_with_regeneration_command(self):
        for path in [self.workflow, self.agent, self.manifest, self.pipeline, self.goal]:
            original = path.read_bytes()
            for content in [None, original + b'\n# changed\n']:
                with self.subTest(path=path, missing=content is None):
                    if content is None:
                        path.unlink()
                    else:
                        path.write_bytes(content)
                    with self.assertRaisesRegex(ModelError, 'generate_project.py'):
                        artifacts.validate(self.root)
                    path.write_bytes(original)
        with patch.object(artifacts, 'GENERATOR_FILES', []):
            with self.assertRaisesRegex(ModelError, 'generator or generic policy changed'):
                artifacts.validate(self.root)

    def test_agent_contract_rejects_each_capability_and_policy_mutation(self):
        original = self.agent.read_text(encoding='utf-8')
        changes = [('entity(build).', 'entity(other).'),
                   ('run_job(Entity, Attempt)', 'run_job(other, Attempt)'),
                   ('observe_after(production).', ''),
                   ('recovery(production, rollback).', ''),
                   ('achievement(production, success).', ''),
                   ('require_healthy(production).', ''),
                   ('all_goals_satisfied :-', 'all_goals_satisfied.\nunused :-')]
        for before, after in changes:
            with self.subTest(before=before):
                self.assertIn(before, original)
                self.agent.write_text(original.replace(before, after), encoding='utf-8')
                with self.assertRaisesRegex(ModelError, 'disagree'):
                    validate_agent(self.workflow, ROOT / 'generator/controller_generic.asl', self.agent)
                # Updating the hash alone cannot bless an inconsistent agent.
                record = json.loads(self.manifest.read_text())
                record['generated_agent_sha256'] = artifacts.digest(self.agent)
                self.manifest.write_text(json.dumps(record))
                with self.assertRaisesRegex(ModelError, 'disagree'):
                    artifacts.validate(self.root)

    def test_two_campaigns_reuse_identical_artifacts_without_writing_project(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in
                  [self.workflow, self.agent, self.manifest]}
        real_run = run_controller.subprocess.run
        def simulated_process(command, **kwargs):
            if command[0] == 'git':
                return real_run(command, **kwargs)
            result = Path(kwargs['env']['BDI_RESULT_FILE'])
            result.write_text('{"outcome":"achieved"}')
            return type('Process', (), {'returncode': 0})()
        for name in ['first', 'second']:
            directory = self.root / name
            with patch.object(sys, 'argv', ['run_controller.py', '--project-dir', str(self.root),
                                           '--scenario', 'healthy', '--artifacts-dir', str(directory)]), \
                 patch.object(run_controller.subprocess, 'run', side_effect=simulated_process), \
                 patch.object(artifacts, 'generate_agent', side_effect=AssertionError('runtime generated')):
                self.assertEqual(run_controller.main(), 0)
            self.assertEqual(self.agent.read_bytes(), (directory / 'controller_agent.asl').read_bytes())
            self.assertEqual(self.workflow.read_bytes(), (directory / '03_workflow_model.yaml').read_bytes())
            record = json.loads((directory / 'generation-manifest.json').read_text())
            self.assertEqual(str(self.agent), record['persistent_artifacts']['agent'])
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_runtime_rejects_before_creating_campaign_or_starting_java(self):
        self.agent.unlink()
        directory = self.root / 'rejected'
        with patch.object(sys, 'argv', ['run_controller.py', '--project-dir', str(self.root),
                                       '--scenario', 'healthy', '--artifacts-dir', str(directory)]), \
             patch.object(run_controller.subprocess, 'run', side_effect=AssertionError('started process')):
            with self.assertRaisesRegex(ModelError, 'generate_project.py'):
                run_controller.main()
        self.assertFalse(directory.exists())

    def test_saved_contract_alone_suffices_for_generation(self):
        original = self.agent.read_bytes()
        self.pipeline.unlink()
        self.goal.unlink()
        artifacts.generate_agent(self.workflow, ROOT / 'generator/controller_generic.asl', self.agent)
        self.assertEqual(original, self.agent.read_bytes())

    def test_existing_campaign_has_actionable_error_without_starting_java(self):
        directory = self.root / 'existing'
        directory.mkdir()
        with patch.object(sys, 'argv', ['run_controller.py', '--project-dir', str(self.root),
                                       '--scenario', 'healthy', '--artifacts-dir', str(directory)]), \
             patch.object(run_controller.subprocess, 'run', side_effect=AssertionError('started process')):
            with self.assertRaisesRegex(ModelError, 'fresh --artifacts-dir'):
                run_controller.main()

    def test_forged_hash_cannot_bless_changed_contract_or_input_projection(self):
        original = self.workflow.read_bytes()
        for field in ['capabilities', 'goals']:
            self.workflow.write_bytes(original)
            document = yaml.safe_load(self.workflow.read_text())
            if field == 'capabilities':
                document[field]['actions']['run_job'].append('unmapped')
            else:
                document[field]['goal']['maintain(M)'] = ['production.health == healthy']
            self.workflow.write_text(yaml.safe_dump(document, sort_keys=False), encoding='utf-8')
            record = json.loads(self.manifest.read_text())
            record['workflow_sha256'] = artifacts.digest(self.workflow)
            self.manifest.write_text(json.dumps(record))
            with self.subTest(field=field), self.assertRaisesRegex(ModelError, 'disagree'):
                artifacts.validate(self.root)

    def test_checked_in_payment_artifacts_are_current(self):
        artifacts.validate(ROOT)
