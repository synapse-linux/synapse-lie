#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare new Q8 fetch assembly with saved1571, without recompiling control."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/q2-q8-aligned-pair-preparation'
def module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/name);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
previous=module('analyze-q2-down-half-storage-static.py');isa=previous.isa;prepare=module('prepare-q2-q8-aligned-pair.py')
def main():
 manifest=ROOT/'config/q2-q8-aligned-pair-source.json';source=json.loads(manifest.read_text())['variants']['q8-aligned-pair']
 assert prepare.inventory(ROOT/source['source'])==source['files']
 for key in ('parent_manifest','measured_parent','control_include','patch'):assert isa.sha(ROOT/source[key])==source[key+'_sha256'],key
 saved=json.loads((ROOT/'config/q2-half-consumer-eight-static.json').read_text());parent_path=ROOT/saved['candidate_assembly_path'];assert isa.sha(parent_path)==saved['candidate_assembly_sha256']
 candidate_path=OUT/'candidate.s';parent,candidate=isa.parse(parent_path),isa.parse(candidate_path);a,b=parent_path.read_text(),candidate_path.read_text()
 assert len(parent)==161 and parent.keys()==candidate.keys()
 changed=[s for s in parent if previous.instructions(a,s)!=previous.instructions(b,s)]
 expected=[s for s in parent if 'DenseF16GEMMKernelILi256ELi128ELi2ELi8ELi1ELi1ELb0E' in s]
 print(json.dumps(dict(changed_count=len(changed),expected_count=len(expected))))
 assert len(expected)==3 and sorted(changed)==sorted(expected)
 for symbol in parent.keys()-set(expected):assert parent[symbol]['resources']==candidate[symbol]['resources'],symbol
 rows=[]
 for symbol in expected:
  old,new=parent[symbol],candidate[symbol]
  assert old['resources']['group_segment_fixed_size']==new['resources']['group_segment_fixed_size']
  assert old['mnemonics'].get('s_barrier',0)==new['mnemonics'].get('s_barrier',0)
  rows.append(dict(symbol=symbol,parent=old,candidate=new))
 commands={n:json.loads((OUT/(n+'-command.json')).read_text()) for n in ('prepare-v2','assembly-v2','fixture-host','fixture-device','wiring','launcher-guards')};assert all(c['exit_code']==0 for c in commands.values())
 failures={n:json.loads((OUT/(n+'-command.json')).read_text()) for n in ('assembly',)};assert failures['assembly']['exit_code']==1
 report=dict(schema='synapse-lie.q2-q8-aligned-pair-static.v1',source_manifest_sha256=isa.sha(manifest),provider_files=1026,retained_parent_assembly_sha256=isa.sha(parent_path),parent_recompiled=False,candidate_assembly_path=str(candidate_path.relative_to(ROOT)),candidate_assembly_sha256=isa.sha(candidate_path),original_bodies_instruction_operand_resource_exact=158,changed_bodies=rows,normalization='Only assembler comments/localBB function numbers/end labels; preserve opcodes,operands and BB suffixes.',commands=commands,preserved_preparation_failures=failures,numerical_contract=source['numerical_contract'],private_bytes=max(r['candidate']['resources']['private_segment_fixed_size'] for r in rows),gpu_run=False,model_inference=False,quality_accepted=False,goal_met=False)
 with (ROOT/'config/q2-q8-aligned-pair-static.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(original_kernels_exact=158,changed_kernels=3,resources=[dict(symbol=r['symbol'],before=r['parent']['resources'],after=r['candidate']['resources'],instructions_before=r['parent']['instructions'],instructions_after=r['candidate']['instructions']) for r in rows],gpu_run=False)))
if __name__=='__main__':main()
