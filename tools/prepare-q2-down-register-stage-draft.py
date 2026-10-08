#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a source-only Q2 down experiment from the bound retained1585 parent."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='config/q2-ssm-fixed-bounds-source.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((ROOT/PARENT).read_text())['variants']['ssm-fixed-bounds']
    relative='src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
    path=ROOT/manifest['source']/relative
    assert sha(path)==manifest['files'][relative]
    s=path.read_text();s=s[:s.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')]
    s=s.replace('RoutedQ2HalfStorageKernel','RoutedQ2RegisterStageDraftKernel')
    s=s.replace('constexpr int kCodeBytes = BM * kChunks * 16;', 'constexpr int kCodeBytes = 0;')
    s=s.replace('constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;', 'constexpr int kScaleBytes = 0;')
    s=s.replace('const int f_c = tid & 1;', 'const int f_c = half_id;\n  const int f_row = wave_id * 16 + sub_lane;')
    s=s.replace('(tid >> 1)', 'f_row')
    s=s.replace('  uint4 f_codes[kWaveRowTiles];', '  uint4 stage_codes[kWaveRowTiles][2];\n  std::uint32_t stage_affine[kWaveRowTiles][4];\n  uint4 f_codes[kWaveRowTiles];',1)
    s=s.replace('        s_codes[swizzle(row, 2 * f_c)] = f_codes[u];\n        s_codes[swizzle(row, (2 * f_c) + 1)] = f_codes_hi[u];', '        stage_codes[u][0] = f_codes[u];\n        stage_codes[u][1] = f_codes_hi[u];',1)
    s=s.replace('          auto* affine = reinterpret_cast<float*>(s_scale) +\n                         2 * (((2 * f_c + part) * BM) + row);\n          affine[0] = d;\n          affine[1] = b;', '          stage_affine[u][2 * part] = __builtin_bit_cast(std::uint32_t, d);\n          stage_affine[u][2 * part + 1] = __builtin_bit_cast(std::uint32_t, b);',1)
    s=s.replace('  const auto compute_stage = [&]() {', '''  const auto stage_word = [half_id](std::uint32_t own, int kb) {
    const auto peer = __builtin_amdgcn_permlanex16(
        own, own, 0x76543210U, 0xFEDCBA98U, false, false);
    return half_id == kb ? own : peer;
  };
  const auto compute_stage = [&]() {''',1)
    s=s.replace('          const uint4 c0 = s_codes[swizzle(row, 2 * kb)];\n          const uint4 c1 = s_codes[swizzle(row, (2 * kb) + 1)];', '          const uint4 c0 = stage_codes[u][0];\n          const uint4 c1 = stage_codes[u][1];',1)
    s=s.replace('            nib[i] = (kSigned && !kIQ2) ? words[i] ^ 0x80808080U : words[i];', '            nib[i] = stage_word(words[i], kb);',1)
    s=s.replace('            const auto* affine = reinterpret_cast<const float*>(s_scale) +\n                                 2 * (((2 * kb + part) * BM) + row);\n            const float d = affine[0], bias = affine[1];', '            const float d = __builtin_bit_cast(float, stage_word(stage_affine[u][2 * part], kb));\n            const float bias = __builtin_bit_cast(float, stage_word(stage_affine[u][2 * part + 1], kb));',1)
    output=ROOT/'experiments/q2-down-register-stage-draft.inc'
    assert not output.exists();output.write_text(s)
    prep=ROOT/'evidence/q2-down-register-stage-draft-preparation';prep.mkdir(exist_ok=True)
    wrapper='''// SPDX-License-Identifier: MIT
// Compiler-only probe. No host executable or device run.
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-down-register-stage-draft.inc"
void CompileQ2RegisterStageDraft(const void* w, const __half* x, const int* tiles,
    const int* bounds, const int* slots, __half* out, const float* inverse,
    hipStream_t stream) {
  hipLaunchKernelGGL((RoutedQ2RegisterStageDraftKernel<WeightType::kQ2_K,128,48,2,false,false,true>),
      dim3(20,1),dim3(256),0,stream,w,x,tiles,bounds,slots,slots,nullptr,
      reinterpret_cast<float*>(out),nullptr,2560,640,inverse);
}
}
'''
    (prep/'probe.hip').write_text(wrapper)
    receipt=dict(schema='synapse-lie.q2-down-register-stage-draft.v1',parent_manifest=PARENT,
        parent_manifest_sha256=sha(ROOT/PARENT),parent_source=manifest['source'],
        parent_include=relative,parent_include_sha256=sha(path),candidate_include=str(output.relative_to(ROOT)),
        candidate_include_sha256=sha(output),active_shape=dict(BM=128,BN=48,BK=2,m=2560,k=640),
        expected_lds_bytes=[18560,8192],wave_count=8,arithmetic='Original F32 affine, half palette, ordered WMMA, inverse F32 product and F16 storage unchanged in source',
        mechanism='Remove wave-private codes and F32-affine LDS; preserve activation and output LDS; cross-half-wave register exchange',
        gpu_run=False,model_measured=False,numerical_qualification=False,goal_met=False)
    with (ROOT/'config/q2-down-register-stage-draft.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt))
if __name__=='__main__':main()
