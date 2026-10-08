#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Move the retained half rounding before wave transpose and pair final stores."""
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
    parent_path = ROOT/'config/q2-down-half-storage-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-half-storage']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured1547 parent inventory changed')
    out = ROOT/'.deps/gufo-q2-down-half-pair-run'
    manifest = ROOT/'config/q2-down-half-pair-source.json'
    patch = ROOT/'experiments/q2-down-half-pair.patch'
    control = ROOT/'experiments/q2-down-half-pair-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    original = (base/REL).read_text()
    kernel = function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    anchor = '  // Transpose each 16x16 tile through LDS, then scatter the 16 rows of each\n'
    replacement = '''  if (out_half == nullptr) {
    // Each original accumulator owner restores and rounds its eight values
    // using one slot scale. Transpose the already-rounded half bytes through
    // wave-private scratch, then issue one aligned word per adjacent pair.
    // No block-wide synchronization or additional rounding is introduced.
    __half* half_tile = reinterpret_cast<__half*>(lds) + wave_id * 256;
    __half* dst_half = reinterpret_cast<__half*>(out);
#pragma unroll
    for (int u = 0; u < kWaveRowTiles; ++u) {
      const int r0 = r_block + wave_id * 16 + u * 128;
#pragma unroll
      for (int j = 0; j < kTokTiles; ++j) {
        const int t0 = t_local + j * 16;
        const int token = t0 + sub_lane;
        const int slot = token < bucket_rows ? rows_out[bucket_begin + token] : -1;
        if (slot >= 0) {
          const float inverse = static_cast<const float*>(w_up)[slot];
#pragma unroll
          for (int l = 0; l < 8; ++l) {
            float restored = acc[u][j][l] * inverse;
            asm("" : "+v"(restored));
            half_tile[sub_lane * 16 + 2 * l + half_id] = __float2half_rn(restored);
          }
        }
        __builtin_amdgcn_wave_barrier();
#pragma unroll
        for (int s = 0; s < 4; ++s) {
          const int flat = (s * 32 + lane_id) * 2;
          const int t = t0 + (flat >> 4);
          const int r = r0 + (flat & 15);
          if (t < bucket_rows && r < m_i) {
            const int dst = rows_out[bucket_begin + t];
            if (dst >= 0) {
              const std::size_t o = std::size_t(dst) * m + std::size_t(r);
              const __half2 packed = *reinterpret_cast<const __half2*>(half_tile + flat);
              if (m % 2 == 0 && r + 1 < m_i) {
                *reinterpret_cast<__half2*>(dst_half + o) = packed;
              } else {
                dst_half[o] = __low2half(packed);
                if (r + 1 < m_i)
                  dst_half[o + 1] = __high2half(packed);
              }
            }
          }
        }
        __builtin_amdgcn_wave_barrier();
      }
    }
    return;
  }

'''
    changed = once(original, anchor, replacement+anchor)
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1026 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal measured1547 half-storage parent; no qualified cohort rerun.\n'+
        kernel.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2HalfPairControlKernel'))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
    measured = ROOT/'config/q2-down-half-storage-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Restore/round per accumulator owner with one slot scale, transpose F16 in wave-private scratch, and pair adjacent output stores. Odd-width rows retain scalar tails.',
        numerical_contract='Retain original F32 inverse-scale product and one RN-even F16 store boundary from1547. No extra rounding, WMMA reordering, output-layout or consumer change.',
        epilogue_scratch_bytes_before=8192,epilogue_scratch_bytes_after=4096,
        lds_allocation_capacity_unchanged=True,additional_runtime_allocations=0,
        additional_streams=0,additional_block_barriers=0,
        risks='Halfword LDS bank conflicts, routing/scale ownership and registers can offset fewer output iterations. Every consumed scratch cell must have a valid writer.',
        inherited_quality='Half-storage1547 changes eight F32-parent logit files (maxKL.00269324); task quality is not accepted by an exact-to1547 optimization.',
        gpu_run=False,model_inference=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-down-half-pair-source.v1',
        variants={'down-half-pair':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
