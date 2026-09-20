import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_controller import ModelError, known_good_sha, validate_live_environment
from workflow_model import compile_inputs


class ControllerInputsTest(unittest.TestCase):
    def setUp(self):
        document, self.model = compile_inputs(ROOT / "models/01_pipeline.yaml", ROOT / "models/02_goal.yaml")
        self.project = document["runtime"]
        self.sha = "a" * 40
        self.receipt = {"mode": "github", "outcome": "achieved", "project": "payment-service",
                        "repository": "example/demo", "release_sha": self.sha,
                        "verified_releases": {"production": {"release_sha": self.sha,
                            "github_run_id": 123, "environment": "production"}}}

    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "receipt.json"
            receipt.write_text(json.dumps(data), encoding="utf-8")
            return known_good_sha(receipt, self.project, self.model, "example/demo")

    def test_live_environment_rejects_missing_or_malformed_credentials_without_echoing(self):
        for token in ['', chr(22), 'secret\nvalue', 'secret value']:
            with self.subTest(token_length=len(token)):
                with self.assertRaises(ModelError) as error:
                    validate_live_environment({'GITHUB_REPOSITORY': 'example/demo', 'GITHUB_TOKEN': token})
                if token: self.assertNotIn(token, str(error.exception))
        with self.assertRaisesRegex(ModelError, 'GITHUB_REPOSITORY'):
            validate_live_environment({'GITHUB_TOKEN': 'test-token'})
        validate_live_environment({'GITHUB_REPOSITORY': 'example/demo', 'GITHUB_TOKEN': 'test-token'})

    def test_verified_live_baseline_is_accepted(self):
        self.assertEqual(self.read(self.receipt), self.sha)

    def test_fixture_failed_or_foreign_receipt_cannot_enable_live_recovery(self):
        for field, value in [("mode", "scenario"), ("outcome", "stopped"),
                             ("repository", "other/repo"), ("release_sha", "main")]:
            data = copy.deepcopy(self.receipt)
            data[field] = value
            with self.assertRaises(ModelError):
                self.read(data)

    def test_wrong_environment_or_missing_verification_is_rejected(self):
        for field, value in [("environment", "staging"), ("github_run_id", 0), ("release_sha", "b" * 40)]:
            data = copy.deepcopy(self.receipt)
            data["verified_releases"]["production"][field] = value
            with self.assertRaises(ModelError):
                self.read(data)



if __name__ == "__main__":
    unittest.main()
