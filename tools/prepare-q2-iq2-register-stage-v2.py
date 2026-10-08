#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate the IQ2 register stage without modifying the shared template."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v1',ROOT/'tools/prepare-q2-iq2-register-stage.py')
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
sha, inventory, once = v1.sha, v1.inventory, v1.once
REL = v1.REL
INC = 'src/models/qwen38_flash_next/kernels/rocm/q2_iq2_register_stage.inc'


def main():
    parent_path=ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent=json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    donor_path=ROOT/'config/q2-iq2-register-stage-source.json'
    donor=json.loads(donor_path.read_text())['variants']['iq2-register-stage']
    for item in (parent,donor):
        assert inventory(ROOT/item['source'])==item['files']
    original=(ROOT/parent['source']/REL).read_text()
    transformed=(ROOT/donor['source']/REL).read_text()
    kernel=v1.function(transformed,v1.PREFIX)
    isolated='// SPDX-License-Identifier: MIT\n'
    isolated+='// Official-Gufo-derived IQ2 experiment; source and original numerical lineage are pinned.\n'
    isolated+='// Only wide nonpacked IQ2 selects this private specialization.\n'
    isolated+=kernel.replace('RoutedF16GEMMKernel','RoutedIq2RegisterStageKernel')+'\n'
    original_kernel=v1.function(original,v1.PREFIX)
    candidate=once(original,original_kernel,
                   original_kernel+'\n\n#include "q2_iq2_register_stage.inc"')
    launch='''  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),
      grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
      rows_slot, nullptr, out, nullptr, m, k, up);'''
    selected='''  if constexpr (BN == 128 && !kPacked) {
    hipLaunchKernelGGL(
        (RoutedIq2RegisterStageKernel<WeightType::kIQ2_XXS, 128, BN, 2, true,
                                      false, false, true>),
        grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
        rows_slot, nullptr, out, nullptr, m, k, up);
  } else {
'''+launch+'\n  }'
    candidate=once(candidate,launch,selected)
    out=ROOT/'.deps/gufo-q2-iq2-register-stage-v2-run'
    manifest=ROOT/'config/q2-iq2-register-stage-source-v2.json'
    patch=ROOT/'experiments/q2-iq2-register-stage-v2.patch'
    if any(p.exists() for p in (out,manifest,patch)):
        raise ValueError('Refusing to overwrite experiment')
    shutil.copytree(ROOT/parent['source'],out)
    (out/REL).write_text(candidate)
    (out/INC).write_text(isolated)
    files=inventory(out)
    delta=sorted(n for n in files if files[n]!=parent['files'].get(n))
    assert len(files)==1028 and delta==sorted([REL,INC])
    assert v1.function(candidate,v1.PREFIX)==original_kernel
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True),candidate.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL))+
        ''.join(difflib.unified_diff([],isolated.splitlines(True),fromfile='/dev/null',tofile='b/'+INC)))
    source=dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-ssm-fixed-bounds-model-results.json'),
        donor_manifest=str(donor_path.relative_to(ROOT)),donor_manifest_sha256=sha(donor_path),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        generator=str(Path(__file__).relative_to(ROOT)),generator_sha256=sha(Path(__file__)),
        control_include=donor['control_include'],control_include_sha256=donor['control_include_sha256'],
        numerical_include=INC,numerical_include_sha256=sha(out/INC),
        symbolic_ownership=v1.ownership(),original_template_source_unchanged=True,
        mechanism=donor['mechanism'],numerical_contract=donor['numerical_contract'],
        risks=donor['risks'],additional_runtime_allocations=0,
        preparation_reason='Initial shared-template candidate changed nine unrelated compiled Q2 bodies. Preserve it; isolate the numerical specialization before device qualification.',
        gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
    with manifest.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-iq2-register-stage-source.v2',
                       variants={'iq2-register-stage':source}),f,indent=2);f.write('\n')
    print(json.dumps(dict(files=len(files),changed_files=delta,original_template_unchanged=True,gpu_run=False)))


if __name__=='__main__':
    main()
