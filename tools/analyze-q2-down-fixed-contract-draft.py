#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the local down specialization to retained parent ISA; no runtime claim."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('group', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    group = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(group)
    meta = json.loads((ROOT / 'config/q2-iq2-fixed-bounds-static.json').read_text())
    parent_path = ROOT / meta['candidate_assembly_path']
    assert sha(parent_path) == meta['candidate_assembly_sha256']
    candidate_path = ROOT / 'evidence/q2-down-fixed-contract-draft-preparation/candidate.s'
    a, b = [group.old.isa.parse(path) for path in (parent_path, candidate_path)]
    at, bt = parent_path.read_text(), candidate_path.read_text()
    assert len(a) == 164 and len(b) == 167 and set(a) <= set(b)
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert group.old.instructions(at, name) == group.old.instructions(bt, name), name
    extra = sorted(set(b) - set(a))
    assert len(extra) == 3
    old_name = 'RoutedQ2HalfStorageKernel'
    new_name = 'RoutedQ2FixedContractDraftKernel'
    pairs = []
    for name in extra:
        old = name.replace(str(len(new_name)) + new_name, str(len(old_name)) + old_name)
        assert old in a, old
        for opcode in ('v_wmma_f32_16x16x16_f16',):
            assert a[old]['mnemonics'][opcode] == b[name]['mnemonics'][opcode], opcode
        assert b[name]['resources']['private_segment_fixed_size'] == 0
        assert b[name]['resources']['group_segment_fixed_size'] == a[old]['resources']['group_segment_fixed_size']
        pairs.append(dict(parent=dict(symbol=old, **a[old]), candidate=dict(symbol=name, **b[name])))
    report = dict(schema='synapse-lie.q2-down-fixed-contract-draft-static.v1',
        draft_sha256=sha(ROOT / 'config/q2-down-fixed-contract-draft.json'),
        parent_assembly=str(parent_path.relative_to(ROOT)), parent_assembly_sha256=sha(parent_path),
        candidate_assembly=str(candidate_path.relative_to(ROOT)), candidate_assembly_sha256=sha(candidate_path),
        retained_bodies_exact=164, private_bodies=3, pairs=pairs,
        parent_recompiled=False, provider_created=False, GPU_run=False,
        arithmetic_qualified=False, performance_claim=False, model_plan=False,
        static_barrier_changes_include_removed_inactive_output_routes=True)
    output = ROOT / 'config/q2-down-fixed-contract-draft-static.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(retained_bodies_exact=164, pairs=[dict(
        instructions=[p['parent']['instructions'], p['candidate']['instructions']],
        vgpr=[p['parent']['resources']['next_free_vgpr'], p['candidate']['resources']['next_free_vgpr']],
        LDS=p['candidate']['resources']['group_segment_fixed_size']) for p in pairs],
        GPU_run=False, performance_claim=False)))


if __name__ == '__main__':
    main()
