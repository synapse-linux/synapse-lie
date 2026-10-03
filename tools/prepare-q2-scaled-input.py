#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a bounded one-plane Q2 activation-scale hypothesis, not a promotion."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-scaled-input'
DIR = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected anchor: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE/DIR/'kernels.hip.cpp') != 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5':
        raise ValueError('Retained kernel source changed')
    kernel = (BASE/DIR/'kernels.hip.cpp').read_text()
    start = kernel.index('template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    end = kernel.index('/// Compacts the routed assignments', start)
    body = kernel[start:end]
    body = once(body, 'bool kPacked = false>', 'bool kPacked = false, bool kScaled = false>')
    body = once(body, 'kType == WeightType::kQ2_K, float,',
                'kType == WeightType::kQ2_K && !kScaled, float,')
    body = once(body, '  constexpr bool kIQ2 =',
                '  constexpr bool kResidual = kQ2 && !kScaled;\n  static_assert(!kScaled || (kQ2 && !kPacked && !kPair));\n  constexpr bool kIQ2 =')
    body = once(body, '(kQ2 ? 2 : 1) * kActPlaneBytes', '(kResidual ? 2 : 1) * kActPlaneBytes')
    body = once(body, 'std::conditional_t<kQ2, float, __half>', 'std::conditional_t<kResidual, float, __half>')
    body = once(body, 'if constexpr (kQ2 && kPacked) {\n        // Eight existing',
                'if constexpr (kResidual && kPacked) {\n        // Eight existing')
    body = once(body, 'else if constexpr (kQ2) {\n        __half hi[8]',
                'else if constexpr (kResidual) {\n        __half hi[8]')
    body = body.replace('kQ2 && kPacked', 'kQ2 && (kPacked || kScaled)')
    body = once(body, 'if constexpr (kQ2)\n          s_act[kActPlaneBytes',
                'if constexpr (kResidual)\n          s_act[kActPlaneBytes')
    body = body.replace('acc_residual[kQ2 ? kWaveRowTiles : 1][kQ2 ? kTokTiles : 1]',
                        'acc_residual[kResidual ? kWaveRowTiles : 1][kResidual ? kTokTiles : 1]')
    body = once(body, 'if constexpr (kQ2)\n        acc_residual', 'if constexpr (kResidual)\n        acc_residual')
    body = once(body, 'if constexpr (kQ2) {\n#pragma unroll\n          for (int q = 0; q < 4;',
                'if constexpr (kResidual) {\n#pragma unroll\n          for (int q = 0; q < 4;')
    body = once(body, 'if constexpr (kQ2) {\n#pragma unroll\n    for (int u',
                'if constexpr (kResidual) {\n#pragma unroll\n    for (int u')
    body = once(body, '              out[o] = v;',
                '''              if constexpr (kScaled)
                out[o] = v * static_cast<const float*>(w_up)[dst];
              else
                out[o] = v;''')
    kernel = kernel[:start] + body + kernel[end:]
    kernel = once(kernel, 'template<int BN, bool kPacked = false>\nvoid LaunchRoutedQ2',
                  '#include "q2_scaled_input.inc"\n\ntemplate<int BN, bool kPacked = false>\nvoid LaunchRoutedQ2')
    header = (BASE/DIR/'kernels.hpp').read_text()
    declaration = '''// Experimental one-plane row scaling; not independent quality qualification.
bool PackQ2ScaledRows(const float*, __half*, float*, std::uint32_t, std::size_t, hipStream_t);
bool RoutedQ2ScaledGemm(const void*, const __half*, const float*, const std::int32_t*,
                       std::uint32_t, std::uint32_t, const std::int32_t*,
                       const std::int32_t*, float*, std::size_t, std::size_t, hipStream_t);
'''
    header = once(header, 'bool RoutedQ2GemmPacked(', declaration+'\nbool RoutedQ2GemmPacked(')
    executor = (BASE/DIR/'executor.cpp').read_text()
    a = executor.index('    if (!RoutedGatedIQ2GemmPacked(')
    b = executor.index('  } else if (wmma_experts)', a)
    old = executor[a:b]
    new = old.replace('RoutedGatedIQ2GemmPacked(', 'RoutedGatedIQ2Gemm(')
    new = once(new, 'reinterpret_cast<std::uint32_t*>(s_.gate_e)', 's_.gate_e')
    new = once(new, '        !RoutedQ2GemmPacked(l.ffn_down_exps.data,\n                            reinterpret_cast<const std::uint32_t*>(s_.gate_e),',
        '''        !PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                          c.expert_ff, stream_) ||
        !RoutedQ2ScaledGemm(l.ffn_down_exps.data, scaled, inverse,''')
    new = '''    // Original F32 SwiGLU feeds one scaled half plane. The unused up
    // allocation owns the compact plane and its per-slot inverse scales.
    auto* scaled = reinterpret_cast<__half*>(s_.up_e);
    auto* inverse = reinterpret_cast<float*>(scaled +
        static_cast<std::size_t>(n_tokens) * used * c.expert_ff);
''' + new
    executor = executor[:a]+new+executor[b:]
    shutil.copytree(BASE, OUT)
    for name, content in [('kernels.hip.cpp',kernel),('kernels.hpp',header),('executor.cpp',executor)]:
        (OUT/DIR/name).write_text(content)
    shutil.copyfile(ROOT/'experiments/q2_scaled_input.inc',OUT/DIR/'q2_scaled_input.inc')
    subprocess.run(['clang-format','-i',*(str(OUT/DIR/n) for n in ['kernels.hip.cpp','kernels.hpp','executor.cpp','q2_scaled_input.inc'])],check=True)
    files=sorted(p.relative_to(OUT) for p in OUT.rglob('*') if p.is_file())
    changed=[p for p in files if not (BASE/p).exists() or (BASE/p).read_bytes()!=(OUT/p).read_bytes()]
    patch=''
    for p in changed:
        old=(BASE/p).read_text().splitlines(True) if (BASE/p).exists() else []
        patch+=''.join(difflib.unified_diff(old,(OUT/p).read_text().splitlines(True),fromfile='a/'+str(p) if old else '/dev/null',tofile='b/'+str(p)))
    patch_path=ROOT/'experiments/q2-scaled-input.patch';patch_path.write_text(patch)
    report=dict(scope='Prepared arithmetic experiment; accuracy and performance unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',base=str(BASE.relative_to(ROOT)),candidate=str(OUT.relative_to(ROOT)),
        changed_files=[dict(path=str(p),base_sha256=sha(BASE/p) if (BASE/p).exists() else None,sha256=sha(OUT/p)) for p in changed],
        patch_sha256=sha(patch_path),tensor_allocation_bytes_added=0,
        activation_contract='F32 SwiGLU -> per-slot power-of-two scale -> one F16 plane -> F32 down sum -> inverse scale',
        limits='No new encoded weight format, no tolerance relaxation; exact replay not assumed')
    (ROOT/'config/q2-scaled-input-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
