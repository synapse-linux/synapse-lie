#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Avoid the HC F32 norm store; reconstruct its rounded values in consumers."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
DONOR = ROOT / '.deps/gufo-q2-bench-hc-sequence'
OUT = ROOT / '.deps/gufo-q2-bench-hc-deferred-norm'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source anchor: ' + before[:100])
    return text.replace(before, after)


def section(text, start, end):
    at = text.index(start)
    return text[at:text.index(end, at)]


HELPER = '''// Match the measured producer ISA: round gamma*scale before multiplying
// by the residual. Keep the F32 boundary before the consumer's FMA or F16.
__device__ __forceinline__ float4 DeferredHcNormValue(
    float4 residual, float scale, float4 gamma) {
  float4 n{__fmul_rn(residual.x, __fmul_rn(scale, gamma.x)),
           __fmul_rn(residual.y, __fmul_rn(scale, gamma.y)),
           __fmul_rn(residual.z, __fmul_rn(scale, gamma.z)),
           __fmul_rn(residual.w, __fmul_rn(scale, gamma.w))};
  asm("" : "+v"(n.x), "+v"(n.y), "+v"(n.z), "+v"(n.w));
  return n;
}

__device__ __forceinline__ float4 LoadDeferredHcNorm(
    const float* residual, const float* scales, const float* gamma,
    std::size_t token, unsigned stream, std::size_t hidden, std::size_t h) {
  return DeferredHcNormValue(Load4(residual + (token * 4 + stream) * hidden + h),
      scales[token * 4 + stream], Load4(gamma + stream * hidden + h));
}

'''

RECONSTRUCT = '''__global__ void ReconstructHcNormKernel(
    const float* residual, const float* scales, const float* gamma,
    float* out, std::size_t count) {
  const std::size_t i = (std::size_t(blockIdx.x) * blockDim.x + threadIdx.x) * 4;
  if (i >= count) return;
  constexpr std::size_t hidden = 2560;
  const std::size_t token = i / (hidden * 4);
  const unsigned stream = (i / hidden) % 4;
  const std::size_t h = i % hidden;
  *reinterpret_cast<float4*>(out + i) =
      LoadDeferredHcNorm(residual, scales, gamma, token, stream, hidden, h);
}

'''

