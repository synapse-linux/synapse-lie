#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the one changed IQ2 geometry to retained production assembly."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-wide-pair-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name,ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-iq2-wide-pair.py')


def main():
    target = ROOT/'config/q2-iq2-wide-pair-static.json'
    if target.exists():raise ValueError('Refusing to overwrite static evidence')
    manifest = ROOT/'config/q2-iq2-wide-pair-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-wide-pair']
    if prepare.inventory(ROOT/source['source']) != source['files']:
        raise ValueError('Frozen provider changed')
    for key in ('parent_manifest','measured_parent','control_include','patch'):
        if prior.sha(ROOT/source[key]) != source[key+'_sha256']:
            raise ValueError('Source binding changed: '+key)
    parent_static_path = ROOT/'config/q2-iq2-lane-commit-static.json'
    parent_static = json.loads(parent_static_path.read_text())
    parent_path = ROOT/parent_static['candidate_assembly_path']
    if prior.sha(parent_path) != parent_static['candidate_assembly_sha256']:
        raise ValueError('Saved parent assembly changed')
    parent = prior.parse(parent_path)
    candidate_path = OUT/'candidate.s'
    candidate = prior.parse(candidate_path)
    removed, added = set(parent)-set(candidate),set(candidate)-set(parent)
    if len(parent) != 157 or len(candidate) != 157 or len(removed) != 1 or len(added) != 1:
        raise ValueError('Production kernel inventory changed')
    old, new = next(iter(removed)),next(iter(added))
    suffix = 'WeightTypeE16ELi128ELi64ELi2ELb1ELb0ELb0'
    if suffix not in old or new != old.replace(suffix,suffix.replace('Li128','Li256')):
        raise ValueError('Unexpected geometry replacement')
    common = set(parent)&set(candidate)
    if any(parent[s]['body_sha256'] != candidate[s]['body_sha256'] for s in common):
        raise ValueError('Unrelated production body changed')
    p,c = parent[old],candidate[new]
    if (p['resources']['group_segment_fixed_size'],c['resources']['group_segment_fixed_size']) != (17536,26752):
        raise ValueError('Unexpected stage LDS')
    if c['resources']['private_segment_fixed_size'] != 0 or c['resources']['wavefront_size32'] != 1:
        raise ValueError('Private bytes or wave width changed')
    if c['mnemonics'].get('v_wmma_f32_16x16x16_f16') != 2*p['mnemonics'].get('v_wmma_f32_16x16x16_f16'):
        raise ValueError('Unexpected matrix instruction count')
    ownership_path = ROOT/'config/q2-iq2-wide-pair-opportunity.json'
    ownership = json.loads(ownership_path.read_text())
    if ownership['source_manifest_sha256'] != source['parent_manifest_sha256']:
        raise ValueError('Ownership audit parent differs')
    commands = {n:json.loads((OUT/(n+'-command.json')).read_text())
                for n in ('generation','assembly','fixture-host','fixture-device','launcher-guards')}
    if any(c['exit_code'] for c in commands.values()):raise ValueError('Preparation failed')
    report = dict(schema='synapse-lie.q2-iq2-wide-pair-static.v1',
        source_manifest_sha256=prior.sha(manifest),source_files_verified=1025,
        retained_parent_static_sha256=prior.sha(parent_static_path),
        retained_parent_assembly_sha256=prior.sha(parent_path),retained_parent_assembly_rebuilt=False,
        candidate_assembly_sha256=prior.sha(candidate_path),candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        ownership_audit_sha256=prior.sha(ownership_path),kernel_count=157,unchanged_bodies=len(common),
        removed_parent_symbol=old,added_candidate_symbol=new,parent=p,candidate=c,
        commands=commands,private_bytes=0,additional_tables=False,additional_runtime_allocations=False,
        gpu_run=False,model_inference=False,numerical_acceptance=False,goal_met=False,
        limits='One changed geometry, logical ownership and static resource counts do not establish GPU safety, numerical parity or throughput. Full-output and original model timing remain necessary.')
    with target.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(kernel_count=157,unchanged_bodies=len(common),
        resources={'parent':p['resources'],'candidate':c['resources']},
        static_block_barriers=[p['mnemonics'].get('s_barrier'),c['mnemonics'].get('s_barrier')],gpu_run=False)))


if __name__ == '__main__':
    main()
