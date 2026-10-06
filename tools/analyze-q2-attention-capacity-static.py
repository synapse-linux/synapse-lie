#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the bounded sparse-attention change against retained parent assembly."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location(
        'group', ROOT/'tools/analyze-q2-ssm-row-group-compose-static.py')
    group = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(group)
    manifest = ROOT/'config/q2-attention-capacity-source.json'
    source = json.loads(manifest.read_text())
    for variant in source['variants'].values():
        base = ROOT/variant['source']
        assert {p.relative_to(base).as_posix(): sha(p) for p in base.rglob('*')
                if p.is_file()} == variant['files']
    parent = json.loads((ROOT/'config/q2-iq2-fixed-bounds-static.json').read_text())
    before = ROOT/parent['candidate_assembly_path']
    after = ROOT/'evidence/q2-attention-capacity-preparation/candidate.s'
    assert sha(before) == parent['candidate_assembly_sha256']
    a, b = [group.old.isa.parse(p) for p in (before, after)]
    assert len(a) == len(b) == 164 and set(a) == set(b)
    at, bt = before.read_text(), after.read_text()
    changed = []
    for symbol in a:
        if (a[symbol]['resources'] != b[symbol]['resources'] or
                group.old.instructions(at, symbol) != group.old.instructions(bt, symbol)):
            changed.append(dict(symbol=symbol, parent=a[symbol], candidate=b[symbol]))
    assert len(changed) == 2
    for row in changed:
        assert 'WmmaCausalAttentionKernelILj4ELj16ELb1' in row['symbol']
        assert row['parent']['resources']['next_free_vgpr'] == row['candidate']['resources']['next_free_vgpr']
        assert row['candidate']['resources']['private_segment_fixed_size'] == 0
        assert row['candidate']['resources']['group_segment_fixed_size'] == 29856
        for mnemonic in ('v_wmma_f32_16x16x16_f16', 'v_fma_mixlo_f16',
                         'v_fma_mixhi_f16', 'v_exp_f32_e32', 's_barrier'):
            assert row['parent']['mnemonics'][mnemonic] == row['candidate']['mnemonics'][mnemonic]
    receipt = ROOT/'evidence/q2-attention-capacity-preparation/assembly-command.json'
    assert json.loads(receipt.read_text())['exit_code'] == 0
    initial = receipt.parent/'initial-source/q2-attention-capacity-source.json'
    compiled = json.loads(initial.read_text())
    numeric = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
    for key, variant in source['variants'].items():
        assert variant['files'][numeric] == compiled['variants'][key]['files'][numeric]
    initial_header = initial.parent/'q2_attention_capacity.h'
    assert ''.join(initial_header.read_text().split()) == ''.join((ROOT/source['header']).read_text().split())
    report = dict(schema='synapse-lie.q2-attention-capacity-static.v1',
        source_manifest_sha256=sha(manifest), parent_assembly_path=str(before.relative_to(ROOT)),
        parent_assembly_sha256=sha(before), candidate_assembly_path=str(after.relative_to(ROOT)),
        candidate_assembly_sha256=sha(after), assembly_command_sha256=sha(receipt),
        assembly_source_manifest_sha256=sha(initial), post_compile_header_whitespace_only=True,
        original_kernels_instruction_operand_resource_exact=162, changed_sparse_bodies=changed,
        original_parent_recompiled=False, GPU_run=False, numerical_qualification=False,
        performance_claim=False, fixed_reference_changed=False)
    with (ROOT/'config/q2-attention-capacity-static.json').open('w') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(unchanged_bodies=162, changed_sparse_bodies=2,
        shared_bytes=29856, private_bytes=0, GPU_run=False)))


if __name__ == '__main__':
    main()
