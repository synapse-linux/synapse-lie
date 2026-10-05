#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assign one wave to each scaled Q2 activation row, with eight rows per CTA."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function

KERNEL = '''__global__ void PackQ2ScaledWaveRowsKernel(const float* x, __half* out,
                                              float* inverse,
                                              std::uint32_t rows) {
  constexpr unsigned cols = 640;
  const unsigned lane = threadIdx.x & 31;
  const std::size_t row = std::size_t(blockIdx.x) * 8 + (threadIdx.x >> 5);
  // Entire waves return together. There are no cross-wave readers/barriers.
  if (row >= rows)
    return;
  const float* src = x + row * cols;
  __half* dst = out + row * cols;
  float4 values[5];
  float local = 0.0F;
#pragma unroll
  for (unsigned i = 0; i < 5; ++i) {
    const unsigned c = (i * 32 + lane) * 4;
    float4 v;
    if (reinterpret_cast<std::uintptr_t>(src) % 16 == 0) {
      v = *reinterpret_cast<const float4*>(src + c);
    } else {
      v = float4{src[c], src[c + 1], src[c + 2], src[c + 3]};
    }
    values[i] = v;
    local = fmaxf(local, fabsf(v.x));
    local = fmaxf(local, fabsf(v.y));
    local = fmaxf(local, fabsf(v.z));
    local = fmaxf(local, fabsf(v.w));
  }
  for (unsigned offset = 16; offset; offset >>= 1)
    local = fmaxf(local, __shfl_down(local, offset, 32));
  float multiplier = 1.0F;
  if (lane == 0) {
    const unsigned bits = __builtin_bit_cast(unsigned, local);
    const int exponent = int((bits >> 23) & 255U) - 127;
    int shift = local == 0.0F ? 0 : 13 - exponent;
    shift = shift < -120 ? -120 : shift > 120 ? 120 : shift;
    multiplier = __builtin_bit_cast(float, unsigned(127 + shift) << 23);
    inverse[row] = __builtin_bit_cast(float, unsigned(127 - shift) << 23);
  }
  multiplier = __shfl(multiplier, 0, 32);
#pragma unroll
  for (unsigned i = 0; i < 5; ++i) {
    const unsigned c = (i * 32 + lane) * 4;
    const float4 v = values[i];
    const __half2 lo = __floats2half2_rn(v.x * multiplier, v.y * multiplier);
    const __half2 hi = __floats2half2_rn(v.z * multiplier, v.w * multiplier);
    if (reinterpret_cast<std::uintptr_t>(dst) % 8 == 0) {
      *reinterpret_cast<uint2*>(dst + c) =
          make_uint2(__builtin_bit_cast(unsigned, lo),
                     __builtin_bit_cast(unsigned, hi));
    } else {
      dst[c] = __low2half(lo);
      dst[c + 1] = __high2half(lo);
      dst[c + 2] = __low2half(hi);
      dst[c + 3] = __high2half(hi);
    }
  }
}
'''


def main():
    parent_path = ROOT/'config/q2-shared-q8-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['shared-q8-pair']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Saved shared-pair provider inventory changed')
    out = ROOT/'.deps/gufo-q2-scaled-wave-pack-run'
    manifest = ROOT/'config/q2-scaled-wave-pack-source.json'
    patch = ROOT/'experiments/q2-scaled-wave-pack.patch'
    control = ROOT/'experiments/q2-scaled-wave-pack-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite an experiment')
    original = (base/REL).read_text()
    kernel = function(original, '__global__ void PackQ2ScaledRowsKernel(')
    changed = once(original, kernel, KERNEL)
    changed = once(changed,
        'hipLaunchKernelGGL(PackQ2ScaledRowsKernel, dim3(rows), dim3(256), 0, stream,\n'
        '                     x, out, inverse, cols);',
        'hipLaunchKernelGGL(PackQ2ScaledWaveRowsKernel, dim3((rows - 1) / 8 + 1),\n'
        '                     dim3(256), 0, stream, x, out, inverse, rows);')
    # Existing declarations, private buffer layout and executor dispatch remain.
    changed = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
                              '--assume-filename='+str(base/REL)],
                             input=changed, text=True, capture_output=True, check=True).stdout
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1027 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal retained1573 row packing, compiled only into the new fixture.\n'+
        kernel.replace('PackQ2ScaledRowsKernel', 'PackQ2ScaledWaveControlKernel'))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    measured = ROOT/'config/q2-shared-q8-pair-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        mechanism='Eight independent wave-owned640-value rows per CTA. Retain five float4 values per lane, reduce maximum within its wave, broadcast original dyadic scale and pack four halves per store.',
        numerical_contract='Same complete-row maximum, exponent/clamp[-120,120], signed-zero handling, F32 multiplication and RN-even F16 boundary. No accumulation, weight, layout, stream or executor-lifetime change.',
        risks='Twenty retained F32 values per lane can increase registers; five vector chunks may change cache traffic. Fewer blocks/barriers do not prove faster packing or model throughput.',
        packing_ctas_at_2048_top10_before=20480, packing_ctas_at_2048_top10_after=2560,
        original_buffers_and_capacity_unchanged=True, additional_allocations=0,
        additional_streams=0, independent_quality=False, gpu_run=False, goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-scaled-wave-pack-source.v1',
        variants={'scaled-wave-pack': variant}, gpu_run=False, goal_met=False), indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta, gpu_run=False)))


if __name__ == '__main__':
    main()
