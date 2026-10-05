#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Redistribute compact IQ2 codebook slices inside four-lane groups."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/prepare-q2-iq2-slice-commit.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT/'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    original = (base/REL).read_text()
    control = ROOT/'experiments/q2-iq2-slice-commit-control.inc'
    kernel = prior.prior.literal.function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    expected = '// SPDX-License-Identifier: MIT\n// Literal measured raw-prefetch1505 parent; old cohorts are not rebuilt.\n'
    expected += kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2SliceControlKernel')+'\n'
    if control.read_text() != expected:
        raise ValueError('Retained literal control is not the measured parent')
    out = ROOT/'.deps/gufo-q2-iq2-lane-commit-run'
    manifest = ROOT/'config/q2-iq2-lane-commit-source.json'
    patch = ROOT/'experiments/q2-iq2-lane-commit.patch'
    if any(p.exists() for p in (out,manifest,patch)):
        raise ValueError('Refusing to overwrite retained experiment')
    start = original.index('  const auto commit_stage =', original.index('__launch_bounds__(256) __global__ void RoutedF16GEMMKernel'))
    begin = original.index('      if constexpr (kIQ2) {', start)
    end = original.index('      } else if constexpr (kSigned || kQ2) {', begin)
    replacement = '''      if constexpr (kIQ2) {
        const uint2 group = f_iq2_group[u];
        const __half d = f_iq2_d[u];
        // SPDX-License-Identifier: MIT
        // Each lane retains its original ten-byte prefetch and scale owner.
        // Four lanes transpose decode ownership: each writes one eight-value
        // slice for each peer's group, preserving every compact LDS byte.
        const int part = lane_id & 3;
#pragma unroll
        for (int owner = 0; owner < 4; ++owner) {
          const int peer_lane = (lane_id & ~3) + owner;
          const int peer_tid = (tid & ~3) + owner;
          const std::uint32_t indices = __shfl(group.x, peer_lane, 32);
          const std::uint32_t signs = __shfl(group.y, peer_lane, 32);
          const unsigned code = (indices >> (8 * part)) & 255U;
          const unsigned sign = (signs >> (7 * part)) & 127U;
          const uint2 magnitude =
              reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          const uint2 decoded = make_uint2(magnitude.x ^ (mask.x & 0x80808080U),
                                           magnitude.y ^ (mask.y & 0x80808080U));
          const int peer_row = (peer_tid >> 1) + (u * 128);
          const int chunk = 2 * (peer_tid & 1) + (part >> 1);
          reinterpret_cast<uint2*>(s_codes + swizzle(peer_row, chunk))[part & 1] = decoded;
        }
        const float scale =
            __half2float(d) * float(2 * (group.y >> 28) + 1) * 0.125F;
        const std::uint32_t dm =
            __builtin_bit_cast(std::uint16_t, __float2half_rn(scale));
        scale_bias = f_live[u] ? dm : 0U;
'''
    changed = original[:begin]+replacement+original[end:]
    # Pure integer redistribution. Preserve these stage boundaries literally.
    for fragment in ('        const float scale =\n            __half2float(d) * float(2 * (group.y >> 28) + 1) * 0.125F;',
                     '    compute_stage();\n    __syncthreads();'):
        if fragment not in changed or fragment not in original:
            raise ValueError('Arithmetic/stage anchor changed')
    shutil.copytree(base,out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = sorted(n for n in files if files[n] != parent['files'].get(n))
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected source delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),
            fromfile='a/'+REL,tofile='b/'+REL)))
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-raw-prefetch-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-iq2-raw-prefetch-model-results.json'),
        control_include=str(control.relative_to(ROOT)),control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        mechanism='Four-lane decode ownership transpose via raw32-bit group exchanges; each lane writes one eight-value slice for four original owners.',
        numerical_contract='Original raw prefetch, scales and rounding, codebook/sign bytes, compact LDS cells, barriers, WMMA K order and epilogues preserved.',
        affected='Eight IQ2 paired routed specializations; no Q2 down/dense/vector decode/attention changes.',
        lane_group_width=4,raw_prefetch_bytes_per_thread=10,
        stage_layout_unchanged=True,tile_geometry_unchanged=True,
        additional_runtime_allocations=0,additional_streams=0,additional_device_tables=0,
        risks='Eight raw32-bit exchanges per stage and scattered64-bit stores may cost more than changed temporary lifetime and cooperative access.',
        gpu_run=False,full_model_measured=False,numerical_acceptance=False,goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-lane-commit-source.v1',
            variants={'iq2-lane-commit':variant},gpu_run=False,goal_met=False),stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(variant='iq2-lane-commit',files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
