#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Share activation tiles across paired IQ2 rows and use a wave-local epilogue."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('lane', ROOT/'tools/prepare-q2-iq2-lane-commit.py')
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
sha, inventory = lane.sha, lane.inventory


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source anchor is not unique: '+old[:100])
    return text.replace(old,new)


def main():
    parent_path = ROOT/'config/q2-iq2-lane-commit-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-lane-commit']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained nominal best source changed')
    original = (base/REL).read_text()
    out = ROOT/'.deps/gufo-q2-iq2-wide-pair-run'
    manifest = ROOT/'config/q2-iq2-wide-pair-source.json'
    patch = ROOT/'experiments/q2-iq2-wide-pair.patch'
    control = ROOT/'experiments/q2-iq2-wide-pair-control.inc'
    if any(p.exists() for p in (out,manifest,patch,control)):
        raise ValueError('Refusing to overwrite experiment')
    kernel = lane.prior.prior.literal.function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    control_text = '// SPDX-License-Identifier: MIT\n// Literal measured lane-commit1509 parent, retained inside the new fixture.\n'
    control_text += kernel.replace('RoutedF16GEMMKernel','RoutedIq2WidePairControlKernel')+'\n'
    changed = replace_once(original,'  static_assert(!kPair || BM == 128);',
        '  static_assert(!kPair || BM == 128 ||\n'
        '                (kType == WeightType::kIQ2_XXS && BM == 256 && BN == 64 && !kPacked));')
    changed = replace_once(changed,
        '        r_block + (kPair ? (tid >> 1) % kRows : (tid >> 1) + (u * 128));',
        '        r_block + (kPair ? ((tid >> 1) + u * 128) % kRows\n'
        '                         : (tid >> 1) + u * 128);')
    changed = replace_once(changed,'      if ((tid >> 1) >= kRows) {',
        '      if ((tid >> 1) + u * 128 >= kRows) {')
    anchor = '''  if constexpr (kPair) {
    // Four waves compute gate rows and four compute the matching up rows.'''
    epilogue = '''  if constexpr (kPair && BM == 256) {
    // SPDX-License-Identifier: MIT
    // The same wave holds gate in u0 and up in u1 for its sixteen rows.
    // Evaluate the original rounded F32 boundaries before transposing only
    // final values. Each scratch plane has one wave and no cross-wave reader.
    constexpr unsigned stride = 18;
    constexpr unsigned plane = 16 * stride;
    static_assert(8 * plane * sizeof(float) <= kLdsBytes);
    float* scratch = reinterpret_cast<float*>(lds) + wave_id * plane;
#pragma unroll
    for (int j = 0; j < kTokTiles; ++j) {
#pragma unroll
      for (int l = 0; l < 8; ++l) {
        float product = acc[1][j][l] * acc[0][j][l];
        asm volatile("" : "+v"(product));
        float value = product * SigmoidF(acc[0][j][l]);
        asm volatile("" : "+v"(value));
        scratch[sub_lane * stride + 2 * l + half_id] = value;
      }
      __builtin_amdgcn_wave_barrier();
#pragma unroll
      for (int unit = 0; unit < 4; ++unit) {
        const int flat = (unit * 32 + lane_id) * 2;
        const int t = t_local + j * 16 + flat / 16;
        const int r = wave_id * 16 + flat % 16;
        if (t < bucket_rows && r_block + r < m_i) {
          const std::int32_t dst = rows_out[bucket_begin + t];
          if (dst >= 0) {
            const int idx = (flat / 16) * stride + flat % 16;
            const auto offset = static_cast<std::size_t>(dst) * m + r_block + r;
            if (m % 2 == 0 && r_block + r + 1 < m_i) {
              *reinterpret_cast<float2*>(out + offset) =
                  make_float2(scratch[idx], scratch[idx + 1]);
            } else {
              out[offset] = scratch[idx];
              if (r_block + r + 1 < m_i)
                out[offset + 1] = scratch[idx + 1];
            }
          }
        }
      }
      __builtin_amdgcn_wave_barrier();
    }
    return;
  }

'''
    changed = replace_once(changed,anchor,epilogue+anchor)
    old_launch = '''  const dim3 grid(static_cast<unsigned>((m + 63) / 64), n_tiles);
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),'''
    new_launch = '''  constexpr int kBM = BN == 64 && !kPacked ? 256 : 128;
  constexpr int kRows = kBM / 2;
  const dim3 grid(static_cast<unsigned>((m + kRows - 1) / kRows), n_tiles);
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, kBM, BN, 2, true, kPacked>),'''
    changed = replace_once(changed,old_launch,new_launch)
    shutil.copytree(base,out)
    (out/REL).write_text(changed)
    with control.open('x') as stream:stream.write(control_text)
    files = inventory(out)
    delta = sorted(n for n in files if files[n] != parent['files'].get(n))
    if len(files) != 1025 or delta != [REL]:raise ValueError('Unexpected source delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/'+REL,tofile='b/'+REL)))
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-lane-commit-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-iq2-lane-commit-model-results.json'),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='BM256 for nonpacked IQ2 BN64 only; gate/up share each wave and activation tile, and final SwiGLU uses per-wave transpose scratch.',
        numerical_contract='Retained raw group/codebook/scale/half bytes and ordered per-dot WMMA; explicit original F32 product and value boundaries before final scatter.',
        unchanged='BN16/48/128, packed IQ2, Q2 down, dense, vector decode, attention, routing descriptors, tensor/stream ownership.',
        original_logical_rows=64,new_logical_rows=128,production_bn=64,
        additional_runtime_allocations=0,additional_streams=0,additional_device_tables=0,
        risks='Doubled accumulators/prefetch increase VGPR and LDS, possibly reducing occupancy; new epilogue requires full numerical/ragged/lifetime replay.',
        gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-wide-pair-source.v1',variants={'iq2-wide-pair':variant},gpu_run=False,goal_met=False),stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(variant='iq2-wide-pair',files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
