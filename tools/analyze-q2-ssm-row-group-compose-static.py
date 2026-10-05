#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify SSM composition against saved1580 ISA without rebuilding its parent."""
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-ssm-row-group-compose-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name,ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ssm = module('prepare-q2-ssm-row-group.py')
static = module('analyze-q2-ssm-row-group-static.py')
old = static.old


def main():
    manifest_path = ROOT/'config/q2-ssm-row-group-compose-source.json'
    source = json.loads(manifest_path.read_text())['variants']['ssm-row-group']
    for key in ('parent_manifest','measured_parent','parent_disposition','standalone_manifest',
                'control_include','patch','fixture','oracle','fixture_contract'):
        assert ssm.sha(ROOT/source[key])==source[key+'_sha256'],key
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['down-register-scatter']
    for variant in (source,parent):
        assert ssm.inventory(ROOT/variant['source'])==variant['files']
    assert source['files'][source['inherited_register_scatter_file']]==source['inherited_register_scatter_sha256']
    parent_static_path = ROOT/'config/q2-down-register-scatter-static.json'
    parent_static = json.loads(parent_static_path.read_text())
    parent_path = ROOT/parent_static['candidate_assembly_path']
    assert ssm.sha(parent_path)==parent_static['candidate_assembly_sha256']
    standalone_static_path = ROOT/'config/q2-ssm-row-group-static.json'
    standalone_static = json.loads(standalone_static_path.read_text())
    standalone_path = ROOT/standalone_static['candidate_assembly_path']
    assert ssm.sha(standalone_path)==standalone_static['candidate_assembly_sha256']
    new_path = OUT/'candidate.s'
    a,b = old.isa.parse(parent_path),old.isa.parse(new_path)
    assert len(a)==len(b)==162
    removed,added = set(a)-set(b),set(b)-set(a)
    assert len(removed)==len(added)==1
    control,candidate = next(iter(removed)),next(iter(added))
    assert 'ILi256ELi128ELi2ELi8ELi1ELi1ELb0ELb1' in control
    assert control.replace('ELi8ELi1ELi1ELb0ELb1','ELi8ELi1ELi4ELb0ELb1')==candidate
    before,after = parent_path.read_text(),new_path.read_text()
    for symbol in set(a)&set(b):
        assert old.instructions(before,symbol)==old.instructions(after,symbol),symbol
        assert a[symbol]['resources']==b[symbol]['resources'],symbol
    assert old.instructions(after,candidate)==old.instructions(standalone_path.read_text(),candidate)
    assert b[candidate]['resources']==standalone_static['candidate_kernel']['resources']
    assert a[control]['resources']==b[candidate]['resources']
    with TemporaryDirectory(dir=OUT,prefix='reconstruct-') as tmp:
        dest = Path(tmp)/ssm.REL
        dest.parent.mkdir(parents=True)
        dest.write_bytes((ROOT/parent['source']/ssm.REL).read_bytes())
        result = subprocess.run(['patch','--batch','-p1','-i',str(ROOT/source['patch'])],
            cwd=tmp,text=True,capture_output=True)
        assert result.returncode==0,result.stderr
        assert ssm.sha(dest)==source['files'][ssm.REL]
    commands = {name:json.loads((OUT/(name+'-command.json')).read_text())
                for name in ('generation','assembly','fixture-host','fixture-device')}
    assert all(r['exit_code']==0 for r in commands.values())
    report = dict(schema='synapse-lie.q2-ssm-row-group-compose-static.v1',
        source_manifest_sha256=ssm.sha(manifest_path),provider_files=1027,
        parent_assembly_path=str(parent_path.relative_to(ROOT)),parent_assembly_sha256=ssm.sha(parent_path),
        candidate_assembly_path=str(new_path.relative_to(ROOT)),candidate_assembly_sha256=ssm.sha(new_path),
        parent_recompiled=False,source_reconstruction_exact=True,
        other_kernels_instruction_operand_resource_exact=161,
        inherited_down_register_scatter_bodies_exact=True,
        ssm_body_exact_to_standalone_compiled_candidate=True,
        parent_kernel=dict(symbol=control,**a[control],compiler_comments=static.compiler_comments(before,control)),
        candidate_kernel=dict(symbol=candidate,**b[candidate],compiler_comments=static.compiler_comments(after,candidate)),
        retained_symbolic_mapping=standalone_static['symbolic_mapping'],
        retained_symbolic_report_sha256=ssm.sha(standalone_static_path),
        literal_control_current_parent_exact=source['control_literal_current_parent_exact'],
        commands=commands,cpu_checks_are_not_gpu_or_model_evidence=True,
        gpu_run=False,model_inference=False,numerical_acceptance=False,goal_met=False)
    with (ROOT/'config/q2-ssm-row-group-compose-static.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(other_kernels_exact=161,ssm_exact_to_standalone=True,
        inherited_register_scatter_exact=True,resources=b[candidate]['resources'],gpu_run=False)))


if __name__=='__main__':
    main()
