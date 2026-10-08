#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch the saved native prefix128K diagnostic under its exact admission."""
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
        raise ValueError('The frozen prefix128K phase accepts no overrides')
    pp = ROOT/'config/q2-long-profile128-plan.json'
    ap = ROOT/'config/q2-long-profile128-window-admission.json'
    p, a = [json.loads(path.read_text()) for path in (pp, ap)]
    assert p['schema'] == 'synapse-lie.q2-long-profile128-plan.v1'
    assert not p['components'] and len(p['arms']) == 1
    arm = p['arms'][0]
    assert (arm['mode'], arm['variant']) == ('q2-prefill128', 'prefill128-q2')
    assert arm['flags'] == ['--native-curve','--profile-prefix128k']
    assert a['state'] == 'Q2_LONG_PROFILE128_WINDOW_ADMITTED' and a['gpu_reserved']
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
print(json.dumps(dict(active_window=True,diagnostic_only=True)))
'''
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)])
    if result.returncode:
        return result.returncode
    return subprocess.run([sys.executable, str(ROOT/'tools/q2-remote.py'), arm['mode'],
                           arm['label'], '--source-variant', arm['variant'], *arm['flags']]).returncode


if __name__ == '__main__':
    sys.exit(main())
