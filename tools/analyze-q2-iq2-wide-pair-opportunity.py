#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a new paired-IQ2 row mapping without claiming implementation or speed."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_path = ROOT/'config/q2-iq2-lane-commit-source.json'
    source = json.loads(source_path.read_text())['variants']['iq2-lane-commit']
    rel = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
    path = ROOT/source['source']/rel
    assert sha(path) == source['files'][rel]
    text = path.read_text()
    anchors = {
        'paired_geometry_limit': 'static_assert(!kPair || BM == 128);',
        'accumulator_row_tiles': 'constexpr int kWaveRowTiles = BM / 128;',
        'current_paired_source_row': 'r_block + (kPair ? (tid >> 1) % kRows : (tid >> 1) + (u * 128));',
        'current_projection_owner': 'if ((tid >> 1) >= kRows)',
        'current_grid': 'const dim3 grid(static_cast<unsigned>((m + 63) / 64), n_tiles);',
        'same_activation_consumed_by_row_tiles': 'acc[u][j] = Wmma(a_lo[u], b_lo, acc[u][j]);',
        'current_cross_wave_pair': 'float product = base[idx + v + 4 * plane] * base[idx + v];',
    }
    locations = {}
    for name, anchor in anchors.items():
        assert text.count(anchor) == 1, name
        locations[name] = {'line': text[:text.index(anchor)].count('\n')+1, 'literal': anchor}

    # Proposed BM256: u0 owns gate rows0..127, u1 owns the same up rows.
    # This validates integer ownership only, not generated memory operations.
    fetch = [(u, tid//2, tid&1) for u in range(2) for tid in range(256)]
    expected_fetch = {(projection,row,chunk) for projection in range(2)
                      for row in range(128) for chunk in range(2)}
    assert len(fetch) == len(set(fetch)) == len(expected_fetch)
    assert set(fetch) == expected_fetch
    accumulator = [(u, wave*16+2*l+half, token)
                   for u in range(2) for wave in range(8)
                   for token in range(16) for half in range(2) for l in range(8)]
    assert len(accumulator) == len(set(accumulator)) == 4096
    assert set(accumulator) == {(u,row,token) for u in range(2)
                               for row in range(128) for token in range(16)}
    stores = [(wave*16+((iteration*32+lane)*2)%16+v,
               ((iteration*32+lane)*2)//16)
              for wave in range(8) for lane in range(32)
              for iteration in range(4) for v in range(2)]
    assert len(stores) == len(set(stores)) == 2048
    assert set(stores) == {(row,token) for row in range(128) for token in range(16)}
    ragged = []
    for m in (1,5,63,64,65,127,128,129,640):
        produced = [(block*128+row,token) for block in range((m+127)//128)
                    for row,token in stores if block*128+row < m]
        assert len(produced) == len(set(produced)) == m*16
        ragged.append({'output_rows':m,'current_blocks':(m+63)//64,'proposed_blocks':(m+127)//128})

    out = ROOT/'config/q2-iq2-wide-pair-opportunity.json'
    report = dict(schema='synapse-lie.q2-iq2-wide-pair-opportunity.v1',
        source_manifest_sha256=sha(source_path), source=str(path.relative_to(ROOT)),
        source_sha256=sha(path), anchors=locations,
        production_bn=64, original_bm=128, proposed_bm=256,
        original_logical_rows_per_block=64, proposed_logical_rows_per_block=128,
        original_accumulator_values_per_lane=32, proposed_accumulator_values_per_lane=64,
        original_stage_lds_bytes=128*64+2*128*4+2*4*65*16,
        proposed_stage_lds_bytes=256*64+2*256*4+2*4*65*16,
        fetched_group_owners_verified=len(fetch), accumulator_owners_verified=len(accumulator),
        output_owners_verified=len(stores), ragged_mapping=ragged,
        fixed_shape_output_rows=640, fixed_shape_grid_x=[10,5],
        activation_stage_loads_relative_at_full_output_shape=0.5,
        matrix_operation_count_reduction=False, fixed_shape_weight_decode_count_reduction=False,
        epilogue_proposal='Keep gate/up accumulators for one row in the same wave; evaluate the existing product and Sigmoid order before publishing only final SwiGLU values to per-wave transpose scratch.',
        synchronization_proposal='Replace cross-wave paired epilogue block barriers with per-wave scratch lifetime barriers; preserve every stage barrier.',
        isolation='Only nonpacked IQ2 BN64 candidate dispatch. Keep BN128/48/16, down, dense, vector decode and routing descriptors unchanged.',
        risks=['Doubled accumulators and prefetched weights can increase VGPR or private spills.',
               'Larger LDS and fewer blocks may reduce useful occupancy.',
               'A new epilogue helper can change floating-point contraction; preserve explicit product/value boundaries.',
               'Full-output and model tests are required; logical enumeration is not GPU race or arithmetic proof.'],
        candidate_implemented=False, candidate_compiled=False, gpu_run=False, model_inference=False,
        throughput_gain_established=False, goal_met=False)
    with out.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({key:report[key] for key in ('fixed_shape_grid_x','original_stage_lds_bytes',
        'proposed_stage_lds_bytes','fetched_group_owners_verified','accumulator_owners_verified',
        'output_owners_verified','candidate_implemented','gpu_run')}))


if __name__ == '__main__':
    main()
