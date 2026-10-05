#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the prepared SSM grid change with the measured 1580 provider."""
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm',ROOT/'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    parent_path = ROOT/'config/q2-down-register-scatter-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-register-scatter']
    standalone_path = ROOT/'config/q2-ssm-row-group-source.json'
    standalone = json.loads(standalone_path.read_text())['variants']['ssm-row-group']
    measured_path = ROOT/'config/q2-down-register-scatter-model-results.json'
    disposition_path = ROOT/'config/q2-down-register-scatter-disposition.json'
    disposition = json.loads(disposition_path.read_text())
    assert disposition['next_composition_variant']=='down-register-scatter'
    assert disposition['model_result_sha256']==ssm.sha(measured_path)
    assert disposition['prefill_tok_s']==1580.226725 and disposition['all21_parent_files_exact']
    for variant in (parent,standalone):
        assert ssm.inventory(ROOT/variant['source'])==variant['files']
    out = ROOT/'.deps/gufo-q2-ssm-row-group-compose-run'
    manifest_path = ROOT/'config/q2-ssm-row-group-compose-source.json'
    if out.exists() or manifest_path.exists():
        raise ValueError('Refusing to overwrite a retained composition')
    original = (ROOT/parent['source']/ssm.REL).read_text()
    changed = ssm.once(ssm.once(original,ssm.ASSERT_BEFORE,ssm.ASSERT_AFTER),ssm.LAUNCH_BEFORE,ssm.LAUNCH_AFTER)
    assert changed==(ROOT/standalone['source']/ssm.REL).read_text()
    shutil.copytree(ROOT/parent['source'],out)
    (out/ssm.REL).write_text(changed)
    files = ssm.inventory(out)
    delta = [name for name in files if files[name]!=parent['files'].get(name)]
    assert len(files)==1027 and delta==[ssm.REL]
    control = ROOT/'experiments/q2-ssm-row-group-control.inc'
    literal = (ssm.function(original,'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')+
               ssm.function(original,'bool DenseF16SsmGemm('))
    recovered = control.read_text().split('\n',2)[2].replace('DenseSsmRowGroupControlKernel','DenseF16GEMMKernel').replace(
        'DenseSsmRowGroupControl','DenseF16SsmGemm')
    assert recovered==literal
    variant = dict(standalone)
    variant.update(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=ssm.sha(parent_path),
        measured_parent=str(measured_path.relative_to(ROOT)),measured_parent_sha256=ssm.sha(measured_path),
        parent_disposition=str(disposition_path.relative_to(ROOT)),parent_disposition_sha256=ssm.sha(disposition_path),
        standalone_manifest=str(standalone_path.relative_to(ROOT)),standalone_manifest_sha256=ssm.sha(standalone_path),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=ssm.sha(control),
        control_literal_current_parent_exact=True,
        inherited_register_scatter_file='src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc',
        inherited_register_scatter_sha256=parent['files']['src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'],
        inherited_quality='Retained1580 inherits F16 task-quality gaps; standalone SSM GPU/model performance remains unmeasured.',
        parent_prefill_tok_s=1580.226725,parent_decode_steps_s=25.10411864,
        gpu_run=False,model_inference=False,numerical_acceptance=False,performance_gain=False,goal_met=False)
    for key,path in [('fixture','tests/q2_ssm_row_group.hip'),('oracle','experiments/q2-ssm-row-group-oracle.inc'),
                     ('fixture_contract','config/q2-ssm-row-group-fixture.json')]:
        variant[key]=path;variant[key+'_sha256']=ssm.sha(ROOT/path)
    with manifest_path.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-ssm-row-group-compose-source.v1',
            variants={'ssm-row-group':variant},gpu_run=False,goal_met=False),f,indent=2);f.write('\n')
    print(json.dumps(dict(provider_files=1027,changed_files=delta,parent_prefill_tok_s=1580.226725,
        current_parent_control_exact=True,gpu_run=False)))


if __name__=='__main__':
    main()
