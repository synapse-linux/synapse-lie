#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify retained kernels and report new expert-ordered layout bodies."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-compact-expert-chain-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    old = module('analyze-q2-down-half-storage-static.py')
    prepare = module('prepare-q2-compact-expert-chain.py')
    manifest = ROOT/'config/q2-compact-expert-chain-source.json'
    source = json.loads(manifest.read_text())['variants']['compact-expert-chain']
    assert prepare.inventory(ROOT/source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert old.isa.sha(ROOT/source[key]) == source[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-scaled-wave-pack-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert old.isa.sha(parent_path) == saved['candidate_assembly_sha256']
    path = OUT/'candidate.s'
    parent, candidate = old.isa.parse(parent_path), old.isa.parse(path)
    before, after = parent_path.read_text(), path.read_text()
    assert len(parent) == 162 and len(candidate) == 170
    assert parent.keys() <= candidate.keys()
    for symbol in parent:
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    added = {s:candidate[s] for s in sorted(candidate.keys()-parent.keys())}
    assert sum('RoutedQ2CompactHalfKernel' in s for s in added) == 3
    assert sum('RoutedIQ2CompactRowsKernel' in s for s in added) == 4
    assert sum('RoutedCompactBoundsKernel' in s for s in added) == 1
    assert all(v['resources']['private_segment_fixed_size'] == 0 for v in added.values())
    report = dict(schema='synapse-lie.q2-compact-expert-chain-static.v1',
        source_manifest_sha256=old.isa.sha(manifest), provider_files=len(source['files']),
        parent_assembly_sha256=old.isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(path.relative_to(ROOT)), candidate_assembly_sha256=old.isa.sha(path),
        original_kernels_instruction_operand_resource_exact=len(parent), added_kernels=added,
        layout='Compact expert-major F32/F16 activations and inverse scales; slot-major half down output.',
        original_buffers_and_capacity_unchanged=True, additional_allocations=0,
        gpu_run=False, quality_accepted=False, goal_met=False)
    with (ROOT/'config/q2-compact-expert-chain-static.json').open('x') as f:
        json.dump(report,f,indent=2); f.write('\n')
    print(json.dumps(dict(original_kernels_exact=len(parent), new_kernels=len(added),
        new_resources={s:v['resources'] for s,v in added.items()}, gpu_run=False)))


if __name__ == '__main__':
    main()
