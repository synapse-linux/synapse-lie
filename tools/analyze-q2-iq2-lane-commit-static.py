#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check ownership bijection and retained production assembly differences."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-lane-commit-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name,ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-iq2-lane-commit.py')


def ownership():
    expected = {(row,group,part) for row in range(128)
                for group in range(2) for part in range(4)}
    actual, offsets = {}, {}
    for tid in range(256):
        part = (tid % 32) % 4
        for owner in range(4):
            peer_lane = ((tid % 32)//4)*4+owner
            peer_tid = (tid//4)*4+owner
            if peer_tid//32 != tid//32 or peer_tid%32 != peer_lane:
                raise ValueError('Peer crosses a wave')
            row,group = divmod(peer_tid,2)
            key = (row,group,part)
            if key in actual:
                raise ValueError('Duplicate logical slice writer')
            actual[key] = (tid,owner)
            chunk = 2*group + part//2
            offset = 16*(row*4+(chunk^((row//2)%4)))+(part%2)*8
            if offset in offsets or offset%8 or not 0 <= offset <= 8192-8:
                raise ValueError('LDS slice collision or invalid extent')
            offsets[offset] = key
    if set(actual) != expected or set(offsets) != set(range(0,8192,8)):
        raise ValueError('Incomplete logical/physical ownership')
    return dict(wave_width=32,lane_group_width=4,threads=256,
                logical_slices=1024,physical_bytes=8192,unique_slice_writers=True,
                complete_lds_coverage=True,peer_wave_identity_exact=True,
                numerical_or_gpu_evidence=False)


def main():
    target = ROOT/'config/q2-iq2-lane-commit-static.json'
    if target.exists():raise ValueError('Refusing to overwrite static evidence')
    manifest = ROOT/'config/q2-iq2-lane-commit-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-lane-commit']
    if prepare.inventory(ROOT/source['source']) != source['files']:
        raise ValueError('Frozen provider changed')
    for key in ('parent_manifest','measured_parent','control_include','patch'):
        if prior.sha(ROOT/source[key]) != source[key+'_sha256']:
            raise ValueError('Source binding changed: '+key)
    saved = json.loads((ROOT/'config/q2-iq2-raw-prefetch-static.json').read_text())['assemblies']['candidate']
    parent_path = ROOT/saved['path']
    if prior.sha(parent_path) != saved['sha256']:
        raise ValueError('Saved parent assembly changed')
    parent = prior.parse(parent_path)
    candidate_path = OUT/'candidate.s'
    candidate = prior.parse(candidate_path)
    affected = sorted(s for s in parent if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s)
    if len(parent) != 157 or len(affected) != 8 or parent.keys() != candidate.keys():
        raise ValueError('Production kernel inventory changed')
    changed = sorted(s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256'])
    if changed != affected:raise ValueError('Unrelated production body changed')
    for symbol in affected:
        p,c = parent[symbol],candidate[symbol]
        if p['resources']['group_segment_fixed_size'] != c['resources']['group_segment_fixed_size']:
            raise ValueError('Compact LDS allocation changed')
        if c['resources']['private_segment_fixed_size'] != 0 or c['resources']['wavefront_size32'] != 1:
            raise ValueError('Private bytes or wave width changed')
        for name in ('v_wmma_f32_16x16x16_f16','v_pk_fma_f16','v_pk_add_f16'):
            if p['mnemonics'].get(name,0) != c['mnemonics'].get(name,0):
                raise ValueError('Arithmetic instruction count changed')
    commands = {n:json.loads((OUT/(n+'-command.json')).read_text())
                for n in ('generation','assembly','fixture-host','fixture-device','launcher-guards')}
    if any(c['exit_code'] for c in commands.values()):
        raise ValueError('Preparation command failed')
    report = dict(schema='synapse-lie.q2-iq2-lane-commit-static.v1',
        source_manifest_sha256=prior.sha(manifest),source_files_verified=1025,
        retained_parent_assembly_sha256=prior.sha(parent_path),retained_parent_assembly_rebuilt=False,
        candidate_assembly_sha256=prior.sha(candidate_path),candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        ownership=ownership(),kernel_count=157,unchanged_bodies=149,changed_iq2_bodies=8,
        iq2_bodies={s:dict(parent=parent[s],candidate=candidate[s]) for s in affected},
        commands=commands,lds_unchanged=True,private_bytes=0,
        additional_tables=False,additional_runtime_allocations=False,gpu_run=False,
        model_inference=False,numerical_acceptance=False,goal_met=False,
        limits='A bijective mapping and static resource changes do not establish GPU race freedom, numerical parity or throughput. Full-output replay and original model timing remain necessary.')
    with target.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(kernel_count=157,changed_iq2_bodies=8,unchanged_bodies=149,
        ownership=report['ownership'],resources={s:{k:d[k]['resources'] for k in ('parent','candidate')}
        for s,d in report['iq2_bodies'].items()},gpu_run=False)))


if __name__ == '__main__':
    main()
