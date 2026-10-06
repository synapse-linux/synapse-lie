#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch only the new Q2 down component/model after a frozen, still-active admission."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shlex
import subprocess
import sys

from q2_window_registry import active_window

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
       'paperboy@192.168.5.157']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(plan_path, admission_path):
    plan = json.loads(plan_path.read_text())
    receipt = json.loads(admission_path.read_text())
    if (plan['schema'] != 'synapse-lie.q2-down-fixed-contract-plan.v1' or
            len(plan['components']) != 1 or plan['components'][0]['mode'] != 'down-fixed-contract-check' or
            plan['components'][0]['variant'] != 'down-fixed-contract' or len(plan['arms']) != 1 or plan['run_controls'] or
            plan['arms'][0]['mode'] != 'q2-counting-down-fixed-contract' or
            plan['arms'][0]['variant'] != 'down-fixed-contract'):
        raise ValueError('Expected one Q2 down fixed contract model candidate plan')
    if (receipt['state'] != 'Q2_DOWN_FIXED_CONTRACT_WINDOW_ADMITTED' or
            receipt['gpu_reserved'] is not True or receipt['owner'] != 'synapse-lie-q2' or
            receipt['plan_sha256'] != sha(plan_path) or
            receipt['previous_release_sha256'] != plan['previous_release_sha256'] or
            receipt['planned_labels'] != [a['label'] for a in plan['components'] + plan['arms']]):
        raise ValueError('Active admission scope differs')
    for name, digest in {**plan['fixtures'], **plan['manifests'],
                        plan['window_helper']: plan['window_helper_sha256']}.items():
        if sha(ROOT / name) != digest:
            raise ValueError('Frozen identity differs: ' + name)
    return plan, receipt, sha(admission_path)


def run(phase, plan_path, admission_path):
    plan, receipt, digest = validate(plan_path, admission_path)
    arm = plan['components'][0] if phase == 'component' else plan['arms'][0]
    if phase in ('component', 'model') and (ROOT / 'evidence' / arm['label']).exists():
        raise ValueError('Cohort exists; preserve it and freeze a fresh cohort')
    if phase not in ('check', 'component', 'model'):
        raise ValueError('Only the new Q2 down component and model is authorized by this plan')
    code = inspect.getsource(active_window) + '\n' + f'''
import hashlib,json,pathlib
path=pathlib.Path({(REMOTE + admission_path.name)!r})
assert hashlib.sha256(path.read_bytes()).hexdigest()=={digest!r}
r=json.loads(path.read_text())
assert r['state']=='Q2_DOWN_FIXED_CONTRACT_WINDOW_ADMITTED' and r['gpu_reserved'] is True
assert r['plan_sha256']=={sha(plan_path)!r}
rows=[json.loads(line) for line in pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines() if line.strip()]
active_window(rows,{digest!r},r['at'])
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
print(json.dumps(dict(admission_active=True,receipt_sha256={digest!r})))
'''
    if phase == 'model':
        label = plan['components'][0]['label']
        code += f'''
p=pathlib.Path({(REMOTE + label + '/results')!r})
c=json.loads((p/'result.json').read_text())
assert c['finished_at'] and c['mode']=='down-fixed-contract-check' and c['model_access'] is False
assert [x['exit_code'] for x in c['commands']][:-1]==[0,0]
assert c['commands'][-1]['exit_code'] in (0,1)
events=[json.loads(line) for line in (p/'03.log').read_text().splitlines() if line.startswith('{{')]
replays=[e for e in events if e.get('event')=='down_fixed_contract_replay']
complete=[e for e in events if e.get('event')=='down_fixed_contract_complete']
assert len(replays)==132 and len(complete)==1
assert all(e['guards_exact'] and e['unwritten_values']==e['nonfinite_values']==0 for e in replays)
print(json.dumps(dict(component_device_work_safe=True,finite_replay_pairs=132,full_model_admitted=True)))
'''
    checked = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)], check=False)
    if checked.returncode or phase == 'check':
        return checked.returncode
    return subprocess.run([sys.executable, str(ROOT / 'tools/q2-remote.py'), arm['mode'],
                           arm['label'], '--source-variant', arm['variant']] +
                          (['--rebuild-mmq'] if phase == 'model' else []), check=False).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'component', 'model'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    args = parser.parse_args()
    return run(args.phase, args.plan, args.admission)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print('Refusing GPU phase: ' + str(error), file=sys.stderr)
        sys.exit(2)
