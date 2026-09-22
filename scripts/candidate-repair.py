"""Shared mechanical candidate diagnosis/restart. No recovery-policy decisions here."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def now(): return datetime.now(timezone.utc).isoformat()
def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=20).strip()

def container(project, service):
    # Do not rely on multiple label filters being intersected by every engine.
    # Include stopped containers, then enforce exact labels locally. Never choose
    # the first match or fall back to a different Compose project.
    ids=docker('ps','-aq','--no-trunc','--filter',f'label=com.docker.compose.project={project}').split()
    inspected=json.loads(docker('inspect',*ids)) if ids else []
    matches=[item for item in inspected
             if item.get('Config',{}).get('Labels',{}).get('com.docker.compose.project')==project
             and item.get('Config',{}).get('Labels',{}).get('com.docker.compose.service')==service
             and item.get('Config',{}).get('Labels',{}).get('com.docker.compose.oneoff','false').lower()!='true']
    if len(matches)!=1:
        raise ValueError(f'Missing or ambiguous target container: project={project}, service={service}, exact_matches={len(matches)}')
    return matches[0]

def inspect_target(project, app, dependency, expected):
    target=container(project,app)
    variables=dict(item.split('=',1) for item in target['Config']['Env'] if '=' in item)
    if variables.get('CI_RUN_ID')!=expected: raise ValueError('Candidate deployment identity mismatch')
    dep=container(project,dependency)
    dep_env=dict(item.split('=',1) for item in dep.get('Config',{}).get('Env',[]) if '=' in item)
    db_user=dep_env.get('POSTGRES_USER','postgres')
    db_name=dep_env.get('POSTGRES_DB',db_user)
    # A running database alone does not establish readiness.
    ready=dep['State'].get('Running',False) and subprocess.run(
        ['docker','exec',dep['Id'],'pg_isready','-U',db_user,'-d',db_name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10).returncode==0
    state='running' if target['State'].get('Running') else 'stopped'
    if target['State'].get('Paused') or target['State'].get('Restarting'): state='unknown'
    return dict(container_id=target['Id'], deployment_execution_id=expected, app_state=state, dependency_ready=bool(ready))

def operate(action, project, app, dependency, expected, base_url, verification_seconds, inject_failure=False):
    before=inspect_target(project,app,dependency,expected)
    result=dict(action=action, observed_at=now(), before=before, status='observed')
    if action=='diagnose': return result
    if before['app_state']!='stopped' or not before['dependency_ready']:
        return dict(result,status='not_applicable')
    # Recheck immediately before the side effect; never restart an unrelated deployment.
    current=inspect_target(project,app,dependency,expected)
    if current!=before: return dict(result,status='not_applicable')
    docker('start',before['container_id'])
    result['restarted_at']=now()
    if inject_failure:
        docker('stop',before['container_id'])
        return dict(result,status='failed',after=inspect_target(project,app,dependency,expected))
    # Fill the common telemetry window with same-release synthetic payment observations.
    # These are probes, not a declaration that the release is healthy.
    deadline=time.monotonic()+verification_seconds
    result['probe_successes']=0
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(base_url+'/health',timeout=5) as response: health=json.load(response)
        except Exception:
            time.sleep(1)
            continue
        if health.get('deploymentRunId')!=expected: raise ValueError('Deployment changed during repair verification')
        request=urllib.request.Request(base_url+'/payments',data=json.dumps({
            'amount':5000,'currency':'AUD','description':'Repair verification',
            'payerName':'Demo Customer','payerEmail':'demo@example.com','provider':'fake','demoCardNumber':'4242424242424242'}).encode(),
            headers={'Content-Type':'application/json','Idempotency-Key':str(__import__('uuid').uuid4())})
        try:
            with urllib.request.urlopen(request,timeout=5) as response:
                if response.status==201: result['probe_successes']+=1
        except Exception: pass  # The agent/gate evaluates telemetry, not this action.
        time.sleep(1)
    return dict(result,status='executed',after=inspect_target(project,app,dependency,expected),completed_at=now())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['diagnose','restart'])
    parser.add_argument('--project');parser.add_argument('--app');parser.add_argument('--bindings')
    parser.add_argument('--dependency');parser.add_argument('--expected',required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:3000')
    parser.add_argument('--verification-seconds',type=int,default=120)
    parser.add_argument('--inject-restart-failure',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.bindings:
        bindings=json.loads(args.bindings)
        args.project=bindings['compose_project'];args.app=bindings['app_service'];args.dependency=bindings['dependency_service']
    if not all((args.project,args.app,args.dependency,args.expected)): parser.error('Missing diagnostic binding or target identity')
    if not 1<=args.verification_seconds<=300: parser.error('Invalid verification window')
    try:
        result=operate(args.action,args.project,args.app,args.dependency,args.expected,args.base_url,args.verification_seconds,args.inject_restart_failure)
    except Exception as error:
        result=dict(action=args.action,status='unknown',reason=str(error),observed_at=now())
    result['expected_execution_id']=args.expected
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status'] in ('observed','executed','not_applicable','failed') else 1

if __name__=='__main__': raise SystemExit(main())
