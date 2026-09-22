"""Dispatch one pre-started conventional trial, or resolve its run without redispatch.

JSON is sent directly to gh stdin, avoiding PowerShell quoting/encoding changes.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import time


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def select_run(runs, worker, title, started):
    earliest=datetime.fromisoformat(started.replace('Z','+00:00'))-timedelta(seconds=5)
    matches=[r for r in runs if r['headSha']==worker and r['displayTitle']==title
             and datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'))>=earliest]
    if len(matches)>1: raise ValueError('Ambiguous matching runs: stop and reconcile; never choose the latest')
    return matches[0] if matches else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--trial',required=True)
    parser.add_argument('--resolve-only',action='store_true')
    args=parser.parse_args();study=read(args.study/'study.json')
    trial=next(t for t in study['trials'] if t['id']==args.trial)
    if trial['mechanism']!='github-actions': raise ValueError('Not a conventional trial')
    folder=args.study/'trials'/trial['id']; start=read(folder/'started.json')
    if (folder/'github-run-id.txt').exists():
        print((folder/'github-run-id.txt').read_text().strip());return
    if not args.resolve_only:
        pair=read(study['pair_file'])
        receipt=read(pair['known_good_receipt'])
        if receipt['release_sha']!=study['v1_sha']: raise ValueError('Baseline differs from frozen study')
        payload=dict(release_sha=study['v2_sha'],scenario=trial['case'],baseline='false',
                     known_good_receipt=json.dumps(receipt),confirm_compatible_rollback='true',seed=str(study['seed']))
        # Exclusive intent persists even if the response is lost. Resume is read-only.
        with (folder/'dispatch-intent.json').open('x',encoding='utf-8') as stream:
            json.dump(dict(at=datetime.now(timezone.utc).isoformat(),worker=study['worker_sha']),stream)
        response=subprocess.run(['gh','workflow','run','ci-cd.yml','--repo',study['repository'],
                                 '--ref',study['worker_ref'],'--json'],input=json.dumps(payload),
                                 text=True,encoding='utf-8',capture_output=True)
        (folder/'dispatch-response.json').write_text(json.dumps(dict(code=response.returncode,stdout=response.stdout,stderr=response.stderr)),encoding='utf-8')
        if response.returncode: raise RuntimeError('Dispatch failed or uncertain. Preserve intent; use --resolve-only.')
    title=f"conventional-{trial['case']}-{study['v2_sha']}"
    for _ in range(15):
        response=subprocess.run(['gh','run','list','--repo',study['repository'],'--workflow','ci-cd.yml',
            '--limit','100','--json','databaseId,displayTitle,headSha,createdAt,status,url'],text=True,encoding='utf-8',capture_output=True,check=True)
        selected=select_run(json.loads(response.stdout),study['worker_sha'],title,start['started_at'])
        if selected:
            (folder/'github-run-id.txt').write_text(str(selected['databaseId'])+'\n',encoding='utf-8')
            print(selected['databaseId']);return
        time.sleep(2)
    raise RuntimeError('No matching run found yet. Use --resolve-only; do not redispatch.')


if __name__=='__main__': main()
