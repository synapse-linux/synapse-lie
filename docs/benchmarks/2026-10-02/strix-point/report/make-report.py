#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the recorded Strix Point smoke report offline; never access a GPU."""
import argparse
import csv
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    return dict(mean=statistics.mean(values), median=statistics.median(values),
                min=min(values), max=max(values), all=values)


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    out = args.output
    receipt_path = HERE.parent/'core-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    for path in sorted((HERE/'input').iterdir()):
        expected = receipt['raw_sha256'][f'evidence/strix-point-core-ud-r1/{path.name}']
        require(sha(path) == expected, f'Input hash mismatch: {path.name}')
    result = receipt['result']
    require(result['state'] == 'PASSED' and result['exit_code'] == 0 and
            result['child_exit_code'] == 0 and not result['cleanup_failures'], 'Campaign failed')
    require(result['model_stat_unchanged'] and
            result['models_before'] == result['models_after'], 'Model identity drift')
    require(not result['final_container_state']['OOMKilled'], 'OOM recorded')
    require(all(receipt['postflight'][k] for k in
                ('supervisor_absent', 'gpu_child_absent', 'lease_free')), 'Incomplete retirement')
    require(result['service_after']['ActiveState'] == 'active', 'Service not restored')
    source = HERE/'input/measurements.jsonl'
    raw = [json.loads(line) for line in source.read_text().splitlines()]
    require(raw == receipt['measurements'] == result['measurements'], 'Receipt measurement drift')
    spec = importlib.util.spec_from_file_location('bench_report', ROOT/'tools/bench-report.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    data = bench.read_result(source)
    identity = data['identity']
    require(not identity['synthetic'] and identity['users'] == 1 and
            identity['warmups'] == 1 and identity['repetitions'] == 3 and
            identity['cache_policy'] == 'ram', 'Unexpected recorded campaign configuration')
    jobs, samples = data['jobs'], data['samples']
    require(all(j['output_ids'] == jobs[0]['output_ids'] for j in jobs), 'Output repeatability drift')
    rows = []
    for job, sample in zip(jobs, samples, strict=True):
        row = {k: v for k, v in job.items() if k not in ('event', 'output_ids')}
        row.update({f'sample_{k}': v for k, v in sample.items()
                    if k not in ('event', 'rep', 'warmup', 'users')})
        row['prefill_tps'] = job['prefill_tokens']*1e9/job['prefill_ns'] if job['prefill_ns'] else None
        row['decode_tps'] = job['output_tokens']*1e9/job['decode_ns']
        rows.append(row)
    measured = [r for r in rows if not r['warmup']]
    metrics = {k: stats([r[k] for r in measured]) for k in (
        'decode_tps', 'sample_output_per_total_wall_tps', 'first_token_ns',
        'cache_restore_ns', 'decode_ns', 'total_ns', 'sample_wall_ns')}
    telemetry = [json.loads(line) for line in (HERE/'input/telemetry.jsonl').read_text().splitlines()]
    start = datetime.fromisoformat(telemetry[0]['at'])
    telemetry_rows = []
    temperatures = []
    for record in telemetry:
        seconds = (datetime.fromisoformat(record['at'])-start).total_seconds()
        row = dict(at=record['at'], elapsed_s=seconds, **record['memory'], **record['gpu'])
        for name in ('k10temp', 'amdgpu', 'nvme'):
            selected = [t for t in record['temperatures'] if t['name'] == name]
            require(bool(selected), f'Missing sensor family: {name}')
            row[f'{name}_max_c'] = max(t['value_c'] for t in selected)
        for sensor in record['temperatures']:
            require(sensor['value_c'] < sensor['limit_c'], 'Thermal guard violation')
            temperatures.append(dict(at=record['at'], elapsed_s=seconds, **sensor))
        owned = [p for p in record['dri'] if p['pid'] == result['container_host_pid']
                 and p['start_ticks'] == result['container_start_ticks']
                 and f'docker-{result["container"]}.scope' in p['cgroup']]
        require(len(owned) <= 1, 'Duplicate process observation')
        status = owned[0].get('status', {}) if owned else {}
        row['process_threads'] = int(status['Threads']) if 'Threads' in status else None
        for field in ('VmRSS', 'VmHWM', 'VmSwap'):
            value = status.get(field)
            if value:
                number, unit = value.split()
                require(unit == 'kB', 'Unexpected proc status unit')
                row[f'{field}_bytes'] = int(number)*1024
            else:
                row[f'{field}_bytes'] = None
        row['system_swap_used_bytes'] = row['SwapTotal']-row['SwapFree']
        telemetry_rows.append(row)
    require(all(a['elapsed_s'] < b['elapsed_s'] for a, b in
                zip(telemetry_rows, telemetry_rows[1:])), 'Reordered telemetry')
    resource_keys = ('k10temp_max_c', 'amdgpu_max_c', 'nvme_max_c', 'MemAvailable',
                     'mem_info_gtt_used', 'mem_info_vram_used', 'gpu_busy_percent',
                     'VmRSS_bytes', 'VmHWM_bytes', 'VmSwap_bytes', 'system_swap_used_bytes')
    resources = {key: stats([r[key] for r in telemetry_rows if r[key] is not None])
                 for key in resource_keys}
    summary = dict(schema='synapse-lie.strix-point-report.v1', scope=receipt['scope'],
                   identity=identity, load_to_ready_ns=data['loading'][0]['load_to_ready_ns'],
                   warmup=rows[0], measured=metrics, resources=resources,
                   observed_process_threads=sorted({r['process_threads'] for r in telemetry_rows
                                                    if r['process_threads'] is not None}),
                   telemetry_records=len(telemetry_rows),
                   telemetry_interval_seconds=stats([b['elapsed_s']-a['elapsed_s'] for a, b in
                                                     zip(telemetry_rows, telemetry_rows[1:])]),
                   output_ids_identical=True, comparison=None)
    out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-ud-r1'
    # The shared reader validates core accounting and exports the normal benchmark view.
    bench.export(data, out/'core', 'LIE .161')
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    write_csv(out/'samples.csv', rows)
    write_csv(out/'telemetry.csv', telemetry_rows)
    write_csv(out/'temperatures.csv', temperatures)
    flat = [dict(metric=key, **{k: v for k, v in value.items() if k != 'all'})
            for key, value in metrics.items()]
    write_csv(out/'statistics.csv', flat)

    def save(fig, name):
        fig.savefig(out/f'{name}.svg', metadata={'Date': None})
        fig.savefig(out/f'{name}.png', dpi=160)
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    labels = ['First / fresh\n(warmup)', 'RAM hit 1', 'RAM hit 2', 'RAM hit 3']
    panels = [
        (('decode_tps', 'Decode'), ('sample_output_per_total_wall_tps', 'Complete client wall')),
        (('first_token_ns', 'First confirmed token'),),
        (('prefill_ns', 'Fresh prefill'), ('cache_capture_ns', 'RAM capture'), ('cache_restore_ns', 'RAM restore')),
        (('decode_ns', 'Decode'), ('total_ns', 'Job total'))]
    for index, (ax, series) in enumerate(zip(axes.flat, panels)):
        scale = 1 if index == 0 else 1e-6
        width = .8/len(series)
        for offset, (key, label) in enumerate(series):
            x = [i-.4+width*(offset+.5) for i in range(len(rows))]
            bars = ax.bar(x, [r[key]*scale for r in rows], width, label=label)
            if index < 2:
                ax.bar_label(bars, fmt='%.2f', fontsize=8, padding=3)
        ax.set_xticks(range(4), labels)
        ax.set_ylabel('Confirmed output tokens/s' if index == 0 else 'Milliseconds')
        ax.set_ylim(0, ax.get_ylim()[1]*1.16)
        ax.grid(axis='y', alpha=.2)
        ax.legend(fontsize=8, loc='upper right')
    fig.suptitle('Strix Point original UD · C1 · 9 prompt / 32 output tokens\n'
                 'First fresh sample shown separately; three RAM-hit measurements; no HTTP')
    save(fig, 'timings')

    fig, axes = plt.subplots(3, 2, figsize=(12, 10), layout='constrained')
    x = [r['elapsed_s'] for r in telemetry_rows]

    def line(ax, key, label, divisor=1):
        ax.plot(x, [r[key]/divisor if r[key] is not None else float('nan')
                    for r in telemetry_rows], marker='.', label=label)

    ax = axes[0, 0]
    for key, label in [('k10temp_max_c', 'CPU'), ('amdgpu_max_c', 'GPU'), ('nvme_max_c', 'NVMe maximum')]:
        line(ax, key, label)
    ax.axhline(85, color='#a93226', linestyle='--', label='Guard 85 C')
    ax.set_ylabel('Temperature (C)'); ax.set_ylim(25, 90)
    line(axes[0, 1], 'mem_info_gtt_used', 'GTT used', 2**30)
    axes[0, 1].axhline(96, color='#a93226', linestyle='--', label='GTT limit 96 GiB')
    axes[0, 1].set_ylabel('GiB'); axes[0, 1].set_ylim(0, 103)
    line(axes[1, 0], 'MemAvailable', 'System MemAvailable', 2**30)
    axes[1, 0].set_ylabel('GiB'); axes[1, 0].set_ylim(bottom=0)
    line(axes[1, 1], 'VmRSS_bytes', 'Owned process RSS', 2**20)
    line(axes[1, 1], 'mem_info_vram_used', 'Whole-device VRAM used', 2**20)
    axes[1, 1].set_ylabel('MiB (overlapping accounting)'); axes[1, 1].set_ylim(bottom=0)
    line(axes[2, 0], 'process_threads', 'Observed process threads')
    axes[2, 0].set_ylabel('Threads, including runtime'); axes[2, 0].set_ylim(0, 50)
    line(axes[2, 1], 'gpu_busy_percent', 'Whole-device GPU busy')
    axes[2, 1].set_ylabel('Percent'); axes[2, 1].set_ylim(0, 110)
    for ax in axes.flat:
        ax.set_xlabel('Seconds since first telemetry record (11:14:12.231 UTC)')
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('Strix Point original UD · sampled loading, inference and retirement\n'
                 '27 observations; memory series overlap; process gaps are missing observations')
    save(fig, 'resources')
    # Normalize generated text for repository whitespace checks, before hashing.
    # Raw input files remain byte-for-byte unchanged.
    for path in sorted(out.rglob('*')):
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    artifacts = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                 if p.is_file() and 'matplotlib-cache' not in p.parts}
    sources = [Path(__file__).resolve(), receipt_path, ROOT/'tools/bench-report.py',
               *sorted((HERE/'input').iterdir())]
    manifest = dict(schema='synapse-lie.offline-report.v1',
                    source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sources},
                    artifact_sha256=artifacts, matplotlib_version=matplotlib.__version__,
                    validation='Receipt hashes, complete core accounting, identical IDs, '
                               'model stat preservation, exit codes, closure and thermal samples')
    (out/'report-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(output=str(out), state='PASSED', samples=len(rows),
                          telemetry_records=len(telemetry_rows), artifacts=len(artifacts))))


if __name__ == '__main__':
    main()
