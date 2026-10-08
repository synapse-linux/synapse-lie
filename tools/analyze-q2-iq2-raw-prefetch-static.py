#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify deferred IQ2 expansion against the saved compact-parent assembly."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-raw-prefetch-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-iq2-halfstage-static.py')
literal = module('prepare-q2-q8-grouped.py')
sha = prior.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    output = ROOT / 'config/q2-iq2-raw-prefetch-static.json'
    require(not output.exists(), 'Refusing to overwrite static evidence')
    paths = dict(parent=ROOT / 'evidence/q2-iq2-halfbyte-preparation/perm-formatted.s',
                 candidate=OUT / 'candidate.s')
    parent, candidate = (prior.parse(paths[key]) for key in ('parent', 'candidate'))
    require(parent.keys() == candidate.keys() and len(parent) == 157, 'Kernel inventory changed')
    changed = sorted(s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256'])
    affected = sorted(s for s in parent if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s)
    require(changed == affected and len(changed) == 8, 'Unrelated body changed')
    for symbol in affected:
        p, c = parent[symbol], candidate[symbol]
        require(p['resources']['group_segment_fixed_size'] == c['resources']['group_segment_fixed_size']
                and c['resources']['private_segment_fixed_size'] == 0, 'Stage/scratch changed')
        for mnemonic in ('v_wmma_f32_16x16x16_f16', 'v_pk_fma_f16', 'v_pk_add_f16'):
            require(p['mnemonics'].get(mnemonic, 0) == c['mnemonics'].get(mnemonic, 0),
                    'Ordered WMMA/consumer half arithmetic count changed')
    manifest_path = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    source = json.loads(manifest_path.read_text())['variants']['iq2-raw-prefetch']
    folder = ROOT / source['source']
    actual = {str(f.relative_to(folder)): sha(f) for f in folder.rglob('*') if f.is_file()}
    require(actual == source['files'] and len(actual) == 1025, 'Provider inventory changed')
    for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
        require(sha(ROOT / source[key]) == source[key + '_sha256'], 'Binding changed: ' + key)
    base = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['iq2-halfbyte-perm']
    parent_text = (ROOT / base['source'] / 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp').read_text()
    kernel = literal.function(parent_text, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    require(kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2RawControlKernel') in
            (ROOT / source['control_include']).read_text(), 'Literal compact control changed')
    for name in ('generation', 'assembly', 'fixture-device', 'fixture-host', 'guards', 'new-format-fixed'):
        require(json.loads((OUT / (name + '-command.json')).read_text())['exit_code'] == 0,
                'Preparation failed: ' + name)
    require('Ran 86 tests' in (OUT / 'guards-stderr.txt').read_text(), 'Missing scope guards')
    require(json.loads((OUT / 'shared-format-command.json').read_text())['exit_code'] == 1,
            'Inherited formatter exit lost')
    names = sorted(set(re.findall(r'^([^:\n]+):\d+:\d+: error:',
                                 (OUT / 'shared-format-stderr.txt').read_text(), re.M)))
    require(len(names) == 9 and all(actual[name] == base['files'][name] for name in names),
            'Formatter rejected changed provider bytes')
    require(json.loads((OUT / 'new-format-command.json').read_text())['exit_code'] == 1 and
            json.loads((OUT / 'fixture-format-token-check.json').read_text())['whitespace_only'],
            'Initial fixture formatting failure/correction lost')
    report = dict(schema='synapse-lie.q2-iq2-raw-prefetch-static.v1',
        source_manifest_sha256=sha(manifest_path), source_files_verified=1025,
        literal_control_exact_to_compact_parent=True, parent_assembly_reused_without_rebuild=True,
        kernel_count=157, unchanged_bodies=149,
        iq2_bodies={s: dict(parent=parent[s], candidate=candidate[s]) for s in affected},
        assemblies={key: dict(path=str(path.relative_to(ROOT)), sha256=sha(path)) for key, path in paths.items()},
        inherited_format_failures={name: actual[name] for name in names},
        commands=[json.loads(path.read_text()) for path in sorted(OUT.glob('*-command.json'))],
        initial_fixture_format_failure='Renamed kernel/event lines need wrapping; whitespace-only correction passes. '
                                       'No production or arithmetic token changes; completed syntax objects retained.',
        comparison_scope='Per-body static instructions/resources only. Moving decode from initial+loop fetch '
                         'to one commit body removes duplicated static loads, not eight dynamic loads per stage. '
                         'Each stage still decodes exactly the same group. Register reductions are compiler evidence, '
                         'not measured occupancy, bandwidth or model throughput.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, promoted=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(unchanged_bodies=149, changed_iq2_bodies=8,
        next_free_vgpr_reductions=sorted(set(parent[s]['resources']['next_free_vgpr'] -
                                           candidate[s]['resources']['next_free_vgpr'] for s in affected)),
        lds_unchanged=True, private_bytes=0, gpu_run=False)))


if __name__ == '__main__':
    main()
