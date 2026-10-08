#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise original-model window ownership and failure release without GPU."""

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
    'q5_model_window', ROOT / 'tools/q2-q5-model-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)
INPUT = ROOT / 'evidence/q2-library-norm-model-candidate-r1/results/pp2048-input.i32'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test(candidate_exit):
    with tempfile.TemporaryDirectory(prefix='lie-q5-model-window-') as temp:
        root = Path(temp)
        run = root / 'run'
        here = run / 'q2-q5-model-shared-down-r1'
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
        prior = run / 'q2-q5-overlay-converter-r1' / 'release.json'
        prior.parent.mkdir()
        prior.write_text(json.dumps(previous) + '\n')
        program = here / 'q2_model'
        program.write_text(
            '#!/usr/bin/env python3\n'
            'import os,pathlib,shutil,sys\n'
            'p=pathlib.Path("results/pp2048-input.i32")\n'
            f'shutil.copyfile({str(INPUT)!r},p)\n'
            'print("fixture",flush=True)\n'
            f'sys.exit({candidate_exit} if '
            'os.environ.get("LIE_EXPERIMENTAL_Q5_DECODE") else 0)\n')
        program.chmod(0o700)
        plan = {
            'schema': 'synapse-lie.q2-q5-model-window-plan.v1',
            'label': here.name, 'family': 'shared-down',
            'arms': ['q8', 'shared-down'], 'model_path': str(model),
            'model_access': True, 'remote_build': False, 'remote_cleanup': False,
            'physical_prompt_tokens': 2048, 'context_capacity': 9216,
            'chunk': 2048, 'output_tokens': 128, 'timed_decode_calls': 127,
            'input_sha256': sha(INPUT), 'timeout_seconds_per_arm': 900,
            'previous_release': str(prior.relative_to(run)),
            'previous_release_sha256': sha(prior),
            'staged_sha256': {program.name: sha(program)},
        }
        (here / 'plan.json').write_text(json.dumps(plan) + '\n')
        registry = root / 'runs.jsonl'
        registry.write_text(json.dumps({'event': 'window_release',
                                        'receipt_sha256': sha(prior),
                                        'owner': 'synapse-lie-q2',
                                        'at': '2026-01-01'}) + '\n')
        window.HERE = here
        window.RUN = run
        window.REGISTRY = registry
        window.PLAN = here / 'plan.json'
        window.ADMISSION = here / 'admission.json'
        window.RESULT = here / 'result.json'
        window.RELEASE = here / 'release.json'
        window.kfd = lambda: []
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
        assert result['complete'] == (candidate_exit == 0)
        assert observed == (0 if candidate_exit == 0 else 1)
        assert [a['exit_code'] for a in result['arms']] == [0, candidate_exit]
        assert all(a['original_input_match'] for a in result['arms'])
        assert all((here / a['name'] / 'arm.json').exists()
                   for a in result['arms'])
        released = json.loads(window.RELEASE.read_text())
        assert len(released['retired_identities']) == 2
        assert len(released['retired_groups']) == 2
        assert released['core_cpu_lease'] == leases[0]
        assert released['leases'] == leases[1:]
        assert released['models'] == previous['models']
        assert sha(model) == hashlib.sha256(b'unchanged model identity').hexdigest()
        events = [json.loads(line) for line in registry.read_text().splitlines()]
        assert [row['event'] for row in events] == [
            'window_release', 'window_admit', 'window_release']
        assert events[-1]['receipt_sha256'] == sha(window.RELEASE)


if __name__ == '__main__':
    test(0)
    test(3)
    print('q5-model window CPU fixture: pass and failure both release')
