#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reuse saved routing evidence to bound a new short-expert IQ2 hypothesis."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / 'config/q2-iq2-tail-audit.json'
    if output.exists():
        raise ValueError('Refusing to overwrite retained audit')
    parent_path = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT / parent['source']
    names = ['src/models/qwen38_flash_next/kernels/rocm/' + name for name in
             ('executor.cpp', 'iq2_mixed_tiles.c', 'iq2_mixed_tiles.h', 'kernels.hip.cpp')]
    for name in names:
        if sha(base / name) != parent['files'][name]:
            raise ValueError('Measured parent source changed: ' + name)
    evidence = ROOT / 'config/q2-iq2-raw-selective-model-results.json'
    saved = json.loads(evidence.read_text())
    if saved['checks']['best_parent']['changed_files'] or not saved['within_arm_exact']:
        raise ValueError('Saved composition does not match parent model files')
    records = saved['routing_records']
    if len(records) != 192:
        raise ValueError('Saved routing coverage changed')
    for i, row in enumerate(records):
        if (row['index'] != i or len(row['histogram']) != 6 or
                sum(row['histogram']) != 512 or
                {k:v for k,v in row.items() if k != 'index'} !=
                {k:v for k,v in records[i % 48].items() if k != 'index'}):
            raise ValueError('Routing session histogram changed')
    bins = [sum(row['histogram'][i] for row in records[:48]) for i in range(6)]
    active = sum(bins[1:])
    mapping = (base / names[1]).read_text()
    executor = (base / names[0]).read_text()
    kernels = (base / names[3]).read_text()
    if ('const uint32_t groups = (counts[e] + 63u) / 64u;' not in mapping or
            'routed_iq2_tail_tiles_, 64)' not in executor or
            'case 48:\n      LaunchRoutedIQ2<48, kPacked>' not in kernels):
        raise ValueError('Active map or available dispatch changed')
    report = dict(schema='synapse-lie.q2-iq2-tail-audit.v1',
        parent_manifest_sha256=sha(parent_path), saved_model_result_sha256=sha(evidence),
        sources={name:sha(base / name) for name in names},
        evidence_scope='Saved IQ2 raw plus selective-Q2-down composition; '
                       '48 layers from one of four identical routing sessions. '
                       'Not a fresh current-best trace or throughput reference.',
        histogram_bins=['0', '1..48', '49..128', '129..255', '256..511', '>=512'],
        histogram_totals=bins, active_expert_layer_buckets=active,
        short_expert_layer_buckets=bins[1], short_fraction_of_active_buckets=bins[1] / active,
        current_full_short_bucket_tile_width=64, available_new_tile_width=48,
        hypothetical_short_bucket_reserved_rows=[64 * bins[1], 48 * bins[1]],
        hypothetical_reserved_row_reduction=16 * bins[1],
        proposed_boundary='Only entire nonempty expert buckets with count<=48, '
                          'at offset zero. Preserve existing128/64 maps for other '
                          'experts and all Q2 down routing/activation arithmetic.',
        no_extra_count_download_needed=True, exact_per_expert_counts_retained=False,
        width16_eligibility_unknown_from_saved_bin=True,
        risks='More dispatch spans, changed occupancy/reuse and map capacity may '
              'erase savings. Existing BN48 code does not qualify new mixed dispatch. '
              'Do not change hot-expert tails from64 to48 with the old encoded '
              'tile index: their starting row need not be divisible by48.',
        qualification='New bounded C17 map, capacity/tail cases, complete mixed '
                      'outputs and original exact2048/tg128 model are required.',
        new_provider_implemented=False, gpu_run=False, performance_gain=False,
        numerical_acceptance=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources', 'risks', 'qualification')}))


if __name__ == '__main__':
    main()
