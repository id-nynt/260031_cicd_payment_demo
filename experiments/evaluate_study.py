"""Offline evaluation of the sequential study guide's predeclared trial ledger.

Reads evidence only. Never dispatches workflows, sends traffic, or resets services.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, median


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def evaluate(study_dir):
    study_dir=Path(study_dir).resolve()
    study=read(study_dir/'study.json')
    trials=study['trials']
    ids=[t['id'] for t in trials]
    if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]+',i) for i in ids):
        raise ValueError('Trial IDs must be unique simple directory names')
    pair_slots=[(t['case'],t['repetition'],t['mechanism']) for t in trials]
    if len(pair_slots)!=len(set(pair_slots)):
        raise ValueError('Duplicate case/repetition/mechanism in study plan')
    rows=[]
    fingerprints={}
    reset_fingerprints={}
    for trial in trials:
        row=dict(trial,eligible=False,recorded=False,issues=[])
        rows.append(row)
        folder=study_dir/'trials'/trial['id']
        if not (folder/'record.json').exists():
            row['issues'].append('not_finalised');continue
        row['recorded']=True
        try:
            record=read(folder/'record.json')
            result_dir=Path(record['result_dir']).resolve()
            if not result_dir.is_relative_to(folder):raise ValueError('Result directory outside scheduled trial')
            result=read(result_dir/'controller-result.json')
            metrics=read(result_dir/'experiment-metrics.json')
            plan=read(Path(str(result_dir)+'-experiment')/'plan.json')
            reset=read(record['reset_result'])
            reset_check=read(record['reset_check'])
            reset_fingerprints.setdefault(json.dumps(reset.get('verified_releases'),sort_keys=True),[]).append(row)
            if reset.get('mode')!='github' or reset.get('outcome')!='achieved' or reset.get('release_sha')!=study['v1_sha'] or reset.get('repository')!=study['repository']:
                row['issues'].append('invalid_reset')
            for entity in ('staging','production'):
                verified=reset.get('verified_releases',{}).get(entity,{})
                observed=reset_check.get(entity,{})
                if (verified.get('release_sha')!=study['v1_sha'] or not verified.get('github_run_id') or
                    not verified.get('execution_id') or observed.get('deploymentRunId')!=verified.get('execution_id') or
                    observed.get('appVersion')!='v1' or observed.get('experimentMode')!='normal' or observed.get('ready') is not True):
                    row['issues'].append('reset_not_verified_'+entity)
            if result.get('repository')!=study['repository']:row['issues'].append('repository_mismatch')
            expected=dict(case=trial['case'],mechanism=trial['mechanism'],seed=study['seed'],
                          release_sha=study['v2_sha'],known_good_sha=study['v1_sha'],mode='github')
            for key,value in expected.items():
                if metrics.get(key)!=value:row['issues'].append('mismatch_'+key)
            if plan.get('comparison',{}).get('worker_sha')!=study['worker_sha']:
                row['issues'].append('worker_mismatch')
            if not metrics.get('protocol_key'):row['issues'].append('missing_protocol_key')
            if metrics.get('eligible_for_comparison') is not True:
                row['issues']+=metrics.get('validation_issues') or ['metrics_ineligible']
            if record.get('fault_reviewed') is not True:row['issues'].append('fault_exposure_not_confirmed')
            if record.get('evidence_complete') is not True:row['issues'].append('evidence_incomplete')
            if trial['mechanism']=='github-actions':
                if read(folder/'native'/'collection.json').get('complete_download') is not True:
                    row['issues'].append('incomplete_native_download')
            for key in ('candidate_delivered','service_restored','candidate_repaired','runtime_seconds',
                        'recovery_seconds','candidate_repair_seconds','retries','repair_attempts',
                        'rollback_attempts','protocol_key','protocol_expectation_met'):
                row[key]=metrics.get(key)
            for key in ('runtime_seconds','recovery_seconds','candidate_repair_seconds','retries','repair_attempts','rollback_attempts'):
                value=row.get(key)
                if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<0):
                    row['issues'].append('invalid_numeric_'+key)
            for key in ('candidate_delivered','service_restored','candidate_repaired'):
                if type(row.get(key)) is not bool:row['issues'].append('invalid_boolean_'+key)
            row['result_dir']=str(result_dir)
            row['outcome']=result.get('outcome')
            row['recovery_outcome']=result.get('recovery_outcome')
            row['safety']=record.get('safety','unverified')
            if row['safety'] not in ('verified_candidate','verified_baseline','unsafe','unverified'):
                raise ValueError('Invalid safety annotation')
            final=read(folder/'final-state.json').get('production',{})
            health=final.get('health',{})
            if row['safety']=='verified_candidate':
                verified=result.get('verified_releases',{}).get('production',{})
                if (not row.get('candidate_delivered') or result.get('outcome')!='achieved' or final.get('ready') is not True or
                    health.get('appVersion')!='v2' or verified.get('release_sha')!=study['v2_sha'] or not verified.get('execution_id') or
                    health.get('deploymentRunId')!=verified.get('execution_id')):
                    row['issues'].append('candidate_safety_not_supported')
            if row['safety']=='verified_baseline':
                restored=result.get('executions',{}).get('rollback',{})
                restored_id=restored.get('executionId',restored.get('execution_id'))
                reset_id=reset.get('verified_releases',{}).get('production',{}).get('execution_id')
                rollback_verified=(result.get('known_good_sha')==study['v1_sha'] and result.get('recovery_outcome')=='restored' and
                    result.get('telemetry',{}).get('rollback')=='allow' and restored.get('status')=='success' and restored_id and
                    health.get('deploymentRunId')==restored_id)
                if (final.get('ready') is not True or health.get('appVersion')!='v1' or not
                    ((reset_id and health.get('deploymentRunId')==reset_id) or rollback_verified)):
                    row['issues'].append('baseline_safety_not_supported')
            interventions=record.get('human_interventions')
            if interventions is not None and (type(interventions) is not int or interventions<0):
                raise ValueError('Interventions must be a nonnegative integer or null')
            row['human_interventions']=interventions
            row['notes']=record.get('notes','')
            fingerprint=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
            fingerprints.setdefault(fingerprint,[]).append(row)
        except (OSError,ValueError,KeyError,TypeError) as error:
            row['issues'].append('missing_or_invalid_evidence: '+str(error))
    # Exclude every duplicate, rather than silently treating a second download as replication.
    for copies in fingerprints.values():
        if len(copies)>1:
            for row in copies:row['issues'].append('duplicate_trial_evidence')
    for copies in reset_fingerprints.values():
        if len(copies)>1:
            for row in copies:row['issues'].append('reset_reused_across_trials')
    for row in rows:row['eligible']=not row['issues']
    pairs=[]
    slots={}
    for row in rows:slots.setdefault((row['case'],row['repetition']),{})[row['mechanism']]=row
    costs=('runtime_seconds','recovery_seconds','candidate_repair_seconds','retries','repair_attempts','human_interventions')
    for (case,repetition),members in slots.items():
        bdi=members.get('bdi',{});native=members.get('github-actions',{})
        matched=bool(bdi.get('eligible') and native.get('eligible') and bdi.get('protocol_key')==native.get('protocol_key'))
        item=dict(case=case,repetition=repetition,matched=matched,
                  reason='' if matched else 'Missing/ineligible partner or unequal protocol_key')
        if matched:
            for key in ('candidate_delivered','service_restored','candidate_repaired'):
                item[key+'_bdi_minus_conventional']=int(bool(bdi[key]))-int(bool(native[key]))
            for key in costs:
                item[key+'_bdi_minus_conventional']=bdi[key]-native[key] if bdi.get(key) is not None and native.get(key) is not None else None
        pairs.append(item)
    groups=[]
    for case,mechanism in dict.fromkeys((r['case'],r['mechanism']) for r in rows):
        planned=[r for r in rows if r['case']==case and r['mechanism']==mechanism]
        valid=[r for r in planned if r['eligible']]
        restorations=[r for r in valid if (r.get('rollback_attempts') or 0)>0]
        repairs=[r for r in valid if (r.get('repair_attempts') or 0)>0]
        safety=[r for r in valid if r['safety']!='unverified']
        item=dict(case=case,mechanism=mechanism,planned=len(planned),recorded=sum(r['recorded'] for r in planned),
                  eligible=len(valid),excluded=sum(r['recorded'] and not r['eligible'] for r in planned),
                  pending=sum(not r['recorded'] for r in planned))
        for metric,denominator,label in [('candidate_delivered',valid,'delivery'),('service_restored',restorations,'restoration'),('candidate_repaired',repairs,'candidate_repair')]:
            item[label+'_denominator']=len(denominator)
            item[label+'_rate']=sum(bool(r[metric]) for r in denominator)/len(denominator) if denominator else None
        item['safety_verified_denominator']=len(safety)
        item['safe_rate']=sum(r['safety'] in ('verified_candidate','verified_baseline') for r in safety)/len(safety) if safety else None
        item['safety_unverified']=len(valid)-len(safety)
        for key in costs:
            values=[r[key] for r in valid if r.get(key) is not None]
            item[key+'_n']=len(values)
            item[key+'_mean']=mean(values) if values else None
            item[key+'_median']=median(values) if values else None
        groups.append(item)
    final_reset_complete=False
    try:
        reset_dir=Path((study_dir/'current-reset.txt').read_text(encoding='utf-8-sig').strip())
        receipt=read(reset_dir/'controller-result.json'); checks=read(reset_dir/'reset-check.json')
        final_reset_complete=(not (reset_dir/'used-by-trial.txt').exists() and receipt.get('outcome')=='achieved'
            and receipt.get('mode')=='github' and receipt.get('repository')==study['repository']
            and receipt.get('release_sha')==study['v1_sha'] and all(
                checks.get(e,{}).get('ready') is True and checks[e].get('appVersion')=='v1'
                and checks[e].get('experimentMode')=='normal'
                and receipt.get('verified_releases',{}).get(e,{}).get('github_run_id')
                and receipt['verified_releases'][e].get('release_sha')==study['v1_sha']
                and checks[e].get('deploymentRunId') and checks[e]['deploymentRunId']==receipt['verified_releases'][e].get('execution_id')
                for e in ('staging','production')))
    except (OSError,ValueError,KeyError): pass
    return rows,pairs,dict(final_reset_complete=bool(final_reset_complete),
        study_complete=bool(all(r['recorded'] for r in rows) and final_reset_complete),planned=len(rows),recorded=sum(r['recorded'] for r in rows),
        eligible=sum(r['eligible'] for r in rows),matched_pairs=sum(p['matched'] for p in pairs),
        planned_pairs=len(pairs),groups=groups,
        limitations=['Descriptive estimates only; small repeated samples do not establish statistical superiority.',
                     'Safety and fault exposure require operator review of raw evidence.',
                     'Compare only matched pairs; marginal group means may include unmatched eligible trials.',
                     'Database state is retained; queue and observation boundaries differ between mechanisms.'])


def export_csv(path,rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows,pairs,summary=evaluate(args.study)
    args.output.mkdir(parents=True,exist_ok=False)
    export_csv(args.output/'trials.csv',rows);export_csv(args.output/'pairs.csv',pairs)
    export_csv(args.output/'groups.csv',summary['groups'])
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('groups','limitations')},indent=2))
    print(args.output.resolve())


if __name__=='__main__':main()
