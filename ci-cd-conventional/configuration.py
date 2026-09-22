"""Frozen conventional policy: no agent, generator or framework runtime dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parent


def digest(path):
    # Match BDI provenance across Windows CRLF and Linux LF checkouts.
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def load_configuration():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    contract = ROOT / 'snapshots/contract.yaml'
    if digest(contract) != config['contract_sha256']:
        raise ValueError('Conventional contract snapshot hash mismatch')
    doc = yaml.safe_load(contract.read_text(encoding='utf-8'))
    expected = dict(execution=doc['execution'], thresholds=doc['bindings']['thresholds'],
                    max_production_ms=int(next(x.split(' <= ')[1] for x in doc['goals']['maintain(M)'] if x.startswith('production.duration'))),
                    recovery_triggers=doc['recovery_policy']['rollback']['run_after'],
                    **({'candidate_repair':doc['candidate_repair']} if 'candidate_repair' in doc else {}),
            **({'rollback_reconsideration':doc['rollback_reconsideration']} if 'rollback_reconsideration' in doc else {}))
    if config['policy'] != expected or config['bindings'] != doc['bindings']:
        raise ValueError('Configuration differs from reviewed contract snapshot')
    for name, entry in config['configuration_inputs'].items():
        if digest(ROOT / 'snapshots' / (name + '.input.yaml')) != entry['sha256']:
            raise ValueError('Conventional source snapshot hash mismatch: ' + name)
    execution = config['policy']['execution']
    if execution['max_retries'] != 1 or execution['retry_interval_seconds'] != 5 or set(execution['retry_safe']) != {'build','test','security','staging','production'}:
        raise ValueError('Static workflow supports one retry after five seconds')
    return config


def known_good_sha(receipt, bindings, repository):
    data = json.loads(receipt.read_text(encoding='utf-8'))
    if (data.get('mode') != 'github' or data.get('outcome') != 'achieved'
            or data.get('project') != bindings['project'] or data.get('repository') != repository):
        raise ValueError('Known-good receipt must verify a live successful release for this project/repository')
    sha = data.get('release_sha', '')
    verified = data.get('verified_releases', {}).get('production', {})
    if (not re.fullmatch('[0-9a-fA-F]{40}', sha) or verified.get('release_sha') != sha
            or not verified.get('github_run_id') or verified.get('environment') != bindings['controller']['environments']['production']):
        raise ValueError('Receipt does not verify the production recovery source')
    return sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-bdi-parity', action='store_true', help='Optional paired-study check; requires the BDI checkout')
    args = parser.parse_args()
    config = load_configuration()
    if args.check_bdi_parity:
        sys.path.insert(0, str(ROOT.parent / 'bdi-cicd-framework'))
        from project_artifacts import validate
        from run_controller import conventional_policy
        doc, _, manifest, _ = validate(ROOT.parent / 'bdi-cicd-framework')
        if (config['policy'] != conventional_policy(doc) or config['bindings'] != doc['bindings']
                or config['contract_sha256'] != manifest['workflow_sha256']
                or config['configuration_inputs'] != manifest['inputs']):
            raise ValueError('BDI and conventional configurations differ; review and refresh conventional snapshots before pairing')
    print('Conventional configuration valid' + ('; BDI parity verified' if args.check_bdi_parity else ''))


if __name__ == '__main__':
    main()
