#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare new bounded IQ2 commits with retained production assembly."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-slice-commit-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-iq2-slice-commit.py')


def main():
    output = ROOT / 'config/q2-iq2-slice-commit-static.json'
    if output.exists():
        raise RuntimeError('Refusing to overwrite static evidence')
    manifest = ROOT / 'config/q2-iq2-slice-commit-source.json'
    variants = json.loads(manifest.read_text())['variants']
    parent_path = ROOT / 'evidence/q2-iq2-raw-prefetch-preparation/candidate.s'
    parent = prior.parse(parent_path)
    affected = sorted(s for s in parent
        if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s)
    if len(parent) != 157 or len(affected) != 8:
        raise RuntimeError('Retained parent kernel inventory changed')
    reports = {}
    for variant, stem in (('iq2-slice-commit', 'slice'), ('iq2-pair-commit', 'pair')):
        source = variants[variant]
        if prepare.inventory(ROOT / source['source']) != source['files']:
            raise RuntimeError('Frozen provider changed: ' + variant)
        for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
            if prior.sha(ROOT / source[key]) != source[key + '_sha256']:
                raise RuntimeError('Retained source binding changed: ' + key)
        path = OUT / (stem + '.s')
        candidate = prior.parse(path)
        if parent.keys() != candidate.keys():
            raise RuntimeError('Production kernel symbols changed')
        changed = sorted(s for s in parent
            if parent[s]['body_sha256'] != candidate[s]['body_sha256'])
        if changed != affected:
            raise RuntimeError('Unrelated production body changed')
        for symbol in affected:
            p, c = parent[symbol], candidate[symbol]
            if (p['resources']['group_segment_fixed_size'] !=
                    c['resources']['group_segment_fixed_size'] or
                    c['resources']['private_segment_fixed_size'] != 0):
                raise RuntimeError('LDS or private storage changed')
            for name in ('v_wmma_f32_16x16x16_f16', 'v_pk_fma_f16', 'v_pk_add_f16'):
                if p['mnemonics'].get(name, 0) != c['mnemonics'].get(name, 0):
                    raise RuntimeError('Arithmetic instruction count changed')
        command = json.loads((OUT / ('assembly-' + stem + '-command.json')).read_text())
        if command['exit_code'] != 0:
            raise RuntimeError('Production assembly compilation failed')
        reports[variant] = dict(source_files_verified=len(source['files']),
            assembly_path=str(path.relative_to(ROOT)), assembly_sha256=prior.sha(path),
            assembly_command=command, changed_iq2_bodies=8, unchanged_bodies=149,
            iq2_bodies={s: dict(parent=parent[s], candidate=candidate[s]) for s in affected},
            allocated_vgpr_unchanged=all(parent[s]['resources']['next_free_vgpr'] ==
                candidate[s]['resources']['next_free_vgpr'] for s in affected),
            lds_unchanged=True, private_bytes=0, gpu_run=False,
            numerical_acceptance=False, performance_gain=False)
    report = dict(schema='synapse-lie.q2-iq2-slice-commit-static.v1',
        source_manifest_sha256=prior.sha(manifest),
        retained_parent_assembly_sha256=prior.sha(parent_path),
        retained_parent_assembly_rebuilt=False, kernel_count=157, variants=reports,
        additional_tables=False, additional_runtime_allocations=False,
        gpu_run=False, model_inference=False, goal_met=False,
        limits='Bounded source temporary lives do not reduce allocated VGPR here. '
               'The eight-value variant adds LDS stores; the sixteen-value variant '
               'retains store counts with changed scheduling. Static counts and '
               'unchanged arithmetic mnemonics do not qualify GPU numerics or speed.')
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(kernel_count=157, variants={k: dict(
        unchanged_bodies=v['unchanged_bodies'], changed_iq2_bodies=v['changed_iq2_bodies'],
        allocated_vgpr_unchanged=v['allocated_vgpr_unchanged']) for k, v in reports.items()},
        gpu_run=False)))


if __name__ == '__main__':
    main()
