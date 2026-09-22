"""Read-only local comparison with a published/fetched control commit; never dispatch."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def control_files(root=ROOT, scope='paired'):
    patterns = [
        '.github/workflows/ci-cd.yml', '.github/workflows/conventional-*.yml',
        '.github/workflows/entity-execution.yml', 'ci-cd-conventional/workflows/*.yml',
        'ci-cd-conventional/config.json', 'ci-cd-conventional/snapshots/*',
        'ci-cd-conventional/configuration.py', 'ci-cd-conventional/native-experiment.py',
        'scripts/native-experiment.py', 'scripts/candidate-repair.py', 'scripts/execute-entity.sh',
        'ci-cd-conventional/run-entity.py', 'experiments/record_trial.py', 'experiments/dispatch_trial.py', 'experiments/collect.py',
        'scripts/run-traffic-scenario.mjs', 'scripts/traffic-scenarios/*.json',
        'experiments/scenarios.json', 'experiments/experiment_metrics.py',
        'experiments/experiment_protocol.py', 'experiments/control_revision.py', 'experiments/evaluate_study.py',
    ]
    if scope == 'paired':
        patterns += ['bdi-cicd-framework/models/*.yaml', 'bdi-cicd-framework/config/*.yaml',
            'bdi-cicd-framework/models/generation-manifest.json',
            'bdi-cicd-framework/generator/controller_generic.asl',
            'bdi-cicd-framework/parser/model_transform.py', 'bdi-cicd-framework/parser/workflow_model.py',
            'bdi-cicd-framework/bdi/controller_agent.asl', 'bdi-cicd-framework/bdi/controller.mas2j',
            'bdi-cicd-framework/bdi/build.gradle', 'bdi-cicd-framework/bdi/logging*.properties',
            'bdi-cicd-framework/bdi/harness/*.java', 'bdi-cicd-framework/monitoring/**/*.java',
            'bdi-cicd-framework/actions/**/*.java']
        patterns += ['bdi-cicd-framework/' + name + '.py' for name in
            ('run_controller', 'run_experiment', 'project_artifacts', 'generate_project',
             'experiment_metrics', 'experiment_protocol')]
    files = set()
    for pattern in patterns:
        matches = [p for p in root.glob(pattern) if p.is_file()]
        if not matches and not any(c in pattern for c in '*?['):
            raise ValueError('Missing control file: ' + pattern)
        files.update(matches)
    return sorted(files)


def verify_control_revision(worker_sha, root=ROOT, scope='paired'):
    if not re.fullmatch(r'[0-9a-fA-F]{40}', worker_sha):
        raise ValueError('Use the resolved full worker commit SHA, not a tag or placeholder')
    hashes, changed = {}, []
    for path in control_files(root, scope):
        relative = path.relative_to(root).as_posix()
        frozen = subprocess.run(['git', 'show', f'{worker_sha}:{relative}'], cwd=root,
                                capture_output=True, encoding='utf-8')
        current = path.read_text(encoding='utf-8')
        if frozen.returncode or frozen.stdout != current:
            changed.append(relative)
        hashes[relative] = hashlib.sha256(current.encode('utf-8')).hexdigest()
    if changed:
        raise ValueError('Control revision is absent locally or differs from these files:\n' +
                         '\n'.join(changed) + '\nFetch the published commit if missing; otherwise review, commit and publish a NEW control tag. Keep existing app SHAs.')
    return hashes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-sha', required=True)
    parser.add_argument('--scope', choices=['paired', 'conventional'], default='paired')
    args = parser.parse_args()
    try:
        hashes = verify_control_revision(args.worker_sha, scope=args.scope)
        print(f'Control revision verified: {len(hashes)} files ({args.scope})')
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
