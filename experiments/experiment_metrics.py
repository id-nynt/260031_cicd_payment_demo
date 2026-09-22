"""Extract auditable per-trial metrics; never dispatch or alter a campaign."""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def extract(directory):
    directory = Path(directory)
    plan = read(Path(str(directory) + '-experiment') / 'plan.json', {})
    result = read(directory / 'controller-result.json', {})
    manifest = read(directory / 'generation-manifest.json', {})
    path = directory / 'experiment-events.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    started = next((e for e in events if e['event'] == 'campaign_started'), None)
    finished = next((e for e in reversed(events) if e['event'] == 'campaign_finished'), None)
    actions = [e for e in events if e['event'] == 'action_started']
    measurements = [e for e in events if e['event'] == 'observation']
    recovery = next((e for e in events if e['event'] == 'recovery_started'), None)
    traffic = read(Path(str(directory) + '-traffic') / 'summary.json', {})
    thresholds = plan.get('thresholds', {'error_rate_high_gt': .05, 'latency_p95_ms_high_gt': 500})
    def bad(e):
        return (e.get('data_status') != 'fresh' or e.get('readiness') != 'ready' or e.get('availability', 0) < 1 or
                e.get('error_rate', 0) > thresholds['error_rate_high_gt'] or e.get('latency_p95_ms', 0) > thresholds['latency_p95_ms_high_gt'])
    adverse = next((e for e in events if (e['event'] == 'observation' and e.get('entity') == 'production' and bad(e)) or
        (e['event'] == 'action_finished' and e.get('entity') == 'production' and e.get('status') != 'success')), None)
    accepted_recovery = next((e for e in events if e['event'] == 'health_accepted' and e.get('entity') == 'rollback' and e.get('decision') == 'allow'), None)
    def duration(a, b):
        return round(stamp(b['timestamp']) - stamp(a['timestamp']), 3) if a and b else None
    verified = result.get('verified_releases', {}).get('production', {})
    delivery = bool(result.get('mode') == 'github' and result.get('outcome') == 'achieved' and not result.get('negative_goal_experiment') and
        verified.get('release_sha') == result.get('release_sha') and verified.get('execution_id'))
    restored = result.get('mode') == 'github' and result.get('recovery_outcome') == 'restored' and result.get('telemetry', {}).get('rollback') == 'allow'
    reasons = []
    if not plan: reasons.append('no_experiment_plan')
    if not started or not finished or not result: reasons.append('incomplete_campaign')
    traffic_by_entity = {}
    if 'traffic_targets' in plan:
        for entity, target in plan['traffic_targets'].items():
            summary = read(Path(str(directory) + target['summary_suffix']) / 'summary.json', {})
            reached = any((e['event'] == 'deployment_ready' and e.get('after_entity') == entity) or
                          (e['event'] == 'observation' and e.get('entity') == entity) for e in events)
            issues = []
            if reached:
                if summary.get('stop_reason') not in ('campaign_finished', 'recovery_started'):
                    issues.append('traffic_failed_or_incomplete')
                if summary.get('entity') != entity or summary.get('scenario') != target['profile'] or summary.get('seed') != plan.get('seed'):
                    issues.append('traffic_configuration_mismatch')
                execution = result.get('executions', {}).get(entity, {})
                execution_id = execution.get('execution_id', execution.get('executionId'))
                if not execution_id or summary.get('execution_id') != execution_id:
                    issues.append('traffic_identity_mismatch')
                if summary.get('release_sha') != result.get('release_sha'):
                    issues.append('traffic_release_mismatch')
                if not summary.get('successful', 0): issues.append('no_successful_traffic_observed')
                if target['fault_expected'] and not summary.get('injected_errors', 0):
                    issues.append('no_injected_traffic_observed')
                if not target['fault_expected'] and summary.get('injected_errors', 0):
                    issues.append('unexpected_injected_traffic')
                if summary.get('unexpected_responses', 0) or summary.get('network_errors', 0):
                    issues.append('unexpected_traffic_errors')
            elif target['fault_expected']:
                issues.append('fault_target_not_reached')
            # An early build/test failure legitimately has no deployment traffic.
            traffic_by_entity[entity] = dict(required=reached, summary=summary, validation_issues=issues)
            reasons.extend(entity + ':' + issue for issue in issues)
    else:
        # Historical plans predate environment-specific traffic evidence.
        if plan.get('traffic_required') and traffic.get('stop_reason') not in ('campaign_finished', 'recovery_started', 'campaign_finished_before_traffic'):
            reasons.append('traffic_failed_or_incomplete')
        if traffic.get('unexpected_responses', 0) or traffic.get('network_errors', 0): reasons.append('unexpected_traffic_errors')
        if plan.get('fault_expected') and not traffic.get('injected_errors', 0): reasons.append('no_injected_traffic_observed')
        if plan.get('traffic_required') and not traffic.get('successful', 0): reasons.append('no_successful_traffic_observed')
    interventions = read(Path(str(directory) + '-experiment') / 'interventions.json')
    mode = result.get('mode')
    if mode != 'github': reasons.append('not_live_execution')
    repair_actions=[e for e in events if e['event']=='repair_started']
    repair_verified=next((e for e in events if e['event']=='decision' and e.get('decision')=='repair_verified'),None)
    if plan.get('case') in ('candidate-stopped','candidate-restart-fails') and not any(
            e['event']=='diagnosis_finished' and (e.get('status')=='app_stopped' or
            (e.get('app_state')=='stopped' and e.get('dependency_ready') is True)) for e in events):
        reasons.append('stopped_candidate_diagnosis_not_confirmed')
    rollback_selected=next((e for e in events if e.get('event')=='rollback_selected'),None)
    rollback_cancelled=next((e for e in events if e.get('event')=='decision' and e.get('decision')=='rollback_cancelled'),None)
    if plan.get('case')=='rollback-reconsideration' and not rollback_selected:
        reasons.append('rollback_intention_not_observed')
    recheck_samples=[]
    if rollback_selected and rollback_cancelled:
        recheck_samples=[e for e in measurements if e.get('entity')=='production' and
            stamp(rollback_selected['timestamp']) < stamp(e['timestamp']) < stamp(rollback_cancelled['timestamp'])]
    recheck_verified=bool(rollback_selected and rollback_selected.get('execution_id') and len(recheck_samples)>=2 and
        all(not bad(e) and e.get('execution_id')==rollback_selected['execution_id'] for e in recheck_samples[-2:]))
    if plan.get('case')=='rollback-reconsideration' and rollback_cancelled and not recheck_verified:
        reasons.append('rollback_cancellation_health_not_verified')
    row = dict(metrics_schema_version=2, rollback_selected=bool(rollback_selected), rollback_cancelled=bool(rollback_cancelled), rollback_reconsideration_seconds=duration(rollback_selected,rollback_cancelled), traffic_by_entity=traffic_by_entity, repair_attempts=len(repair_actions), diagnoses=sum(e['event']=='diagnosis_started' for e in events),
        candidate_repaired=bool(delivery and repair_verified and repair_actions and any(
            e['event']=='repair_finished' and e.get('status')=='executed' for e in events)),
        candidate_repair_seconds=duration(repair_actions[0] if repair_actions else None,repair_verified),
        repair_failures=sum(e['event']=='repair_finished' and e.get('status')!='executed' for e in events),
        campaign=str(directory.resolve()), mechanism=manifest.get('mechanism'), case=plan.get('case'), seed=plan.get('seed'),
        comparison_key=plan.get('comparison_key'), protocol_key=plan.get('protocol_key'), mode=mode, outcome=result.get('outcome'), recovery_outcome=result.get('recovery_outcome'),
        candidate_delivered=delivery, service_restored=bool(restored), production_dispatched=any(e.get('entity')=='production' for e in actions),
        runtime_seconds=duration(started, finished), time_to_candidate_seconds=duration(started, finished) if delivery else None,
        recovery_seconds=duration(adverse, accepted_recovery) if restored else None,
        detection_to_recovery_decision_seconds=duration(adverse, recovery),
        action_attempts=len(actions), retries=sum(e.get('attempt', 1)>1 and e.get('entity')!='rollback' for e in actions),
        rollback_attempts=sum(e.get('entity')=='rollback' for e in actions), observations=len(measurements),
        reconciliations=sum(e['event']=='reconciliation' for e in events),
        summed_entity_duration_ms=sum(e.get('duration_ms',0) for e in events if e['event']=='action_finished'),
        traffic_requests=sum(v['summary'].get('requests', 0) for v in traffic_by_entity.values()) if traffic_by_entity else traffic.get('requests'),
        traffic_errors=sum(v['summary'].get('injected_errors', 0) for v in traffic_by_entity.values()) if traffic_by_entity else traffic.get('injected_errors'),
        release_sha=result.get('release_sha'), known_good_sha=result.get('known_good_sha'),
        human_interventions=len(interventions) if isinstance(interventions,list) else None,
        validation_issues=reasons, eligible_for_comparison=not reasons)
    # These are protocol expectations, not an independent oracle proving application correctness.
    expectations = {'rollback-reconsideration':bool(delivery and recheck_verified and rollback_selected and rollback_cancelled and not row['rollback_attempts'] and stamp(rollback_cancelled['timestamp']) > stamp(rollback_selected['timestamp'])), 'candidate-stopped':delivery and row['candidate_repaired'] and row['repair_attempts']==1,
        'candidate-restart-fails':bool(restored) and row['repair_attempts']==1 and not delivery, 'healthy': delivery, 'transient-test-failure': delivery and row['retries'] == 1,
        'build-failure': not row['production_dispatched'] and result.get('outcome') == 'stopped' and result.get('executions', {}).get('build', {}).get('status') == 'failure',
        'staging-persistent': not row['production_dispatched'] and result.get('outcome') == 'stopped',
        'test-failure': not row['production_dispatched'] and result.get('executions',{}).get('test',{}).get('status')=='failure',
        'staging-temporary': delivery,
        'infrastructure-failure': not row['production_dispatched'] and result.get('executions',{}).get('staging',{}).get('status')=='failure',
        'deployment-timeout': not row['production_dispatched'] and result.get('executions',{}).get('staging',{}).get('status')=='timeout' and row['retries']==1,
        'service-unavailable': bool(restored) and not delivery,
        'production-temporary': delivery, 'production-persistent': bool(restored) and not delivery}
    row['protocol_expectation_met'] = expectations.get(plan.get('case'))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaigns', nargs='+', type=Path)
    parser.add_argument('--csv', type=Path)
    args = parser.parse_args()
    rows = []
    for directory in args.campaigns:
        row = extract(directory)
        (directory / 'experiment-metrics.json').write_text(json.dumps(row, indent=2)+'\n')
        rows.append(row)
        print(json.dumps(row))
    if args.csv:
        with args.csv.open('w', newline='', encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


if __name__ == '__main__': main()
