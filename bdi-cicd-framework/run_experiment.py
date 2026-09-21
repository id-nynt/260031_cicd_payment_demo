"""Manually launch ONE comparative trial; automatically coordinate traffic and evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import urllib.request
import urllib.parse
from project_artifacts import ROOT, validate, digest, ModelError
from run_controller import conventional_policy, known_good_sha, validate_live_environment
from workflow_model import runtime_settings
from experiment_metrics import extract
from experiment_protocol import protocol_key

CATALOG = json.loads((ROOT.parent/'scripts/experiment-scenarios.json').read_text())
CASES = {name: (case['entity'], case['profile'], case['fault']) for name, case in CATALOG.items()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mechanism', required=True, choices=['bdi', 'conventional'])
    parser.add_argument('--case', required=True, choices=CASES)
    parser.add_argument('--release-sha', required=True)
    parser.add_argument('--known-good', required=True, type=Path)
    parser.add_argument('--confirm-compatible-rollback', action='store_true', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--artifacts-dir', type=Path)
    parser.add_argument('--prepare-only', action='store_true', help='Write a reviewable plan only; no launch/traffic')
    args = parser.parse_args()
    if not 0 <= args.seed <= 4294967295: raise ModelError('Seed must be an unsigned 32-bit integer')
    if not re.fullmatch('[0-9a-f]{40}', args.release_sha): raise ModelError('Supply the published 40-character candidate SHA, not a tag or local HEAD')
    document, model, manifest, inputs = validate(ROOT)
    # Both mechanisms must use exactly the contract supported by the conventional comparator.
    policy = conventional_policy(document)
    config = runtime_settings(document)
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('BDI_') and key not in ('BDI_WORKFLOW_REF',): env.pop(key)
    if not args.prepare_only: validate_live_environment(env)
    if not env.get('GITHUB_REPOSITORY') or not env.get('BDI_WORKFLOW_REF'): raise ModelError('Set GITHUB_REPOSITORY and BDI_WORKFLOW_REF before preparing a trial')
    baseline_sha = known_good_sha(args.known_good, config, model, env['GITHUB_REPOSITORY'])
    worker_sha = None
    if not args.prepare_only:
        # Confirm publication before any dispatch; record the resolved worker revision.
        def remote_commit(ref):
            url = 'https://api.github.com/repos/' + env['GITHUB_REPOSITORY'] + '/commits/' + urllib.parse.quote(ref, safe='')
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + env['GITHUB_TOKEN'],
                'Accept': 'application/vnd.github+json', 'User-Agent': 'payment-comparison-preflight'})
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)['sha']
        if remote_commit(args.release_sha) != args.release_sha:
            raise ModelError('Candidate is not the expected published commit')
        worker_sha = remote_commit(env['BDI_WORKFLOW_REF'])
        # GitHub workflow_dispatch expects a branch/tag ref; retain that ref and record its resolved SHA.

    entity, profile, fault = CASES[args.case]
    campaign = (args.artifacts_dir or ROOT/'runs'/f'{datetime.now().strftime("%Y%m%d-%H%M%S")}-{args.mechanism}-{args.case}-{uuid.uuid4().hex[:6]}').resolve()
    if campaign.exists(): raise ModelError('Use a new campaign directory')
    companion = Path(str(campaign)+'-experiment')
    companion.mkdir(parents=True, exist_ok=False)
    fault_file = companion/'faults.properties'
    fault_file.write_text(fault+'\n')
    env['BDI_EXECUTION_PLAN'] = str(fault_file)
    env['BDI_RELEASE_SHA'] = args.release_sha
    traffic_profile = ROOT.parent/'scripts/traffic-scenarios'/f'{profile}.json' if profile else None
    sources = {str(p.relative_to(ROOT.parent)): digest(p) for p in [
        ROOT/'run_controller.py', ROOT/'run_experiment.py', ROOT/'experiment_metrics.py',
        ROOT.parent/'scripts/run-traffic-scenario.mjs', *sorted((ROOT/'bdi/harness').glob('*.java'))]}
    comparison = dict(case=args.case, seed=args.seed, candidate=args.release_sha, baseline=baseline_sha,
        repository=env['GITHUB_REPOSITORY'], worker=env['BDI_WORKFLOW_REF'], worker_sha=worker_sha, contract=digest(ROOT/'models/03_workflow_model.yaml'),
        policy=policy, profile=digest(traffic_profile) if traffic_profile else None, pause_ms=60000,
        sources=sources)
    plan = dict(schema_version=1, prepared_at=datetime.now(timezone.utc).isoformat(), mechanism=args.mechanism,
        case=args.case, seed=args.seed, campaign=str(campaign), thresholds=policy['thresholds'],
        traffic_required=profile is not None, fault_expected=bool(profile and 'errors' in profile),
        comparison=comparison, comparison_key=hashlib.sha256(json.dumps(comparison,sort_keys=True).encode()).hexdigest(),
        known_good_receipt=str(args.known_good.resolve()), baseline_receipt_sha256=digest(args.known_good),
        limitations=['Reset is operator-confirmed; no database snapshot restoration', 'Local controller with remote selected jobs; native GitHub DAG is a separate entry point'])
    plan['protocol_key'] = protocol_key(args.case,args.seed,args.release_sha,baseline_sha,worker_sha,comparison['contract'],policy,{'selected':comparison['profile'],'healthy':digest(ROOT.parent/'scripts/traffic-scenarios/healthy.json')})
    (companion/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(f'Campaign: {campaign}\nPlan: {companion / "plan.json"}', flush=True)
    if args.prepare_only:
        print('Prepared only. No controller or traffic launched. Use a NEW path for the live launch.'); return 0
    command = [sys.executable,'-B',str(ROOT/'run_controller.py'),'--mechanism',args.mechanism,'--known-good',str(args.known_good.resolve()),
        '--confirm-compatible-rollback','--artifacts-dir',str(campaign),'--pause-after','staging,production','--pause-ms','60000']
    traffic = []
    try:
        for traffic_entity in ['staging','production']:
            selected_profile = profile if traffic_entity == entity and profile else 'healthy'
            traffic_output = str(campaign)+'-traffic' if traffic_entity == entity else str(campaign)+'-traffic-'+traffic_entity
            traffic.append(subprocess.Popen(['node', str(ROOT.parent/'scripts/run-traffic-scenario.mjs'), '--campaign',str(campaign),
                '--scenario',selected_profile,'--entity',traffic_entity,'--seed',str(args.seed),'--output',traffic_output],cwd=ROOT.parent))
        with (companion/'controller-console.log').open('w', encoding='utf-8') as console_log:
            process = subprocess.Popen(command,cwd=ROOT.parent,env=env,stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            for line in process.stdout:
                console_log.write(line);console_log.flush();print(line,end='',flush=True)
            process.wait()
        for client in traffic:
            try: client.wait(timeout=10)
            except subprocess.TimeoutExpired:
                client.terminate(); client.wait()
        if campaign.exists():
            row=extract(campaign)
            (campaign/'experiment-metrics.json').write_text(json.dumps(row,indent=2)+'\n')
            print(json.dumps(row,indent=2))
        return process.returncode
    finally:
        for client in traffic:
            if client.poll() is None: client.terminate(); client.wait()

if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ModelError, OSError, ValueError, KeyboardInterrupt) as error:
        print(f'Experiment stopped: {error}. If a controller was interrupted, reconcile before another trial.',file=sys.stderr)
        raise SystemExit(2)