RECONSTRUCT_API = '''bool ReconstructHcNorm(const float* residual, const float* scales,
    const float* gamma, float* out, std::uint32_t tokens, hipStream_t stream) {
  if (tokens == 0 || residual == nullptr || scales == nullptr ||
      gamma == nullptr || out == nullptr) return false;
  const std::size_t count = std::size_t(tokens) * 10240;
  hipLaunchKernelGGL(ReconstructHcNormKernel, dim3((count / 4 + 255) / 256),
      dim3(kThreads), 0, stream, residual, scales, gamma, out, count);
  return true;
}

'''


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL / 'kernels.hip.cpp') != 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5':
        raise ValueError('Retained source differs')
    if sha(DONOR / REL / 'kernels.hip.cpp') != 'b832e97c62d682874acca9dad06adaa10787b77c823debe634694b9516953194':
        raise ValueError('Measured paired producer differs')
    original = (BASE / REL / 'kernels.hip.cpp').read_text()
    donor = (DONOR / REL / 'kernels.hip.cpp').read_text()
    source = once(original, 'template<typename XnT, bool kMix = true>\n',
                  HELPER + 'template<typename XnT, bool kMix = true>\n')
    producers, wrappers = [], []
    for old, new, kernel_end, wrapper_end in [
        ('HcCombineF32Half', 'HcCombineDeferredNorm', '\n/// F32 MoE epilogue', '\nbool HcCombineMoeF32('),
        ('HcCombineMoeF32Half', 'HcCombineMoeDeferredNorm', '\n/// HcCombineVec4Kernel<__half>', '\nbool HcCombineMoeF16('),
    ]:
        body = section(donor, '__global__ void ' + old + 'Kernel(', kernel_end)
        body = body.replace(old, new)
        body = re.sub(r'\bxn\b', 'norm_scales', body)
        body = once(body,
            '    scale[k] = rsqrtf(total / static_cast<float>(hidden) + eps);\n  }',
            '    scale[k] = rsqrtf(total / static_cast<float>(hidden) + eps);\n  }\n'
            '  if (threadIdx.x == 0) {\n'
            '    *reinterpret_cast<float4*>(norm_scales + std::size_t(t) * 4) =\n'
            '        float4{scale[0], scale[1], scale[2], scale[3]};\n  }')
        body, count = re.subn(r'      n = float4\{v\[c\]\.x.*?\};',
            '      n = DeferredHcNormValue(v[c], sc, gm);', body, flags=re.S)
        if count != 1:
            raise ValueError('Unexpected normalized output expression')
        body = once(body, '      float* out = norm_scales + (static_cast<std::size_t>(t) * hc_dim) + e;\n', '')
        body = once(body, '      *reinterpret_cast<float4*>(out) = n;\n', '')
        producers.append(body)
        wrapper = section(donor, 'bool ' + old + '(', wrapper_end).replace(old, new)
        wrappers.append(re.sub(r'\bxn\b', 'norm_scales', wrapper))
    # Retain all original controls verbatim. Additional kernels are isolated
    # experimental numerical ports; the runtime dispatch is not changed yet.
    source = once(source, '/// F32 MoE epilogue in LDS',
                  '\n'.join(producers) + '\n' + RECONSTRUCT + '/// F32 MoE epilogue in LDS')
    inject = section(original, 'template<typename XnT, bool kMix = true>',
                     '\n/// The W8A8 GEMM')
    inject = inject.replace('HcMixEpilogueVec4Kernel', 'HcInjectDeferredNormKernel')
    inject = once(inject, 'std::uint32_t hidden) {',
                  'std::uint32_t hidden, const float* norm_scales, const float* norm_gamma) {\n'
                  '  static_assert(!kMix && std::is_same_v<XnT, float>);')
    inject = once(inject,
        '    v[s] = i < hidden ? Load4(x + idx) : float4{0.0F, 0.0F, 0.0F, 0.0F};',
        '    v[s] = i < hidden ? LoadDeferredHcNorm(xn, norm_scales, norm_gamma,\n'
        '        t, s, hidden, i) : float4{0.0F, 0.0F, 0.0F, 0.0F};')
    source = once(source, '\n/// The W8A8 GEMM', '\n' + inject + '\n/// The W8A8 GEMM')
    source = once(source, 'bool HcCombineMoeF32(', ''.join(wrappers) + RECONSTRUCT_API + 'bool HcCombineMoeF32(')
    # Copy only the selected HC-up specialization's common stage and epilogue.
    # The attention and generic dense epilogues are not part of this port.
    dense = section(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,',
                    '\nbool AttentionF16Gemm(')
    body = dense[dense.index('  static_assert(WM * WN'):]
    body = body[:body.index('  if constexpr (kAttention) {')] + body[body.index('  if constexpr (kHcMix) {'):]
    body = body[:body.index('  // Transpose the result')] + '}\n'
    body = once(body, '            const float4 v = Load4(xn + token * m + stream * hidden + h);',
        '            const float4 v = LoadDeferredHcNorm(xn, norm_scales, norm_gamma,\n'
        '                token, stream, hidden, h);')
    signature = '''__launch_bounds__(512) __global__ void HcMixDeferredNormKernel(
    const void* __restrict__ w, const __half* __restrict__ x,
    float* __restrict__ y, std::size_t batch, std::size_t m, std::size_t k,
    const float* xn, __half* mixed_half, void* mixed_q8,
    const float* norm_scales, const float* norm_gamma) {
  constexpr int BM = 256, BN = 128, BK = 1, WM = 4, WN = 2, kRowGroup = 8;
  constexpr bool kHcMix = true, kSsmConv = false, kAttention = false,
                 kHalfWeights = true, kHcUpChains = true;
'''
    source = once(source, '\nbool AttentionF16Gemm(', '\n' + signature + body + '\nbool AttentionF16Gemm(')
    mix = section(original, 'bool HcMixRawF16Gemm(', '\nbool UnquantizedF16Gemm(')
    mix = mix.replace('HcMixRawF16Gemm', 'HcMixDeferredNorm')
    mix = once(mix, 'hipStream_t stream) {',
        'hipStream_t stream, const float* norm_scales, const float* norm_gamma) {\n'
        '  if (norm_scales == nullptr || norm_gamma == nullptr) return false;')
    mix = once(mix,
        '  hipLaunchKernelGGL((DenseF16GEMMKernel<256, 128, 1, 4, 2, 8, true, false,\n'
        '                                         false, true, true>),',
        '  hipLaunchKernelGGL(HcMixDeferredNormKernel,')
    mix = once(mix, '4 * hidden, rank, xn, mixed_half, nullptr);',
        '4 * hidden, rank, xn, mixed_half, nullptr, norm_scales, norm_gamma);')
    mix = mix.replace('HcMixEpilogueVec4Kernel<float, false>', 'HcInjectDeferredNormKernel<float, false>')
    mix = once(mix, '                       nullptr, inject, hidden);',
        '                       nullptr, inject, hidden, norm_scales, norm_gamma);')
    mix = mix.replace('// Original half weights and the existing F32 normalized streams. Interleave',
                      '// Original half weights and reconstructed F32 normalized streams. Interleave')
    source = once(source, '\nbool UnquantizedF16Gemm(', '\n' + mix + '\nbool UnquantizedF16Gemm(')
    declarations = '''/// Experimental deferred norm: residual [tokens][4][2560] and four
/// F32 scales per token retain the original norm without storing its F32 rows.
/// Gamma, scales and residual must survive both mix and inject consumers.
/// All buffers are disjoint except an explicitly reused consumer half output.
'''
    for wrapper in wrappers + [RECONSTRUCT_API, mix]:
        declarations += wrapper[:wrapper.index('{')].rstrip() + ';\n\n'
    shutil.copytree(BASE, OUT)
    (OUT / REL / 'kernels.hip.cpp').write_text(source)
    header = (BASE / REL / 'kernels.hpp').read_text()
    header = once(header, '}  // namespace gufo::models::qwen38_flash_next::rocm',
                  declarations + '}  // namespace gufo::models::qwen38_flash_next::rocm')
    (OUT / REL / 'kernels.hpp').write_text(header)
    changed = [str(REL / n) for n in ('kernels.hip.cpp', 'kernels.hpp')]
    subprocess.run(['clang-format', '-i', *changed], cwd=OUT, check=True)
    patch = ROOT / 'experiments/q2-hc-deferred-norm.patch'
    patch.write_text(''.join(''.join(difflib.unified_diff(
        (BASE / n).read_text().splitlines(True), (OUT / n).read_text().splitlines(True),
        fromfile='a/' + n, tofile='b/' + n)) for n in changed))
    report = {'scope': 'Isolated numerical experiment; executor dispatch unchanged',
        'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        'base': str(BASE.relative_to(ROOT)), 'donor': str(DONOR.relative_to(ROOT)),
        'donor_kernel_sha256': sha(DONOR / REL / 'kernels.hip.cpp'),
        'output': str(OUT.relative_to(ROOT)), 'patch_sha256': sha(patch),
        'changed_files': {n: {'base_sha256': sha(BASE / n), 'candidate_sha256': sha(OUT / n)} for n in changed},
        'arithmetic': 'Measured gamma*scale F32 rounding, then residual multiplication; exactness unproven',
        'storage': 'Four scales per token plus original F16 down input; no F32 norm write',
        'promotion': False, 'model_wired': False}
    (ROOT / 'config/q2-hc-deferred-norm-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
