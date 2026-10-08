#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare bounded persistent IQ2/Q2_K prefill mirrors from retained 1585."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('prepare_ssm', ROOT/'tools/prepare-q2-ssm-row-group.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
once, sha, inventory = prior.once, prior.sha, prior.inventory


def mirror_kernel(text, name):
    start = text.rfind('template<WeightType', 0, text.index('void ' + name + '('))
    end = text.index('\n}\n', start) + 3
    old = text[start:end]
    new = once(old, 'bool kPacked = false, bool kScaled = false>',
               'bool kPacked = false, bool kScaled = false, bool kMirror = false>')
    new = once(new, 'constexpr int kCodeBytes = BM * kChunks * 16;',
               'constexpr int kCodeBytes = kMirror ? 0 : BM * kChunks * 16;')
    new = once(new, 'constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;',
               'constexpr int kScaleBytes = kMirror ? 0 : (kQ2 ? 4 : 1) * BK * BM * 4;')
    new = once(new, 'constexpr int kLdsBytes = kStageBytes > 8 * 1024 ? kStageBytes : 8 * 1024;',
        'constexpr int kMinBytes = kMirror ? 9216 : 8192;\n'
        '  constexpr int kLdsBytes = kStageBytes > kMinBytes ? kStageBytes : kMinBytes;')
    for signature in ('fetch_stage = [&](int kb0)', 'commit_stage = [&]()'):
        a = new.index('  const auto ' + signature + ' {')
        a = new.index('\n', a) + 1
        b = new.index('\n#pragma unroll\n    for (int i = 0; i < kActFetch;', a)
        new = new[:a] + '    if constexpr (!kMirror) {\n' + new[a:b] + '\n    }' + new[b:]
    new = once(new, 'const auto compute_stage = [&]() {',
               'const auto compute_stage = [&](int kb0) {')
    new = once(new, 'if constexpr (!kSigned && !kQ2) {',
               'if constexpr (!kMirror && !kSigned && !kQ2) {')
    a = new.index('        const __half2 sb =', new.index('const auto compute_stage'))
    b = new.index('        __builtin_memcpy(&a_hi[u], &h[8], 32);', a)
    b = new.index('\n', b)
    direct = '''        // SPDX-License-Identifier: MIT
        if constexpr (kMirror) {
          static_assert(kIQ2 || (kQ2 && kScaled));
          const int logical_row = r_block + (kPair ? row % kRows : row);
          const void* cached = w;
          if constexpr (kPair) {
            if (row >= kRows) cached = w_up;
          }
          if (logical_row < m_i) {
            const auto* weights = static_cast<const __half*>(cached) +
                std::size_t(expert) * m * k;
            const std::size_t offset = (std::size_t(kb0 + kb) * 2 * m +
                                       logical_row) * 16;
            __builtin_memcpy(&a_lo[u], weights + offset, 32);
            __builtin_memcpy(&a_hi[u], weights + offset + m * 16, 32);
          } else {
            a_lo[u] = v16h{};
            a_hi[u] = v16h{};
          }
        } else {
'''
    new = new[:a] + direct + new[a:b] + '\n        }' + new[b:]
    new = once(new, '    compute_stage();', '    compute_stage(kb0);')
    return text[:start] + new + text[end:]


