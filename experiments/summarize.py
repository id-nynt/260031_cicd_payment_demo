"""Export recorded trials and paired delivery outcomes; never infer success from missing evidence."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def summarize(root, candidate=None):
    rows = []
    for path in sorted(root.rglob('experiment-metrics.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        if candidate and row.get('release_sha') != candidate:
            continue
        row['evidence_path'] = str(path.resolve())
        # Downloaded metrics retain the runner's original path; retain it as provenance.
        rows.append(row)
    incomplete = []
    for path in sorted(root.rglob('collection.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if not record.get('complete_download'):
            incomplete.append(str(path.resolve()))
            for row in rows:
                if path.parent in Path(row['evidence_path']).parents:
                    row['eligible_for_comparison'] = False
                    row['validation_issues'] = row.get('validation_issues', []) + ['incomplete_download']
    groups = {}
    for row in rows:
        key = (row.get('mechanism'), row.get('case'))
        groups.setdefault(key, []).append(row)
    summary = []
    for (mechanism, case), trials in sorted(groups.items(), key=lambda x: str(x[0])):
        valid = [r for r in trials if r.get('eligible_for_comparison') is True]
        recovered = [r for r in valid if r.get('service_restored')]
        recovery_attempted = [r for r in valid if r.get('rollback_attempts', 0) > 0]
        times = [r['recovery_seconds'] for r in recovered if r.get('recovery_seconds') is not None]
        summary.append(dict(mechanism=mechanism, case=case, recorded=len(trials), eligible=len(valid),
            excluded=len(trials)-len(valid), delivered=sum(bool(r.get('candidate_delivered')) for r in valid),
            delivery_rate=sum(bool(r.get('candidate_delivered')) for r in valid)/len(valid) if valid else None,
            recovery_attempted=len(recovery_attempted), restored=len(recovered),
            restoration_rate=len(recovered)/len(recovery_attempted) if recovery_attempted else None,
            mean_recovery_seconds=mean(times) if times else None,
            mean_retries=mean(r['retries'] for r in valid) if valid else None))
    pairs = {}
    for row in rows:
        if row.get('eligible_for_comparison') and row.get('protocol_key'):
            pairs.setdefault(row['protocol_key'], {}).setdefault(row['mechanism'], []).append(row)
    matched = [dict(protocol_key=key, bdi_trials=len(value.get('bdi', [])),
                    conventional_trials=len(value.get('github-actions', [])),
                    balanced=len(value.get('bdi', [])) == len(value.get('github-actions', [])))
               for key, value in pairs.items()]
    return rows, dict(groups=summary, protocol_groups=matched, incomplete_collections=incomplete)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent/'results')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', help='Measured v2 SHA; excludes bootstrap/reset releases')
    args = parser.parse_args()
    rows, summary = summarize(args.root, args.candidate)
    args.output.mkdir(parents=True, exist_ok=False)
    fields = sorted({key for row in rows for key in row})
    with (args.output/'trials.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (dict,list)) else v for k,v in r.items()} for r in rows)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
