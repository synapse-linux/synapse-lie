#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Emit the consumer's F16 norm alongside the unchanged F32 HC norm."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
OUT = ROOT / '.deps/gufo-q2-bench-hc-norm-half'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source differs from measured checkpoint: ' + before[:80])
    return source.replace(before, after)


def preserve_rounding(body):
    # The measured gfx1151 baseline accumulates w*w, then y*y, z*z, x*x.
    body = once(body,
        '      const float sq =\n'
        '          v[c].x * v[c].x + v[c].y * v[c].y + v[c].z * v[c].z + v[c].w * v[c].w;',
        '      // Retain the measured F32 sum-of-squares contraction order.\n'
        '      const float sq = __fmaf_rn(v[c].x, v[c].x,\n'
        '          __fmaf_rn(v[c].z, v[c].z,\n'
        '              __fmaf_rn(v[c].y, v[c].y, __fmul_rn(v[c].w, v[c].w))));')
    return once(body, '      *reinterpret_cast<float4*>(out) = n;',
        '      // Anchor F32 rounding before conversion. Without this barrier\n'
        '      // fast-math can emit a mixed FMA rounding directly into F16.\n'
        '      asm("" : "+v"(n.x), "+v"(n.y), "+v"(n.z), "+v"(n.w));\n'
        '      *reinterpret_cast<float4*>(out) = n;')


