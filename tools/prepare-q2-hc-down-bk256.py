#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an attributed original-F16 HC-down port; no GPU/model execution."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
KERNELS = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: '+old[:80])
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT/'config/q2-reaudit-composition-source.json'
    parent = json.loads(parent_path.read_text())['variants']['reaudit-q8-row']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured exact Q8/row provider changed')
    snapshot_path = ROOT/'evidence/external-optimization-audit-20261004/snapshot.json'
    origin = next(row for row in json.loads(snapshot_path.read_text())['snapshots']
                  if row['repository'] == 'Aristo94/GSQHalo.cpp')
    if origin['commit'] != '5fc881b114c1ea130f5df6a30a98be2f8d397de6':
        raise ValueError('Public source pin changed')
    corpus = snapshot_path.parent/'GSQHalo.cpp'
    for name in ('ggml/src/ggml-cuda/mmb.cu', 'LICENSE'):
        expected = next(f['sha256'] for f in origin['files'] if f['path'] == name)
        if sha(corpus/name) != expected:
            raise ValueError('Pinned public source changed: '+name)
    source = (corpus/'ggml/src/ggml-cuda/mmb.cu').read_text()
    start = source.index('typedef uint32_t mmb_v4u ')
    end = source.index('\n#if defined(__HIP_PLATFORM_AMD__)\n__device__ __forceinline__ float gm_mul_rn', start)
    port = source[start:end]
    first = port.index('// HC down [')
    last = port.index('template <int BM', first)
    port = port[:first] + ('// Original F16 HC weights and activations; native16-byte loads, BK256\n'
                          '// staging, one LDS buffer and direct F32 stores. No model conversion.\n') + port[last:]
    port = replace(port, '#if defined(__HIP_DEVICE_COMPILE__) && !defined(RDNA3)\n    NO_DEVICE_CODE; // WMMA kernels are RDNA3-only; the host gate keeps other devices off this path\n#else\n', '')
    port = replace(port, '\n#endif\n}', '\n}')
    port = port.replace('mmb_v4u', 'HcDownVector4').replace('mmb_frag16', 'HcDownFragment16')
    port = port.replace('mmb_hcd_kernel', 'HcDownBk256Kernel').replace('MMB_NT', '256')
    port = port.replace('v16s', 'v16h').replace('uint16_t', 'std::uint16_t').replace('uint32_t', 'std::uint32_t')
    port = port.replace('__launch_bounds__(256, 2)', '__launch_bounds__(256, 1)')
    port = replace(port, '    v8f acc[TM][TN];', '    v8f acc[TM][TN], high[TM][TN]{};')
    port = replace(port,
        'acc[i][j] = __builtin_amdgcn_wmma_f32_16x16x16_bf16_w32(b[j], a[i], acc[i][j]);',
        '{\n                    // Preserve two FP32 K16 chains, alternating within each K32 pair.\n'
        '                    if ((kk & 16) == 0)\n'
        '                        acc[i][j] = __builtin_amdgcn_wmma_f32_16x16x16_f16_w32(b[j], a[i], acc[i][j]);\n'
        '                    else\n'
        '                        high[i][j] = __builtin_amdgcn_wmma_f32_16x16x16_f16_w32(b[j], a[i], high[i][j]);\n'
        '                }')
    port = replace(port, 'D[(size_t) t * M + m] = acc[i][j][e];',
                   'D[(size_t) t * M + m] = acc[i][j][e] + high[i][j][e];')
    license_text = (corpus/'LICENSE').read_text()
    header = ('// SPDX-License-Identifier: MIT\n/*\n'+license_text.rstrip()+'\n*/\n'
              '// Adapted from Aristo94/GSQHalo.cpp, pin5fc881b114c1ea130f5df6a30a98be2f8d397de6,\n'
              '// ggml/src/ggml-cuda/mmb.cu mmb_hcd_kernel and fragment loaders.\n'
              '// LIE adaptation: original F16 operands, two K16 chains, gfx1151 only.\n'
              '// Arithmetic equivalence to hipBLASLt7526 is not asserted.\nnamespace {\n')
    wrapper = '''
}  // namespace

bool HcDownBk256F16Gemm(const void* w, const __half* x, float* out,
                       std::size_t batch, std::size_t m, std::size_t k,
                       hipStream_t stream) {
  if (!w || !x || !out || batch < 96 || batch > 2048 || m != 320 || k != 10240)
    return false;
  hipLaunchKernelGGL((HcDownBk256Kernel<64, 32, 16, 16, 256, 1>),
      dim3(5, (batch + 31) / 32), dim3(256), 0, stream,
      static_cast<const std::uint16_t*>(w),
      reinterpret_cast<const std::uint16_t*>(x), out, 320, 10240,
      static_cast<int>(batch), 10240, 10240);
  return hipGetLastError() == hipSuccess;
}
'''
    candidate = ROOT/'.deps/gufo-q2-hc-down-bk256'
    patch_path = ROOT/'experiments/q2-hc-down-bk256.patch'
    manifest_path = ROOT/'config/q2-hc-down-bk256-source.json'
    if any(p.exists() for p in (candidate, patch_path, manifest_path)):
        raise ValueError('Refusing to overwrite retained candidate or source receipt')
    shutil.copytree(base, candidate)
    (candidate/(KERNELS+'q2_hc_down_bk256.inc')).write_text(header+port+wrapper)
    cpp = candidate/(KERNELS+'kernels.hip.cpp')
    cpp.write_text(replace(cpp.read_text(), '\nbool UnquantizedF16Gemm(',
                           '\n#include "q2_hc_down_bk256.inc"\n\nbool UnquantizedF16Gemm('))
    hpp = candidate/(KERNELS+'kernels.hpp')
    hpp.write_text(replace(hpp.read_text(), '\nbool UnquantizedF16Gemm(', '''
/// Original F16 HC down, [batch][10240] to [batch][320], BK256 native loads.
/// Valid only at96..2048 rows on gfx1151. Unsupported shapes launch nothing.
/// Changes library accumulation; independent/model qualification is required.
bool HcDownBk256F16Gemm(const void* w, const __half* x, float* out,
                       std::size_t batch, std::size_t m, std::size_t k,
                       hipStream_t stream);
bool UnquantizedF16Gemm('''))
    blas = candidate/(KERNELS+'blaslt.cpp')
    blas.write_text(replace(blas.read_text(), '  // Library edge tiles change the accumulation order', '''  // Isolated candidate replaces only original-F16 HC down; all other plans stay.
  if (type == HIP_R_16F && m == 320 && n >= 96 && n <= 2048 && k == 10240)
    return HcDownBk256F16Gemm(weights, static_cast<const __half*>(input), out,
                             n, m, k, stream_);
  // Library edge tiles change the accumulation order'''))
    files = inventory(candidate)
    changed = [name for name, digest in files.items() if parent['files'].get(name) != digest]
    if set(changed) != {KERNELS+n for n in ('kernels.hip.cpp', 'kernels.hpp', 'blaslt.cpp', 'q2_hc_down_bk256.inc')}:
        raise ValueError('Unexpected candidate delta')
    patch = '// SPDX-License-Identifier: MIT\n'
    for name in changed:
        before = (base/name).read_text() if (base/name).exists() else ''
        patch += ''.join(difflib.unified_diff(before.splitlines(keepends=True),
                    (candidate/name).read_text().splitlines(keepends=True),
                    fromfile='a/'+name, tofile='b/'+name))
    with patch_path.open('x') as stream:
        stream.write(patch)
    third_party = ROOT/'third_party/gsqhalo'
    third_party.mkdir(exist_ok=False)
    (third_party/'LICENSE').write_bytes((corpus/'LICENSE').read_bytes())
    report = dict(schema='synapse-lie.q2-hc-down-bk256-source.v1',
        base=parent['source'], candidate=str(candidate.relative_to(ROOT)),
        parent_manifest_sha256=sha(parent_path), parent_variant='reaudit-q8-row',
        public_origin=dict(repository=origin['repository'], commit=origin['commit'],
            path='ggml/src/ggml-cuda/mmb.cu', source_sha256=sha(corpus/'ggml/src/ggml-cuda/mmb.cu'),
            license_sha256=sha(corpus/'LICENSE'), local_license='third_party/gsqhalo/LICENSE'),
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path),
        files=files, changed_files=changed, unchanged_files=len(files)-len(changed),
        geometry=dict(batch_min=96, batch_max=2048, m=320, k=10240, bm=64, bn=32,
                      bk=256, threads=256, lds_bytes=50688, lds_buffers=1),
        original_f16_weights=True, original_f16_activations=True, bf16_conversion=False,
        two_fp32_k16_chains=True, additional_device_allocations=0,
        new_gpu_run=False, new_model_forward=False, numerical_qualification=False,
        performance_qualification=False, goal_met=False)
    with manifest_path.open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(candidate=report['candidate'], files=len(files), changed=changed,
                         original_f16=True, lds_bytes=50688, gpu_run=False)))


if __name__ == '__main__':
    main()
