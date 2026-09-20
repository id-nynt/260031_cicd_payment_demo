"""Run real Jason reasoning with simulated adapters; never contacts GitHub or Docker."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import yaml

ROOT = Path(__file__).resolve().parent
NORMAL = ["build", "test", "security", "staging", "production"]
CASES = [
    ("temporary_fault", "telemetry_transient", NORMAL, "achieved", "not_needed", []),
    ("production_temporary_fault", "production_transient", NORMAL, "achieved", "not_needed", []),
    ("flapping", "telemetry_flapping", NORMAL[:-1], "unknown", "not_attempted", []),
    ("deadline", "observation_deadline", NORMAL[:-1], "unknown", "not_attempted", []),
    ("deterministic_failure", "deterministic_test_failure", ["build", "test"], "stopped", "not_attempted", []),
    ("dispatch_rejected", "dispatch_rejected", ["build"], "stopped", "not_attempted", []),
    ("production_retry", "production_retry", NORMAL + ["production"], "achieved", "not_needed", []),
    ("production_retry_unsafe", "production_retry", NORMAL + ["rollback"], "stopped", "restored", []),
    ("healthy", "healthy", NORMAL, "achieved", "not_needed", []),
    ("staging_only", "healthy", NORMAL[:-1], "achieved", "not_needed", ["--goal", str(ROOT / "examples/staging_goal.yaml")]),
    ("retry", "transient_test_failure", ["build", "test", "test", "security", "staging", "production"], "achieved", "not_needed", []),
    ("exhaustion", "exhausted_test_failure", ["build", "test", "test"], "stopped", "not_attempted", []),
    ("staging_block", "telemetry_block", NORMAL[:-1], "stopped", "not_attempted", []),
    ("delayed", "telemetry_delayed", NORMAL, "achieved", "not_needed", []),
    ("staging_unknown", "telemetry_unknown", NORMAL[:-1], "unknown", "not_attempted", []),
    ("production_failure", "production_failure", NORMAL + ["rollback"], "stopped", "restored", []),
    ("production_unhealthy", "production_unhealthy", NORMAL + ["rollback"], "stopped", "restored", []),
    ("production_unknown", "production_unknown", NORMAL + ["rollback"], "stopped", "restored", []),
    ("rollback_failure", "rollback_failure", NORMAL + ["rollback"], "stopped", "failed", []),
    ("rollback_unhealthy", "rollback_unhealthy", NORMAL + ["rollback"], "stopped", "failed", []),
    ("maintenance_violation", "healthy", NORMAL + ["rollback"], "stopped", "restored", []),
    ("rollback_unknown", "rollback_unknown", NORMAL + ["rollback"], "unknown", "unverified", []),
    ("reconciled_success", "reconciled_success", NORMAL, "achieved", "not_needed", []),
    ("reconciled_failure", "reconciled_failure", ["build", "test", "test", "security", "staging", "production"], "achieved", "not_needed", []),
    ("execution_uncertain", "execution_uncertain", NORMAL, "unknown", "unresolved", []),
    ("baseline_no_recovery", "production_unhealthy", NORMAL, "stopped", "not_attempted", ["--baseline"]),
    ("pause", "healthy", NORMAL, "achieved", "not_needed", ["--pause-after", "security", "--pause-ms", "750"]),
    ("second_project", "healthy", ["package", "verify", "preview"], "achieved", "not_needed",
     ["--pipeline", str(ROOT / "examples/reporting_pipeline.yaml"), "--goal", str(ROOT / "examples/reporting_goal.yaml")]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "bdi/build" / ("recovery-suite-" + uuid.uuid4().hex[:8]))
    parser.add_argument("--case", action="append", choices=[case[0] for case in CASES], help="run only named cases")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # Shortened waits only for this local matrix. The normal live manifest stays unchanged.
    project = yaml.safe_load((ROOT / "models/01_pipeline.yaml").read_text(encoding="utf-8"))
    project["execution"]["observation_attempts"] = 3
    project["execution"]["observation_interval_seconds"] = 0
    project["execution"]["reconciliation_interval_seconds"] = 0
    project["execution"]["retry_interval_seconds"] = 0
    quick = output / "quick-pipeline.yaml"
    quick.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    import copy
    unsafe = copy.deepcopy(project)
    unsafe['jobs']['production']['retry_safe'] = False
    unsafe_path = output / 'unsafe-pipeline.yaml'
    unsafe_path.write_text(yaml.safe_dump(unsafe,sort_keys=False),encoding='utf-8')
    duration_goal = yaml.safe_load((ROOT / "models/02_goal.yaml").read_text(encoding="utf-8"))
    duration_goal['goal']['maintain(M)'] = ['production.duration <= 1','production.health == healthy']
    duration_path = output / 'duration-goal.yaml'
    duration_path.write_text(yaml.safe_dump(duration_goal,sort_keys=False),encoding='utf-8')
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("BDI_") or key in ("GITHUB_TOKEN", "GH_TOKEN"):
            env.pop(key)
    # Generate once per configuration revision, outside the campaign loop.
    configurations = {
        'payment': (quick, ROOT / 'models/02_goal.yaml'),
        'unsafe': (unsafe_path, ROOT / 'models/02_goal.yaml'),
        'staging': (quick, ROOT / 'examples/staging_goal.yaml'),
        'duration': (quick, duration_path),
        'reporting': (ROOT / 'examples/reporting_pipeline.yaml', ROOT / 'examples/reporting_goal.yaml'),
    }
    for key, (pipeline, goal) in configurations.items():
        subprocess.run([sys.executable, str(ROOT / 'generate_project.py'), '--project-dir',
                        str(output / 'projects' / key), '--pipeline', str(pipeline), '--goal', str(goal)],
                       env=env, check=True, stdout=subprocess.DEVNULL)
    rows = []
    for name, scenario, expected, outcome, recovery, extra in CASES:
        if args.case and name not in args.case: continue
        directory = output / name
        key = {'staging_only': 'staging', 'maintenance_violation': 'duration',
               'second_project': 'reporting', 'production_retry_unsafe': 'unsafe'}.get(name, 'payment')
        extra = extra if name not in ('staging_only', 'second_project') else []
        command = [sys.executable, str(ROOT / "run_controller.py"), "--scenario", scenario,
                   "--project-dir", str(output / 'projects' / key),
                   "--artifacts-dir", str(directory), *extra]
        with (output / (name + "-console.log")).open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=ROOT.parent, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        result = json.loads((directory / "controller-result.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (directory / "controller-journal.jsonl").read_text(encoding="utf-8").splitlines()]
        actual = [event["entity"] for event in events if event["event"] == "entity_execution_started"]
        assert actual == expected, (name, expected, actual)
        assert (result["outcome"], result["recovery_outcome"]) == (outcome, recovery), (name, result)
        assert completed.returncode == {"achieved": 0, "stopped": 1, "unknown": 2}[outcome], (name, completed.returncode)
        if recovery in ("restored", "failed", "unverified"):
            assert "production" in result["unmet_goals"]
            assert actual.count("rollback") == 1
            assert any(e["event"] == "bdi_recovery_decision" for e in events)
        if name.startswith("reconciled_"):
            reconciliation = next(e for e in events if e["event"] == "bdi_reconciliation")
            original = next(e for e in events if e["event"] == "entity_execution_finished" and e["entity"] == reconciliation["entity"])
            assert original["execution_id"] == reconciliation["execution_id"]
            assert original["attempt"] == reconciliation["attempt"]
        if name in ("temporary_fault", "production_temporary_fault"):
            assert any(e['event'] == 'telemetry_measurement' and e['round'] >= 3 for e in events)
            assert 'rollback' not in actual
        if name == "pause":
            from datetime import datetime
            paused = next(e for e in events if e["event"] == "controller_pause")
            successor = next(e for e in events if e["event"] == "entity_execution_started" and e["entity"] == "staging")
            assert (datetime.fromisoformat(successor["timestamp"]) - datetime.fromisoformat(paused["timestamp"])).total_seconds() >= 0.70
        ids = [e["execution_id"] for e in events if e["event"] == "entity_execution_finished"]
        assert len(ids) == len(set(ids))
        rows.append({"case": name, "expected": expected, "actual": actual, "outcome": outcome,
                     "recovery": recovery, "telemetry": result["telemetry"], "execution_ids": ids,
                     "achieved_goals": result["achieved_goals"], "unmet_goals": result["unmet_goals"],
                     "manifest": json.loads((directory / "generation-manifest.json").read_text(encoding="utf-8"))})
        (output / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"PASS {name}: {','.join(actual)} -> {outcome}/{recovery}", flush=True)
    print(f"Local scenario evidence: {output}")


if __name__ == "__main__":
    main()
