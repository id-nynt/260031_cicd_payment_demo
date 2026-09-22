"""Native GitHub Actions helpers: validation, a bounded telemetry gate, evidence.
Job ordering/retry/rollback belongs to ci-cd.yml, never to this module.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'ci-cd-conventional'))
from configuration import load_configuration, digest, known_good_sha
from experiments.experiment_metrics import extract
from experiments.experiment_protocol import protocol_key, traffic_targets

CATALOG = json.loads((ROOT/'experiments/scenarios.json').read_text())

def now(): return datetime.now(timezone.utc).isoformat()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
def emit(path, event, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(dict(timestamp=now(), event=event, mechanism='github-actions', **fields))+'\n')
def output(key, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f: f.write(f'{key}={value}\n')
def api(path):
    request = urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'], 'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response: return json.load(response)
def configuration():
    config = load_configuration()
    return {'bindings': config['bindings']}, None, config['policy']


def prepare(directory):
    config = load_configuration()
    policy = config['policy']
    directory.mkdir(parents=True, exist_ok=False)
    sha, case = os.environ['RELEASE_SHA'], os.environ['SCENARIO']
    if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('release_sha must be a full published commit SHA')
    if case not in CATALOG: raise ValueError('Unknown scenario')
    seed = int(os.environ['SEED'])
    if not 0 <= seed <= 4294967295: raise ValueError('Invalid seed')
    if api('commits/'+sha)['sha'] != sha: raise ValueError('Candidate not published')
    baseline = os.environ.get('BASELINE') == 'true'
    good = ''
    if baseline:
        if case != 'healthy': raise ValueError('First baseline must be healthy')
    else:
        if os.environ.get('CONFIRM_ROLLBACK') != 'true': raise ValueError('Confirm database-compatible rollback')
        receipt = directory/'known-good.json'
        write(receipt, json.loads(os.environ['KNOWN_GOOD_RECEIPT']))
        good = known_good_sha(receipt, config['bindings'], os.environ['GITHUB_REPOSITORY'])
        if api('commits/'+good)['sha'] != good: raise ValueError('Known-good source not published')
    comparison = dict(case=case, seed=seed, candidate=sha, baseline=good, policy=policy,
        worker_sha=os.environ['GITHUB_SHA'], contract_sha256=config['contract_sha256'])
    write(directory/'plan.json', dict(schema_version=2, case=case, seed=seed, mechanism='github-actions', comparison=comparison,
        thresholds=policy['thresholds'], traffic_targets=traffic_targets(case, CATALOG[case]), traffic_required=bool(CATALOG[case]['profile']),
        fault_expected=bool(CATALOG[case]['profile'] and 'errors' in CATALOG[case]['profile']),
        comparison_key=None, native_workflow=True, workflow_layout='six-jobs-v1', repository=os.environ['GITHUB_REPOSITORY'], configuration_inputs=config['configuration_inputs'],
        protocol_key=protocol_key(case,seed,sha,good,os.environ['GITHUB_SHA'],config['contract_sha256'],policy,
            {'selected':digest(ROOT/'scripts/traffic-scenarios'/f"{CATALOG[case]['profile']}.json") if CATALOG[case]['profile'] else None,
             'healthy':digest(ROOT/'scripts/traffic-scenarios/healthy.json')},
            {k:v['sha256'] for k,v in config['configuration_inputs'].items()})))
    import shutil
    shutil.copyfile(ROOT/'ci-cd-conventional/config.json', directory/'config.json')
    for source in (ROOT/'ci-cd-conventional/snapshots').iterdir():
        shutil.copyfile(source, directory/source.name)
    shutil.copytree(ROOT/'ci-cd-conventional/workflows', directory/'workflows')
    shutil.copyfile(ROOT/'experiments/scenarios.json', directory/'scenarios.json')
    emit(directory/'experiment-events.jsonl','campaign_started', release_sha=sha, scenario=case)
    output('known_good_sha', good)


def measure(bindings, entity, execution_id, get=None, verify_identity=False):
    endpoints = bindings['environments']['production' if entity=='rollback' else entity]
    def fetch(url):
        with urllib.request.urlopen(url, timeout=5) as r: return json.load(r)
    get = get or fetch
    try:
        if verify_identity and get(urllib.parse.urljoin(endpoints['ready_url'],'/health')).get('deploymentRunId') != execution_id:
            raise ValueError('Candidate deployment identity mismatch')
        get(endpoints['ready_url'])
        values = {}
        for key, query in bindings['metrics'].items():
            data = get(endpoints['prometheus_url']+'/api/v1/query?'+urllib.parse.urlencode({'query':query.replace('{{run_id}}',execution_id)}))
            if data.get('status') != 'success': raise ValueError('Prometheus query failed')
            result = data['data']['result']
            if len(result) != 1: raise ValueError('Missing/ambiguous metric')
            timestamp, value = result[0]['value']; value = float(value)
            if not math.isfinite(value) or not math.isfinite(float(timestamp)) or float(timestamp)>time.time()+5 or time.time()-float(timestamp) > bindings['max_age_seconds']: raise ValueError('Non-finite/stale metric')
            values[key] = value
        if not -5 <= values.get('sample_age_seconds_query',0) <= bindings['max_age_seconds']: raise ValueError('Stale readiness sample')
        return dict(data_status='fresh',readiness='ready', error_rate=values['error_rate_query'],
            latency_p95_ms=values['latency_p95_ms_query'],availability=values['availability_query'])
    except urllib.error.HTTPError as error:
        if error.code == 503 and error.url == endpoints['ready_url']:
            return dict(data_status='fresh',readiness='not_ready',error_rate=0,latency_p95_ms=0,availability=0)
        return dict(data_status='unavailable',readiness='unknown',error_rate=0,latency_p95_ms=0,availability=0,reason=str(error))
    except Exception as error:
        return dict(data_status='unavailable',readiness='unknown',error_rate=0,latency_p95_ms=0,availability=0,reason=str(error))

def healthy(sample, thresholds):
    return (sample['data_status']=='fresh' and sample['readiness']=='ready' and sample['availability']>=1
        and sample['error_rate']<=thresholds['error_rate_high_gt'] and sample['latency_p95_ms']<=thresholds['latency_p95_ms_high_gt'])

def observe(policy, sample, record, clock=time.monotonic, sleep=time.sleep, repair=None, deadline_limit=lambda: float("inf")):
    execution=policy['execution']; deadline=clock()+execution['observation_timeout_seconds']; consecutive=0; value={}
    round_number=0
    while round_number<execution['observation_attempts']:
        if clock()>=min(deadline,deadline_limit()): break
        round_number+=1
        value=sample(); record(round_number,value)
        if repair is not None and (value['data_status'] != 'fresh' or value['readiness'] != 'ready' or value['availability'] < 1):
            result=repair()
            repair=None
            if result == 'executed':
                consecutive=0
                round_number=0
                deadline=clock()+execution['observation_timeout_seconds']
                continue
            if result in ('failed','unknown','exhausted'): return 'block'
        consecutive=consecutive+1 if healthy(value,policy['thresholds']) else 0
        if clock()>=min(deadline,deadline_limit()): break
        if consecutive>=execution['healthy_observations']: return 'allow'
        if round_number<execution['observation_attempts']: sleep(min(execution['observation_interval_seconds'],max(0,deadline-clock())))
    return 'block' if value.get('data_status') == 'fresh' and not healthy(value,policy['thresholds']) else 'unknown'

def gate(directory, entity, execution_id, sha, scenario, seed, execution_directory=None):
    doc, _, policy = configuration()
    events=directory/'experiment-events.jsonl'; directory.mkdir(parents=True,exist_ok=False)
    selected=CATALOG[scenario]; traffic=None; traffic_log=None
    emit(events,'execution_configuration',entity=entity,execution_id=execution_id,release_sha=sha)
    try:
        if entity in ['staging','production']:
            emit(events,'deployment_ready',after_entity=entity,milliseconds=60000)
            target = traffic_targets(scenario, selected).get(entity)
            if target:
                traffic_log = (directory/'traffic-console.log').open('w', encoding='utf-8')
                traffic=subprocess.Popen(['node',str(ROOT/'scripts/run-traffic-scenario.mjs'),'--campaign',str(directory),
                    '--scenario',target['profile'],'--entity',entity,'--seed',str(seed),'--output',str(directory)+'-traffic'], stdout=traffic_log, stderr=subprocess.STDOUT)
            time.sleep(60)
        def record(round_number, value):
            emit(events,'observation',entity=entity,round=round_number,**value)
            print(f'OBSERVE {entity} round={round_number} data={value["data_status"]} error_rate={value["error_rate"]}',flush=True)
        if entity == 'production':
            if execution_directory:
                receipts=[json.loads(p.read_text()) for p in execution_directory.glob('attempt-*.json')]
                matching=[r for r in receipts if r['executionId']==execution_id and r['status']=='success']
                if len(matching)!=1: raise ValueError('Missing production duration evidence')
                duration=matching[0]['durationMs']
            else:
                raise ValueError('Production gate requires execution receipts')
            if duration>policy['max_production_ms']:
                emit(events,'maintenance_violation',entity=entity,duration_ms=duration)
                raise ValueError('Production exceeded duration constraint')
        repair_start=[None]; repaired=[False]
        def repair():
            rule=policy['candidate_repair'][entity]
            binding=doc['bindings']['diagnostics'][entity]
            repair_start[0]=time.monotonic()
            def operation(action):
                receipt=directory/(action+'-receipt.json')
                emit(events,'repair_started' if action=='restart' else 'diagnosis_started',entity=entity,attempt=1,deployment_execution_id=execution_id)
                command=[sys.executable,str(ROOT/'scripts/candidate-repair.py'),action,
                    '--project',binding['compose_project'],'--app',binding['app_service'],'--dependency',binding['dependency_service'],
                    '--expected',execution_id,'--verification-seconds',str(rule['verification_window_seconds']),'--output',str(receipt)]
                if action=='restart' and scenario=='candidate-restart-fails':command.append('--inject-restart-failure')
                process=subprocess.run(command)
                evidence=json.loads(receipt.read_text()) if receipt.exists() else {'status':'unknown'}
                if process.returncode!=0:evidence['status']='unknown'
                emit(events,'repair_finished' if action=='restart' else 'diagnosis_finished',entity=entity,attempt=1,status=evidence['status'],
                    deployment_execution_id=execution_id,app_state=evidence.get('before',{}).get('app_state'),dependency_ready=evidence.get('before',{}).get('dependency_ready'))
                return evidence
            diagnosis=operation('diagnose')
            if diagnosis['status']!='observed': return 'unknown'
            if diagnosis['before']['app_state'] not in ('running','stopped'):return 'unknown'
            if diagnosis['before']['app_state']!='stopped' or not diagnosis['before']['dependency_ready']:return 'not_applicable'
            if time.monotonic()-repair_start[0]>=rule['deadline_seconds']:return 'exhausted'
            status=operation('restart')['status']
            repaired[0]=status=='executed'
            # A selected repair that could not execute falls back; only a diagnostic
            # not_applicable result resumes passive observation.
            return status if status in ('executed','failed') else 'unknown'
        def sample():
            if repair_start[0] is not None and time.monotonic()-repair_start[0]>=policy['candidate_repair'][entity]['deadline_seconds']:
                return dict(data_status='unavailable',readiness='unknown',error_rate=0,latency_p95_ms=0,availability=0)
            return measure(doc['bindings'],entity,execution_id,verify_identity=repaired[0])
        decision=observe(policy,sample,record,repair=repair if entity in policy.get('candidate_repair',{}) else None,
            deadline_limit=lambda: repair_start[0]+policy['candidate_repair'][entity]['deadline_seconds'] if repair_start[0] is not None else float('inf'))
        restart_receipt=directory/'restart-receipt.json'
        if decision=='allow' and restart_receipt.exists() and json.loads(restart_receipt.read_text())['status']=='executed':
            emit(events,'decision',entity=entity,decision='repair_verified',counter=1)
        emit(events,'health_accepted',entity=entity,decision=decision)
        write(directory/'gate-result.json',dict(entity=entity,decision=decision,execution_id=execution_id,release_sha=sha))
        output('decision',decision)
        print(f'HEALTH {entity} = {decision}',flush=True)
        return 0 if decision=='allow' else 1
    finally:
        emit(events,'observation_finished',entity=entity)
        if traffic:
            try: traffic.wait(timeout=10)
            except subprocess.TimeoutExpired: traffic.terminate();traffic.wait()
        if traffic_log: traffic_log.close()


def finish(directory, downloaded, remote=None):
    directory.mkdir(parents=True,exist_ok=False)
    plans=list(downloaded.rglob('plan.json'))
    if len(plans)!=1: raise ValueError('Missing/ambiguous preparation evidence; no certified result')
    plan=json.loads(plans[0].read_text()); case=plan['case']; sha=plan['comparison']['candidate']; good=plan['comparison']['baseline']
    events=[]
    for path in downloaded.rglob('experiment-events.jsonl'):
        events.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    gates={}
    for path in downloaded.rglob('gate-result.json'):
        item=json.loads(path.read_text());gates[item['entity']]=item
    jobs=[] if remote is None else remote['jobs']
    if remote is None:
        for page in range(1,101):
            batch=api(f'actions/runs/{os.environ["GITHUB_RUN_ID"]}/attempts/{os.environ["GITHUB_RUN_ATTEMPT"]}/jobs?per_page=100&page={page}')['jobs'];jobs+=batch
            if len(batch)<100:break
    executions={}
    names={'Build entity':'build','Test entity':'test','Security entity':'security','Staging entity':'staging','Production entity':'production','Rollback entity':'rollback'}
    for job in jobs:
        if plan.get('workflow_layout') == 'six-jobs-v1': continue
        entity=next((v for k,v in names.items() if job['name'].endswith(k)),None)
        if not entity or job['conclusion']=='skipped' or not job.get('started_at') or not job.get('completed_at'):continue
        attempt=2 if '/ retry /' in job['name'] else 1
        execution_id=f'native-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}-{entity}-{attempt}'
        duration=(datetime.fromisoformat(job['completed_at'].replace('Z','+00:00'))-datetime.fromisoformat(job['started_at'].replace('Z','+00:00'))).total_seconds()*1000
        status={'timed_out':'timeout'}.get(job['conclusion'],job['conclusion'])
        if status == 'success' and any(s['conclusion']=='failure' for s in job.get('steps',[])):status='failure'
        if any(s['name']=='Controlled transient failure' and s['conclusion']=='failure' for s in job.get('steps',[])):status='transient_failure'
        fields=dict(entity=entity,attempt=attempt,execution_id=execution_id,mechanism='github-actions')
        events+=[dict(timestamp=job['started_at'],event='action_started',**fields),dict(timestamp=job['completed_at'],event='action_finished',status=status,duration_ms=duration,**fields)]
        if entity=='rollback':events.append(dict(timestamp=job['started_at'],event='recovery_started',entity='production'))
        if attempt>=executions.get(entity,{}).get('attempt',0):executions[entity]=dict(status=status,attempt=attempt,executionId=execution_id,githubRunId=int(os.environ['GITHUB_RUN_ID']),durationMs=duration)
    if plan.get('workflow_layout') == 'six-jobs-v1':
        seen=set()
        for path in sorted(downloaded.rglob('attempt-*.json')):
            item=json.loads(path.read_text()); entity=item['entity']; attempt=item['attempt']
            if (entity,attempt) in seen: raise ValueError('Duplicate execution receipt')
            seen.add((entity,attempt))
            if item['release_sha'] != (good if entity=='rollback' else sha): raise ValueError('Receipt release mismatch')
            fields=dict(entity=entity,attempt=attempt,execution_id=item['executionId'],mechanism='github-actions')
            events += [dict(timestamp=item['started_at'],event='action_started',**fields),
                       dict(timestamp=item['completed_at'],event='action_finished',status=item['status'],duration_ms=item['durationMs'],**fields)]
            if entity=='rollback':events.append(dict(timestamp=item['started_at'],event='recovery_started',entity='production'))
            if attempt>=executions.get(entity,{}).get('attempt',0): executions[entity]=item
        # Terminal jobs without receipts are evidence gaps, never certified successes.
        for job in jobs:
            entity=job['name'].lower()
            if entity in ('build','test','security','staging','production','rollback') and job.get('conclusion')!='skipped' and entity not in executions:
                raise ValueError('Missing execution receipt for terminal job: '+entity)
    telemetry={k:v['decision'] for k,v in gates.items()}
    delivered=all(executions.get(e,{}).get('status')=='success' for e in ['build','test','security','staging','production']) and all(telemetry.get(e)=='allow' for e in ['staging','production']) and 'rollback' not in executions
    restored=executions.get('rollback',{}).get('status')=='success' and telemetry.get('rollback')=='allow'
    result=dict(mode='github',mechanism='github-actions',project='payment-service',repository=os.environ['GITHUB_REPOSITORY'],
        release_sha=sha,known_good_sha=good,outcome='achieved' if delivered else 'stopped',
        recovery_outcome='restored' if restored else 'failed' if 'rollback' in executions else 'not_attempted',
        telemetry=telemetry,executions=executions,verified_releases={})
    if delivered:
        for entity in ['staging','production']:
            result['verified_releases'][entity]=dict(release_sha=sha,execution_id=gates[entity]['execution_id'],github_run_id=int(os.environ['GITHUB_RUN_ID']),environment=entity)
    finished=max((j.get('completedAt',j.get('completed_at','')) or '' for j in jobs),default='')
    events.append(dict(timestamp=finished or now(),event='campaign_finished',outcome=result['outcome']))
    events.sort(key=lambda e:datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')))
    (directory/'experiment-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    write(directory/'controller-result.json',result);write(directory/'generation-manifest.json',dict(mechanism='github-actions'))
    write(Path(str(directory)+'-experiment')/'plan.json',plan)
    summaries = [json.loads(p.read_text()) for p in downloaded.rglob('summary.json')]
    for entity, target in plan.get('traffic_targets', traffic_targets(case, CATALOG[case])).items():
        matching = [s for s in summaries if s.get('entity') == entity]
        if len(matching) > 1: raise ValueError('Ambiguous traffic summaries for ' + entity)
        if matching:
            write(Path(str(directory)+target['summary_suffix'])/'summary.json', matching[0])
    write(directory/'github-jobs.json',jobs)
    metrics=extract(directory);write(directory/'experiment-metrics.json',metrics)
    with open(os.environ.get('GITHUB_STEP_SUMMARY',str(directory/'summary.md')),'a',encoding='utf-8') as f:
        f.write(f'## Conventional result\nCandidate delivered: {delivered}\n\nRecovery: {result["recovery_outcome"]}\n\nDownload native-result and native-* evidence artifacts.\n')
    return 0 if delivered else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','gate','finish']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--execution-directory',type=Path);p.add_argument('--entity');p.add_argument('--execution-id');p.add_argument('--release-sha');p.add_argument('--scenario',choices=CATALOG);p.add_argument('--seed',type=int,default=42);p.add_argument('--downloaded',type=Path)
    a=p.parse_args()
    if a.command=='prepare':prepare(a.directory)
    elif a.command=='gate':sys.exit(gate(a.directory,a.entity,a.execution_id,a.release_sha,a.scenario,a.seed,a.execution_directory))
    else:sys.exit(finish(a.directory,a.downloaded))
