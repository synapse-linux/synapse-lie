#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch the private IQ2 token256 GPU component under its active admission."""

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
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=10', 'paperboy@192.168.5.157']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if len(sys.argv) != 1:
        raise ValueError('Frozen IQ2 token256 phase accepts no overrides')
    plan_path = ROOT / 'config/q2-iq2-token256-plan.json'
    admission_path = ROOT / 'config/q2-iq2-token256-window-admission.json'
    plan = json.loads(plan_path.read_text())
    admission = json.loads(admission_path.read_text())
    assert plan['schema'] == 'synapse-lie.q2-iq2-token256-plan.v1'
    assert plan['arms'] == [] and len(plan['components']) == 1
    component = plan['components'][0]
    assert (component['mode'], component['variant']) == (
        'iq2-token256-check', 'iq2-token256-probe')
    assert admission['state'] == 'Q2_IQ2_TOKEN256_WINDOW_ADMITTED'
    assert admission['gpu_reserved'] and admission['plan_sha256'] == sha(plan_path)
    assert admission['planned_labels'] == [component['label']]
    for name, digest in plan['fixtures'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(ROOT / plan['window_helper']) == plan['window_helper_sha256']
    assert sha(ROOT / plan['phase_helper']) == plan['phase_helper_sha256']
    assert not (ROOT / 'evidence' / component['label']).exists()
    code = inspect.getsource(active_window) + '\n' + f'''
import hashlib,json,pathlib
root=pathlib.Path({REMOTE!r})
path=root/{admission_path.name!r}
assert hashlib.sha256(path.read_bytes()).hexdigest()=={sha(admission_path)!r}
a=json.loads(path.read_text())
plan=root/{plan_path.name!r}
assert hashlib.sha256(plan.read_bytes()).hexdigest()=={sha(plan_path)!r}
rows=[json.loads(line) for line in pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines() if line.strip()]
active_window(rows,{sha(admission_path)!r},a['at'])
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
print(json.dumps(dict(active_window=True,component_only=True)))
'''
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)])
    if result.returncode:
        return result.returncode
    return subprocess.run([sys.executable, str(ROOT / 'tools/q2-remote.py'),
                           component['mode'], component['label'],
                           '--source-variant', component['variant']]).returncode


if __name__ == '__main__':
    sys.exit(main())
