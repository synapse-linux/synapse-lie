#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose a smaller SSM tile, compact transpose and ordered fragment phases."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fence', action='store_true')
    args = parser.parse_args()
    name = 'ssm-resident-fence' if args.fence else 'ssm-resident'
    out = ROOT / ('evidence/q2-' + name + '-preparation')
    inc = ROOT / ('experiments/q2-' + name + '-draft.inc')
    require_absent = (out, inc)
    assert not any(p.exists() for p in require_absent)
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert ssm.inventory(base) == parent['files']
    original = (base / ssm.REL).read_text()
    body = ssm.function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    symbol = 'DenseSsmResidentFenceKernel' if args.fence else 'DenseSsmResidentKernel'
    body = body.replace('DenseF16GEMMKernel', symbol)
    body = once(body, '  constexpr int kTransposeChunks = 8 * 16 * 36 * sizeof(float) / sizeof(uint4);',
        '  constexpr int kTransposeChunks =\n'
        '      (kSsmConv ? 8 * 32 * 32 : 8 * 16 * 36) * sizeof(float) / sizeof(uint4);')
    body = once(body, '  constexpr unsigned kOutputStride = 36;',
        '  constexpr unsigned kOutputStride = kSsmConv ? 32 : 36;\n'
        '  const auto ssm_index = [](unsigned token, unsigned row) {\n'
        '    return token * 32 + (row ^ ((token & 7) << 2));\n'
        '  };')
    old = '''          tile_scratch[((sub_lane + group * 16) * kOutputStride) + (2 * l) +
                       half_id] = acc[i][j + group][l];
          tile_scratch[((sub_lane + group * 16) * kOutputStride) + 16 +
                       (2 * l) + half_id] = acc[i + 1][j + group][l];'''
    new = '''          if constexpr (kSsmConv) {
            tile_scratch[ssm_index(sub_lane + group * 16, 2 * l + half_id)] =
                acc[i][j + group][l];
            tile_scratch[ssm_index(sub_lane + group * 16, 16 + 2 * l + half_id)] =
                acc[i + 1][j + group][l];
          } else {
''' + old + '''
          }'''
    body = once(body, old, new)
    body = once(body, '          static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 8 &&\n                        WN == 1);',
                      '          static_assert(BM == 128 && BN == 128 && BK == 2 && WM == 4 &&\n                        WN == 2);')
    body = once(body, '              const float4 current = src[v];',
        '              const float4 current = *reinterpret_cast<const float4*>(\n'
        '                  tile_scratch + ssm_index(tok_l, row_l + v * 4));')
    for history in (3, 2, 1):
        body = once(body, f'tile_scratch + (tok_l - {history}) * kOutputStride + row_l + v * 4);',
                    f'tile_scratch + ssm_index(tok_l - {history}, row_l + v * 4));')
    start = body.index('      v16h a_lo[kWaveRowTiles];')
    end = body.index('    }\n    __syncthreads();\n  }\n\n  if constexpr (kHalfWeights', start)
    phases = '''      // Every accumulator keeps its low/high K16 sequence. The two phases
      // shorten simultaneously live fragments for this 128-row tile.
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
FENCE      }
'''.replace('FENCE', '        __builtin_amdgcn_sched_barrier(0);\n' if args.fence else '')
    body = body[:start] + phases + body[end:]
    body = once(body, '  static_assert(WM * WN == 8, "256 threads is 8 waves");',
        '  static_assert(WM * WN == 8, "256 threads is 8 waves");\n'
        '  static_assert(kSsmConv && !kHalfWeights && !kHcUpChains && !kHcMix && !kAttention);')
    wrapper = ssm.function(original, 'bool DenseF16SsmGemm(')
    wrapper = wrapper.replace('DenseF16SsmGemm', 'DenseSsmResidentFence' if args.fence else 'DenseSsmResident')
    wrapper = wrapper.replace('DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>',
                              symbol + '<128, 128, 2, 4, 2, 1, false, true>')
    wrapper = once(wrapper, 'm / 256', 'm / 128')
    generated = '// SPDX-License-Identifier: MIT\n// Private SSM composition from the retained IQ2 fixed-bounds provider.\n' + body + '\n' + wrapper + '\n'
    formatted = subprocess.run(['clang-format', '--style=file:' + str(base / '.clang-format')],
                               input=generated, text=True, capture_output=True)
    assert formatted.returncode == 0, formatted.stderr
    with inc.open('x') as stream:
        stream.write(formatted.stdout)
    out.mkdir()
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
    record = dict(argv=argv, started_at=started, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=compiled.returncode, variant=name, draft=str(inc.relative_to(ROOT)), draft_sha256=sha(inc),
        parent_manifest_sha256=sha(manifest), retained_files=1028, GPU_run=False,
        assembly_sha256=sha(assembly) if compiled.returncode == 0 else None,
        grid_rows=[64, 128], grid_token_width=128, K32_per_stage=2, K_stages=40,
        ordered_K16_products_per_output=160, stage_bytes=32768, transpose_bytes=32768,
        source_block_barriers=80, compiler_phase_fence=args.fence,
        original_convolution_boundaries=True, original_raw_live_mask=True,
        model_selector=False, numerical_acceptance=False, performance_measurement=False)
    (out / 'assembly-command.json').write_text(json.dumps(record, indent=2) + '\n')
    assert ssm.inventory(base) == parent['files']
    print(json.dumps(record))
    if compiled.returncode:
        print((out / 'assembly.stderr').read_text()[-3500:])
    raise SystemExit(compiled.returncode)


if __name__ == '__main__':
    main()
