#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check paired-half epilogue scope against the retained measured assembly."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-down-half-pair-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


previous = module('analyze-q2-down-half-storage-static.py')
isa = previous.isa
prepare = module('prepare-q2-down-half-pair.py')


def main():
    manifest = ROOT/'config/q2-down-half-pair-source.json'
    source = json.loads(manifest.read_text())['variants']['down-half-pair']
    assert prepare.inventory(ROOT/source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
        assert isa.sha(ROOT/source[key]) == source[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-down-half-storage-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert isa.sha(parent_path) == saved['candidate_assembly_sha256']
    candidate_path = OUT/'candidate.s'
    parent, candidate = isa.parse(parent_path), isa.parse(candidate_path)
    a, b = parent_path.read_text(), candidate_path.read_text()
    assert len(parent) == 161 and parent.keys() == candidate.keys()
    changed = [s for s in parent if previous.instructions(a,s) != previous.instructions(b,s)]
    expected = [s for s in parent if 'RoutedQ2HalfStorageKernel' in s]
    assert len(expected) == 3 and sorted(changed) == sorted(expected)
    for symbol in parent.keys()-set(expected):
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    rows = []
    for symbol in expected:
        old, new = parent[symbol], candidate[symbol]
        assert new['resources']['private_segment_fixed_size'] == 0
        assert old['resources']['group_segment_fixed_size'] == new['resources']['group_segment_fixed_size']
        assert old['mnemonics'].get('s_barrier',0) == new['mnemonics'].get('s_barrier',0)
        rows.append(dict(symbol=symbol, width=int(re.search(r'ELi128ELi(\d+)ELi2',symbol)[1]),
                         parent=old, candidate=new))
    commands = {n:json.loads((OUT/(n+'-command.json')).read_text()) for n in
                ('generation','assembly','fixture-host','fixture-device','wiring','launcher-guards')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-down-half-pair-static.v1',
        source_manifest_sha256=isa.sha(manifest), provider_files=1026,
        retained_parent_assembly_sha256=isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=isa.sha(candidate_path),
        original_bodies_instruction_operand_resource_exact=158, changed_bodies=rows,
        normalization='Only assembler comments, local BB function numbers and end-label numbers; opcodes, operands and basic-block suffixes preserved.',
        numerical_contract=source['numerical_contract'], inherited_quality=source['inherited_quality'],
        allocated_capacity_unchanged=True, private_bytes=0, commands=commands,
        gpu_run=False, model_inference=False, quality_accepted=False, goal_met=False)
    with (ROOT/'config/q2-down-half-pair-static.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(original_kernels_exact=158,changed_kernels=3,private_bytes=0,
        resources=[dict(width=r['width'],before=r['parent']['resources'],after=r['candidate']['resources'],
                        instructions_before=r['parent']['instructions'],instructions_after=r['candidate']['instructions']) for r in rows],gpu_run=False)))


if __name__ == '__main__':
    main()