def main():
    parent_path = ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained 1585 source changed')
    source = ROOT/'.deps/gufo-q2-expert-cache-r3-run'
    manifest = ROOT/'config/q2-expert-cache-source-v3.json'
    patch = ROOT/'experiments/q2-expert-cache-v3.patch'
    if any(p.exists() for p in (source, manifest, patch)):
        raise ValueError('Refusing to overwrite expert-cache source')
    original = {name:(base/PREFIX/name).read_text() for name in
        ('kernels.hip.cpp','kernels.hpp','q2_down_half_storage.inc',
         'device_model.hpp','device_model.cpp','executor.cpp')}
    main_kernel = mirror_kernel(original['kernels.hip.cpp'], 'RoutedF16GEMMKernel')
    half_kernel = mirror_kernel(original['q2_down_half_storage.inc'], 'RoutedQ2HalfStorageKernel')
    # Clone launch wrappers, not arithmetic kernels. Existing public routes
    # instantiate kMirror=false and remain available for every cache miss.
    a = main_kernel.index('template<int BN, bool kPacked = false>\nvoid LaunchRoutedIQ2(')
    b = main_kernel.index('\nbool RoutedGatedIQ2GemmPacked(', a)
    gate = main_kernel[a:b].replace('LaunchRoutedIQ2', 'LaunchCachedIQ2').replace(
        'RoutedGatedIQ2Gemm', 'RoutedCachedIQ2Gemm').replace(
        '2, true, kPacked>', '2, true, kPacked, false, true>')
    scaled = (base/PREFIX/'q2_scaled_input.inc').read_text()
    down = scaled[scaled.index('template<int BN>\nvoid LaunchRoutedQ2Scaled('):]
    down = down.replace('LaunchRoutedQ2Scaled', 'LaunchCachedQ2Scaled').replace(
        'RoutedQ2ScaledGemm', 'RoutedCachedQ2ScaledGemm').replace(
        '2, false, false, true>', '2, false, false, true, true>')
    a = half_kernel.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage(')
    b = half_kernel.index('\n__global__ void HcCombineMoeHalfDeferredNormKernel(', a)
    down_half = half_kernel[a:b].replace('LaunchRoutedQ2HalfStorage', 'LaunchCachedQ2HalfStorage').replace(
        'RoutedQ2ScaledHalfGemm', 'RoutedCachedQ2ScaledHalfGemm').replace(
        '2, false, false, true>', '2, false, false, true, true>')
    extra = (ROOT/'experiments/q2_expert_cache_convert.inc').read_text() + '\n' + gate + down + down_half
    main_kernel = once(main_kernel, '#include "q2_down_half_storage.inc"',
        '#include "q2_down_half_storage.inc"\n#include "lie_q2_expert_cache.inc"')
    header = original['kernels.hpp']
    declarations = 'bool ConvertExpertCache(const void*, void*, bool, std::uint32_t, std::uint32_t, std::uint32_t, hipStream_t);\n'
    for name in ('RoutedGatedIQ2Gemm', 'RoutedQ2ScaledGemm', 'RoutedQ2ScaledHalfGemm'):
        a = header.index('bool '+name+'(');b = header.index(';',a)+1
        declarations += header[a:b].replace(name, name.replace('RoutedGatedIQ2', 'RoutedCachedIQ2').replace('RoutedQ2', 'RoutedCachedQ2'))+'\n'
    header = once(header, 'bool RoutedGatedIQ2Gemm(', '// SPDX-License-Identifier: MIT\n'+declarations+'\nbool RoutedGatedIQ2Gemm(')
    model_header = once(original['device_model.hpp'], '  void* data{nullptr};',
        '  void* data{nullptr};\n  // SPDX-License-Identifier: MIT\n  void* prefill_cache{nullptr};')
    model = once(original['device_model.cpp'], '#include <initializer_list>',
        '#include <initializer_list>\n#include <chrono>\n#include <cstdio>\n#include <limits>\n'
        '#include "lie_q2_expert_cache_policy.h"')
    insertion = (ROOT/'experiments/q2_expert_cache_upload.inc').read_text()
    model = once(model, '  return m;\n}\n\n}  // namespace', insertion+'\n  return m;\n}\n\n}  // namespace')
    executor = original['executor.cpp']
    executor = once(executor, '      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,',
        '      const bool cached = l.ffn_gate_exps.prefill_cache && l.ffn_up_exps.prefill_cache;\n'
        '      return (cached ? RoutedCachedIQ2Gemm : RoutedGatedIQ2Gemm)(\n'
        '          cached ? l.ffn_gate_exps.prefill_cache : l.ffn_gate_exps.data,\n'
        '          cached ? l.ffn_up_exps.prefill_cache : l.ffn_up_exps.data,')
    executor = once(executor, '              ? RoutedQ2ScaledHalfGemm(\n                    l.ffn_down_exps.data,',
        '              ? (l.ffn_down_exps.prefill_cache ? RoutedCachedQ2ScaledHalfGemm : RoutedQ2ScaledHalfGemm)(\n'
        '                    l.ffn_down_exps.prefill_cache ? l.ffn_down_exps.prefill_cache : l.ffn_down_exps.data,')
    executor = once(executor, '              : RoutedQ2ScaledGemm(l.ffn_down_exps.data,',
        '              : (l.ffn_down_exps.prefill_cache ? RoutedCachedQ2ScaledGemm : RoutedQ2ScaledGemm)(\n'
        '                    l.ffn_down_exps.prefill_cache ? l.ffn_down_exps.prefill_cache : l.ffn_down_exps.data,')
    changed = {'kernels.hip.cpp':main_kernel,'kernels.hpp':header,
        'q2_down_half_storage.inc':half_kernel,'device_model.hpp':model_header,
        'device_model.cpp':model,'executor.cpp':executor,'lie_q2_expert_cache.inc':extra,
        'lie_q2_expert_cache_policy.h':(ROOT/'experiments/q2_expert_cache_policy.h').read_text()}
    formatted = {}
    for name, body in changed.items():
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false', '--style=file:'+str(base/'.clang-format'),
            '--assume-filename='+str(base/PREFIX/name)], input=body,text=True,capture_output=True,check=True)
        formatted[PREFIX+name] = result.stdout
    shutil.copytree(base,source)
    for name,body in formatted.items(): (source/name).write_text(body)
    files=inventory(source)
    delta=sorted(name for name in files if files[name]!=parent['files'].get(name))
    if delta!=sorted(formatted) or len(files)!=len(parent['files'])+2:
        raise ValueError('Unexpected source changes')
    with patch.open('x') as f:
        f.write('// SPDX-License-Identifier: MIT\n')
        for name,body in sorted(formatted.items()):
            f.write(''.join(difflib.unified_diff((base/name).read_text().splitlines(True)
                if (base/name).exists() else [],body.splitlines(True),
                fromfile='a/'+name if (base/name).exists() else '/dev/null',tofile='b/'+name)))
    variant=dict(source=str(source.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-ssm-fixed-bounds-model-results.json'),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Persistent exact prefill IQ2/Q2_K half operands in K16-row tiles; six evenly spaced trunk layers within32GiB and8GiB free reserve; original encoded weights retained.',
        expected_cache_layers=[0,8,16,24,32,40],expected_additional_resident_bytes=30199062528,
        cache_budget_bytes=32*1024**3, model_dispatch_changed=True, gpu_run=False,numerical_acceptance=False)
    with manifest.open('x') as f:json.dump(dict(schema='synapse-lie.q2-expert-cache-source.v1',variants={'expert-cache':variant}),f,indent=2);f.write('\n')
    print(json.dumps(dict(provider_files=len(files),changed=delta,gpu_run=False)))


if __name__=='__main__': main()
