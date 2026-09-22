import unittest
from pathlib import Path
import yaml

try:
    from tools.model_transform import ModelError, parse_model, project_beliefs, transform
except ModuleNotFoundError:
    # Keep direct execution (`py tools/test_model_transform.py`) runnable from
    # the repository root as well as module execution (`py -m tools...`).
    from model_transform import ModelError, parse_model, project_beliefs, transform


ROOT = Path(__file__).resolve().parents[1]


class ModelTransformTest(unittest.TestCase):
    def setUp(self):
        self.pipeline = (ROOT / "parser/fixtures/legacy" / "01_pipeline.yaml").read_text(encoding="utf-8")
        self.goals = (ROOT / "parser/fixtures/legacy" / "02_goal.yaml").read_text(encoding="utf-8")
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
        pipeline_text = self.pipeline.replace("recover_from: production", "recover_from: ghost")
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
        model = parse_model(ROOT / "parser/fixtures/legacy" / "01_pipeline.yaml", ROOT / "parser/fixtures/legacy" / "02_goal.yaml")
        self.assertEqual(model.entities, ("build", "test", "security", "staging", "production", "rollback"))
        self.assertEqual(set(model.dependencies), {
            ("build", "test"), ("test", "security"), ("security", "staging"),
            ("staging", "production"),
        })
        self.assertEqual(model.final_entity, "production")
        self.assertEqual(model.recovery, (("production", "rollback"),))
        self.assertNotIn("rollback", model.required_entities)
        generated = project_beliefs(model)
        self.assertIn("recover_on(production, telemetry_block, rollback).", generated)
        self.assertIn("require_healthy(production).", generated)

    def test_controller_goal_closure_and_observation(self):
        pipeline = ROOT / "parser/fixtures/legacy" / "payment_pipeline.yaml"
        staging = parse_model(pipeline, ROOT / "parser/fixtures/legacy" / "payment_goal_staging.yaml")
        production = parse_model(pipeline, ROOT / "parser/fixtures/legacy" / "payment_goal_production.yaml")
        self.assertEqual(staging.required_entities, ("build", "test", "security", "staging"))
        self.assertNotIn("production", staging.required_entities)
        self.assertEqual(production.required_entities,
                         ("build", "test", "security", "staging", "production"))
        self.assertEqual(production.observations, (("production", "staging"),))
        generated = project_beliefs(production)
        self.assertIn("required(production).", generated)
        self.assertIn("observe_before(production, staging).", generated)

    def test_second_project_uses_same_supported_language(self):
        from workflow_model import compile_inputs
        _, model = compile_inputs(ROOT / "examples" / "reporting_pipeline.yaml",
                                  ROOT / "examples" / "reporting_goal.yaml")
        self.assertEqual(model.entities, ("package", "verify", "preview"))
        self.assertEqual(model.required_entities, model.entities)

    def test_dispatch_workflow_contains_independent_exactly_selected_entities(self):
        workflow = yaml.load((ROOT.parent / ".github" / "workflows" / "entity-execution.yml")
                             .read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        jobs = {name: job for name,job in workflow["jobs"].items() if name not in {"report","candidate_operation"}}
        self.assertEqual(set(jobs), {"build", "test", "security", "staging", "production", "rollback"})
        for entity, job in jobs.items():
            self.assertNotIn("needs", job)
            self.assertEqual(job["if"], f"inputs.entity == '{entity}'")
            checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
            self.assertEqual(checkout["with"]["ref"], "${{ inputs.release_sha }}")
        self.assertEqual(jobs["staging"]["concurrency"]["group"], "payment-deployment-control")
        self.assertEqual(jobs["production"]["concurrency"]["group"], "payment-deployment-control")
        self.assertEqual(jobs["rollback"]["environment"], "production")
        self.assertEqual(jobs["rollback"]["concurrency"]["group"], "payment-deployment-control")
        conventional = yaml.load((ROOT.parent / ".github/workflows/ci-cd.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual({"workflow_dispatch"}, set(conventional["on"]))

    def test_recovery_cannot_be_a_normal_goal_or_dependency(self):
        pipeline, goals = self.write_inputs(self.directory, goals=self.goals.replace("production.status == success", "rollback.status == success"))
        with self.assertRaisesRegex(ModelError, "normal goal"):
            parse_model(pipeline, goals)
        pipeline, goals = self.write_inputs(self.directory, pipeline=self.pipeline.replace("needs: staging", "needs: rollback").replace("    observe_before: staging\n", ""))
        with self.assertRaisesRegex(ModelError, "conditional leaf"):
            parse_model(pipeline, goals)

    def test_recovery_requires_supported_trigger_and_verification(self):
        for text in (self.pipeline.replace("telemetry_block", "invented"), self.pipeline.replace("observe_after: true", "observe_after: false")):
            pipeline, goals = self.write_inputs(self.directory, pipeline=text)
            with self.assertRaises(ModelError):
                parse_model(pipeline, goals)


if __name__ == "__main__":
    unittest.main()
