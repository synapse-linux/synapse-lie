#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check one packing replacement against the retained production assembly."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-scaled-wave-pack-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    old = module('analyze-q2-down-half-storage-static.py')
    prepare = module('prepare-q2-scaled-wave-pack.py')
    manifest = ROOT/'config/q2-scaled-wave-pack-source.json'
    source = json.loads(manifest.read_text())['variants']['scaled-wave-pack']
    assert prepare.inventory(ROOT/source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch', 'control_include'):
        assert old.isa.sha(ROOT/source[key]) == source[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-shared-q8-pair-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert old.isa.sha(parent_path) == saved['candidate_assembly_sha256']
    candidate_path = OUT/'candidate.s'
    parent, candidate = old.isa.parse(parent_path), old.isa.parse(candidate_path)
    before, after = parent_path.read_text(), candidate_path.read_text()
    removed, added = set(parent) - set(candidate), set(candidate) - set(parent)
    assert len(parent) == len(candidate) == 162 and len(removed) == len(added) == 1
    assert 'PackQ2ScaledRowsKernel' in next(iter(removed))
    assert 'PackQ2ScaledWaveRowsKernel' in next(iter(added))
    for symbol in set(parent) & set(candidate):
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    replacement = candidate[next(iter(added))]
    assert replacement['resources']['private_segment_fixed_size'] == 0
    assert replacement['resources']['group_segment_fixed_size'] == 0
    assert replacement['mnemonics'].get('s_barrier', 0) == 0
    initial = json.loads((OUT/'initial-format-source.json').read_text())['variants']['scaled-wave-pack']
    initial_source = ROOT/(initial['source']+'-initial-format')
    assert prepare.inventory(initial_source) == initial['files']
    initial_assembly = OUT/'initial-format-candidate.s'
    initial_kernels = old.isa.parse(initial_assembly)
    assert initial_kernels.keys() == candidate.keys()
    for symbol in candidate:
        assert old.instructions(initial_assembly.read_text(), symbol) == old.instructions(after, symbol)
        assert initial_kernels[symbol]['resources'] == candidate[symbol]['resources']
    commands = {n: json.loads((OUT/(n+'-command.json')).read_text()) for n in
                ('prepare-formatted', 'assembly-formatted', 'fixture-host-final', 'fixture-device-final', 'launcher-guards-final')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-scaled-wave-pack-static.v1',
        source_manifest_sha256=old.isa.sha(manifest), provider_files=1027,
        parent_assembly_sha256=old.isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=old.isa.sha(candidate_path), other_kernels_exact=161,
        parent_kernel=parent[next(iter(removed))], candidate_kernel=replacement,
        preserved_initial_format_source=str(initial_source.relative_to(ROOT)),
        formatting_correction_instruction_equivalent=True,
        preserved_format_exits={name: json.loads((OUT/(name+'-command.json')).read_text())['exit_code']
                                for name in ('shared-format', 'changed-format', 'changed-format-corrected')},
        commands=commands, numerical_contract=source['numerical_contract'],
        packing_ctas_before=20480, packing_ctas_after=2560,
        static_instructions_not_dynamic_work_or_speed=True,
        gpu_run=False, independent_quality=False, goal_met=False)
    with (ROOT/'config/q2-scaled-wave-pack-static.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(other_kernels_exact=161, resources=replacement['resources'], gpu_run=False)))


if __name__ == '__main__':
    main()
