#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and reproduce .161 memory or fresh-prefill LIE/Gufo bundles offline."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROFILES = {
    'memory': {'suite': 'memory', 'warmups': 1, 'repetitions': 1,
               'targets': [(0, 2048), (16384, 20480)], 'capacity': 133121},
    'fresh-128k': {'suite': 'fresh', 'warmups': 0, 'repetitions': 2,
                   'targets': [(0, size) for size in (1500, 8000, 8192, 32768, 131072)],
                   'capacity': 262144},
    'fresh-256k': {'suite': 'fresh', 'warmups': 0, 'repetitions': 2,
                   'targets': [(0, 258794)], 'capacity': 262144},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, profile, arm):
    collection = json.loads((root/'collection.json').read_text())
    assert collection['exit_code'] == 0 and collection['inventory']['result_state'] == 'PASSED'
    assert collection['inventory']['model_stat_unchanged']
    assert all(collection['inventory'][key] for key in
               ('supervisor_absent', 'gpu_child_absent', 'lease_free'))
    for name, record in collection['inventory']['files'].items():
        path = root/name
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], path
    manifest = json.loads((root/'manifest.json').read_text())
    assert manifest['bench_profile'] == profile and manifest['bench_impl'] == arm
    result = json.loads((root/'result.json').read_text())
    assert result['state'] == 'PASSED' and result['exit_code'] == 0
    assert result['child_exit_code'] == 0 and result['thermal_ceiling_c'] == 100
    assert result['model_stat_unchanged'] and not result['cleanup_failures']
    assert result['service_after']['ActiveState'] == 'active'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=PROFILES)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    config = PROFILES[args.profile]
    bundle = HERE/args.profile
    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    runs = {}
    resources = {}
    estimates = {}
    timelines = {}
    for arm, execution in (('lie', 'LIE-reactive-ready-batch'),
                           ('gufo', 'upstream-native-batch')):
        root = bundle/'input'/arm
        source(root, args.profile, arm)
        run = report.read_result(root/'measurements.jsonl')
        ident = run['identity']
        assert ident['suite'] == config['suite'] and ident['execution'] == execution
        assert not ident['synthetic'] and ident['warmups'] == config['warmups']
        assert ident['repetitions'] == config['repetitions'] and ident['output_limit'] == 128
        rows = [json.loads(line) for line in (root/'measurements.jsonl').read_text().splitlines()]
        inputs = [r for r in rows if r.get('event') == 'input']
        assert [(r['depth'], r['target_prompt_tokens']) for r in inputs] == config['targets']
        assert [r['context_capacity'] for r in inputs] == [config['capacity']]*len(inputs)
        assert len(run['configurations']) == len(inputs)
        assert all(r['full_output_budget'] and r['repetitions'] == config['repetitions']
                   for r in run['configurations'])
        loads = run['loading']
        assert loads and all(r['context_capacity'] == config['capacity'] and
                             r['resident_bytes_estimate'] > 0 and
                             r['session_bytes_estimate'] > 0 for r in loads)
        estimates[arm] = [{'resident_bytes_estimate': r['resident_bytes_estimate'],
                           'session_bytes_estimate': r['session_bytes_estimate']}
                          for r in loads]
        telemetry = [json.loads(line) for line in (root/'telemetry.jsonl').read_text().splitlines()]
        timelines[arm] = telemetry
        resources[arm] = {'observations': len(telemetry),
                          'peak_c': {sensor: max(t['value_c'] for row in telemetry
                                                  for t in row['temperatures'] if t['name'] == sensor)
                                     for sensor in ('k10temp', 'amdgpu', 'nvme')},
                          'sampled_peak_gtt_used_bytes': max(row['gpu']['mem_info_gtt_used']
                                                              for row in telemetry)}
        runs[arm] = run
    pairs = report.compare(runs['lie'], runs['gufo'])
    assert len(pairs) == len(config['targets']) and all(
        r['eligible'] and r['tokens_equal'] and r['pp_frontier_equal'] and
        r['tg_frontier_equal'] for r in pairs)
    thread_observations = None
    if args.profile == 'fresh-256k':
        thread_observations = json.loads((bundle/'input/thread-observations.json').read_text())
        assert thread_observations['schema'] == 'synapse-lie.point-thread-observations.v1'
        observations = thread_observations['observations']
        assert len(observations) == 2
        for arm, observation in zip(('lie', 'gufo'), observations):
            result = json.loads((bundle/'input'/arm/'result.json').read_text())
            collection = json.loads((bundle/'input'/arm/'collection.json').read_text())
            assert observation['label'] == collection['label']
            assert observation['pid'] == result['container_host_pid']
            assert observation['container_start_ticks'] == result['container_start_ticks']
            assert result['started_at'] <= observation['at'] <= result['ended_at']
            assert observation['threads_snapshot'] == observation['task_entries'] > 0
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-'+args.profile+'-2026-10-02'
    report.export(runs['lie'], out, 'LIE .161', runs['gufo'], 'Gufo .161')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    if len(config['targets']) == 1:
        for axis, key in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
            values = [runs[arm]['configurations'][0][key] for arm in ('lie', 'gufo')]
            axis.bar([0, 1], [v['median'] for v in values],
                     yerr=[[v['median']-v['min'] for v in values],
                           [v['max']-v['median'] for v in values]],
                     color=['tab:blue', 'tab:orange'], capsize=5)
            axis.set_xticks([0, 1], ['LIE .161', 'Gufo .161'])
    else:
        for label, arm in (('LIE .161', 'lie'), ('Gufo .161', 'gufo')):
            records = runs[arm]['configurations']
            x = [r['prompt_tokens'] if config['suite'] == 'fresh' else r['depth']
                 for r in records]
            for axis, key in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
                values = [r[key] for r in records]
                axis.errorbar(x, [v['median'] for v in values],
                              yerr=[[v['median']-v['min'] for v in values],
                                    [v['max']-v['median'] for v in values]],
                              marker='o', capsize=3, label=label)
    for axis, name in ((axes[0], 'New prefill token/s'), (axes[1], 'Decode token/s')):
        axis.set(xlabel='Path' if len(config['targets']) == 1 else
                 'Full physical prompt tokens' if config['suite'] == 'fresh'
                 else 'Occupied prefix tokens', ylabel=name, ylim=(0, None))
        axis.grid(alpha=.2)
        if len(config['targets']) > 1:
            axis.legend()
    figure.suptitle('Original UD on Strix Point .161 · '+args.profile+
                    ' · PP/TG direct executor rates\nExact input, output and '
                    'frontier identity; bars: observed min/max; zero-based axes')
    figure.savefig(out/'benchmark-zero.svg', metadata={'Date': None})
    figure.savefig(out/'benchmark-zero.png', dpi=160)
    if len(config['targets']) == 1:
        figure.savefig(out/'benchmark.svg', metadata={'Date': None})
        figure.savefig(out/'benchmark.png', dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for arm, label in (('lie', 'LIE'), ('gufo', 'Gufo')):
        telemetry = timelines[arm]
        times = [datetime.datetime.fromisoformat(row['at']) for row in telemetry]
        minutes = [(value-times[0]).total_seconds()/60 for value in times]
        for sensor, name, style in (('k10temp', 'CPU', '-'), ('amdgpu', 'GPU', '--')):
            values = [max(t['value_c'] for t in row['temperatures'] if t['name'] == sensor)
                      for row in telemetry]
            axes[0].plot(minutes, values, linestyle=style, label=f'{label} {name}')
        axes[1].plot(minutes, [row['gpu']['mem_info_gtt_used']/2**30 for row in telemetry],
                     label=label)
    axes[0].axhline(100, color='black', linewidth=1, linestyle=':', label='CPU/GPU guard')
    axes[0].set(xlabel='Minutes since admission', ylabel='Sampled sensor °C', ylim=(0, 105))
    axes[1].set(xlabel='Minutes since admission', ylabel='Sampled whole-device GTT GiB',
                ylim=(0, None))
    for axis in axes:
        axis.grid(alpha=.2)
        axis.legend()
    figure.suptitle('Original UD '+args.profile+' · separate admitted runs aligned at start\n'
                    'One-second supervisor samples; GTT includes whole device, not exact model allocation')
    figure.savefig(out/'resources.svg', metadata={'Date': None})
    figure.savefig(out/'resources.png', dpi=160)
    plt.close(figure)
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    (out/'size-estimates.json').write_text(json.dumps(estimates, indent=2)+'\n')
    if thread_observations is not None:
        (out/'thread-observations.json').write_text(json.dumps(thread_observations, indent=2)+'\n')
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    sources = [ROOT/'tools/bench-report.py', Path(__file__).resolve(),
               *sorted((bundle/'input').rglob('*'))]
    artifact = {'schema': 'synapse-lie.point-paired-report.v1', 'profile': args.profile,
                'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources if p.is_file()},
                'output_sha256': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(artifact, indent=2)+'\n')
    print(json.dumps({'status': 'PAIRED_PASS', 'profile': args.profile,
                      'points': len(pairs), 'all_tokens_and_frontiers_equal': True,
                      'output': str(out)}))


if __name__ == '__main__':
    main()
