#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit coefficient reuse geometry and ISA without claiming device execution."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location(
        'static', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    static = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(static)
    draft_path = ROOT / 'config/q2-hc-inject-reuse-draft-v3.json'
    draft = json.loads(draft_path.read_text())
    parent_path = ROOT / draft['parent_manifest']
    assert sha(parent_path) == draft['parent_manifest_sha256']
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()} == parent['files']
    for key in ('include', 'compiler_probe'):
        assert sha(ROOT / draft[key]) == draft[key + '_sha256']
    saved = json.loads((ROOT / 'config/q2-ssm-fixed-bounds-static.json').read_text())
    parent_isa = ROOT / saved['candidate_assembly_path']
    assert sha(parent_isa) == saved['candidate_assembly_sha256']
    v2_result_path = ROOT / 'config/q2-hc-inject-reuse-draft-static.json'
    v2_result = json.loads(v2_result_path.read_text())
    v2_isa = ROOT / v2_result['candidate_assembly']
    assert sha(v2_isa) == v2_result['candidate_assembly_sha256']
    v3_isa = ROOT / 'evidence/q2-hc-inject-reuse-draft-preparation/candidate-v3.s'
    original, before, after = (static.old.isa.parse(p) for p in (parent_isa, v2_isa, v3_isa))
    original_text, before_text, after_text = (p.read_text() for p in (parent_isa, v2_isa, v3_isa))
    assert len(original) == 162 and len(before) == len(after) == 165
    assert set(original) < set(after)
    for name in original:
        assert original[name]['resources'] == after[name]['resources'], name
        assert static.old.instructions(original_text, name) == static.old.instructions(after_text, name), name
    comparisons = {}
    for kind in ('Raw', 'Deferred', 'Reduce'):
        old = next(k for k in before if 'HcInjectReuseDraft' + kind + 'Kernel' in k)
        new = next(k for k in after if 'HcInjectReuseLdsDraft' + kind + 'Kernel' in k)
        comparisons[kind.lower()] = dict(v2=before[old], v3=after[new])
        if kind == 'Reduce':
            assert before[old]['resources'] == after[new]['resources']
            assert static.old.instructions(before_text, old) == static.old.instructions(after_text, new)
        else:
            assert after[new]['resources']['group_segment_fixed_size'] == 24576
            assert after[new]['resources']['private_segment_fixed_size'] == 0
            for op, count in (('v_wmma_f32_16x16x16_f16', 16), ('s_barrier', 26)):
                assert before[old]['mnemonics'][op] == after[new]['mnemonics'][op] == count
    text = (ROOT / draft['include']).read_text()
    for kind in ('Raw', 'Deferred'):
        start = text.index('void HcInjectReuseLdsDraft' + kind + 'Kernel(')
        finish = text.index('\n}\n', start)
        body = text[start:finish]
        stage = body.index('float* inject_coeff = gates + 4 * kPlane;')
        retirement = body.rfind('    __syncthreads();\n  }', 0, stage)
        publication = body.index('        __syncthreads();', stage)
        first_read = body.index('Load4(inject_coeff +', stage)
        assert 0 < retirement < stage < publication < first_read
        assert 'Load4(inject_w + group * hidden + h)' in body[stage:publication]
    # Source geometry only: distinct vector writers, disjoint gate/weight LDS,
    # and the exact original coefficient index for every output/stream/hidden.
    hidden_tile, gate_floats = 64, 4 * 16 * 65
    staged = {(tid // 16, (tid % 16) * 4) for tid in range(256)}
    assert staged == {(g, h) for g in range(16) for h in range(0, 64, 4)}
    assert gate_floats % 4 == 0
    assert (gate_floats + 16 * hidden_tile) * 4 <= 24576
    addresses_checked = 0
    for tile in range(40):
        for output in range(4):
            for stream in range(4):
                for h_local in range(0, 64, 4):
                    group = output * 4 + stream
                    source_index = group * 2560 + tile * 64 + h_local
                    old_index = output * 10240 + stream * 2560 + tile * 64 + h_local
                    assert source_index == old_index and (group, h_local) in staged
                    assert gate_floats + group * hidden_tile + h_local + 4 <= 24576 // 4
                    addresses_checked += 1
    geometric = []
    for tokens in (96, 97, 129, 2048):
        token_blocks = (tokens + 127) // 128
        geometric.append(dict(tokens=tokens, CTAs=40 * token_blocks,
            v2_logical_coefficient_payload_bytes=tokens * 2560 * 4 * 4 * 4,
            v3_logical_coefficient_payload_bytes=40 * token_blocks * 4096,
            additional_dot_workspace_write_read_bytes=tokens * 2560 * 4 * 2))
    commands = []
    prep = ROOT / 'evidence/q2-hc-inject-reuse-draft-preparation'
    for label in ('lds-draft-v3-generation', 'lds-draft-v3-assembly'):
        path = prep / (label + '-command.json')
        result = json.loads(path.read_text())
        assert result['exit_code'] == 0
        commands.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), exit_code=0))
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-draft-static.v3',
        draft_manifest_sha256=sha(draft_path), parent_assembly_sha256=sha(parent_isa),
        previous_static_manifest_sha256=sha(v2_result_path),
        candidate_assembly=str(v3_isa.relative_to(ROOT)), candidate_assembly_sha256=sha(v3_isa),
        original_kernel_bodies_instruction_operand_resource_exact=162,
        reducer_instruction_operand_resource_exact=True,
        comparisons=comparisons, symbolic_geometry=geometric,
        coefficient_address_vectors_checked=addresses_checked,
        coefficient_tile_bytes=4096, existing_lds_bytes=24576,
        gate_transpose_bytes=gate_floats * 4, extra_lds_bytes=0, extra_barriers=0,
        source_publication_order_verified=True, commands=commands,
        logical_traffic_limit='Counted source payload requests, not measured DRAM/cache transactions; the small coefficient matrix may already hit cache',
        dot_workspace_limit='20MiB compact dots require a qualified borrow of down_e and40MiB write/read traffic at2048; no executor lifetime integration yet',
        saved_parent_recompiled=False, parent_source_unchanged=True,
        behavioral_tests_run=False, GPU_run=False, production_provider=False,
        numerical_acceptance=False, performance_measured=False, goal_met=False)
    with (ROOT / 'config/q2-hc-inject-reuse-draft-static-v3.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_bodies_exact=162, reducer_exact=True,
        coefficient_tile_bytes=4096, addresses_checked=addresses_checked,
        producers={k: dict(instructions=v['v3']['instructions'], resources=v['v3']['resources'])
                   for k, v in comparisons.items() if k != 'reduce'},
        extra_barriers=0, GPU_run=False, performance_measured=False)))


if __name__ == '__main__':
    main()
