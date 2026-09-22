"""Finalize a scheduled trial from saved evidence, without deployment or network access.

Never overwrite a record, manufacture missing evidence, or infer interventions.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from evaluate_study import evaluate, read


def injected_stop_evidence(folder, mechanism, collected, candidate_id):
    """Read explicit worker confirmation, never infer injection from a requested fault."""
    if not candidate_id:
        return False
    if mechanism == 'github-actions':
        paths=[folder/'native/github-run.log']
    else:
        remote=Path(collected.get('directory') or folder/'missing-remote-evidence').resolve()
        if not remote.is_relative_to(folder.resolve()):
            raise ValueError('Remote evidence directory outside this trial')
        paths=list(remote.glob('*.log'))
    for path in paths:
        if not path.exists(): continue
        for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            if 'FAULT_INJECTION_JSON=' not in line: continue
            try: evidence=json.loads(line.split('FAULT_INJECTION_JSON=',1)[1])
            except ValueError: continue  # Echoed shell source is not evidence.
            if (evidence.get('event')=='fault_injected' and evidence.get('fault')=='candidate_stopped'
                    and evidence.get('status')=='observed' and evidence.get('app_state')=='stopped'
                    and evidence.get('project')=='payment-production' and evidence.get('service')=='app'
                    and evidence.get('container_id')
                    and evidence.get('deployment_execution_id')==candidate_id
                    and evidence.get('expected_execution_id')==candidate_id):
                return True
    return False


def make_record(study_dir, trial_id, interventions=None, notes=''):
    study_dir=Path(study_dir).resolve()
    study=read(study_dir/'study.json')
    matches=[t for t in study['trials'] if t['id']==trial_id]
    if len(matches)!=1: raise ValueError('Trial must be uniquely declared in study.json')
    if interventions is not None and interventions<0: raise ValueError('Negative intervention count')
    trial=matches[0]; folder=study_dir/'trials'/trial_id
    start=read(folder/'started.json')
    result_dir=Path((folder/'result-path.txt').read_text(encoding='utf-8-sig').strip()).resolve()
    if not result_dir.is_relative_to(folder): raise ValueError('Result outside this trial')
    result=read(result_dir/'controller-result.json') if (result_dir/'controller-result.json').exists() else {}
    metrics=read(result_dir/'experiment-metrics.json') if (result_dir/'experiment-metrics.json').exists() else {}
    final=read(folder/'final-state.json') if (folder/'final-state.json').exists() else {}
    reset=read(start['reset_result'])
    collection=folder/('native/collection.json' if trial['mechanism']=='github-actions' else 'remote-collection.json')
    collected=read(collection) if collection.exists() else {}
    complete=collected.get('complete_download' if trial['mechanism']=='github-actions' else 'complete') is True
    safety='unverified'; health=final.get('production',{}).get('health',{})
    ready=final.get('production',{}).get('ready') is True
    identity=health.get('deploymentRunId')
    verified=result.get('verified_releases',{}).get('production',{})
    rollback=result.get('executions',{}).get('rollback',{})
    rollback_id=rollback.get('executionId',rollback.get('execution_id'))
    if ready and identity:
        if (health.get('appVersion')=='v2' and result.get('outcome')=='achieved' and
            verified.get('release_sha')==study['v2_sha'] and verified.get('execution_id')==identity):
            safety='verified_candidate'
        elif health.get('appVersion')=='v1' and (
            identity==reset.get('verified_releases',{}).get('production',{}).get('execution_id') or
            (identity==rollback_id and result.get('known_good_sha')==study['v1_sha'] and
             result.get('recovery_outcome')=='restored' and rollback.get('status')=='success' and
             result.get('telemetry',{}).get('rollback')=='allow')):
            safety='verified_baseline'
    event_path=result_dir/'experiment-events.jsonl'
    events=[json.loads(line) for line in event_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()] if event_path.exists() else []
    case=trial['case']; exposed=False; fault_injected=None; diagnosis_succeeded=None
    if case=='healthy':
        traffic=metrics.get('traffic_by_entity',{})
        exposed=all(traffic.get(e,{}).get('required') is True and
            traffic[e].get('summary',{}).get('successful',0)>0 and not traffic[e].get('validation_issues')
            for e in ('staging','production'))
    elif case=='test-failure':
        # Confirm the forced fault, not just an arbitrary failed test.
        config=any(e.get('entity')=='test' and e.get('failure_mode')=='force_failure' for e in events)
        receipts=list(result_dir.parent.parent.rglob('attempt-*.json')) if trial['mechanism']=='github-actions' else []
        config=config or any(read(p).get('entity')=='test' and read(p).get('failure_mode')=='force_failure' for p in receipts)
        exposed=config and result.get('executions',{}).get('test',{}).get('status')=='failure'
    elif case in ('production-temporary','production-persistent','rollback-reconsideration'):
        traffic=metrics.get('traffic_by_entity',{}).get('production',{})
        expected={'production-temporary':'temporary-errors','production-persistent':'persistent-errors','rollback-reconsideration':'rollback-reconsideration-errors'}[case]
        exposed=(traffic.get('summary',{}).get('scenario')==expected and traffic.get('summary',{}).get('injected_errors',0)>0
                 and not traffic.get('validation_issues'))
    elif case in ('candidate-stopped','candidate-restart-fails'):
        candidate=result.get('executions',{}).get('production',{})
        candidate_id=candidate.get('executionId',candidate.get('execution_id'))
        diagnosis_succeeded=bool(candidate_id and any(
            e.get('event')=='diagnosis_finished' and e.get('entity')=='production'
            and e.get('deployment_execution_id')==candidate_id
            and (e.get('status')=='app_stopped' or
                 (e.get('status')=='observed' and e.get('app_state')=='stopped' and e.get('dependency_ready') is True))
            for e in events))
        fault_injected=injected_stop_evidence(folder,trial['mechanism'],collected,candidate_id)
        exposed=fault_injected
    return dict(result_dir=str(result_dir),reset_result=start['reset_result'],reset_check=start['reset_check'],
        evidence_complete=complete,fault_reviewed=bool(exposed),safety=safety,human_interventions=interventions,
        fault_injected=fault_injected,diagnosis_succeeded=diagnosis_succeeded,
        notes=notes,review_method='saved-evidence-v2',finalised_at=datetime.now(timezone.utc).isoformat())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',required=True,type=Path)
    parser.add_argument('--trial',required=True)
    parser.add_argument('--human-interventions',type=int)
    parser.add_argument('--notes',default='')
    args=parser.parse_args()
    record=make_record(args.study,args.trial,args.human_interventions,args.notes)
    target=args.study/'trials'/args.trial/'record.json'
    with target.open('x',encoding='utf-8') as stream: json.dump(record,stream,indent=2)
    rows,_,_=evaluate(args.study)
    row=next(r for r in rows if r['id']==args.trial)
    print(json.dumps(dict(record=str(target.resolve()),eligible=row['eligible'],issues=row['issues']),indent=2))
    print('Recorded means preserved, not necessarily eligible or successful. Resolve live work before any reset.')


if __name__=='__main__': main()
