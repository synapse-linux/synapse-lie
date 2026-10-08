#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate the active Q2 down register-palette draft from retained1585."""
import difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REL='src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
INC='src/models/qwen38_flash_next/kernels/rocm/q2_down_register_palette.inc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
def once(s,a,b):
    assert s.count(a)==1,a[:100]
    return s.replace(a,b,1)
def main():
    parent_path=ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent=json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    assert inventory(ROOT/parent['source'])==parent['files']
    static_path=ROOT/'config/q2-down-register-stage-draft-static.json'
    static=json.loads(static_path.read_text())
    draft_path=ROOT/'experiments/q2-down-register-stage-draft-v3.inc'
    assert sha(draft_path)==static['candidates']['v3']['include_sha256']
    original=(ROOT/parent['source']/REL).read_text()
    control=original[:original.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')].replace('RoutedQ2HalfStorageKernel','RoutedQ2RegisterPaletteControlKernel')
    cp=ROOT/'experiments/q2-down-register-palette-control.inc';assert not cp.exists();cp.write_text(control)
    isolated=draft_path.read_text().replace('RoutedQ2RegisterStageDraftV3Kernel','RoutedQ2RegisterPaletteKernel')
    candidate=once(original,'template<int BN>\nvoid LaunchRoutedQ2HalfStorage', '#include "q2_down_register_palette.inc"\n\ntemplate<int BN>\nvoid LaunchRoutedQ2HalfStorage')
    a=candidate.index('  hipLaunchKernelGGL(\n      (RoutedQ2HalfStorageKernel',candidate.index('void LaunchRoutedQ2HalfStorage'))
    b=candidate.index('\n}',a)
    launch=candidate[a:b]
    selected='  if constexpr (BN == 48) {\n'+launch.replace('RoutedQ2HalfStorageKernel','RoutedQ2RegisterPaletteKernel')+'\n  } else {\n'+launch+'\n  }'
    candidate=candidate[:a]+selected+candidate[b:]
    out=ROOT/'.deps/gufo-q2-down-register-palette-run'
    manifest=ROOT/'config/q2-down-register-palette-source.json';patch=ROOT/'experiments/q2-down-register-palette.patch'
    assert not any(p.exists() for p in (out,manifest,patch))
    shutil.copytree(ROOT/parent['source'],out)
    (out/REL).write_text(candidate);(out/INC).write_text(isolated)
    files=inventory(out);delta=sorted(n for n in files if files[n]!=parent['files'].get(n))
    assert len(files)==1028 and delta==sorted([REL,INC])
    assert candidate[:candidate.index('#include "q2_down_register_palette.inc"')]==original[:original.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')]
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL))+''.join(difflib.unified_diff([],isolated.splitlines(True),fromfile='/dev/null',tofile='b/'+INC)))
    source=dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',measured_parent_sha256=sha(ROOT/'config/q2-ssm-fixed-bounds-model-results.json'),
        draft_static=str(static_path.relative_to(ROOT)),draft_static_sha256=sha(static_path),
        donor_include=str(draft_path.relative_to(ROOT)),donor_include_sha256=sha(draft_path),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),generator=str(Path(__file__).relative_to(ROOT)),generator_sha256=sha(Path(__file__)),
        control_include=str(cp.relative_to(ROOT)),control_include_sha256=sha(cp),
        numerical_include=INC,numerical_include_sha256=sha(out/INC),
        original_kernel_source_unchanged=True,additional_runtime_allocations=0,
        mechanism='Active BN48 scaled-half down only: wave-private codes and exact half palettes in registers; shared activation and padded output stages unchanged',
        numerical_contract='Original F32 scale/bias, each explicit FMA and F16 palette rounding, ordered WMMA, F32 inverse product and half output; no numeric qualification from source',
        gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
    with manifest.open('x') as f:json.dump(dict(schema='synapse-lie.q2-down-register-palette-source.v1',variants={'down-register-palette':source}),f,indent=2);f.write('\n')
    print(json.dumps(dict(files=len(files),changed_files=delta,gpu_run=False)))
if __name__=='__main__':main()
