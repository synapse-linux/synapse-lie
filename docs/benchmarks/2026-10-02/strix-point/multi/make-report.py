#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the .161 LIE reactive, direct Gufo and LIE serial multi benchmark."""
import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ARMS = ('lie', 'gufo', 'serial')
LABELS = {'lie': 'LIE reactive .161', 'gufo': 'Gufo native .161',
          'serial': 'LIE serial .161'}
EXECUTIONS = {'lie': 'LIE-reactive-ready-batch', 'gufo': 'upstream-native-batch',
              'serial': 'LIE-serial-interleaved'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source(root):
    collection = json.loads((root/'collection.json').read_text())
    assert collection['exit_code'] == 0 and collection['inventory']['result_state'] == 'PASSED'
    assert all(collection['inventory'][key] for key in
               ('supervisor_absent', 'gpu_child_absent', 'lease_free'))
    assert collection['inventory']['model_stat_unchanged']
    for file, record in collection['inventory']['files'].items():
        path = root/file
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], path
    result = json.loads((root/'result.json').read_text())
    assert result['state'] == 'PASSED' and result['exit_code'] == 0
    assert result['child_exit_code'] == 0 and result['thermal_ceiling_c'] == 100
    assert result['model_stat_unchanged'] and not result['cleanup_failures']
    assert result['service_after']['ActiveState'] == 'active'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    data = {}
    raw = {}
    for arm in ARMS:
        root = HERE/'input'/arm
        validate_source(root)
        run = report.read_result(root/'measurements.jsonl')
        ident = run['identity']
        assert ident['execution'] == EXECUTIONS[arm]
        assert (ident['suite'], ident['synthetic'], ident['warmups'],
                ident['repetitions'], ident['output_limit'], ident['pp_target']) == (
                    'multi', False, 1, 3, 128, 2048)
        assert [r['users'] for r in run['configurations']] == [1, 2, 4, 6, 8]
        assert all(r['full_output_budget'] and r['prompt_tokens'] == 2048 and
                   r['depth'] == 0 for r in run['configurations'])
        data[arm] = run
        raw[arm] = [json.loads(line) for line in (root/'measurements.jsonl').read_text().splitlines()]
    comparisons = {arm: report.compare(data['lie'], data[arm]) for arm in ('gufo', 'serial')}
    for group in comparisons.values():
        assert all(row['eligible'] and row['tokens_equal'] and row['pp_frontier_equal'] and
                   row['tg_frontier_equal'] for row in group)
    counters = {}
    for users in (1, 2, 4, 6, 8):
        rows = [r for r in raw['lie'] if r.get('event') == 'sample' and
                r['users'] == users and not r['warmup']]
        assert len(rows) == 3
        counters[str(users)] = [{key: r[key] for key in
                                 ('decode_single_calls', 'decode_batches', 'decode_batch_rows')}
                                for r in rows]
        if users > 1:
            assert all(r['decode_single_calls'] == 0 and r['decode_batches'] == 128 and
                       r['decode_batch_rows'] == 128*users for r in rows)
        else:
            assert all(r['decode_single_calls'] == 128 and r['decode_batches'] == 0 and
                       r['decode_batch_rows'] == 0 for r in rows)
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-multi-2026-10-02'
    import matplotlib.pyplot as plt
    summary = {'arms': data, 'comparisons': comparisons}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    with (out/'summary.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['arm', 'users', 'prompt_tokens_per_user', 'repetitions',
                         'pp_median_tps', 'pp_min_tps', 'pp_max_tps',
                         'tg_median_tps', 'tg_min_tps', 'tg_max_tps'])
        for arm in ARMS:
            for r in data[arm]['configurations']:
                writer.writerow([arm, r['users'], r['prompt_tokens'], r['repetitions'],
                                 *[r[metric][stat] for metric in ('prefill_tps', 'decode_tps')
                                   for stat in ('median', 'min', 'max')]])
    (out/'reactive-dispatch.json').write_text(json.dumps(counters, indent=2)+'\n')
    resources = {}
    timelines = {}
    for arm in ARMS:
        telemetry = [json.loads(line) for line in
                     (HERE/'input'/arm/'telemetry.jsonl').read_text().splitlines()]
        timelines[arm] = telemetry
        resources[arm] = {
            'observations': len(telemetry),
            'peak_c': {sensor: max(t['value_c'] for row in telemetry
                                   for t in row['temperatures'] if t['name'] == sensor)
                       for sensor in ('k10temp', 'amdgpu', 'nvme')},
            'sampled_peak_gtt_used_bytes': max(row['gpu']['mem_info_gtt_used']
                                               for row in telemetry)}
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for arm in ARMS:
        rows = data[arm]['configurations']
        for axis, metric in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
            values = [r[metric] for r in rows]
            axis.errorbar([r['users'] for r in rows], [v['median'] for v in values],
                          yerr=[[v['median']-v['min'] for v in values],
                                [v['max']-v['median'] for v in values]],
                          marker='o', capsize=3, label=LABELS[arm])
    for axis, name in ((axes[0], 'Aggregate new prefill token/s'),
                       (axes[1], 'Aggregate confirmed decode token/s')):
        axis.set(xlabel='Concurrent users', ylabel=name)
        axis.grid(alpha=.2)
        axis.legend()
    figure.suptitle('Original UD, Strix Point .161 · PP2048/TG128 per user · '
                    '1 warmup + 3 measured samples\n'
                    'Matched physical prompts, outputs and executor frontiers; '
                    'bars show observed min/max')
    figure.savefig(out/'benchmark.svg', metadata={'Date': None})
    figure.savefig(out/'benchmark.png', dpi=160)
    for axis in axes:
        axis.set_ylim(bottom=0)
    figure.savefig(out/'benchmark-zero.svg', metadata={'Date': None})
    figure.savefig(out/'benchmark-zero.png', dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for arm in ARMS:
        telemetry = timelines[arm]
        times = [datetime.datetime.fromisoformat(row['at']) for row in telemetry]
        minutes = [(value-times[0]).total_seconds()/60 for value in times]
        for sensor, suffix, style in (('k10temp', 'CPU', '-'), ('amdgpu', 'GPU', '--')):
            values = [max(t['value_c'] for t in row['temperatures'] if t['name'] == sensor)
                      for row in telemetry]
            axes[0].plot(minutes, values, linestyle=style, label=f'{arm} {suffix}')
        axes[1].plot(minutes, [row['gpu']['mem_info_gtt_used']/2**30 for row in telemetry],
                     label=arm)
    axes[0].axhline(100, color='black', linewidth=1, linestyle=':', label='CPU/GPU guard')
    axes[0].set(xlabel='Minutes since admission', ylabel='Sampled sensor °C', ylim=(0, 105))
    axes[1].set(xlabel='Minutes since admission', ylabel='Sampled whole-device GTT GiB',
                ylim=(0, None))
    for axis in axes:
        axis.grid(alpha=.2)
        axis.legend()
    figure.suptitle('Original UD multi-user · separate admitted .161 runs aligned at start\n'
                    'One-second supervisor samples; GTT includes whole device, not exact model allocation')
    figure.savefig(out/'resources.svg', metadata={'Date': None})
    figure.savefig(out/'resources.png', dpi=160)
    plt.close(figure)
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    sources = [ROOT/'tools/bench-report.py', Path(__file__).resolve(),
               *sorted((HERE/'input').rglob('*'))]
    manifest = {
        'schema': 'synapse-lie.point-multi-report.v1',
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources if p.is_file()},
        'output_sha256': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'status': 'TRIPLE_PASS', 'users': [1, 2, 4, 6, 8],
                      'all_tokens_and_frontiers_equal': True, 'output': str(out)}))


if __name__ == '__main__':
    main()
