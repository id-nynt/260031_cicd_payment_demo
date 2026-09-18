import unittest
from pathlib import Path
import yaml

try:
    from tools.model_transform import ModelError, parse_model, transform
except ModuleNotFoundError:
    # Keep direct execution (`py tools/test_model_transform.py`) runnable from
    # the repository root as well as module execution (`py -m tools...`).
    from model_transform import ModelError, parse_model, transform


ROOT = Path(__file__).resolve().parents[1]


class ModelTransformTest(unittest.TestCase):
    def setUp(self):
        self.pipeline = (ROOT / "models" / "01_pipeline.yaml").read_text(encoding="utf-8")
        self.goals = (ROOT / "models" / "02_goal.yaml").read_text(encoding="utf-8")
        self.directory = ROOT / "parser" / "testdata"

    def tearDown(self):
        for path in self.directory.iterdir():
            if path.name != ".gitkeep":
                path.unlink()

    def write_inputs(self, directory, pipeline=None, goals=None):
        pipeline_path = directory / "pipeline.yaml"
        goals_path = directory / "goals.yaml"
        pipeline_path.write_text(pipeline or self.pipeline, encoding="utf-8")
        goals_path.write_text(goals or self.goals, encoding="utf-8")
        return pipeline_path, goals_path

    def test_valid_pipeline(self):
        pipeline, goals = self.write_inputs(self.directory)
        model = parse_model(pipeline, goals)
        self.assertEqual(model.entities[0], "build")
        self.assertEqual(model.final_entity, "production")
        self.assertEqual(model.max_retries, 1)

    def test_unknown_dependency(self):
        pipeline, goals = self.write_inputs(self.directory, self.pipeline.replace("needs: build", "needs: missing"))
        with self.assertRaisesRegex(ModelError, "unknown dependency"):
            parse_model(pipeline, goals)

    def test_cyclic_dependency(self):
        cyclic = self.pipeline.replace("  test:\n    needs: build", "  test:\n    needs: security")
        pipeline, goals = self.write_inputs(self.directory, cyclic)
        with self.assertRaisesRegex(ModelError, "cyclic dependency"):
            parse_model(pipeline, goals)

    def test_unknown_goal_entity(self):
        goals_text = self.goals.replace("production.status == success", "missing.status == success", 1)
        pipeline, goals = self.write_inputs(self.directory, goals=goals_text)
        with self.assertRaisesRegex(ModelError, "unknown entity"):
            parse_model(pipeline, goals)

    def test_unknown_observable(self):
        goals_text = self.goals.replace("production.duration <= 100000", "production.throughput <= 100000")
        pipeline, goals = self.write_inputs(self.directory, goals=goals_text)
        with self.assertRaisesRegex(ModelError, "unsupported observable property"):
            parse_model(pipeline, goals)

    def test_malformed_comparison(self):
        goals_text = self.goals.replace("production.duration <= 100000", "production.duration")
        pipeline, goals = self.write_inputs(self.directory, goals=goals_text)
        with self.assertRaisesRegex(ModelError, "malformed comparison"):
            parse_model(pipeline, goals)

    def test_recovery_target_validation(self):
        pipeline_text = self.pipeline.replace("needs.production.result == 'failure'", "needs.ghost.result == 'failure'")
        pipeline, goals = self.write_inputs(self.directory, pipeline_text)
        with self.assertRaises(ModelError):
            parse_model(pipeline, goals)

    def test_retry_policy_and_goal_translation(self):
        directory = self.directory
        pipeline, goals = self.write_inputs(directory)
        workflow = directory / "workflow.yaml"
        beliefs = directory / "beliefs.asl"
        model = transform(pipeline, goals, workflow, beliefs)
        self.assertIn("max_retries: 1", workflow.read_text(encoding="utf-8"))
        generated = beliefs.read_text(encoding="utf-8")
        self.assertIn("achievement(production, success).", generated)
        self.assertIn("max_duration(production, 100000).", generated)
        self.assertIn("avoid_missing(production, test).", generated)
        self.assertEqual(model.final_entity, "production")

    def test_deterministic_output(self):
        directory = self.directory
        pipeline, goals = self.write_inputs(directory)
        first_workflow, first_beliefs, first_agent = directory / "one.yaml", directory / "one.asl", directory / "one-agent.asl"
        second_workflow, second_beliefs, second_agent = directory / "two.yaml", directory / "two.asl", directory / "two-agent.asl"
        generic = ROOT / "generator" / "bdi_generic.asl"
        transform(pipeline, goals, first_workflow, first_beliefs, first_agent, generic)
        transform(pipeline, goals, second_workflow, second_beliefs, second_agent, generic)
        self.assertEqual(first_workflow.read_bytes(), second_workflow.read_bytes())
        self.assertEqual(first_beliefs.read_bytes(), second_beliefs.read_bytes())
        self.assertEqual(first_agent.read_bytes(), second_agent.read_bytes())

    def test_real_payment_workflow_mapping(self):
        payment_root = ROOT.parent
        model = parse_model(payment_root / ".github" / "workflows" / "ci-cd.yml",
                            ROOT / "models" / "payment_goal.yaml",
                            ROOT / "models" / "payment_project.yaml")
        self.assertEqual(model.entities, ("build", "test", "security", "staging", "production"))
        self.assertEqual(set(model.dependencies), {
            ("build", "security"), ("test", "security"),
            ("build", "staging"), ("test", "staging"), ("security", "staging"),
            ("staging", "production"),
        })
        self.assertEqual(model.final_entity, "production")

        workflow = yaml.load((payment_root / ".github" / "workflows" / "ci-cd.yml").read_text(encoding="utf-8"),
                             Loader=yaml.BaseLoader)
        jobs = workflow["jobs"]
        self.assertEqual(jobs["bdi-gate"]["needs"], "deploy-staging")
        self.assertEqual(jobs["deploy-production"]["needs"], "bdi-gate")
        self.assertEqual(jobs["bdi-gate"]["permissions"]["actions"], "read")
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["experiment_mode"]["options"],
                         ["normal", "high_error_rate"])


if __name__ == "__main__":
    unittest.main()
