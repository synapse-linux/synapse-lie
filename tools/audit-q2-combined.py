#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the cumulative campaign's frozen inputs, results and admission."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('combined', ROOT / 'tools/analyze-q2-combined.py')
combined = importlib.util.module_from_spec(spec)
spec.loader.exec_module(combined)
require = combined.require


def main():
    fixtures = ['CMakeLists.txt', 'cmake/hip/CMakeLists.txt',
                'tools/q2-remote.py', 'tools/q2-runner.py',
                'tools/q2_process.py', 'tools/q2_thermal.py', 'tools/q2_reuse.py',
                'experiments/ple_flow.c', 'experiments/ple_flow.h',
                'tests/q2_remote_test.py', 'tests/q2_model.cpp',
                'tests/q2_profile_markers.hip', 'tests/q2_narrow_vector.cpp',
                'tests/ple_flow.c', 'tests/q2_ple_lookahead.cpp']
    runs = {}
    labels = ['q2-combined-host-r1', 'q2-combined-retained-narrow-r1',
              'q2-combined-scaled-narrow-r1', 'q2-combined-reference-r1',
              'q2-combined-retained-model-r1', 'q2-combined-scaled-model-r1',
              'q2-combined-scaled-control-r1', 'q2-combined-ud-r1', 'q2-combined-ple-r1']
    for label in labels:
        path = ROOT / 'evidence' / label
        receipt = json.loads((path / 'results/result.json').read_text())
        transport = json.loads((path / 'transport.json').read_text())
        require(transport['exit_code'] == 0, 'Transport failed: ' + label)
        exits = [c['exit_code'] for c in receipt['commands']]
        count = 6 if receipt['mode'] == 'cpu' else 3 if 'narrow' in label else 4
        require(exits == [0] * count and receipt['state'] not in ('RUNNING', 'FAILED'),
                'Incomplete commands: ' + label)
        for name, item in receipt['artifacts'].items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                    'Unsafe artifact path')
            local = path / 'results' / name
            require(local.stat().st_size == item['bytes'] and
                    combined.digest(local) == item['sha256'], 'Changed artifact: ' + name)
        validation = combined.audit_capsule(path, fixtures)
        require(validation['artifacts_verified'] == len(receipt['artifacts']),
                'Incomplete collection: ' + label)
        if receipt['mode'] != 'cpu':
            require(receipt['locks'] == receipt['postflight_locks'] and
                    [(v['device'], v['inode']) for v in receipt['locks']] ==
                    [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)] and
                    not receipt['preflight_kfd'] and not receipt['postflight_kfd'],
                    'Unresolved GPU admission: ' + label)
            require(receipt['binary_sha256'] == receipt['binary_sha256_after'],
                    'Changed binary: ' + label)
        if receipt['model_access']:
            require(receipt['models_before'] == receipt['models_after'], 'Changed model witness')
        else:
            require(receipt['mode'] in ('cpu', 'narrow-vector-check'), 'Missing model execution')
        runs[label] = dict(validation, state=receipt['state'], command_exits=exits,
                           model_access=receipt['model_access'],
                           source_variant=transport['source_variant'],
                           finished_at=receipt['finished_at'])
    report = dict(scope='Frozen inputs, actual exits and evidence integrity; not numerical promotion',
                  runs=runs, artifacts_verified=sum(r['artifacts_verified'] for r in runs.values()),
                  source_files_verified=sum(r['source_files_verified'] for r in runs.values()))
    (ROOT / 'config/q2-combined-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'runs'}, indent=2))


if __name__ == '__main__':
    main()
