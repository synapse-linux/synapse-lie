#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe one short K320 chain in both original-F16 HC-up/mix routes."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)
sha, once = ssm.sha, ssm.once
DEFERRED = 'src/models/qwen38_flash_next/kernels/rocm/q2_hc_moe_deferred.inc'


def single_chain(body, phased):
    condition = 'kHalfWeights && !kHcUpChains'
    assert body.count(condition) == 4
    body = body.replace(condition, 'false')
    body = once(body,
        '  // Separate K16 chains reduce FP32 accumulation error for the sensitive\n'
        '  // unquantized router/gate projections, with the same order in every chunk.',
        '  // Experimental K320 HC-up only: low/high products update one chain.\n'
        '  // This deliberately changes FP32 rounding; original half operands remain.')
    if phased:
        start = body.index('      v16h a_lo[kWaveRowTiles];')
        end = body.index('    }\n    __syncthreads();\n  }\n\n  if constexpr (false)', start)
        body = body[:start] + '''      // Bound live fragments to one K16 half while retaining each
      // output's ascending low/high update order in this new single chain.
#pragma unroll
      for (int half = 0; half < 2; ++half) {
        v16h a[kWaveRowTiles];
#pragma unroll
        for (int i = 0; i < kWaveRowTiles; ++i) {
          const int row = (((wave_row * kWaveRowTiles) + i) * 16) + sub_lane;
          uint4 c[2];
#pragma unroll
          for (int q = 0; q < 2; ++q)
            c[q] = s_a[kb][row][swizzle(row, q + 2 * half)];
          __builtin_memcpy(&a[i], &c[0], 32);
        }
#pragma unroll
        for (int j = 0; j < kWaveTokTiles; ++j) {
          const int t = (((wave_tok * kWaveTokTiles) + j) * 16) + sub_lane;
          uint4 c[2];
#pragma unroll
          for (int q = 0; q < 2; ++q)
            c[q] = s_b[kb][t][swizzle(t, q + 2 * half)];
          v16h b;
          __builtin_memcpy(&b, &c[0], 32);
#pragma unroll
          for (int i = 0; i < kWaveRowTiles; ++i)
            acc[i][j] = Wmma(a[i], b, acc[i][j]);
        }
        __builtin_amdgcn_sched_barrier(0);
      }
''' + body[end:]
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phased', action='store_true')
    args = parser.parse_args()
    suffix = '-phased' if args.phased else ''
    out = ROOT / ('evidence/q2-hc-up-short-chain' + suffix + '-preparation')
    inc = ROOT / ('experiments/q2-hc-up-short-chain' + suffix + '-draft.inc')
    assert not out.exists() and not inc.exists()
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert ssm.inventory(base) == parent['files']
    original = (base / ssm.REL).read_text()
    deferred_original = (base / DEFERRED).read_text()
    dense = ssm.function(original,
        'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    dense = single_chain(dense.replace('DenseF16GEMMKernel', 'HcUpShortChainKernel'), args.phased)
    dense = once(dense, '  static_assert(WM * WN == 8, "256 threads is 8 waves");',
        '  static_assert(WM * WN == 8, "256 threads is 8 waves");\n'
        '  static_assert(kHalfWeights && kHcMix && !kHcUpChains && !kSsmConv && !kAttention);\n'
        '  static_assert(BM == 256 && BN == 128 && BK == 1 && WM == 4 && WN == 2 && kRowGroup == 8);')
    plain = ssm.function(original, 'bool HcMixRawF16Gemm(')
    plain = plain.replace('HcMixRawF16Gemm', 'HcMixRawF16ShortChain')
    plain = plain.replace('DenseF16GEMMKernel', 'HcUpShortChainKernel')
    plain = once(plain, 'false, true, true>),', 'false, true, false>),')
    plain = once(plain, 'grid, dim3(512)', 'grid, dim3(256)')
    deferred = ssm.function(deferred_original,
        '__launch_bounds__(512) __global__ void HcMixDeferredNormKernel(')
    deferred = single_chain(deferred, args.phased)
    deferred = once(deferred, '__launch_bounds__(512)', '__launch_bounds__(256)')
    deferred = once(deferred, 'kHcUpChains = true;', 'kHcUpChains = false;')
    deferred = deferred.replace('HcMixDeferredNormKernel', 'HcMixDeferredShortChainKernel')
    wrapper = ssm.function(deferred_original, 'bool HcMixDeferredNorm(')
    wrapper = wrapper.replace('HcMixDeferredNormKernel', 'HcMixDeferredShortChainKernel')
    wrapper = wrapper.replace('HcMixDeferredNorm(', 'HcMixDeferredShortChain(')
    wrapper = once(wrapper, 'grid, dim3(512)', 'grid, dim3(256)')
    generated = ('// SPDX-License-Identifier: MIT\n'
        '// Derived from independently fetched official Gufo and retained LIE Q2.\n'
        '// Only K320 original-F16 HC-up/mix; experimental rounding change.\n' +
        '\n'.join((dense, plain, deferred, wrapper)))
    if args.phased:
        generated = generated.replace('ShortChain', 'ShortChainPhased')
    formatted = subprocess.run(['clang-format', '--style=file:' + str(base / '.clang-format')],
                               input=generated, text=True, capture_output=True)
    assert formatted.returncode == 0, formatted.stderr
    out.mkdir()
    with inc.open('x') as stream:
        stream.write(formatted.stdout)
    (out / 'draft.inc').write_bytes(inc.read_bytes())
    probe = out / 'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n#include "../../' + parent['source'] + '/' + ssm.REL + '"\n'
        'namespace gufo::models::qwen38_flash_next::rocm {\n#include "draft.inc"\n}\n')
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(probe.relative_to(ROOT))
    assembly = out / 'candidate.s'
    argv[argv.index('-o') + 1] = str(assembly.relative_to(ROOT))
    (out / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out / 'assembly.stdout').open('x') as stdout, (out / 'assembly.stderr').open('x') as stderr:
        compiled = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
    record = dict(argv=argv, started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=compiled.returncode, draft=str(inc.relative_to(ROOT)), draft_sha256=sha(inc),
        parent_manifest_sha256=sha(manifest), retained_files=len(parent['files']),
        assembly_sha256=sha(assembly) if assembly.exists() else None,
        source_paths=['ordinary HC-up/mix', 'deferred-normalization HC-up/mix'],
        production_K=320, original_F16_operands=True, old_accumulator_chains=2,
        new_accumulator_chains=1, original_blocks_at_2048=640, new_blocks_at_2048=640,
        old_threads_per_block=512, new_threads_per_block=256,
        old_wmma_products_per_output=20, new_wmma_products_per_output=20,
        old_epilogue_block_barriers=24, new_epilogue_block_barriers=16,
        changed_FP32_rounding=True, phased_K16_compiler_fence=args.phased,
        independent_quality_qualification=False,
        GPU_run=False, model_selector=False, numerical_acceptance=False, performance_measurement=False)
    (out / 'assembly-command.json').write_text(json.dumps(record, indent=2) + '\n')
    assert ssm.inventory(base) == parent['files']
    print(json.dumps(record))
    if compiled.returncode:
        print((out / 'assembly.stderr').read_text()[-3500:])
    raise SystemExit(compiled.returncode)


if __name__ == '__main__':
    main()
