#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate isolated HC mix/injection compiler probes from the retained provider."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def inject_epilogue(body):
    old = '          float4 value{0.0F, 0.0F, 0.0F, 0.0F};'
    assert body.count(old) == 1
    body = body.replace(old, old+'\n          float dot[4] = {0.0F, 0.0F, 0.0F, 0.0F};')
    anchor = '            // Preserve the separate mixer\'s F32 FMA rounding.'
    assert body.count(anchor) == 1
    # Saved parent ISA has four first-product MULs followed by sixty FMAs.
    # Keep each output's sixteen products in stream/component order.
    extra = '''            if (inject_w != nullptr) {
#pragma unroll
              for (unsigned o = 0; o < 4; ++o) {
                const float4 q = Load4(inject_w + o * m + stream * hidden + h);
                if (stream == 0)
                  dot[o] = __fmul_rn(q.x, v.x);
                else
                  dot[o] = __fmaf_rn(q.x, v.x, dot[o]);
                dot[o] = __fmaf_rn(q.y, v.y, dot[o]);
                dot[o] = __fmaf_rn(q.z, v.z, dot[o]);
                dot[o] = __fmaf_rn(q.w, v.w, dot[o]);
              }
            }
'''
    body = body.replace(anchor, extra+anchor)
    anchor = '          value.x *= 0.25F;'
    assert body.count(anchor) == 1
    body = body.replace(anchor, '''          if (inject_w != nullptr) {
            // Compact [token][hidden/4][four outputs], in disjoint dead scratch.
            *reinterpret_cast<float4*>(injection_dots + token * hidden + h) =
                float4{dot[0], dot[1], dot[2], dot[3]};
          }
'''+anchor)
    return body


REDUCER = '''// SPDX-License-Identifier: MIT
// Numerical compiler probe derived from the retained official Gufo provider.
// No production selector, executor lifetime change or runtime acceptance.
__global__ void HcInjectReuseDraftReduceKernel(const float* dots, float* inject,
                                              std::uint32_t hidden) {
  const std::uint32_t t = blockIdx.x;
  const std::uint32_t i = (blockIdx.y * blockDim.x + threadIdx.x) * 4;
  const float4 v = i < hidden ? Load4(dots + std::size_t(t) * hidden + i)
                              : float4{0.0F, 0.0F, 0.0F, 0.0F};
  const float dot[4] = {v.x, v.y, v.z, v.w};
  __shared__ float partial[4][kThreads / 32];
  const std::uint32_t lane = threadIdx.x % warpSize;
  const std::uint32_t wave = threadIdx.x / warpSize;
#pragma unroll
  for (std::uint32_t o = 0; o < 4; ++o) {
    const float sum = WaveSum(dot[o]);
    if (lane == 0) partial[o][wave] = sum;
  }
  __syncthreads();
  if (threadIdx.x < 4) {
    float total = 0.0F;
    for (std::uint32_t w = 0; w < blockDim.x / warpSize; ++w)
      total += partial[threadIdx.x][w];
    inject[(std::size_t(t) * 4 + threadIdx.x) * gridDim.y + blockIdx.y] = total;
  }
}

'''


WRAPPERS = '''
// These private launchers exist only to instantiate the compiler probes.
// The intended production workspace is down_e after its previous combine,
// before the next MoE; the executor has not adopted this contract.
bool HcInjectReuseDraftRaw(const void* up, const __half* low_rank,
                          const float* xn, const float* inject_w, float* mixed,
                          __half* mixed_half, void* mixed_q8, float* dots,
                          std::size_t dot_bytes, float* inject,
                          std::uint32_t n_tokens, hipStream_t stream) {
  constexpr unsigned hidden = 2560, rank = 320;
  if (n_tokens < 96 || !up || !low_rank || !xn || !inject_w || !mixed ||
      !dots || !inject || dot_bytes < std::size_t(n_tokens) * hidden * sizeof(float))
    return false;
  hipLaunchKernelGGL((HcInjectReuseDraftRawKernel<256,128,1,4,2,8,true,false,
                                                false,true,true>),
      dim3((n_tokens+127)/128,4*hidden/256), dim3(512), 0, stream,
      up,low_rank,mixed,n_tokens,4*hidden,rank,inject_w,dots,xn,mixed_half,mixed_q8);
  if (hipGetLastError() != hipSuccess) return false;
  hipLaunchKernelGGL(HcInjectReuseDraftReduceKernel,
      dim3(n_tokens,HcInjectPartsVec4(hidden)),dim3(kThreads),0,stream,
      dots,inject,hidden);
  return hipGetLastError() == hipSuccess;
}

bool HcInjectReuseDraftDeferred(const void* up, const __half* low_rank,
                               const float* residual, const float* scales,
                               const float* gamma, const float* inject_w,
                               float* mixed, __half* mixed_half, float* dots,
                               std::size_t dot_bytes, float* inject,
                               std::uint32_t n_tokens, hipStream_t stream) {
  constexpr unsigned hidden = 2560, rank = 320;
  if (n_tokens < 96 || !up || !low_rank || !residual || !scales || !gamma ||
      !inject_w || !mixed || !dots || !inject ||
      dot_bytes < std::size_t(n_tokens) * hidden * sizeof(float))
    return false;
  hipLaunchKernelGGL(HcInjectReuseDraftDeferredKernel,
      dim3((n_tokens+127)/128,4*hidden/256),dim3(512),0,stream,
      up,low_rank,mixed,n_tokens,4*hidden,rank,residual,mixed_half,nullptr,
      scales,gamma,inject_w,dots);
  if (hipGetLastError() != hipSuccess) return false;
  hipLaunchKernelGGL(HcInjectReuseDraftReduceKernel,
      dim3(n_tokens,HcInjectPartsVec4(hidden)),dim3(kThreads),0,stream,
      dots,inject,hidden);
  return hipGetLastError() == hipSuccess;
}
'''


