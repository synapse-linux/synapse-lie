#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Consume eight half expert outputs per lane with ordered accumulations."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def main():
    parent_path = ROOT/'config/q2-down-half-vector-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-half-vector']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured1570 parent inventory changed')
    out = ROOT/'.deps/gufo-q2-half-consumer-eight-run'
    manifest = ROOT/'config/q2-half-consumer-eight-source.json'
    patch = ROOT/'experiments/q2-half-consumer-eight.patch'
    control = ROOT/'experiments/q2-half-consumer-eight-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    kernel = function(original, '__global__ void HcCombineMoeHalfDeferredNormKernel(')
    start = kernel.index('  for (std::uint32_t i = threadIdx.x * 4;')
    end = kernel.index('  // All lanes finish the shared row', start)
    retained = kernel[start:end]
    replacement = (ROOT/'experiments/q2-half-consumer-eight-loop.inc').read_text()
    changed = once(original, retained, replacement)
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1026 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured1570 half-input consumer; no saved cohort rerun.\n'+
        kernel.replace('HcCombineMoeHalfDeferredNormKernel', 'HcCombineMoeHalfEightControlKernel'))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL,tofile='b/'+REL)))
    measured = ROOT/'config/q2-down-half-vector-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Eight half-input values per lane, two ordered float4 accumulators and aligned128-bit input loads with existing Load4 fallback. Two outer passes instead of three at hidden2560.',
        numerical_contract='Preserve per-value expert FMA order and shared-expert FMA; later HC/residual/norm source is literal. No producer, representation, wrapper, dispatch or allocation change.',
        additional_runtime_allocations=0,additional_streams=0,additional_block_barriers=0,
        risks='Eight accumulators and alignment branch can raise registers/stalls. Existing four-value loads are already64-bit vectorized; reduced loop work need not reduce model time.',
        inherited_quality='Measured1570 is exact to half-storage1547 whose F16 boundary changes eight F32-parent logit files; independent task quality remains open.',
        gpu_run=False,model_inference=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-half-consumer-eight-source.v1',
        variants={'half-consumer-eight':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
