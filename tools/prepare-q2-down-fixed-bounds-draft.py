#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a local compiler probe for the active Q2 down geometry; no provider."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    donor = ROOT / parent['source'] / 'src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
    relative = str(donor.relative_to(ROOT / parent['source']))
    assert sha(donor) == parent['files'][relative]
    text = donor.read_text()
    body = text[:text.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage')]
    body = body.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2FixedBoundsDraftKernel')
    old = '__half* __restrict__ out_half, std::size_t m, std::size_t k,'
    assert body.count(old) == 1
    body = body.replace(old, '__half* __restrict__ out_half, std::size_t input_m, std::size_t input_k,')
    old = '    const void* __restrict__ w_up) {'
    assert body.count(old) == 1
    body = body.replace(old, old + '''
  // A future guarded selector must require m2560/k640 and aligned half output.
  static_assert(BM == 128 && (BN == 16 || BN == 48 || BN == 64));
  constexpr std::size_t m = 2560, k = 640;''')
    assert body.count('    f_live[u] = r < m_i;') == 1
    body = body.replace('    f_live[u] = r < m_i;', '    f_live[u] = true;')
    assert body.count('if (t < bucket_rows && r < m_i)') == 3
    body = body.replace('if (t < bucket_rows && r < m_i)', 'if (t < bucket_rows)')
    old = '''if (m % 8 == 0 &&
            reinterpret_cast<std::uintptr_t>(dst_half) % 16 == 0)'''
    assert body.count(old) == 1
    body = body.replace(old, 'if constexpr (true)')
    output = ROOT / 'experiments/q2-down-fixed-bounds-draft.inc'
    prep = ROOT / 'evidence/q2-down-fixed-bounds-draft-preparation'
    assert not output.exists() and not prep.exists(), 'Preserve existing draft'
    prep.mkdir()
    output.write_text(body)
    wrapper = '''// SPDX-License-Identifier: MIT
// Local compiler probe only; no launch, provider or benchmark selector.
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-down-fixed-bounds-draft.inc"
'''
    for bn in (16, 48, 64):
        wrapper += f'''template __global__ void RoutedQ2FixedBoundsDraftKernel<WeightType::kQ2_K,128,{bn},2,false,false,true>(
 const void*, const __half*, const std::int32_t*, const std::int32_t*,
 const std::int32_t*, const std::int32_t*, const float*, float*, __half*,
 std::size_t, std::size_t, const void*);
'''
    wrapper += '}\n'
    unit = prep / 'candidate.hip'
    unit.write_text(wrapper)
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(unit.relative_to(ROOT))
    argv[argv.index('-o') + 1] = str((prep / 'candidate.s').relative_to(ROOT))
    argv.insert(argv.index('-S'), '-I.')
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    report = dict(schema='synapse-lie.q2-down-fixed-bounds-draft.v1',
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        donor=str(donor.relative_to(ROOT)), donor_sha256=sha(donor),
        include=str(output.relative_to(ROOT)), include_sha256=sha(output),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        shape=dict(m=2560, k=640, BM=128, BN=[16,48,64], grid_rows=20, output_alignment=16),
        proof='20 row blocks times128 rows cover2560 exactly; WMMA row groups and eight-half stores stay inside each128-row block. Ten K64 stages exactly cover640; quantized row stride remains ceil(640/256)*84=252 bytes.',
        arithmetic_changed=False, routing_or_ragged_token_bounds_changed=False,
        provider_created=False, runtime_selector=False, GPU_admission=False,
        model_run=False, performance_claim=False)
    with (ROOT / 'config/q2-down-fixed-bounds-draft.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(private_bodies=3, m=2560, k=640, model_run=False)))


if __name__ == '__main__':
    main()
