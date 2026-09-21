"""Extract auditable per-trial metrics; never dispatch or alter a campaign."""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


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
    if plan.get('traffic_required') and traffic.get('stop_reason') not in ('campaign_finished', 'recovery_started', 'campaign_finished_before_traffic'):
        reasons.append('traffic_failed_or_incomplete')
    if traffic.get('unexpected_responses', 0) or traffic.get('network_errors', 0): reasons.append('unexpected_traffic_errors')
    if plan.get('fault_expected') and not traffic.get('injected_errors', 0): reasons.append('no_injected_traffic_observed')
    if plan.get('traffic_required') and not traffic.get('successful', 0): reasons.append('no_successful_traffic_observed')
    interventions = read(Path(str(directory) + '-experiment') / 'interventions.json')
    mode = result.get('mode')
    if mode != 'github': reasons.append('not_live_execution')
    row = dict(campaign=str(directory.resolve()), mechanism=manifest.get('mechanism'), case=plan.get('case'), seed=plan.get('seed'),
        comparison_key=plan.get('comparison_key'), mode=mode, outcome=result.get('outcome'), recovery_outcome=result.get('recovery_outcome'),
        candidate_delivered=delivery, service_restored=bool(restored), production_dispatched=any(e.get('entity')=='production' for e in actions),
        runtime_seconds=duration(started, finished), time_to_candidate_seconds=duration(started, finished) if delivery else None,
        recovery_seconds=duration(adverse, accepted_recovery) if restored else None,
        detection_to_recovery_decision_seconds=duration(adverse, recovery),
        action_attempts=len(actions), retries=sum(e.get('attempt', 1)>1 and e.get('entity')!='rollback' for e in actions),
        rollback_attempts=sum(e.get('entity')=='rollback' for e in actions), observations=len(measurements),
        reconciliations=sum(e['event']=='reconciliation' for e in events),
        summed_entity_duration_ms=sum(e.get('duration_ms',0) for e in events if e['event']=='action_finished'),
        traffic_requests=traffic.get('requests'), traffic_errors=traffic.get('injected_errors'),
        release_sha=result.get('release_sha'), known_good_sha=result.get('known_good_sha'),
        human_interventions=len(interventions) if isinstance(interventions,list) else None,
        validation_issues=reasons, eligible_for_comparison=not reasons)
    # These are protocol expectations, not an independent oracle proving application correctness.
    expectations = {'healthy': delivery, 'transient-test-failure': delivery and row['retries'] == 1,
        'build-failure': not row['production_dispatched'] and result.get('outcome') == 'stopped' and result.get('executions', {}).get('build', {}).get('status') == 'failure',
        'staging-persistent': not row['production_dispatched'] and result.get('outcome') == 'stopped',
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