def main():
    parent_path = ROOT/'config/q2-ssm-fixed-bounds-source.json'
    manifest = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/manifest['source']
    assert {str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()} == manifest['files']
    original = (base/REL/'kernels.hip.cpp').read_text()
    raw = function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,',
                   'bool AttentionF16Gemm(')
    assert raw.count('void DenseF16GEMMKernel(') == 1
    raw = raw.replace('void DenseF16GEMMKernel(', 'void HcInjectReuseDraftRawKernel(')
    signature = '    std::size_t runtime_k,\n'
    assert raw.count(signature) == 1
    raw = raw.replace(signature, signature+'    const float* inject_w, float* injection_dots,\n')
    raw = inject_epilogue(raw)
    deferred_source = (base/REL/'q2_hc_moe_deferred.inc').read_text()
    deferred = function(deferred_source, '__launch_bounds__(512) __global__ void HcMixDeferredNormKernel(',
                        'bool HcMixDeferredNorm(')
    deferred = deferred.replace('void HcMixDeferredNormKernel(', 'void HcInjectReuseDraftDeferredKernel(')
    signature = '    const float* norm_scales, const float* norm_gamma) {'
    assert deferred.count(signature) == 1
    deferred = deferred.replace(signature, '    const float* norm_scales, const float* norm_gamma,\n'
        '    const float* inject_w, float* injection_dots) {')
    deferred = inject_epilogue(deferred)
    out = ROOT/'experiments/q2-hc-inject-reuse-draft.inc'
    with out.open('x') as f:
        f.write(REDUCER+raw+deferred+WRAPPERS)
    prep = ROOT/'evidence/q2-hc-inject-reuse-draft-preparation'
    prep.mkdir(exist_ok=False)
    wrapper = prep/'probe.hip'
    wrapper.write_text('// SPDX-License-Identifier: MIT\n#include "'+str(base/REL/'kernels.hip.cpp')+'"\n'
        'namespace gufo::models::qwen38_flash_next::rocm {\n#include "'+str(out)+'"\n}\n')
    argv = json.loads((ROOT/'evidence/q2-down-register-palette-preparation/assembly-argv.json').read_text())
    argv = [('-I'+str(base)) if a.startswith('-I.deps/') else a for a in argv]
    argv[argv.index('-S')+1] = str(wrapper)
    argv[-1] = str(prep/'candidate.s')
    (prep/'assembly-argv.json').write_text(json.dumps(argv,indent=2)+'\n')
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-draft.v1',
        parent_manifest='config/q2-ssm-fixed-bounds-source.json',parent_manifest_sha256=sha(parent_path),
        parent_provider=manifest['source'],parent_files_verified=len(manifest['files']),
        parent_numerical_sha256=sha(base/REL/'kernels.hip.cpp'),
        parent_deferred_sha256=sha(base/REL/'q2_hc_moe_deferred.inc'),
        include=str(out.relative_to(ROOT)),include_sha256=sha(out),generator_sha256=sha(Path(__file__)),
        compiler_probe=str(wrapper.relative_to(ROOT)),compiler_probe_sha256=sha(wrapper),
        fixed_geometry=dict(hidden=2560,streams=4,rank=320),
        proposed_workspace=dict(source='down_e',bytes_at_2048=2048*2560*4,
            allocation_added=False,executor_adopted=False),
        contract='Reuse each normalized float4 already read by HC mix to compute four injection dots. '
            'Preserve first MUL then15 FMA per dot and original wave/block/chunk reduction in second kernel. '
            'No reassociation or atomic summation. Rounded F32 dot storage replaces a second normalized read.',
        gates=['Complete ordinary/raw-Q8/deferred mix, half/Q8 and injection output equality including tails',
               'Complete alternating mix/inject cycle with rotated HC weights beyond32MiB',
               'Prove old down_e reader complete, separate workspace and new MoE writer ordered',
               'Original fixed2048/tg128 candidate-only model test after fresh .157 admission'],
        gpu_run=False,production_provider=False,numerical_acceptance=False,performance_measured=False,goal_met=False)
    with (ROOT/'config/q2-hc-inject-reuse-draft.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(include=report['include'],workspace_bytes=report['proposed_workspace']['bytes_at_2048'],
        GPU_run=False,production_provider=False)))


if __name__ == '__main__':
    main()
