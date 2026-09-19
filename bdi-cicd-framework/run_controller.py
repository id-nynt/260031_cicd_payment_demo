"""Validate, generate, and start the BDI CI/CD controller with one command."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "parser"))
from model_transform import ModelError, generation_manifest, parse_model, transform  # noqa: E402


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
    sources = controller.get("release_sources", {})
    recovery = {target for _, target in model.recovery}
    if set(sources) != recovery or any(value != "known_good" for value in sources.values()):
        raise ModelError("controller.release_sources must map every recovery entity to known_good")
    observed = {source for _, source in model.observations} | set(model.observe_after)
    observed.update(item.entity for item in model.maintenance if item.property == "health")
    if observed - set(controller.get("environments", {})):
        raise ModelError("Every observed entity requires a controller.environments mapping")
    for source, target in model.recovery:
        if controller["environments"].get(source) != controller["environments"].get(target):
            raise ModelError("Recovery must restore the same environment as its source")


def known_good_sha(receipt: Path, project: Path, model, repository: str) -> str:
    data = json.loads(receipt.read_text(encoding="utf-8"))
    config = load_mapping(project)
    if data.get("mode") != "github" or data.get("outcome") != "achieved" or data.get("project") != config["project"] or data.get("repository") != repository:
        raise ModelError("Known-good receipt must be an achieved live campaign for this project/repository")
    sha = data.get("release_sha", "")
    import re
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ModelError("Known-good receipt requires an immutable 40-character commit SHA")
    for source, _ in model.recovery:
        if source in model.required_entities:
            verified = data.get("verified_releases", {}).get(source, {})
            if verified.get("release_sha") != sha or not verified.get("github_run_id") or verified.get("environment") != config["controller"]["environments"].get(source):
                raise ModelError(f"Receipt does not verify recovery source {source} in the same environment")
    return sha


def git_sha(repository_root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository_root,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=ROOT / "models" / "01_pipeline.yaml")
    parser.add_argument("--goal", type=Path, default=ROOT / "models" / "02_goal.yaml")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--scenario", choices=["healthy", "transient_test_failure", "exhausted_test_failure",
                                                "telemetry_block", "telemetry_unknown", "telemetry_delayed",
                                                "production_failure", "production_unhealthy", "production_unknown",
                                                "rollback_failure", "rollback_unknown", "execution_uncertain"])
    parser.add_argument("--known-good", type=Path, help="achieved live campaign result verifying the baseline release")
    parser.add_argument("--baseline", action="store_true", help="explicit first baseline run without prior recovery release")
    parser.add_argument("--confirm-compatible-rollback", action="store_true", help="confirm source rollback is compatible with retained database schema/data")
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
    workflow = ROOT / "models" / "03_workflow_model.yaml"
    beliefs = ROOT / "generator" / "controller_project.asl"
    agent = ROOT / "bdi" / "controller_agent.asl"
    campaign = os.environ.get("BDI_CAMPAIGN_ID", "campaign-" + uuid.uuid4().hex[:12])
    artifacts = (args.artifacts_dir.resolve() if args.artifacts_dir else
                 ROOT / "bdi" / "build" / "controller-runs" / campaign)
    manifest = artifacts / "generation-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    model = parse_model(pipeline, goal)
    validate_mapping(model, project)
    if any(set(job) & {"steps", "runs-on", "timeout-minutes", "if"} for job in load_mapping(pipeline)["jobs"].values()):
        raise ModelError("Controller pipeline supports logical jobs only; put runner commands in the dispatch workflow")
    transform(pipeline, goal, workflow, beliefs, agent, ROOT / "generator" / "controller_generic.asl")
    (ROOT / "models" / "controller_workflow_model.yaml").write_text(workflow.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    manifest.write_text(generation_manifest(pipeline, goal, project, model), encoding="utf-8", newline="\n")
    print(f"Generated controller for goals {[item.entity for item in model.achievements]}; required={list(model.required_entities)}")
    if args.generate_only:
        return 0

    baseline_sha = ""
    recovery_required = any(source in model.required_entities for source, _ in model.recovery)
    if args.baseline and args.known_good:
        raise ModelError("Choose --baseline or --known-good, not both")
    if args.scenario and not args.baseline:
        baseline_sha = "1" * 40  # Explicitly simulated; never accepted as a live receipt.
    elif args.known_good:
        if not args.confirm_compatible_rollback:
            raise ModelError("Source rollback requires --confirm-compatible-rollback; no database rollback is performed")
        baseline_sha = known_good_sha(args.known_good, project, model, os.environ.get("GITHUB_REPOSITORY", ""))
    elif recovery_required and not args.baseline:
        raise ModelError("Provide --known-good verified-result.json, or --baseline for the initial known-good deployment")

    repository_root = ROOT.parent
    environment = os.environ.copy()
    environment["BDI_GUI"] = str(args.gui).lower()
    environment.pop("BDI_SCENARIO", None)
    environment["BDI_KNOWN_GOOD_SHA"] = baseline_sha
    environment["BDI_GOALS"] = json.dumps([item.entity for item in model.achievements])
    environment["BDI_HEALTH_GOALS"] = json.dumps([item.entity for item in model.maintenance if item.property == "health"])
    environment["BDI_MANIFEST_FILE"] = str(manifest)
    environment["BDI_PROJECT_FILE"] = str(project)
    environment["BDI_CAMPAIGN_ID"] = campaign
    environment.setdefault("BDI_RELEASE_SHA", git_sha(repository_root))
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record.update({"release_sha": environment["BDI_RELEASE_SHA"], "known_good_sha": baseline_sha,
                   "controller_source_sha": git_sha(repository_root),
                   "generated_agent_sha256": hashlib.sha256(agent.read_bytes()).hexdigest(),
                   "generic_policy_sha256": hashlib.sha256((ROOT / "generator/controller_generic.asl").read_bytes()).hexdigest()})
    source_files = [ROOT / "run_controller.py", ROOT / "parser/model_transform.py",
                    ROOT.parent / ".github/workflows/entity-execution.yml", *sorted((ROOT / "bdi/harness").glob("*.java"))]
    record["source_files_sha256"] = {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
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
    # The repository wrapper may be checked out without an executable bit.
    command = ([str(wrapper)] if os.name == "nt" else ["bash", str(wrapper)]) + ["--no-daemon", "runController"]
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
