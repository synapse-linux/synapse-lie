#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the active F16 producer/consumer boundary; no model execution."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'config/q2-down-register-scatter-pair-source.json'
    provider = json.loads(manifest_path.read_text())['variants']['down-register-scatter']
    base = ROOT / provider['source']
    prefix = 'src/models/qwen38_flash_next/kernels/rocm/'
    paths = [prefix + name for name in ('kernels.hip.cpp', 'executor.cpp',
                                       'q2_scaled_input.inc', 'q2_down_half_storage.inc')]
    code = {}
    for rel in paths:
        assert sha(base / rel) == provider['files'][rel], rel
        code[Path(rel).name] = (base / rel).read_text()
    kernel, pack, down, executor = (code[k] for k in
        ('kernels.hip.cpp', 'q2_scaled_input.inc', 'q2_down_half_storage.inc', 'executor.cpp'))
    assert 'constexpr int kRows = kPair ? BM / 2 : BM;' in kernel
    assert 'RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>' in kernel
    assert 'constexpr unsigned cols = 640;' in pack
    assert '13 - exponent' in pack and 'float4 values[5];' in pack
    assert 'dim3(static_cast<unsigned>((m + 127) / 128), n_tiles)' in down
    assert '!PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,' in executor
    slots, ff, hidden = 2048 * 10, 640, 2560
    producer_blocks, consumer_blocks = ff // (128 // 2), hidden // 128
    f32, f16 = slots * ff * 4, slots * ff * 2
    baseline = f32 + f32 + f16 + consumer_blocks * f16
    direct_f32 = f32 + consumer_blocks * f32
    assert producer_blocks == 10 and consumer_blocks == 20
    assert baseline == 625 * 1024**2 and direct_f32 == 1050 * 1024**2
    # This is storage arithmetic for prospective layouts, not a compiled kernel.
    simultaneous_bm, bn, bk = 2 * ff, 128, 2
    simultaneous_staging = simultaneous_bm * 4 * 16 + bk * simultaneous_bm * 4 + bk * 4 * (bn + 1) * 16
    serial_bn = 16
    serial_stage = 128 * 4 * 16 + bk * 128 * 4 + bk * 4 * (serial_bn + 1) * 16
    report = dict(schema='synapse-lie.q2-producer-fusion-boundary.v1',
        parent_manifest_sha256=sha(manifest_path), parent_prefill_tok_s=1580.226725,
        inspected_source={str((base / p).relative_to(ROOT)): sha(base / p) for p in paths},
        fixed_shape=dict(tokens=2048, used=10, expert_ff=640, hidden=2560,
                         gate_columns_per_cta=64, gate_ctas_per_complete_row=producer_blocks,
                         down_output_rows_per_cta=128, down_ctas_per_complete_output=consumer_blocks),
        logical_payload_bytes=dict(gate_f32_write=f32, pack_f32_read=f32,
            pack_half_write=f16, down_half_reads_all_output_tiles=consumer_blocks * f16,
            baseline_total=baseline, direct_f32_down_total=direct_f32,
            direct_f32_extra_per_layer=direct_f32 - baseline,
            direct_f32_extra_across48_layers=(direct_f32 - baseline) * 48,
            producer_fusion_potential_removed_write_read=2 * f32),
        storage_sketches=dict(simultaneous_pair_rows=simultaneous_bm,
            simultaneous_bn128_stage_bytes=simultaneous_staging,
            sequential_bn16_stage_plus_complete_row_bytes=serial_stage + serial_bn * ff * 4),
        findings=[
            'Current whole-row power-of-two scale depends on all ten64-column producer CTAs. Fusing the existing pack into one producer epilogue needs cross-CTA coordination or a different ownership layout.',
            'Reading F32 and packing independently inside all20 down output tiles increases unpadded logical payload demand625 to1050MiB/layer. Cache and routing padding are not modeled; this is not measured DRAM traffic.',
            'A last-producer counter design could remove a launch but still reads/writes the F32 intermediate and adds global publication/reset costs. It does not remove the requested buffer pass.',
            'Per64-column scales need rescaling or restored partial accumulation in down; rounding at subnormal boundaries must be qualified. They do not preserve the original whole-row contract by algebra alone.',
            'A simultaneous full640-column pair needs a new1280-row physical tile; the existing template admits only BM128/256. Sequential64-column computation at BN16 reduces activation reuse across tokens versus the current64/128 paths. Neither is implemented or measured.',
        ],
        next_boundary='Design whole-row ownership or a precision-preserving compact producer representation before replacing the current half consumer. Keep full fusion open; do not promote the direct F32 consumer from source traffic arithmetic.',
        padded_route_demand_modeled=False, cache_hits_measured=False,
        hardware_transactions_measured=False, rejected_all_fusion=False,
        gpu_run=False, model_inference=False, performance_gain=False, goal_met=False)
    with (ROOT / 'config/q2-producer-fusion-boundary.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(gate_blocks=producer_blocks, down_blocks=consumer_blocks,
                          baseline_logical_mib=baseline / 1024**2,
                          direct_f32_logical_mib=direct_f32 / 1024**2,
                          simultaneous_stage_bytes=simultaneous_staging, gpu_run=False)))


if __name__ == '__main__':
    main()
