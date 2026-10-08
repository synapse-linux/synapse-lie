#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the full-inventory amendment against a closed CPU-only fixture."""

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
    'token160_handover', ROOT / 'tools/q2-iq2-token160-handover.py')
handover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handover)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with tempfile.TemporaryDirectory(prefix='lie-token160-handover-') as temp:
        root = Path(temp)
        run = root / 'run'
        here = run / 'component'
        here.mkdir(parents=True)
        model = root / 'model.gguf'
        model.write_bytes(b'fixed model')
        stat = model.stat()
        leases = []
        for index in range(5):
            path = root / f'lease-{index}'
            path.write_bytes(b'')
            info = path.stat()
            leases.append({'path': str(path), 'device': info.st_dev,
                           'inode': info.st_ino})
        previous = {
            'core_cpu_lease': leases[0], 'leases': leases[1:],
            'retired_identities': [{'pid': 9999999, 'start_ticks': 1}],
            'retired_groups': [9999999],
            'models': [{'path': str(model), 'device': stat.st_dev,
                        'inode': stat.st_ino, 'bytes': stat.st_size,
                        'mtime_ns': stat.st_mtime_ns, 'ctime_ns': stat.st_ctime_ns}],
        }
        prior = run / 'prior.json'
        prior.write_text(json.dumps(previous) + '\n')
        admission = here / 'admission.json'
        admission.write_text('{}\n')
        plan = here / 'plan.json'
        plan.write_text('{}\n')
        result = here / 'result.json'
        result.write_text(json.dumps({'exit_code': 0, 'finished_at': '2026-01-01',
                                      'model_access': False, 'pid': 9999998,
                                      'start_ticks': 1,
                                      'process_group': 9999998}) + '\n')
        release = here / 'release.json'
        release.write_text(json.dumps({
            'state': 'Q2_IQ2_TOKEN160_WINDOW_RELEASED',
            'component_result_sha256': sha(result),
            'admission_sha256': sha(admission), 'kfd': [],
            'models_unchanged': 7, 'leases_free': 5,
            'remote_cleanup': False}) + '\n')
        registry = root / 'registry.jsonl'
        registry.write_text(json.dumps({'event': 'window_release',
                                        'receipt_sha256': sha(release)}) + '\n')
        handover.HERE = here
        handover.RUN = run
        handover.REGISTRY = registry
        handover.PREVIOUS = prior
        handover.RELEASE = release
        handover.RESULT = result
        handover.OUT = here / 'handover.json'
        handover.PRIOR_SHA = sha(prior)
        handover.RELEASE_SHA = sha(release)
        handover.RESULT_SHA = sha(result)
        handover.PLAN_SHA = sha(plan)
        handover.sample = lambda: [
            {'device': 'k10temp', 'temperature_mc': 35000, 'over_limit': False},
            {'device': 'amdgpu', 'temperature_mc': 40000, 'over_limit': False},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            handover.main()
        report = json.loads(handover.OUT.read_text())
        assert report['retired_identities'] == [
            {'pid': 9999999, 'start_ticks': 1},
            {'pid': 9999998, 'start_ticks': 1}]
        assert report['retired_groups'] == [9999998, 9999999]
        assert report['core_cpu_lease'] == leases[0]
        assert report['models'] == previous['models']
        events = [json.loads(line) for line in registry.read_text().splitlines()]
        assert events[-1]['receipt_sha256'] == sha(handover.OUT)
        assert sha(model) == hashlib.sha256(b'fixed model').hexdigest()
    print('token160 full-inventory handover fixture passed')


if __name__ == '__main__':
    main()
