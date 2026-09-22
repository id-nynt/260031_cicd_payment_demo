"""Common pairing identity, independent of the decision mechanism."""
import hashlib
import json

def protocol_key(case, seed, candidate, baseline, worker_sha, contract, policy, profile, input_hashes=None):
    values=dict(case=case,seed=seed,candidate=candidate,baseline=baseline,worker_sha=worker_sha,
                contract=contract,policy=policy,profile=profile,pause_ms=60000,input_hashes=input_hashes)
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def traffic_targets(case, selected):
    """Traffic clients shared by both mechanisms; repair uses separate production probes."""
    targets = {}
    for entity in ('staging', 'production'):
        if entity == 'production' and case in ('candidate-stopped', 'candidate-restart-fails'):
            continue
        profile = selected['profile'] if entity == selected['entity'] and selected['profile'] else 'healthy'
        targets[entity] = dict(profile=profile, fault_expected='errors' in profile,
            summary_suffix='-traffic' if entity == selected['entity'] else '-traffic-' + entity)
    return targets
