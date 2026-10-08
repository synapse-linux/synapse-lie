#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check isolated production down scope against saved parent ISA."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence/q2-down-register-palette-preparation'
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/name);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    p=module('prepare-q2-down-register-palette.py');g=module('analyze-q2-ssm-row-group-compose-static.py')
    manifest_path=ROOT/'config/q2-down-register-palette-source.json'
    source=json.loads(manifest_path.read_text())['variants']['down-register-palette']
    parent=json.loads((ROOT/source['parent_manifest']).read_text())['variants']['ssm-fixed-bounds']
    for item in (source,parent):assert p.inventory(ROOT/item['source'])==item['files']
    for key,val in source.items():
        if key.endswith('_sha256'):
            path=ROOT/source['source']/source[key[:-7]] if key=='numerical_include_sha256' else ROOT/source[key[:-7]]
            assert p.sha(path)==val,key
    metadata=json.loads((ROOT/'config/q2-ssm-fixed-bounds-static.json').read_text())
    before_path=ROOT/metadata['candidate_assembly_path'];assert p.sha(before_path)==metadata['candidate_assembly_sha256']
    after_path=BASE/'candidate.s';a,b=g.old.isa.parse(before_path),g.old.isa.parse(after_path)
    ta,tb=before_path.read_text(),after_path.read_text();assert len(a)==len(b)==162
    mapping={};changed=[]
    for symbol in b:
        old=symbol
        if 'RoutedQ2RegisterPaletteKernel' in symbol:
            old=symbol.replace(str(len('RoutedQ2RegisterPaletteKernel'))+'RoutedQ2RegisterPaletteKernel',str(len('RoutedQ2HalfStorageKernel'))+'RoutedQ2HalfStorageKernel')
        assert old in a and old not in mapping
        mapping[old]=symbol
        if g.old.instructions(ta,old)!=g.old.instructions(tb,symbol).replace(symbol,old) or a[old]['resources']!=b[symbol]['resources']:
            changed.append((old,symbol))
    assert set(mapping)==set(a) and len(changed)==1,changed
    old,new=changed[0];assert 'ELi128ELi48ELi2ELb0ELb0ELb1EEEv' in new
    prior,current=a[old],b[new]
    assert [prior['resources']['group_segment_fixed_size'],current['resources']['group_segment_fixed_size']]==[18560,8320]
    assert current['resources']['private_segment_fixed_size']==0
    assert prior['mnemonics']['s_barrier']==current['mnemonics']['s_barrier']==8
    assert prior['mnemonics']['v_wmma_f32_16x16x16_f16']==current['mnemonics']['v_wmma_f32_16x16x16_f16']==12
    control=(ROOT/source['control_include']).read_text().replace('RoutedQ2RegisterPaletteControlKernel','RoutedQ2HalfStorageKernel')
    original=(ROOT/parent['source']/p.REL).read_text()
    assert control==original[:original.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')]
    report=dict(schema='synapse-lie.q2-down-register-palette-static.v1',source_manifest_sha256=p.sha(manifest_path),provider_files=1028,
        parent_assembly_sha256=p.sha(before_path),candidate_assembly_sha256=p.sha(after_path),parent_recompiled=False,
        other_kernels_instruction_operand_resource_exact=161,literal_parent_control_exact=True,
        parent_kernel=prior,candidate_kernel=current,active_shape=dict(BM=128,BN=48,BK=2,m=2560,k=640),
        gpu_run=False,numerical_acceptance=False,model_measured=False,goal_met=False)
    with (ROOT/'config/q2-down-register-palette-static.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(unchanged=161,resources=[prior['resources'],current['resources']],instructions=[prior['instructions'],current['instructions']],gpu_run=False)))
if __name__=='__main__':main()
