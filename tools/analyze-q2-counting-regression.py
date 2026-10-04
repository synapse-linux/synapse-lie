#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the frozen historical counting replay without replacing the HTTP curve."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
audit = module('analyze-q2-combined.py')
curve = module('analyze-q2-curve.py')
require = shared.require


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite results')
    plan = read(ROOT/'config/q2-counting-regression-plan.json')
    harness = read(ROOT/'config/q2-counting-harness.json')
    host_path = ROOT/'evidence'/plan['host']
    host = curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands']) == 6,
            'Historical counting host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 22' in (host_path/'results'/name).read_text(),
                'Missing complete Debug/ASan gate')
    host_receipt = read(ROOT/'config/q2-counting-regression-host-results.json')
    require(audit.digest(host_path/'source.tar.gz') == host_receipt['capsule_sha256'],
            'Host capsule changed')
    with tarfile.open(host_path/'source.tar.gz') as archive:
        for name, expected in host_receipt['fixtures'].items():
            require(audit.digest(ROOT/name) == expected ==
                    hashlib.sha256(archive.extractfile(name).read()).hexdigest(),
                    'Host-qualified fixture changed: '+name)
    require(audit.digest(ROOT/harness['origin']) == harness['origin_sha256'],
            'Historical source archive changed')
    with tarfile.open(ROOT/harness['origin']) as archive:
        require(archive.extractfile(harness['origin_member']).read() ==
                (ROOT/harness['source']).read_bytes(), 'Historical tester differs')
    for name, expected in plan['fixture_identities'].items():
        require(audit.digest(ROOT/name) == expected, 'Planned input changed: '+name)

    models, roots = {}, {}
    for key, arm in zip(('legacy', 'ordered', 'mixed', 'ud'), plan['arms']):
        path = ROOT/'evidence'/arm['label']
        root, model = shared.arm(path, arm['variant'])
        receipt = curve.artifacts(path)
        require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4,
                'Changed model command scope')
        require('-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
                '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
                receipt['commands'][-1]['argv'][-1] == 'bench2k' and
                not receipt.get('mmq_reuse'), 'Frozen counting scope or MMQ rebuild changed')
        require(model['within_arm_replay'] == dict(checks=9, exact=9),
                'Unstable within-arm outputs')
        model['validation'] = audit.audit_capsule(path, list(host_receipt['fixtures']))
        if key == 'legacy':
            expected = plan['historical_provider_files']
        elif key in ('ordered', 'mixed'):
            name = 'q2-iq2-signs-ordered-asm-source.json' if key == 'ordered' else 'q2-iq2-mixed-model-source.json'
            expected = read(ROOT/'config'/name)['files']
        else:
            expected = plan['historical_ud_provider_files']
        with tarfile.open(path/'source.tar.gz') as archive:
            files = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                     for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        if expected is not None:
            require(files == expected, 'Provider inventory differs: '+key)
        model['source_inventory_sha256'] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        models[key], roots[key] = model, root

    old_root, old = shared.arm(ROOT/'evidence/q2-library-norm-model-candidate-r1', 'library-norm-cycle')
    replay = {'legacy_vs_historical': shared.compare(old_root, roots['legacy']),
              'ordered_vs_legacy': shared.compare(roots['legacy'], roots['ordered']),
              'mixed_vs_ordered': shared.compare(roots['ordered'], roots['mixed'])}
    histories_exact = all(not any(n.endswith(('.i32', '.u32')) for n in r['changed'])
                          for r in replay.values())
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {ref: {metric: 100 * (models[key]['measurements'][metric]['median'] /
                models[ref]['measurements'][metric]['median'] - 1) for metric in metrics}
                for ref in ('legacy', 'ordered', 'ud')}
               for key in ('ordered', 'mixed')}
    report = dict(schema='synapse-lie.q2-counting-regression.v1',
        scope=harness['scope'], model=models, historical=old, replay=replay,
        histories_exact=histories_exact, median_change_percent=changes,
        promoted=False, goal_met=False, independent_model_quality=False,
        limits='Historical counting regression check only. Sequential arms, three measurements each; no canonical HTTP, broad-context or statistical zero-margin acceptance.')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(histories_exact=histories_exact,
        medians={k:{m:v['measurements'][m]['median'] for m in metrics} for k,v in models.items()},
        changed_files={k:v['changed'] for k,v in replay.items()}, goal_met=False)))
    raise SystemExit(0 if histories_exact else 1)


if __name__ == '__main__':
    main()
