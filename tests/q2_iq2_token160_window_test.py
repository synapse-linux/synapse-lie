#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise bounded admission, owned child lifetime and release without GPU."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location(
    'token160_window', ROOT / 'tools/q2-iq2-token160-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test(exit_code):
    with tempfile.TemporaryDirectory(prefix='lie-token160-window-') as temp:
        root = Path(temp)
        run = root / 'run'
        here = run / 'q2-iq2-token160-component-r1'
        here.mkdir(parents=True)
        model = root / 'model.gguf'
        model.write_bytes(b'unchanged model identity')
        stat = model.stat()
        leases = []
        for index in range(5):
            path = root / f'lease-{index}'
            path.write_bytes(b'')
            identity = path.stat()
            leases.append({'path': str(path), 'device': identity.st_dev,
                           'inode': identity.st_ino})
        previous = {
            'core_cpu_lease': leases[0], 'leases': leases[1:],
            'retired_identities': [], 'retired_groups': [],
            'models': [{'path': str(model), 'device': stat.st_dev,
                        'inode': stat.st_ino, 'bytes': stat.st_size,
                        'mtime_ns': stat.st_mtime_ns, 'ctime_ns': stat.st_ctime_ns}],
        }
        prior = run / 'previous.json'
        prior.write_text(json.dumps(previous) + '\n')
        program = here / 'q2_iq2_token160_check'
        program.write_text(f'#!/bin/sh\nprintf "fixture\\n"\nsleep 0.2\nexit {exit_code}\n')
        program.chmod(0o700)
        plan = {
            'schema': 'synapse-lie.q2-iq2-token160-window-plan.v1',
            'label': here.name, 'component_only': True,
            'model_access': False, 'remote_build': False, 'remote_cleanup': False,
            'previous_release': prior.name,
            'previous_release_sha256': sha(prior),
            'staged_sha256': {program.name: sha(program)},
        }
        (here / 'plan.json').write_text(json.dumps(plan) + '\n')
        registry = root / 'runs.jsonl'
        registry.write_text(json.dumps({'event': 'window_release',
                                        'receipt_sha256': sha(prior),
                                        'owner': 'synapse-lie-q2', 'at': '2026-01-01'}) + '\n')
        window.HERE = here
        window.RUN = run
        window.REGISTRY = registry
        window.PLAN = here / 'plan.json'
        window.ADMISSION = here / 'admission.json'
        window.RELEASE = here / 'release.json'
        window.RESULT = here / 'result.json'
        window.clients = lambda: []
        window.sample = lambda: [
            {'device': 'k10temp', 'temperature_mc': 35000, 'over_limit': False},
            {'device': 'amdgpu', 'temperature_mc': 40000, 'over_limit': False},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            loaded, prior_data = window.load()
            window.preflight_or_admit('preflight', loaded, prior_data)
            assert not window.ADMISSION.exists()
            window.preflight_or_admit('admit', loaded, prior_data)
            observed = window.run(loaded, prior_data)
            window.release(loaded, prior_data)
        result = json.loads(window.RESULT.read_text())
        assert result['exit_code'] == exit_code
        assert observed == (0 if exit_code == 0 else 1)
        assert window.ADMISSION.exists() and window.RELEASE.exists()
        assert sha(model) == hashlib.sha256(b'unchanged model identity').hexdigest()
        events = [json.loads(line) for line in registry.read_text().splitlines()]
        assert [row['event'] for row in events] == [
            'window_release', 'window_admit', 'window_release']
        assert events[-1]['receipt_sha256'] == sha(window.RELEASE)
        assert (here / 'component.stdout').read_text() == 'fixture\n'


if __name__ == '__main__':
    test(0)
    test(3)
    print('token160 window CPU fixture: pass and failure both release')
