"""Common pairing identity, independent of the decision mechanism."""
import hashlib
import json

def protocol_key(case, seed, candidate, baseline, worker_sha, contract, policy, profile):
    values=dict(case=case,seed=seed,candidate=candidate,baseline=baseline,worker_sha=worker_sha,
                contract=contract,policy=policy,profile=profile,pause_ms=60000)
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
