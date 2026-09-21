"""Local parity checks: real Jason vs imperative controller, simulated external adapters only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import yaml
from project_artifacts import ROOT, generate

CASES=['healthy','transient_test_failure','exhausted_test_failure','production_failure','execution_uncertain','telemetry_block','production_transient','production_unhealthy']
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'bdi/build'/('comparison-'+uuid.uuid4().hex[:8]))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    pipeline=yaml.safe_load((ROOT/'models/01_pipeline.yaml').read_text())
    pipeline['execution'].update(observation_attempts=3,observation_interval_seconds=0,retry_interval_seconds=0,reconciliation_interval_seconds=0)
    p=args.output/'pipeline.yaml';p.write_text(yaml.safe_dump(pipeline,sort_keys=False))
    project=args.output/'project';generate(project,p,ROOT/'models/02_goal.yaml')
    env={k:v for k,v in os.environ.items() if not k.startswith('BDI_') and k not in ('GITHUB_TOKEN','GH_TOKEN','EXPERIMENT_EVENTS_FILE','EXPERIMENT_MECHANISM')}
    rows=[]
    for case in CASES:
        pair=[]
        for mechanism in ('bdi','conventional'):
            target=args.output/f'{case}-{mechanism}'
            with (args.output/f'{case}-{mechanism}.log').open('w') as log:
                process=subprocess.run([sys.executable,'-B',str(ROOT/'run_controller.py'),'--project-dir',str(project),'--mechanism',mechanism,
                    '--scenario',case,'--artifacts-dir',str(target)],env=env,stdout=log,stderr=subprocess.STDOUT)
            result=json.loads((target/'controller-result.json').read_text())
            events=[json.loads(l) for l in (target/'experiment-events.jsonl').read_text().splitlines()]
            row={'case':case,'mechanism':mechanism,'outcome':result['outcome'],'recovery':result['recovery_outcome'],
                'actions':[(e['entity'],e['attempt']) for e in events if e['event']=='action_started'],
                'health':result['telemetry'],'exit_code':process.returncode}
            assert len([e for e in events if e['event']=='campaign_finished'])==1,row
            rows.append(row);pair.append(row)
            print(case,mechanism,result['outcome'],result['recovery_outcome'],flush=True)
        for key in ('outcome','recovery','actions','health','exit_code'): assert pair[0][key]==pair[1][key],(case,key,pair)
    (args.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('All eight simulated pairs agree. This is correctness verification, not a live superiority result.')
if __name__=='__main__':main()
