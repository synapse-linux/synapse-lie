#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check retained control instructions and the new compact-output specializations."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-down-half-storage-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


isa = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-down-half-storage.py')


def instructions(text, symbol):
    start = text.index(symbol+':')
    end = text.index('\n\t.section\t.rodata', start)
    lines = []
    for line in text[start:end].splitlines():
        line = line.split(';', 1)[0].strip()
        if not line:
            continue
        line = re.sub(r'\.LBB\d+_', '.LBB_', line)
        line = re.sub(r'\.Lfunc_end\d+', '.Lfunc_end', line)
        lines.append(line)
    return '\n'.join(lines)


def main():
    manifest = ROOT/'config/q2-down-half-storage-source.json'
    source = json.loads(manifest.read_text())['variants']['down-half-storage']
    assert prepare.inventory(ROOT/source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert isa.sha(ROOT/source[key]) == source[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-iq2-live-compose-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert isa.sha(parent_path) == saved['candidate_assembly_sha256']
    candidate_path = OUT/'candidate.s'
    parent, candidate = isa.parse(parent_path), isa.parse(candidate_path)
    a, b = parent_path.read_text(), candidate_path.read_text()
    assert len(parent) == 157 and len(candidate) == 161
    assert parent.keys() <= candidate.keys()
    for symbol in parent:
        assert instructions(a, symbol) == instructions(b, symbol), symbol
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    new = {s:candidate[s] for s in sorted(candidate.keys()-parent.keys())}
    assert sum('RoutedQ2HalfStorageKernel' in s for s in new) == 3
    assert sum('HcCombineMoeHalfDeferredNormKernel' in s for s in new) == 1
    assert all(v['resources']['private_segment_fixed_size'] == 0 for v in new.values())
    commands = {n:json.loads((OUT/(n+'-command.json')).read_text()) for n in
                ('generation', 'assembly', 'fixture-host', 'fixture-device', 'wiring', 'launcher-guards')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-down-half-storage-static.v1',
        source_manifest_sha256=isa.sha(manifest), provider_files=1026,
        retained_parent_assembly_sha256=isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=isa.sha(candidate_path),
        original_bodies_instruction_operand_resource_exact=157, new_bodies=new,
        normalization='Only assembler comments, local BB function numbers and end-label numbers; opcodes, operands and basic-block suffixes preserved.',
        logical_output_bytes_before=209715200, logical_output_bytes_after=104857600,
        allocated_capacity_unchanged=True, private_bytes=0, commands=commands,
        gpu_run=False, model_inference=False, quality_accepted=False, goal_met=False)
    path = ROOT/'config/q2-down-half-storage-static.json'
    with path.open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(original_kernels_exact=157,new_kernels=4,private_bytes=0,gpu_run=False)))


if __name__ == '__main__':
    main()
