"""Validate, generate, and start the BDI CI/CD controller with one command."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "parser"))
from model_transform import ModelError, generation_manifest, transform  # noqa: E402


def load_mapping(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ModelError(f"{path}: top level must be a mapping")
    return value


def resolve_project(pipeline: Path, override: Path | None) -> Path:
    if override is not None:
        return override.resolve()
    name = load_mapping(pipeline).get("project_file")
    if not isinstance(name, str) or not name:
        raise ModelError("pipeline.project_file is required unless --project is supplied")
    return (pipeline.parent / name).resolve()


def validate_mapping(model, project: Path) -> None:
    root = load_mapping(project)
    controller = root.get("controller")
    if not isinstance(controller, dict) or not isinstance(controller.get("jobs"), dict):
        raise ModelError(f"{project}: controller.jobs mapping is required")
    configured = set(controller["jobs"])
    entities = set(model.entities)
    if configured != entities:
        raise ModelError(f"controller.jobs must exactly map pipeline entities; missing={sorted(entities-configured)}, extra={sorted(configured-entities)}")


def git_sha(repository_root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository_root,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=ROOT / "models" / "payment_pipeline.yaml")
    parser.add_argument("--goal", type=Path, default=ROOT / "models" / "payment_goal_production.yaml")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--scenario", choices=["healthy", "transient_test_failure", "exhausted_test_failure",
                                                "telemetry_block", "telemetry_unknown", "telemetry_delayed"])
    parser.add_argument("--artifacts-dir", type=Path,
                        help="directory for this campaign's manifest, journal, result, and lock")
    parser.add_argument("--pause-after", help="scenario entity after which to pause before returning its result")
    parser.add_argument("--pause-ms", type=int, default=0)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--gui", action="store_true", help="open Jason MAS Console and keep the final agent mind available until closed")
    args = parser.parse_args()

    pipeline = args.pipeline.resolve()
    goal = args.goal.resolve()
    project = resolve_project(pipeline, args.project)
    workflow = ROOT / "models" / "controller_workflow_model.yaml"
    beliefs = ROOT / "generator" / "controller_project.asl"
    agent = ROOT / "bdi" / "controller_agent.asl"
    campaign = os.environ.get("BDI_CAMPAIGN_ID", "campaign-" + uuid.uuid4().hex[:12])
    artifacts = (args.artifacts_dir.resolve() if args.artifacts_dir else
                 ROOT / "bdi" / "build" / "controller-runs" / campaign)
    manifest = artifacts / "generation-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    model = transform(pipeline, goal, workflow, beliefs, agent, ROOT / "generator" / "controller_generic.asl")
    validate_mapping(model, project)
    manifest.write_text(generation_manifest(pipeline, goal, project, model), encoding="utf-8", newline="\n")
    print(f"Generated controller for goals {[item.entity for item in model.achievements]}; required={list(model.required_entities)}")
    if args.generate_only:
        return 0

    repository_root = ROOT.parent
    environment = os.environ.copy()
    environment["BDI_GUI"] = str(args.gui).lower()
    environment.pop("BDI_SCENARIO", None)
    environment["BDI_PROJECT_FILE"] = str(project)
    environment["BDI_CAMPAIGN_ID"] = campaign
    environment.setdefault("BDI_RELEASE_SHA", git_sha(repository_root))
    environment.setdefault("BDI_JOURNAL_FILE", str(artifacts / "controller-journal.jsonl"))
    environment.setdefault("BDI_RESULT_FILE", str(artifacts / "controller-result.json"))
    # One repository-wide lock prevents concurrent campaigns controlling the same targets.
    environment.setdefault("BDI_LOCK_FILE", str(ROOT / "bdi" / "build" / "controller.lock"))
    if args.scenario:
        environment["BDI_SCENARIO"] = args.scenario
    if args.pause_after:
        environment["BDI_PAUSE_AFTER_ENTITY"] = args.pause_after
        environment["BDI_PAUSE_MILLISECONDS"] = str(args.pause_ms)
    wrapper = ROOT / "bdi" / ("gradlew.bat" if os.name == "nt" else "gradlew")
    command = [str(wrapper), "--no-daemon", "runController"]
    process = subprocess.run(command, cwd=ROOT / "bdi", env=environment)
    result_path = Path(environment["BDI_RESULT_FILE"])
    if not result_path.exists():
        return process.returncode or 2
    outcome = json.loads(result_path.read_text(encoding="utf-8")).get("outcome", "unknown")
    return {"achieved": 0, "stopped": 1, "unknown": 2}.get(outcome, 2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ModelError, OSError, subprocess.CalledProcessError) as error:
        print(f"controller startup failed: {error}", file=sys.stderr)
        raise SystemExit(2)
