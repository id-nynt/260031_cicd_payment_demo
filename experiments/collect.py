"""Download one conventional trial, including failed runs, into a fresh evidence folder."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import importlib.util
import os

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--run-id', required=True, type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--no-interventions', action='store_true', help='Operator attests no manual intervention during this trial')
    args = parser.parse_args()
    target = args.output or ROOT/'results/conventional'/str(args.run_id)
    target.mkdir(parents=True, exist_ok=False)
    record = dict(run_id=args.run_id, repository=args.repo, collected_at=datetime.now(timezone.utc).isoformat(), errors=[])
    commands = [
        ('github-run.json', ['view', str(args.run_id), '--json', 'databaseId,headSha,conclusion,status,url,jobs,createdAt,updatedAt']),
        ('github-run.log', ['view', str(args.run_id), '--log']),
        (None, ['download', str(args.run_id), '--dir', str(target/'artifacts')]),
    ]
    for filename, command in commands:
        response = subprocess.run(['gh', 'run', *command, '--repo', args.repo], text=True, encoding='utf-8', errors='replace', capture_output=True)
        if filename:
            (target/filename).write_text(response.stdout, encoding='utf-8')
        if response.returncode:
            record['errors'].append(dict(command=command[:2], message=response.stderr))
    results = list(target.rglob('experiment-metrics.json'))
    run = {}
    try:
        run = json.loads((target/'github-run.json').read_text(encoding='utf-8'))
        if run.get('status') != 'completed':
            record['errors'].append(dict(message='Remote workflow is not terminal; collect again after it finishes'))
    except (OSError, ValueError):
        record['errors'].append(dict(message='Missing or invalid GitHub run metadata'))
    if not results and run.get('status') == 'completed' and not record['errors']:
        try:
            plans=list((target/'artifacts').rglob('plan.json'))
            if len(plans)!=1: raise ValueError('Missing/ambiguous preparation artifact')
            plan=json.loads(plans[0].read_text(encoding='utf-8-sig'))
            if plan.get('workflow_layout')!='six-jobs-v1': raise ValueError('Missing server result for legacy workflow')
            if plan.get('repository')!=args.repo or plan['comparison']['worker_sha']!=run['headSha']:
                raise ValueError('Collected workflow identity differs from plan')
            import sys
            sys.path.insert(0,str(ROOT.parent/'ci-cd-conventional'))
            spec=importlib.util.spec_from_file_location('native_collector',ROOT.parent/'ci-cd-conventional/native-experiment.py')
            native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
            # Offline aggregation: no dispatch, API calls, health requests or repair.
            os.environ['GITHUB_REPOSITORY']=args.repo
            os.environ['GITHUB_RUN_ID']=str(args.run_id)
            native.finish(target/'artifacts/native-result/result',target/'artifacts',remote=run)
            results=list(target.rglob('experiment-metrics.json'))
        except Exception as error:
            record['errors'].append(dict(message='Offline aggregation failed: '+str(error)))
    record['metrics_found'] = len(results)
    record['complete_download'] = not record['errors'] and len(results) == 1
    if args.no_interventions:
        for metrics in results:
            companion = Path(str(metrics.parent)+'-experiment')
            companion.mkdir(exist_ok=True)
            (companion/'interventions.json').write_text('[]\n', encoding='utf-8')
            # Preserve server metrics; create a separate operator annotation.
        (target/'interventions.json').write_text('[]\n', encoding='utf-8')
    (target/'collection.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(target.resolve())
    if not record['complete_download']:
        raise SystemExit('Incomplete evidence retained; inspect collection.json. Do not delete this trial.')


if __name__ == '__main__':
    main()
