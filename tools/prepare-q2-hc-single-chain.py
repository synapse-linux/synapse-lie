#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate a single K16 accumulator chain in the original-F16 HC down path."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-hc-single-chain'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp')
EXPECTED = 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source boundary: ' + old[:90])
    return text.replace(old, new)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Retained paired-HC-up source changed')
    original = (BASE / REL).read_text()
    start = original.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = original.index('\nbool AttentionF16Gemm(', start)
    body = original[start:end]
    body = once(body, 'bool kHalfWeights = false, bool kHcUpChains = false>',
                'bool kHalfWeights = false, bool kHcUpChains = false,\n'
                '         bool kHcSingleChain = false>')
    body = once(body, '  constexpr int kBlockThreads = kHcUpChains ? 512 : 256;',
                '  static_assert(!kHcSingleChain ||\n'
                '                (kHalfWeights && !kHcUpChains && !kHcMix &&\n'
                '                 !kSsmConv && !kAttention && BM == 64 && BN == 128));\n'
                '  constexpr int kBlockThreads = kHcUpChains ? 512 : 256;')
    condition = 'kHalfWeights && !kHcUpChains'
    # Exclude the assertion above: only the two array dimensions, compute
    # choice and final reduction are changed. Both K16 products still execute.
    anchor = body.index('  v8f acc[kWaveRowTiles][kWaveTokTiles];')
    prefix, accumulation = body[:anchor], body[anchor:]
    if accumulation.count(condition) != 4:
        raise ValueError('Unexpected accumulator condition count')
    accumulation = accumulation.replace(condition, condition + ' && !kHcSingleChain')
    accumulation = once(accumulation,
        '  // Separate K16 chains reduce FP32 accumulation error for the sensitive\n'
        '  // unquantized router/gate projections, with the same order in every chunk.',
        '  // HC down may explicitly select one chain: low/high K16 products\n'
        '  // update the same accumulator in order. This changes FP32 rounding;\n'
        '  // all other raw-half projections retain their original two chains.')
    changed = original[:start] + prefix + accumulation + original[end:]
    changed = once(changed,
        '(DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true>),',
        '(DenseF16GEMMKernel<64, 128, 2, 2, 4, 5, false, false, false, true, false, true>),')
    changed = once(changed,
        '  // unquantized router. Retain the two FP32 K16 accumulation chains; only\n'
        '  // macro-tile geometry differs. The caller has already narrowed inputs.',
        '  // unquantized router. Only the admitted HC down shape selects a single\n'
        '  // FP32 K16 chain; other shapes keep their existing reduction order.\n'
        '  // The caller has already narrowed inputs; model weights are unchanged.')
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                       and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected changed inventory')
    patch = ROOT / 'experiments/q2-hc-single-chain.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), target.read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared exploratory source; numerical and performance verdicts unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
        candidate=str(OUT.relative_to(ROOT)), changed_files=inventory,
        base_sha256=sha(BASE / REL), candidate_sha256=sha(target), patch_sha256=sha(patch),
        dispatch='Original F16 HC down M320/K10240, n>=96, unchanged 64x128/BK2 tile and 256 threads',
        numeric_contract='Original F16 weights and narrowed inputs; low/high K16 products sequentially update one F32 accumulator instead of separate chains plus final addition',
        preserved='Fused paired HC up, scalar decode, routed IQ2/Q2, PLE, activation boundaries, original model files and public ABI',
        numerical_limits_changed=False, model_conversion=False,
        limit='Deliberate arithmetic change; independent FP64 and saved model frontiers must be measured. No inherited DS4 exactness or runtime adoption.')
    (ROOT / 'config/q2-hc-single-chain-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