def main():
    shutil.copytree(BASE, OUT)
    path = OUT / REL / 'kernels.hip.cpp'
    source = path.read_text()
    start = source.index('template<typename XnT>\n__global__ void HcCombineVec4Kernel')
    end = source.index('\n/// F32 MoE epilogue in LDS', start)
    original = source[start:end]
    body = '''/// Preserve the F32 combine and publish its F16 consumer input in the
/// same pass. The F32 norm remains available to mixing and inject products.
__global__ void HcCombineF32HalfKernel(float* res, const float* block_out,
    const float* inject, std::uint32_t inject_parts, const float* gamma,
    float* xn, __half* norm_half, std::uint32_t hidden, float eps) {
''' + original[original.index('  constexpr std::uint32_t kStreams = 4;'):]
    body = once(body, '  const std::size_t num_blocks = hc_dim / 32;\n', '')
    output_start = body.index('      XnT* out = xn +')
    emit = '''      float* out = xn + (static_cast<std::size_t>(t) * hc_dim) + e;
      *reinterpret_cast<float4*>(out) = n;
      __half* half = norm_half + (static_cast<std::size_t>(t) * hc_dim) + e;
      *reinterpret_cast<__half2*>(half) = __floats2half2_rn(n.x, n.y);
      *reinterpret_cast<__half2*>(half + 2) = __floats2half2_rn(n.z, n.w);
    }
  }
}
'''
    body = preserve_rounding(body[:output_start] + emit)
    source = source[:end] + '\n' + body + source[end:]
    start = source.index('__global__ void HcCombineMoeF32Kernel(')
    end = source.index('\n/// HcCombineVec4Kernel<__half>', start)
    body = source[start:end]
    body = once(body, 'float* xn, std::uint32_t hidden, float eps) {',
                     'float* xn, std::uint32_t hidden, float eps, __half* norm_half) {')
    body = once(body, '      *reinterpret_cast<float4*>(out) = n;',
        '''      *reinterpret_cast<float4*>(out) = n;
      if (norm_half != nullptr) {
        __half* half = norm_half + (static_cast<std::size_t>(t) * hc_dim) + e;
        *reinterpret_cast<__half2*>(half) = __floats2half2_rn(n.x, n.y);
        *reinterpret_cast<__half2*>(half + 2) = __floats2half2_rn(n.z, n.w);
      }''')
    source = source[:start] + preserve_rounding(body) + source[end:]
    start = source.index('bool HcCombineMoeF32(')
    end = source.index('\nbool HcCombineMoeF16(', start)
    body = source[start:end]
    body = once(body, 'hipStream_t stream) {', 'hipStream_t stream, __half* norm_half) {')
    body = once(body, '                     eps);', '                     eps, norm_half);')
    source = source[:start] + body + source[end:]
    signature = '''bool HcCombineF32Half(float* res, const float* block_out,
    const float* inject, std::uint32_t inject_parts, const float* gamma,
    float* xn, __half* norm_half, std::uint32_t n_tokens,
    std::uint32_t hidden, std::uint32_t streams, float eps, hipStream_t stream)'''
    function = signature + ''' {
  if (n_tokens < 16 || hidden != 2560 || streams != 4 || inject_parts == 0 ||
      res == nullptr || block_out == nullptr || inject == nullptr ||
      gamma == nullptr || xn == nullptr || norm_half == nullptr) {
    return false;
  }
  hipLaunchKernelGGL(HcCombineF32HalfKernel, dim3(n_tokens), dim3(kThreads), 0,
      stream, res, block_out, inject, inject_parts, gamma, xn, norm_half,
      hidden, eps);
  return true;
}

'''
    source = once(source, 'bool HcCombineMoeF32(', function + 'bool HcCombineMoeF32(')
    path.write_text(source)
    path = OUT / REL / 'kernels.hpp'
    source = path.read_text()
    start = source.index('bool HcCombineMoeF32(')
    end = source.index('\n/// HcCombineF16 with the MoE', start)
    body = once(source[start:end], 'hipStream_t stream);',
                'hipStream_t stream, __half* norm_half = nullptr);')
    source = source[:start] + body + source[end:]
    source = once(source, '/// F32 MoE epilogue plus F32 HC combine',
        '/// F32 norm plus its rounded F16 copy; no new input precision.\n'
        '/// Fixed hidden=2560, streams=4, n_tokens>=16, gamma required.\n'
        '/// F32 and F16 outputs must be distinct; refuses before any launch.\n'
        + signature + ';\n\n/// F32 MoE epilogue plus F32 HC combine')
    source = once(source, '/// Uses one shared row, no global scratch and no F16 narrowing.',
        '/// Uses one shared row and no global scratch. Optional norm_half\n'
        '/// receives the rounded F16 copy when gamma is non-null; otherwise\n'
        '/// neither normalized output is written. Outputs must be distinct.')
    path.write_text(source)
    path = OUT / REL / 'executor.cpp'
    source = path.read_text()
    anchor = '  xn_half_ = wide_mixer_ && MatrixRows(n_tokens) && gamma != nullptr;'
    source = once(source, anchor, anchor + '''
  // Keep F32 xn for the Q2 mixer and inject path, while producing exactly
  // the narrowed copy its original-F16 down projection already consumes.
  const bool produce_half = !wide_mixer_ && n_tokens >= 96 &&
      n_tokens <= options_.max_batch && gamma != nullptr &&
      c.hc_count == 4 && c.hidden_size == 2560 &&
      c.HcDim() <= model_->max_half_cols();
  auto* norm_half = produce_half ? static_cast<__half*>(s_.x_half) : nullptr;
  const auto publish_half = [&]() {
    half_src_ = s_.xn;
    half_rows_ = n_tokens;
    half_cols_ = c.HcDim();
    half_bf16_ = false;
  };
  if (produce_half) {
    // The producer overwrites x_half; invalidate its old identity first.
    half_src_ = nullptr;
  }''')
    start = source.index('  if (moe_f32_pending_) {')
    end = source.index('  if (moe_pending_) {', start)
    body = source[start:end]
    body = once(body, '                        stream_)) {\n      return;',
        '                        stream_, norm_half)) {\n'
        '      if (produce_half) publish_half();\n      return;')
    source = source[:start] + body + source[end:]
    source = once(source,
        '  HcCombine(res, s_.block_out, s_.inject, inject_parts_, gamma, s_.xn, n_tokens,',
        '''  if (produce_half && HcCombineF32Half(res, s_.block_out, s_.inject,
          inject_parts_, gamma, s_.xn, norm_half, n_tokens, c.hidden_size,
          c.hc_count, c.rms_eps, stream_)) {
    publish_half();
    return;
  }
  HcCombine(res, s_.block_out, s_.inject, inject_parts_, gamma, s_.xn, n_tokens,''')
    source = once(source,
        '    xn_half_ = false;\n    RmsNormRows(res, m.norm.f32(), s_.xn,',
        '    xn_half_ = false;\n'
        '    // Recomputing xn invalidates every previously published copy.\n'
        '    half_src_ = nullptr;\n'
        '    q8t_src_ = nullptr;\n'
        '    RmsNormRows(res, m.norm.f32(), s_.xn,')
    path.write_text(source)
    names = ['executor.cpp', 'kernels.hip.cpp', 'kernels.hpp']
    subprocess.run(['clang-format', '-i', *[str(OUT / REL / name) for name in names]], check=True)
    changed = [str(p.relative_to(BASE)) for p in sorted(BASE.rglob('*')) if p.is_file()
               and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes()]
    patch = ''.join(''.join(difflib.unified_diff((BASE / name).read_text().splitlines(True),
                    (OUT / name).read_text().splitlines(True), fromfile='a/' + name,
                    tofile='b/' + name)) for name in changed)
    path = ROOT / 'experiments/q2-hc-norm-half.patch'; path.write_text(patch)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = {'scope': 'Isolated source identity only; no GPU evidence',
              'base': 'measured F32 MoE/HC fusion',
              'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
              'file_count': sum(p.is_file() for p in BASE.rglob('*')),
              'changed_files': {n: {'base_sha256': sha(BASE/n), 'candidate_sha256': sha(OUT/n)} for n in changed},
              'patch_sha256': sha(path), 'generator': str(Path(__file__).relative_to(ROOT))}
    (ROOT / 'config/q2-hc-norm-half-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Prepared fused F32/F16 norm:', changed)


if __name__ == '__main__':
    main()
