#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe HC-down with original F16 weights read directly by each consumer wave."""
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/prepare-q2-ssm-row-group.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, once = prior.sha, prior.once
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_hc_down_bk256.inc'


def main():
    manifest = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert prior.inventory(base) == parent['files']
    source = (base / REL).read_text()
    source = source.replace('HcDownBk256Kernel', 'HcDownDirectWeightKernel')
    source = source.replace('HcDownBk256F16Gemm', 'HcDownDirectWeightF16Gemm')
    # Keep the inherited MIT attribution in the private derived include.
    source = source.replace('typedef std::uint32_t HcDownVector4 __attribute__((ext_vector_type(4)));', '')
    a = source.index('__device__ __forceinline__ v16h HcDownFragment16(')
    b = source.index('// Original F16', a)
    source = source[:a] + source[b:]
    source = once(source, '  __shared__ __align__(16) std::uint16_t As[NBUF][BM * LDS];\n', '')
    source = once(source, '  const std::uint16_t* ap[A_IT];\n', '')
    source = once(source, '  int al[A_IT], bl[B_IT];', '  int bl[B_IT];')
    a = source.index('#pragma unroll\n  for (int i = 0; i < A_IT; ++i) {')
    b = source.index('#pragma unroll\n  for (int i = 0; i < B_IT; ++i)', a)
    source = source[:a] + source[b:]
    source = once(source, '  HcDownVector4 ra[A_IT], rb[B_IT];\n'
        '#pragma unroll\n  for (int i = 0; i < A_IT; ++i)\n'
        '    ra[i] = *(const HcDownVector4*)ap[i];', '  HcDownVector4 rb[B_IT];')
    a = source.index('#pragma unroll\n  for (int i = 0; i < A_IT; ++i)\n')
    b = source.index('#pragma unroll\n  for (int i = 0; i < B_IT; ++i)', a)
    source = source[:a] + source[b:]
    source = once(source, '#pragma unroll\n      for (int i = 0; i < A_IT; ++i)\n'
        '        ra[i] = *(const HcDownVector4*)(ap[i] + k0);\n', '')
    source = once(source,
        '        a[i] = HcDownFragment16(As[s] + (wm * WTM + i * 16 + r) * LDS + kk);',
        '        a[i] = HcDownFragment16(W + (size_t)(m0 + wm * WTM + i * 16 + r) * ldw + ks * BK + kk);')
    a = source.index('#pragma unroll\n      for (int i = 0; i < A_IT; ++i)\n')
    b = source.index('#pragma unroll\n      for (int i = 0; i < B_IT; ++i)', a)
    source = source[:a] + source[b:]
    source = once(source, '  constexpr int LDS = BK + 8, CPR = BK / 8;',
        '  static_assert(BM == 64 && BN == 32 && WTM == 16 && WTN == 16 && BK == 256 && NBUF == 1);\n'
        '  constexpr int LDS = BK + 8, CPR = BK / 8;')
    source = once(source, '  constexpr int A_IT = (BM * CPR + 256 - 1) / 256,\n'
        '                B_IT = (BN * CPR + 256 - 1) / 256;',
        '  constexpr int B_IT = (BN * CPR + 256 - 1) / 256;')
    source = source.replace('// Original F16 operands, two K16 chains, gfx1151 only.',
        '// Original F16 operands, two K16 chains, gfx1151 only.\n'
        '// New probe: remove weight LDS staging. Two token waves load each\n'
        '// original weight fragment directly. Activation staging/order unchanged.\n'
        '// Increased logical weight loads are a measured tradeoff, not a free gain.')
    assert 'As[' not in source and 'ra[' not in source and 'ap[' not in source
    out = ROOT / 'evidence/q2-hc-down-direct-weight-preparation'
    inc = ROOT / 'experiments/q2-hc-down-direct-weight.inc'
    assert not out.exists() and not inc.exists()
    formatted = subprocess.run(['clang-format', '--style=file:' + str(base / '.clang-format')],
                               input=source, text=True, capture_output=True)
    assert formatted.returncode == 0, formatted.stderr
    out.mkdir()
    inc.write_text(formatted.stdout)
    (out / 'draft.inc').write_bytes(inc.read_bytes())
    probe = out / 'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n#include "../../' + parent['source'] + '/' + prior.REL + '"\n'
        'namespace gufo::models::qwen38_flash_next::rocm {\n#include "draft.inc"\n}\n')
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(probe.relative_to(ROOT))
    assembly = out / 'candidate.s'
    argv[argv.index('-o') + 1] = str(assembly.relative_to(ROOT))
    (out / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out / 'assembly.stdout').open('x') as stdout, (out / 'assembly.stderr').open('x') as stderr:
        result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
    report = dict(argv=argv, started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), exit_code=result.returncode,
        draft=str(inc.relative_to(ROOT)), draft_sha256=sha(inc),
        parent_manifest_sha256=sha(manifest), assembly_sha256=sha(assembly) if assembly.exists() else None,
        original_F16_operands=True, original_K16_accumulation_order=True,
        logical_weight_load_factor=2, logical_activation_load_factor=1,
        removed_weight_LDS_bytes=33792, expected_LDS_bytes=16896,
        production_selector=False, GPU_run=False, model_rate_claim=False)
    (out / 'assembly-command.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
