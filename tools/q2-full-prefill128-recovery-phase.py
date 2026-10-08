#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the owner-requested retained128 native curve under its active window."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shlex
import subprocess
import sys
from q2_window_registry import active_window

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'
SSH=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','ConnectTimeout=10','paperboy@192.168.5.157']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('arm',choices=('64','128'))
    args=parser.parse_args()
    pp=ROOT/'config/q2-full-prefill128-recovery-plan.json';ap=ROOT/'config/q2-full-prefill128-recovery-window-admission.json'
    p=json.loads(pp.read_text());a=json.loads(ap.read_text())
    assert p['schema']=='synapse-lie.q2-full-prefill128-recovery-plan.v1' and not p['components'] and len(p['arms'])==2
    assert a['state']=='Q2_FULL_PREFILL128_RECOVERY_WINDOW_ADMITTED' and a['gpu_reserved'] and a['plan_sha256']==sha(pp)
    for name,digest in {**p['fixtures'],**p['manifests']}.items():assert sha(ROOT/name)==digest,name
    arm=p['arms'][0 if args.arm=='64' else 1]
    assert not (ROOT/'evidence'/arm['label']).exists(),'Preserve existing cohort'
    code=inspect.getsource(active_window)+'\n'+f'''
import hashlib,json,pathlib
path=pathlib.Path({(REMOTE+ap.name)!r})
assert hashlib.sha256(path.read_bytes()).hexdigest()=={sha(ap)!r}
a=json.loads(path.read_text())
rows=[json.loads(x) for x in pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines() if x.strip()]
active_window(rows,{sha(ap)!r},a['at'])
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
import sys
sys.path.insert(0,{(REMOTE)!r}+{p['host']!r}+'/tools')
from q2_thermal import sample,enforce
temps=sample();enforce(temps)
assert all(t['device']!='k10temp' or t['temperature_mc']<=60000 for t in temps),'CPU above cold-start admission'
print(json.dumps(dict(active_window=True,curve={args.arm!r},thermal=temps)))
'''
    result=subprocess.run(SSH+['python3 -c '+shlex.quote(code)])
    if result.returncode:return result.returncode
    return subprocess.run([sys.executable,str(ROOT/'tools/q2-remote.py'),arm['mode'],arm['label'],
                           '--source-variant',arm['variant'],'--native-curve','--prefill-only-depth',str(arm['depth'])]).returncode


if __name__=='__main__':sys.exit(main())
