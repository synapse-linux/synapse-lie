#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Omit unread activation stores in the active scaled-Q2 down consumer."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('lane',ROOT/'tools/prepare-q2-iq2-lane-commit.py')
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
sha,inventory = lane.sha,lane.inventory


def main():
    parent_path = ROOT/'config/q2-iq2-live-compose-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-live-compose']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained parent source changed')
    audit = json.loads((ROOT/'config/q2-scaled-live-stage-opportunity.json').read_text())
    if audit['inspected_parent_manifest_sha256'] != sha(parent_path):
        raise ValueError('Down store audit parent changed')
    out = ROOT/'.deps/gufo-q2-down-live-stage-run'
    manifest = ROOT/'config/q2-down-live-stage-source.json'
    patch = ROOT/'experiments/q2-down-live-stage.patch'
    control = ROOT/'experiments/q2-down-live-stage-control.inc'
    if any(p.exists() for p in (out,manifest,patch,control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    old = '        (!(kIQ2 && kPair && kTokTiles > 1) || t < live_tok_tiles * 16);'
    new = '''        (!((kIQ2 && kPair && kTokTiles > 1) ||
           (kQ2 && kScaled && BN >= 48)) || t < live_tok_tiles * 16);'''
    if original.count(old) != 1:
        raise ValueError('Store predicate anchor changed')
    changed = original.replace(old,new)
    kernel = lane.prior.prior.literal.function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    shutil.copytree(base,out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [n for n in files if files[n] != parent['files'].get(n)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured IQ2 live-compose1511 parent, unchanged scaled-Q2 down.\n'+
        kernel.replace('RoutedF16GEMMKernel','RoutedDownLiveControlKernel')+'\n')
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
    measured = ROOT/'config/q2-iq2-live-compose-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        affected='Scaled Q2_K down BN48/64 only; BN16 and all other kernels retain their predicate.',
        numerical_contract='Keep final live16-row zero padding, logical640/stored768 K tail, original '
            'encoded weights, affine decoder, scaled F16 input, WMMA order, inverse and F32 epilogue.',
        mechanism='Compute slot eligibility once before K stages; omit stores only where the existing '
            'matrix loop has no readers. No new arithmetic, grid shape or allocation.',
        risks='Predicate scheduling and scalar-register demand can offset omitted LDS stores.',
        numerical_kernel_source_unchanged=False,additional_runtime_allocations=0,
        additional_streams=0,gpu_run=False,model_inference=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-down-live-stage-source.v1',
        variants={'down-live-stage':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=1025,changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
