#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure one new original long prefix with the immutable row-byte candidate."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('depth', type=int, choices=(64,128))
    args = parser.parse_args()
    pp = ROOT/'config/q2-ple-row-bytes-long-plan.json'
    ap = ROOT/'config/q2-ple-row-bytes-long-window-admission.json'
    p, a = [json.loads(path.read_text()) for path in (pp, ap)]
    assert p['schema'] == 'synapse-lie.q2-ple-row-bytes-long-plan.v1'
    assert not p['components'] and [arm['depth'] for arm in p['arms']] == [65536,131072]
    arm = next(arm for arm in p['arms'] if arm['depth'] == args.depth*1024)
    assert (arm['mode'], arm['variant']) == ('q2-prefill-ple-row-bytes', 'prefill-ple-row-bytes-q2')
    assert arm['flags'] == ['--native-curve']
    assert a['state'] == 'Q2_PLE_ROW_BYTES_LONG_WINDOW_ADMITTED' and a['gpu_reserved']
    assert a['plan_sha256'] == sha(pp) and a['planned_labels'] == [x['label'] for x in p['arms']]
    for name, digest in {**p['fixtures'], **p['manifests']}.items():
        assert sha(ROOT/name) == digest, name
    assert not (ROOT/'evidence'/arm['label']).exists(), 'Preserve existing cohort'
    code = inspect.getsource(active_window) + '\n' + f'''
import hashlib,json,pathlib,sys,time
path=pathlib.Path({(REMOTE+ap.name)!r})
assert hashlib.sha256(path.read_bytes()).hexdigest()=={sha(ap)!r}
a=json.loads(path.read_text())
rows=[json.loads(x) for x in pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines() if x.strip()]
active_window(rows,{sha(ap)!r},a['at'])
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
sys.path.insert(0,{(REMOTE+p['host']+'/tools')!r})
from q2_thermal import sample,enforce
deadline=time.monotonic()+600
while True:
 temps=sample();enforce(temps)
 if all(t['device']!='k10temp' or t['temperature_mc']<=60000 for t in temps):break
 if time.monotonic()>=deadline:raise RuntimeError('CPU cold-start admission timeout')
 time.sleep(2)
print(json.dumps(dict(active_window=True,depth={arm['depth']!r},thermal=temps)))
'''
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)])
    if result.returncode:
        return result.returncode
    return subprocess.run([sys.executable, str(ROOT/'tools/q2-remote.py'), arm['mode'],
        arm['label'], '--source-variant', arm['variant'], *arm['flags'],
        '--prefill-only-depth', str(arm['depth'])]).returncode


if __name__ == '__main__':
    sys.exit(main())
