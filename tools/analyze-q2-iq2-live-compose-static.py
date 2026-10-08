#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the new live-store composition to retained source and production ISA."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-live-compose-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-iq2-live-compose.py')


def main():
    target = ROOT/'config/q2-iq2-live-compose-static.json'
    if target.exists():
        raise ValueError('Refusing to overwrite static evidence')
    manifest = ROOT/'config/q2-iq2-live-compose-source.json'
    source = json.loads(manifest.read_text())['variants']['iq2-live-compose']
    if prepare.inventory(ROOT/source['source']) != source['files']:
        raise ValueError('Frozen provider changed')
    for key in ('parent_manifest', 'measured_parent', 'retained_component',
                'retained_patch', 'retained_transformer', 'patch'):
        if prior.sha(ROOT/source[key]) != source[key+'_sha256']:
            raise ValueError('Source binding changed: '+key)
    saved = json.loads((ROOT/'config/q2-iq2-lane-commit-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    if prior.sha(parent_path) != saved['candidate_assembly_sha256']:
        raise ValueError('Saved parent assembly changed')
    parent = prior.parse(parent_path)
    candidate_path = OUT/'candidate.s'
    candidate = prior.parse(candidate_path)
    affected = sorted(s for s in parent if 'RoutedF16GEMMKernel' in s and
                      'WeightTypeE16' in s and any('ELi'+str(n)+'ELi2ELb1' in s for n in (48,64,128)))
    if len(parent) != 157 or len(affected) != 6 or parent.keys() != candidate.keys():
        raise ValueError('Production kernel inventory changed')
    changed = sorted(s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256'])
    if changed != affected:
        raise ValueError('Unrelated production body changed')
    for symbol in affected:
        p,c = parent[symbol],candidate[symbol]
        for key in ('group_segment_fixed_size', 'next_free_vgpr', 'wavefront_size32'):
            if p['resources'][key] != c['resources'][key]:
                raise ValueError('LDS, vector registers or wave width changed')
        if c['resources']['private_segment_fixed_size'] != 0:
            raise ValueError('Private allocation introduced')
        for name in ('v_wmma_f32_16x16x16_f16','v_pk_fma_f16','v_pk_add_f16','s_barrier'):
            if p['mnemonics'].get(name,0) != c['mnemonics'].get(name,0):
                raise ValueError('Arithmetic or barrier instruction count changed')
    audit_path = ROOT/'config/q2-iq2-live-stage-composition-opportunity.json'
    audit = json.loads(audit_path.read_text())
    if audit['parent_manifest_sha256'] != source['parent_manifest_sha256']:
        raise ValueError('Slot audit parent changed')
    if len(audit['coverage']) != 20 or not all(c['all_readers_written'] for c in audit['coverage']):
        raise ValueError('Incomplete slot ownership audit')
    commands = {n:json.loads((OUT/(n+'-command.json')).read_text())
                for n in ('generation','assembly','wiring','launcher-guards')}
    if any(c['exit_code'] for c in commands.values()):
        raise ValueError('Preparation command failed')
    report = dict(schema='synapse-lie.q2-iq2-live-compose-static.v1',
        source_manifest_sha256=prior.sha(manifest),source_files_verified=1025,
        retained_parent_assembly_sha256=prior.sha(parent_path),retained_parent_assembly_rebuilt=False,
        candidate_assembly_sha256=prior.sha(candidate_path),candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        slot_audit_sha256=prior.sha(audit_path),slot_audit_cases=20,
        kernel_count=157,unchanged_bodies=151,changed_iq2_bodies=6,
        iq2_bodies={s:dict(parent=parent[s],candidate=candidate[s]) for s in affected},
        commands=commands,lds_unchanged=True,vgpr_unchanged=True,private_bytes=0,
        additional_tables=False,additional_runtime_allocations=False,gpu_run=False,
        model_inference=False,numerical_acceptance=False,goal_met=False,
        limits='Static assembly and retained slot ownership do not establish GPU numerical safety or throughput of this new composition. The original model replay and timings remain required.')
    with target.open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(kernel_count=157,changed_iq2_bodies=6,unchanged_bodies=151,
        lds_unchanged=True,vgpr_unchanged=True,private_bytes=0,gpu_run=False)))


if __name__ == '__main__':
    main()
