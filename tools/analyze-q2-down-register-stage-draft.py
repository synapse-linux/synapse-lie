#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect Q2 down compiler probes; no runtime or numerical acceptance."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence/q2-down-register-stage-draft-preparation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    spec=importlib.util.spec_from_file_location('group',ROOT/'tools/analyze-q2-ssm-row-group-compose-static.py')
    group=importlib.util.module_from_spec(spec);spec.loader.exec_module(group)
    metadata=json.loads((ROOT/'config/q2-ssm-fixed-bounds-static.json').read_text())
    before_path=ROOT/metadata['candidate_assembly_path']
    assert sha(before_path)==metadata['candidate_assembly_sha256']
    before=group.old.isa.parse(before_path);text_before=before_path.read_text()
    parent_symbols=[s for s in before if 'RoutedQ2HalfStorageKernel' in s and 'ELi128ELi48ELi2ELb0ELb0ELb1' in s]
    assert len(parent_symbols)==1
    parent=before[parent_symbols[0]]
    drafts={}
    for variant in ('v2','v3'):
        path=BASE/('candidate-'+variant+'.s');after=group.old.isa.parse(path);body=path.read_text()
        candidates=[s for s in after if 'RoutedQ2RegisterStageDraft'+variant.upper()+'Kernel' in s]
        assert len(after)==163 and len(candidates)==1
        s=candidates[0];kernel=after[s]
        assert kernel['resources']['group_segment_fixed_size']==8320
        assert kernel['resources']['private_segment_fixed_size']==0
        assert kernel['mnemonics']['s_barrier']==parent['mnemonics']['s_barrier']==8
        assert kernel['mnemonics']['v_wmma_f32_16x16x16_f16']==parent['mnemonics']['v_wmma_f32_16x16x16_f16']==12
        assert all(before[s]['resources']==after[s]['resources'] and
            group.old.instructions(text_before,s)==group.old.instructions(body,s) for s in before)
        command=json.loads((BASE/('assembly-'+variant+'-command.json')).read_text());assert command['exit_code']==0
        drafts[variant]=dict(assembly_path=str(path.relative_to(ROOT)),assembly_sha256=sha(path),
            include_sha256=sha(ROOT/('experiments/q2-down-register-stage-draft-'+variant+'.inc')),
            symbol=s,**kernel,compiler_comments=group.static.compiler_comments(body+'\n\t.section\t.text',s),
            production_kernels_exact=162,compile_command=command)
    original={(tid//2,tid%2) for tid in range(256)}
    changed={((tid//32)*16+(tid%16),(tid%32)//16) for tid in range(256)}
    assert original==changed and len(original)==256
    assert all(((tid//32)*16+(tid%16))//16==tid//32 for tid in range(256))
    report=dict(schema='synapse-lie.q2-down-register-stage-draft-static.v1',parent_assembly_sha256=sha(before_path),
        parent_kernel=parent,candidates=drafts,parent_recompiled=False,
        symbolic_stage_fetch_group_set_unchanged=256,source_wave_private_weight_ownership=True,
        LDS_code_affine_bytes_removed=12288,allocation_reduction_bytes=10240,
        epilogue_capacity_preserved=8320,initial_failed_compile_preserved=True,
        active_shape=dict(BM=128,BN=48,BK=2,m=2560,k=640),
        limits='Compiler-only isolated probes, no production selector/provider or runtime fixture. More register exchange may offset fewer LDS accesses; no numeric/performance acceptance.',
        gpu_run=False,model_measured=False,numerical_acceptance=False,performance_gain=False,goal_met=False)
    output=ROOT/'config/q2-down-register-stage-draft-static.json'
    with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(parent_resources=parent['resources'],parent_instructions=parent['instructions'],
        drafts={k:dict(resources=v['resources'],instructions=v['instructions'],unchanged=v['production_kernels_exact']) for k,v in drafts.items()},gpu_run=False)))
if __name__=='__main__':main()
