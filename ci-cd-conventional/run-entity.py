"""One mechanical attempt; the YAML decides ordering and bounded retries."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def status_for(code, failure_mode='none'):
    if code==75 and failure_mode!='transient_failure': return 'failure'
    if code==124 and failure_mode!='deployment_timeout': return 'failure'
    return {0: 'success', 75: 'transient_failure', 124: 'timeout'}.get(code, 'failure')


def run(entity, attempt, app, directory):
    directory.mkdir(parents=True, exist_ok=True)
    identity = f'native-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{entity}-{attempt}'
    env = dict(os.environ, ENTITY=entity, CI_RUN_ID=identity)
    if attempt > 1 and env.get('FAILURE_MODE') == 'transient_failure':
        env['FAILURE_MODE'] = 'none'
    started = datetime.now(timezone.utc).isoformat()
    # Refuse replay of a locally started attempt, even if its receipt was lost.
    with (directory/f'intent-{attempt}.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(execution_id=identity, started_at=started), stream)
    clock = time.monotonic()
    process = subprocess.Popen(['bash', str(ROOT/'scripts/execute-entity.sh')], cwd=app, env=env, start_new_session=True)
    try:
        status = status_for(process.wait(timeout=60 if env.get('FAILURE_MODE')=='deployment_timeout' else 1200), env.get('FAILURE_MODE','none'))
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        # An actual timeout may have changed the deployment: never retry blindly.
        status = 'timeout' if env.get('FAILURE_MODE')=='deployment_timeout' else 'unknown'
    finished = datetime.now(timezone.utc).isoformat()
    receipt = dict(entity=entity, attempt=attempt, status=status, executionId=identity,
                   githubRunId=int(env['GITHUB_RUN_ID']), release_sha=env['RELEASE_SHA'],
                   started_at=started, completed_at=finished, failure_mode=env.get('FAILURE_MODE','none'),
                   durationMs=(time.monotonic()-clock)*1000)
    path = directory/f'attempt-{attempt}.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f'status={status}\nexecution_id={identity}\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entity', required=True, choices=['build','test','security','staging','production','rollback'])
    parser.add_argument('--attempt', required=True, type=int, choices=[1,2])
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    run(args.entity, args.attempt, args.app, args.directory)
