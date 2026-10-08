#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch the new partition selector component under its exact active admission."""
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
    if len(sys.argv) != 1:
        raise ValueError('The frozen partition selector phase accepts no overrides')
    pp = ROOT/'config/q2-select-partition-plan.json'
    ap = ROOT/'config/q2-select-partition-window-admission.json'
    p, a = [json.loads(path.read_text()) for path in (pp, ap)]
    assert p['schema'] == 'synapse-lie.q2-select-partition-plan.v1'
    assert not p['arms'] and len(p['components']) == 1
    arm = p['components'][0]
    assert (arm['mode'], arm['variant']) == ('select-partition-check', 'iq2-fixed-bounds')
    assert a['state'] == 'Q2_SELECT_PARTITION_WINDOW_ADMITTED' and a['gpu_reserved']
    assert a['plan_sha256'] == sha(pp) and a['planned_labels'] == [arm['label']]
    for name, digest in {**p['fixtures'], **p['manifests']}.items():
        assert sha(ROOT/name) == digest, name
    assert not (ROOT/'evidence'/arm['label']).exists(), 'Preserve existing cohort'
    code = inspect.getsource(active_window) + '\n' + f'''
import hashlib,json,pathlib
path=pathlib.Path({(REMOTE+ap.name)!r})
assert hashlib.sha256(path.read_bytes()).hexdigest()=={sha(ap)!r}
a=json.loads(path.read_text())
rows=[json.loads(x) for x in pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines() if x.strip()]
active_window(rows,{sha(ap)!r},a['at'])
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
print(json.dumps(dict(active_window=True,component_only=True)))
'''
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)])
    if result.returncode:
        return result.returncode
    return subprocess.run([sys.executable, str(ROOT/'tools/q2-remote.py'), arm['mode'],
                           arm['label'], '--source-variant', arm['variant']]).returncode


if __name__ == '__main__':
    sys.exit(main())
