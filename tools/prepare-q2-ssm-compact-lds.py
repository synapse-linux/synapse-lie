#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare SSM BK1 with a compact XOR transpose; preserve arithmetic and history."""
from collections import Counter
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def layout_checks():
    def index(t, r):
        return t * 32 + (r ^ ((t & 7) << 2))
    slots = {index(t, r) for t in range(32) for r in range(32)}
    assert slots == set(range(1024))
    stores = {}
    for group in range(2):
        for lane in range(32):
            t, half = lane % 16 + group * 16, lane // 16
            for piece in range(2):
                for component in range(8):
                    row = piece * 16 + component * 2 + half
                    address = index(t, row)
                    assert address not in stores
                    stores[address] = (t, row)
    reads = 0
    for t in range(32):
        for r in range(0, 32, 4):
            start = index(t, r)
            assert start % 4 == 0
            for component in range(4):
                assert stores[start + component] == (t, r + component)
                reads += 1
            if t >= 3:
                for earlier in range(t - 3, t):
                    start = index(earlier, r)
                    for component in range(4):
                        assert stores[start + component] == (earlier, r + component)
                        reads += 1
    bank_models = []
    for group in range(2):
        for piece in range(2):
            for component in range(8):
                old, new = [], []
                for lane in range(32):
                    t, row = lane % 16 + group * 16, piece * 16 + component * 2 + lane // 16
                    old.append((t * 36 + row) % 32)
                    new.append(index(t, row) % 32)
                old_counts, new_counts = Counter(old), Counter(new)
                assert sorted(old_counts.values()) == sorted(new_counts.values())
                bank_models.append(max(new_counts.values()))
    # Both schedules visit every K16 fragment in exactly the same order.
    orders = [[(block + kk) * 2 + half for block in range(0, 80, bk)
               for kk in range(bk) for half in range(2)] for bk in (2, 1)]
    assert orders[0] == orders[1] == list(range(160))
    return dict(unique_float_slots_per_wave=len(slots), producer_stores=len(stores),
        scalar_read_coordinates_checked=reads, float4_alignment_preserved=True,
        modeled_32bank_store_cases=len(bank_models), modeled_max_lanes_per_bank=max(bank_models),
        modeled_store_bank_count_distribution_unchanged=True,
        bank_model_is_not_hardware_measurement=True, ordered_k16_fragments=160,
        parent_k_stages=40, candidate_k_stages=80, block_barriers_per_k_stage=2,
        source_barriers_per_block=[80, 160],
        source_stage_bytes=[49152, 24576], source_transpose_bytes=[36864, 32768],
        source_shared_allocation_bytes=[49152, 32768],
        grid_and_convolution_boundaries_unchanged=True, floating_arithmetic_tested=False)


def main():
    parent_path = ROOT / 'config/q2-down-register-scatter-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-register-scatter']
    base = ROOT / parent['source']
    assert ssm.inventory(base) == parent['files']
    original = (base / ssm.REL).read_text()
    changed = ssm.once(original,
        '  constexpr int kTransposeChunks = 8 * 16 * 36 * sizeof(float) / sizeof(uint4);',
        '  constexpr int kTransposeChunks =\n'
        '      (kSsmConv ? 8 * 32 * 32 : 8 * 16 * 36) * sizeof(float) / sizeof(uint4);')
    changed = ssm.once(changed, '  constexpr unsigned kOutputStride = 36;',
        '  // SSM keeps float4 alignment with an XOR row permutation, without padding.\n'
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
    changed = ssm.once(changed, old, new)
    changed = ssm.once(changed,
        '          static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 8 &&\n',
        '          static_assert(BM == 256 && BN == 128 && BK == 1 && WM == 8 &&\n')
    changed = ssm.once(changed, '              const float4 current = src[v];',
        '              const float4 current = *reinterpret_cast<const float4*>(\n'
        '                  tile_scratch + ssm_index(tok_l, row_l + v * 4));')
    for history in (3, 2, 1):
        changed = ssm.once(changed,
            'tile_scratch + (tok_l - %d) * kOutputStride + row_l + v * 4);' % history,
            'tile_scratch + ssm_index(tok_l - %d, row_l + v * 4));' % history)
    changed = ssm.once(changed, 'DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>',
                       'DenseF16GEMMKernel<256, 128, 1, 8, 1, 1, false, true>')
    for fragment in ('float SsmConv4Value(', '__global__ void SsmConvBoundaryKernel('):
        assert ssm.function(original, fragment) == ssm.function(changed, fragment)
    destination = ROOT / '.deps/gufo-q2-ssm-compact-lds-run'
    manifest = ROOT / 'config/q2-ssm-compact-lds-source.json'
    patch = ROOT / 'experiments/q2-ssm-compact-lds.patch'
    assert not any(p.exists() for p in (destination, manifest, patch))
    shutil.copytree(base, destination)
    (destination / ssm.REL).write_text(changed)
    files = ssm.inventory(destination)
    assert len(files) == 1027 and [p for p in files if files[p] != parent['files'][p]] == [ssm.REL]
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True), fromfile='a/' + ssm.REL, tofile='b/' + ssm.REL)))
    proof = layout_checks()
    variant = dict(source=str(destination.relative_to(ROOT)), files=files,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=ssm.sha(parent_path),
        measured_parent='config/q2-down-register-scatter-model-results.json',
        measured_parent_sha256=ssm.sha(ROOT / 'config/q2-down-register-scatter-model-results.json'),
        parent_prefill_tok_s=1580.226725, parent_decode_steps_s=25.10411864,
        patch=str(patch.relative_to(ROOT)), patch_sha256=ssm.sha(patch),
        mechanism='SSM-only BK2 to BK1 with padding-free XOR row layout in its32-token '
                  'convolution transpose. Shared allocation49,152 to32,768 bytes; K16 order unchanged.',
        source_layout_proof=proof,
        risks='More K-stage barriers and altered register scheduling may offset lower LDS allocation. '
              'Modeled bank counts are not hardware transactions or measured block residency.',
        row_group=1, fixed_shape_specializations_composed=False,
        model_upload_changed=False, new_allocations=0, new_streams=0, launch_count_changed=False,
        grid_changed=False, scalar_decode_changed=False, parent_recompiled=False,
        current_frozen_campaign_changed=False, gpu_run=False, model_inference=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-compact-lds-source.v1',
                       variants={'ssm-compact-lds': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, layout_proof=proof, gpu_run=False)))


if __name__ == '__main__':
    main()
