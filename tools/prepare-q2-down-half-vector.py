#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Copy eight already-rounded halves per aligned lane output store."""
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
    parent_path = ROOT/'config/q2-down-half-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-half-pair']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured1566 parent inventory changed')
    out = ROOT/'.deps/gufo-q2-down-half-vector-run'
    manifest = ROOT/'config/q2-down-half-vector-source.json'
    patch = ROOT/'experiments/q2-down-half-vector.patch'
    control = ROOT/'experiments/q2-down-half-vector-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    kernel = function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    start = original.index('#pragma unroll\n        for (int s = 0; s < 4; ++s) {')
    end = original.index('        __builtin_amdgcn_wave_barrier();', start)
    retained = original[start:end]
    replacement = '''        if (m % 8 == 0 && reinterpret_cast<std::uintptr_t>(dst_half) % 16 == 0) {
          // Two lanes cover one complete token row of the 16x16 half tile.
          // Both addresses are 16-byte aligned; m and r are multiples of 8,
          // so r<m implies all eight output halves are valid.
          const int flat = lane_id * 8;
          const int t = t0 + (flat >> 4);
          const int r = r0 + (flat & 15);
          if (t < bucket_rows && r < m_i) {
            const int dst = rows_out[bucket_begin + t];
            if (dst >= 0) {
              const std::size_t o = std::size_t(dst) * m + std::size_t(r);
              *reinterpret_cast<uint4*>(dst_half + o) =
                  *reinterpret_cast<const uint4*>(half_tile + flat);
            }
          }
        } else {
'''+''.join('  '+line if line.strip() else line for line in retained.splitlines(True))+'''        }
'''
    changed = once(original, retained, replacement)
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1026 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured1566 half-pair parent; no qualified cohort rerun.\n'+
        kernel.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2HalfVectorControlKernel'))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
    measured = ROOT/'config/q2-down-half-pair-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='One aligned128-bit output load/store per lane replaces four pair-store rounds when output base is16-byte aligned and m is divisible by8. Retain original pair fallback otherwise.',
        numerical_contract='Copy existing RN-even half bytes without arithmetic, conversion, WMMA, scale, routing, consumer or output-layout changes.',
        epilogue_scratch_bytes_before=4096,epilogue_scratch_bytes_after=4096,
        lds_allocation_capacity_unchanged=True,additional_runtime_allocations=0,
        additional_streams=0,additional_block_barriers=0,
        risks='Wider LDS reads, register scheduling and active-lane mapping can offset fewer scatter rounds. Vector path requires both pointer and row alignment; invalid slots remain guarded.',
        inherited_quality='Measured1566 is exact to half-storage1547, whose F16 boundary changes eight F32-parent logit files; independent task quality remains open.',
        gpu_run=False,model_inference=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-down-half-vector-source.v1',
        variants={'down-half-vector':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
