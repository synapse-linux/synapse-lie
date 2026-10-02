#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce a diagnostic of the incomplete .161 thermal-stop benchmark offline."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    receipt = json.loads((HERE/'input/collection.json').read_text())
    assert receipt['exit_code'] == 0 and receipt['inventory']['result_state'] == 'FAILED'
    for name, identity in receipt['inventory']['files'].items():
        file = HERE/'input'/name
        assert file.stat().st_size == identity['bytes'] and sha(file) == identity['sha256'], name
    result = json.loads((HERE/'input/result.json').read_text())
    assert result['error'] == "RuntimeError('Thermal limit')" and result['exit_code'] == 1
    assert result['model_stat_unchanged'] and not result['cleanup_failures']
    assert result['service_after']['ActiveState'] == 'active'
    assert all(receipt['inventory'][key] for key in ('supervisor_absent', 'gpu_child_absent', 'lease_free'))
    rows = [json.loads(line) for line in (HERE/'input/measurements.jsonl').read_text().splitlines()]
    assert rows[0]['schema'] == 'synapse-lie.bench.v1' and rows[0]['suite'] == 'single'
    assert rows[-1]['event'] == 'failed' and rows[-1]['exit_code'] == 1
    points = {r['point']: r for r in rows if r['event'] == 'input'}
    samples = [r for r in rows if r['event'] == 'sample']
    assert len(samples) == 4 and [r['point'] for r in samples] == [0, 0, 1, 1]
    assert all(r['full_output_budget'] and r['output_tokens'] == 128 for r in samples)
    assert any(r['event'] == 'sample_begin' and r['point'] == 2 for r in rows)
    telemetry = [json.loads(line) for line in (HERE/'input/telemetry.jsonl').read_text().splitlines()]
    start = datetime.fromisoformat(telemetry[0]['at'])
    series = []
    for r in telemetry:
        values = {name: max(t['value_c'] for t in r['temperatures'] if t['name'] == name)
                  for name in ('k10temp', 'amdgpu', 'nvme')}
        series.append({'elapsed_s': (datetime.fromisoformat(r['at'])-start).total_seconds(),
                       'cpu_c': values['k10temp'], 'gpu_c': values['amdgpu'],
                       'nvme_c': values['nvme'], 'gtt_used_gib': r['gpu']['mem_info_gtt_used']/2**30})
    assert max(r['cpu_c'] for r in series) >= 85
    sample_rows = []
    for r in samples:
        p = points[r['point']]
        sample_rows.append({'point': r['point'], 'depth': r['depth'], 'prompt_tokens': r['prompt_tokens'],
                            'physical_ids_sha256': p['physical_ids_sha256'], 'rep': r['rep'],
                            'warmup': r['warmup'], 'prefill_tokens': r['prefill_tokens_per_user'],
                            'prefill_ns': r['prefill_ns'], 'prefill_tps': r['prefill_tps'],
                            'decode_ns': r['decode_ns'], 'decode_tps': r['decode_tps'],
                            'output_tokens': r['output_tokens'], 'full_output_budget': r['full_output_budget']})
    summary = {'schema': 'synapse-lie.point-thermal-attempt.v1', 'status': 'FAILED_THERMAL',
               'campaign_exit_code': 1, 'completed_points': [0, 4096],
               'interrupted_point': 8192, 'samples': sample_rows,
               'peak_c': {name: max(r[name+'_c'] for r in series) for name in ('cpu', 'gpu', 'nvme')},
               'sampled_gtt_used_max_bytes': max(r['gpu']['mem_info_gtt_used'] for r in telemetry),
               'model_stat_unchanged': True, 'service_restored': True, 'lease_free': True,
               'valid_full_campaign': False}
    out = args.output; out.mkdir(parents=True, exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    for name, data in [('samples.csv', sample_rows), ('telemetry.csv', series)]:
        with (out/name).open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(data[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(data)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-thermal-2026-10-02'
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for name, label in [('cpu', 'CPU'), ('gpu', 'GPU'), ('nvme', 'NVMe maximum')]:
        axes[0].plot([r['elapsed_s'] for r in series], [r[name+'_c'] for r in series], label=label)
    axes[0].axhline(85, color='#a93226', linestyle='--', label='Guard 85 C')
    axes[0].set(xlabel='Seconds since first observation', ylabel='Temperature (C)', ylim=(25, 90))
    axes[0].legend(); axes[0].grid(alpha=.2)
    measured = [r for r in sample_rows if not r['warmup']]
    depths = [r['depth'] for r in measured]
    pp_line = axes[1].plot(depths, [r['prefill_tps'] for r in measured],
                           marker='o', color='#1f77b4', label='New prefill token/s')
    tg_axis = axes[1].twinx()
    tg_line = tg_axis.plot(depths, [r['decode_tps'] for r in measured],
                           marker='s', color='#d95f02', label='Decode token/s')
    axes[1].set(xlabel='Completed occupied prefix tokens', ylabel='Prefill token/s',
                xlim=(-250, 4350), ylim=(0, 550))
    tg_axis.set(ylabel='Decode token/s', ylim=(0, 14))
    axes[1].grid(alpha=.2)
    axes[1].legend(pp_line+tg_line, ['Prefill', 'Decode'], loc='lower left')
    fig.suptitle('INCOMPLETE Strix Point single-user AR attempt · thermal stop at 85 C')
    fig.savefig(out/'diagnostic.svg', metadata={'Date': None})
    fig.savefig(out/'diagnostic.png', dpi=160)
    plt.close(fig)
    for file in out.glob('*.svg'):
        file.write_text('\n'.join(line.rstrip() for line in file.read_text().splitlines())+'\n')
    (out/'artifact-sha256.json').write_text(json.dumps({p.name:sha(p) for p in sorted(out.iterdir())
                                                       if p.is_file()},indent=2)+'\n')
    print(json.dumps({'output': str(out), 'status': summary['status'],
                      'completed_points': summary['completed_points'], 'telemetry_records': len(series)}))


if __name__ == '__main__':main()
