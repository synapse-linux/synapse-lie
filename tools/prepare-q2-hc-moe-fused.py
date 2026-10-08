#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an isolated F32 MoE/HC fusion without changing the norm reduction."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-vec-exact'
OUT = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source differs from measured checkpoint: ' + before[:80])
    return source.replace(before, after)


def main():
    shutil.copytree(BASE, OUT)
    path = OUT / REL / 'kernels.hip.cpp'
    source = path.read_text()
    start = source.index('template<typename XnT>\n__global__ void HcCombineVec4Kernel')
    end = source.index('\n/// HcCombineVec4Kernel<__half>', start)
    body = source[start:end]
    header_end = body.index('  constexpr std::uint32_t kStreams = 4;')
    body = '''/// F32 MoE epilogue in LDS, followed by the original F32 combine's
/// lane/chunk mapping and reduction tree. A shared row avoids reading each
/// expert four times without materializing block_out in global memory.
__global__ void HcCombineMoeF32Kernel(
    float* res, const float* expert_out, const float* weights,
    const float* shared_out, const float* gate, std::uint32_t gate_stride,
    std::uint32_t used, const float* inject, std::uint32_t inject_parts,
    const float* gamma, float* xn, std::uint32_t hidden, float eps) {
''' + body[header_end:]
    body = once(body,
        '  const float* src = block_out + static_cast<std::size_t>(t) * hidden;',
        '''  __shared__ __attribute__((aligned(16))) float moe[2560];
  const float g = SigmoidF(gate[static_cast<std::size_t>(t) * gate_stride]);
  for (std::uint32_t i = threadIdx.x * 4; i < hidden; i += kThreads * 4) {
    float4 acc{0.0F, 0.0F, 0.0F, 0.0F};
    const float* rows = expert_out + static_cast<std::size_t>(t) * used * hidden + i;
    for (std::uint32_t s = 0; s < used; ++s) {
      const float wk = weights[t * used + s];
      const float4 value = Load4(rows + static_cast<std::size_t>(s) * hidden);
      // Keep the reference epilogue's rounded expert accumulation separate
      // from the residual update, despite fast-math across this fusion.
      acc.x = __fmaf_rn(wk, value.x, acc.x);
      acc.y = __fmaf_rn(wk, value.y, acc.y);
      acc.z = __fmaf_rn(wk, value.z, acc.z);
      acc.w = __fmaf_rn(wk, value.w, acc.w);
    }
    const float4 sh = *reinterpret_cast<const float4*>(
        shared_out + static_cast<std::size_t>(t) * hidden + i);
    acc.x = __fmaf_rn(g, sh.x, acc.x);
    acc.y = __fmaf_rn(g, sh.y, acc.y);
    acc.z = __fmaf_rn(g, sh.z, acc.z);
    acc.w = __fmaf_rn(g, sh.w, acc.w);
    *reinterpret_cast<float4*>(moe + i) = acc;
  }
  // All lanes finish the shared row before any stream reads it.
  __syncthreads();
  const float* src = moe;''')
    # F32-only output. Leave residual, sum-of-squares, WaveSum and scaling
    # expressions verbatim, including the original per-thread stream mapping.
    body = once(body, '  const std::size_t num_blocks = hc_dim / 32;\n', '')
    output_start = body.index('      XnT* out = xn +')
    body = body[:output_start] + '''      float* out = xn + (static_cast<std::size_t>(t) * hc_dim) + e;
      *reinterpret_cast<float4*>(out) = n;
    }
  }
}
'''
    source = source[:end] + '\n' + body + source[end:]
    signature = '''bool HcCombineMoeF32(float* res, const float* expert_out,
                     const float* weights, const float* shared_out,
                     const float* gate, std::uint32_t gate_stride,
                     std::uint32_t used, const float* inject,
                     std::uint32_t inject_parts, const float* gamma, float* xn,
                     std::uint32_t n_tokens, std::uint32_t hidden,
                     std::uint32_t streams, float eps, hipStream_t stream)'''
    function = signature + ''' {
  if (n_tokens < 16 || hidden != 2560 || streams != 4 || used == 0 ||
      used > 32 || gate_stride == 0 || inject_parts == 0 || res == nullptr ||
      expert_out == nullptr || weights == nullptr || shared_out == nullptr ||
      gate == nullptr || inject == nullptr || (gamma != nullptr && xn == nullptr)) {
    return false;
  }
  hipLaunchKernelGGL(HcCombineMoeF32Kernel, dim3(n_tokens), dim3(kThreads), 0,
      stream, res, expert_out, weights, shared_out, gate, gate_stride, used,
      inject, inject_parts, gamma, xn, hidden, eps);
  return true;
}

'''
    source = once(source, 'bool HcCombineMoeF16(', function + 'bool HcCombineMoeF16(')
    path.write_text(source)
    path = OUT / REL / 'kernels.hpp'
    source = path.read_text()
    source = once(source, '/// HcCombineF16 with the MoE epilogue fused in:',
        '/// F32 MoE epilogue plus F32 HC combine with the separate route\'s\n'
        '/// norm reduction order. Four streams, hidden=2560, n_tokens>=16,\n'
        '/// 1..32 experts. Gamma may be null (residual only); otherwise xn\n'
        '/// is required. Unsupported inputs return false before any launch.\n'
        '/// Uses one shared row, no global scratch and no F16 narrowing.\n'
        + signature + ';\n\n/// HcCombineF16 with the MoE epilogue fused in:')
    path.write_text(source)
    path = OUT / REL / 'executor.hpp'
    source = once(path.read_text(), '  mutable bool moe_pending_{false};',
        '  mutable bool moe_pending_{false};\n'
        '  /// Original Q2 F32 expert rows await the immediate combine.\n'
        '  mutable bool moe_f32_pending_{false};')
    path.write_text(source)
    path = OUT / REL / 'executor.cpp'
    source = path.read_text()
    source = once(source, '  if (moe_pending_) {', '''  if (moe_f32_pending_) {
    moe_f32_pending_ = false;
    if (!xn_half_ &&
        HcCombineMoeF32(res, s_.down_e, s_.weights, s_.shexp_out,
            s_.router + c.num_experts, c.num_experts + 1, c.num_experts_used,
            s_.inject, inject_parts_, gamma, s_.xn, n_tokens, c.hidden_size,
            c.hc_count, c.rms_eps, stream_)) {
      return;
    }
    MoeEpilogueVec4(s_.down_e, s_.weights, s_.shexp_out,
        s_.router + c.num_experts, c.num_experts + 1, s_.block_out,
        n_tokens, c.num_experts_used, c.hidden_size, stream_);
  }
  if (moe_pending_) {''')
    source = once(source,
        '  } else if (MatrixRows(n_tokens)) {\n    MoeEpilogueVec4(s_.down_e,',
        '''  } else if (iq2_wmma && !wide_mixer_ && n_tokens >= 16 &&
             c.hc_count == 4 && c.num_experts_used > 0 &&
             c.num_experts_used <= 32 && out == s_.block_out) {
    // Consumed by Combine immediately, before any scratch can be reused.
    // Separate from the existing UD pending flag: down_e is F32 here.
    moe_f32_pending_ = true;
  } else if (MatrixRows(n_tokens)) {
    MoeEpilogueVec4(s_.down_e,''')
    path.write_text(source)
    files = ['executor.cpp', 'executor.hpp', 'kernels.hip.cpp', 'kernels.hpp']
    subprocess.run(['clang-format', '-i', *[str(OUT / REL / f) for f in files]], check=True)
    changed = [str(p.relative_to(BASE)) for p in sorted(BASE.rglob('*'))
               if p.is_file() and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    patch = ''.join(''.join(difflib.unified_diff((BASE / name).read_text().splitlines(True),
                    (OUT / name).read_text().splitlines(True), fromfile='a/' + name,
                    tofile='b/' + name)) for name in changed)
    patch_path = ROOT / 'experiments/q2-hc-moe-fused.patch'
    patch_path.write_text(patch)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = {'scope': 'Isolated source identity; no runtime evidence',
              'base': 'measured byte-exact HC up vector source',
              'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
              'file_count': sum(p.is_file() for p in BASE.rglob('*')),
              'changed_files': {name: {'base_sha256': sha(BASE / name),
                                       'candidate_sha256': sha(OUT / name)} for name in changed},
              'patch_sha256': sha(patch_path), 'generator': str(Path(__file__).relative_to(ROOT))}
    (ROOT / 'config/q2-hc-moe-fused-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared F32 MoE/HC fusion:', changed)


if __name__ == '__main__':
    main()
