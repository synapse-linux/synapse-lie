#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit private HC compiler probes without qualifying execution or speed."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('static',ROOT/'tools/analyze-q2-ssm-row-group-compose-static.py')
    static = importlib.util.module_from_spec(spec);spec.loader.exec_module(static)
    path = ROOT/'config/q2-hc-inject-reuse-draft-v2.json'
    draft = json.loads(path.read_text())
    parent_path = ROOT/draft['parent_manifest']
    assert sha(parent_path) == draft['parent_manifest_sha256']
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/parent['source']
    assert {str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()} == parent['files']
    for key in ('include','compiler_probe'):
        assert sha(ROOT/draft[key]) == draft[key+'_sha256']
    saved = json.loads((ROOT/'config/q2-ssm-fixed-bounds-static.json').read_text())
    before_path = ROOT/saved['candidate_assembly_path']
    assert sha(before_path) == saved['candidate_assembly_sha256']
    after_path = ROOT/'evidence/q2-hc-inject-reuse-draft-preparation/candidate-v2.s'
    before,after = static.old.isa.parse(before_path),static.old.isa.parse(after_path)
    a,b = before_path.read_text(),after_path.read_text()
    assert len(before)==162 and len(after)==165 and set(before)<set(after)
    for name in before:
        assert before[name]['resources']==after[name]['resources'],name
        assert static.old.instructions(a,name)==static.old.instructions(b,name),name
    probes = {name:after[name] for name in set(after)-set(before)}
    parents={}
    for suffix,old_part,new_part in (
        ('raw','DenseF16GEMMKernelILi256ELi128ELi1ELi4ELi2ELi8ELb1ELb0ELb0ELb1ELb1','HcInjectReuseDraftRawKernel'),
        ('deferred','HcMixDeferredNormKernel','HcInjectReuseDraftDeferredKernel')):
        old = next(k for k in before if old_part in k)
        new = next(k for k in probes if new_part in k)
        parents[suffix]=dict(parent=before[old],candidate=after[new])
        for field in ('group_segment_fixed_size','next_free_vgpr','private_segment_fixed_size','wavefront_size32'):
            assert before[old]['resources'][field]==after[new]['resources'][field]
        for op,count in (('v_wmma_f32_16x16x16_f16',16),('s_barrier',26)):
            assert before[old]['mnemonics'][op]==after[new]['mnemonics'][op]==count
    # Read/write ownership: the row-group permutation covers each block once;
    # active epilogue lanes cover each token and hidden float4 exactly once.
    geometries=[]
    local={(group*4*16+j*16+tid//16,(tid%16)*4)
           for group in range(2) for j in range(4) for tid in range(256)}
    assert local=={(t,h) for t in range(128) for h in range(0,64,4)}
    for tokens in (96,97,129,2048):
        token_blocks=(tokens+127)//128
        blocks=set()
        for y in range(40):
            for x in range(token_blocks):
                within=(y%8)*token_blocks+x
                pair=((y//8)*8+within%8,within//8)
                assert pair not in blocks;blocks.add(pair)
        assert blocks=={(h,t) for h in range(40) for t in range(token_blocks)}
        geometries.append(dict(tokens=tokens,blocks=len(blocks),unique_dot_vectors=tokens*640,
            workspace_bytes=tokens*2560*4,reduction_parts=3,last_part_live_lanes=128,
            producer_coverage_exact=True))
    executor=base/'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'
    text=executor.read_text()
    assert 's.down_e = f32(slots * hidden);' in text
    assert 'const std::size_t slots' in text
    report=dict(schema='synapse-lie.q2-hc-inject-reuse-draft-static.v1',
        draft_manifest_sha256=sha(path),parent_assembly_sha256=sha(before_path),
        candidate_assembly=str(after_path.relative_to(ROOT)),candidate_assembly_sha256=sha(after_path),
        saved_parent_recompiled=False,parent_source_unchanged=True,
        original_kernel_bodies_instruction_operand_resource_exact=162,
        private_kernels=probes,producer_comparisons=parents,symbolic_geometry=geometries,
        workspace_source_sha256=sha(executor),
        workspace_limit='down_e allocation already holds slots*hidden F32 elements; '
            'new dots need rows*hidden. Reuse requires previous combine reader complete, '
            'both HC launches ordered before next MoE writer, no pending expert output and no alias.',
        instructions_increase=True,vgpr_lds_private_increase=False,sgpr_increase=True,
        behavioral_host_tests_run=False,GPU_run=False,numerical_acceptance=False,
        performance_measured=False,production_provider=False,goal_met=False)
    with (ROOT/'config/q2-hc-inject-reuse-draft-static.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(original_bodies_exact=162,private_kernels=3,
        workspace_bytes_2048=2048*2560*4,producer_vgpr=242,producer_lds=24576,
        GPU_run=False,performance_measured=False)))


if __name__=='__main__':
    main()
