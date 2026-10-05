#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Specialize integer geometry of the fixed2560 half-input consumer."""
import difflib
import importlib.util
import json
import re
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def main():
    parent_path = ROOT/'config/q2-half-consumer-eight-source.json'
    parent = json.loads(parent_path.read_text())['variants']['half-consumer-eight']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured1571 parent inventory changed')
    out = ROOT/'.deps/gufo-q2-half-fixed-width-run'
    manifest = ROOT/'config/q2-half-fixed-width-source.json'
    patch = ROOT/'experiments/q2-half-fixed-width.patch'
    control = ROOT/'experiments/q2-half-fixed-width-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    kernel = function(original, '__global__ void HcCombineMoeHalfDeferredNormKernel(')
    signature_end = kernel.index(') {') + 3
    body = kernel[signature_end:]
    body = re.sub(r'\bhidden\b', 'kHidden', body)
    body = once(body, 'static_cast<float>(kHidden)', 'static_cast<float>(hidden)')
    changed_kernel = kernel[:signature_end] + '\n  // Integer geometry only; preserve the original floating normalization divisor.\n  constexpr std::uint32_t kHidden = 2560;' + body
    assert len(re.findall(r'\bhidden\b', changed_kernel[signature_end:])) == 1
    assert 'total / static_cast<float>(hidden) + eps' in changed_kernel
    changed = once(original, kernel, changed_kernel)
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1026 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured1571 half-input consumer; no saved cohort rerun.\n'+
        kernel.replace('HcCombineMoeHalfDeferredNormKernel', 'HcCombineMoeHalfWidthControlKernel'))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL,tofile='b/'+REL)))
    measured = ROOT/'config/q2-half-consumer-eight-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Compile-time2560 integer indexing and bounds inside the already fixed-width wrapper. Retain runtime hidden solely for the original floating normalization divisor.',
        numerical_contract='Preserve expert/shared FMA, residual update, square contraction, WaveSum order, ordered total and runtime floating hidden division, rsqrt and F16 rounding. Integer indices are equivalent for wrapper-accepted2560. Wrapper/producer/representation/dispatch/allocation unchanged.',
        additional_runtime_allocations=0,additional_streams=0,additional_block_barriers=0,
        risks='Constant propagation changes instruction scheduling and register allocation; arithmetic source preservation needs complete GPU/model checks. Fewer integer instructions do not prove lower latency.',
        inherited_quality='Measured1571 is exact to half-storage1547 whose F16 boundary changes eight F32-parent logit files; independent task quality remains open.',
        gpu_run=False,model_inference=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-half-fixed-width-source.v1',
        variants={'half-fixed-width':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
