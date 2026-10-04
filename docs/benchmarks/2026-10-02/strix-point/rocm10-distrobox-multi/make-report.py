#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and plot ROCm 10 Distrobox and earlier ROCm 7.2 multi-user runs."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OLD = HERE.parent/'multi/input'
ARMS = ('lie', 'gufo', 'serial')
EXECUTIONS = {'lie': 'LIE-reactive-ready-batch',
              'gufo': 'upstream-native-batch',
              'serial': 'LIE-serial-interleaved'}
USERS = (1, 2, 4, 6, 8)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_receipts():
    source = HERE/'input'
    collection = json.loads((source/'collection.json').read_text())
    assert collection['schema'] == 'synapse-lie.point-rocm10-distrobox-multi.v1'
    assert collection['remote_files_verified'] > 0 and collection['hash_mismatches'] == 0
    assert all(code == 0 for code in collection['collection_command_exits'].values())
    postflight = collection['postflight']
    assert postflight[0] == collection['kernel']
    assert len(postflight) == 6 and postflight[2] == 'ActiveState=active'
    assert postflight[3] == postflight[1].removeprefix('MainPID=')
    assert postflight[4].startswith('ID ') and postflight[5] == 'lease_exit:0'
    hashes = {}
    for line in (source/'remote-sha256.txt').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        hashes[relative] = digest
    assert len(hashes) == collection['remote_files_verified']
    for arm in ARMS:
        run = source/arm
        result = json.loads((run/'result.json').read_text())
        manifest = json.loads((run/'manifest.json').read_text())
        assert (manifest['action'], manifest['stack'], manifest['transport'],
                manifest['bench_profile'], manifest['bench_impl']) == (
                    'bench', 'rocm10-fedora43', 'distrobox',
                    'multi-serial' if arm == 'serial' else 'multi',
                    'gufo' if arm == 'gufo' else 'lie')
        assert manifest['image'] == collection['docker_image_id']
        assert result['manifest_sha256'] == sha(run/'manifest.json')
        assert result['runner_sha256'] == sha(run/'runner.py')
        assert result['state'] == 'PASSED' and result['exit_code'] == 0
        assert int((run/'supervisor.exit').read_text()) == 0
        assert result['child_exit_code'] == 0 and result['bench_result']['samples'] == 20
        assert result['model_stat_unchanged'] and not result['cleanup_failures']
        assert result['service_after']['ActiveState'] == 'active'
        assert result['lease_released_at']
        for path in run.iterdir():
            remote = f'rocm10-point-distrobox-multi-{arm}-kernel715-r1/{path.name}'
            assert sha(path) == hashes[remote], path
    return collection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New output directory')
    args = parser.parse_args()
    collection = validate_receipts()
    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    runs = {}
    counters = {}
    resources = {}
    for stack, folder in (('rocm10', HERE/'input'), ('rocm7', OLD)):
        runs[stack] = {}
        for arm in ARMS:
            path = folder/arm/'measurements.jsonl'
            result = report.read_result(path)
            identity = result['identity']
            assert (identity['suite'], identity['synthetic'], identity['execution'],
                    identity['warmups'], identity['repetitions'], identity['pp_target'],
                    identity['output_limit']) == ('multi', False, EXECUTIONS[arm],
                                                  1, 3, 2048, 128)
            assert tuple(r['users'] for r in result['configurations']) == USERS
            assert all(r['full_output_budget'] and r['prompt_tokens'] == 2048
                       for r in result['configurations'])
            runs[stack][arm] = result
            if stack == 'rocm10':
                telemetry = [json.loads(line) for line in
                             (folder/arm/'telemetry.jsonl').read_text().splitlines()]
                resources[arm] = {
                    'observations': len(telemetry),
                    'peak_c': {name: max(t['value_c'] for row in telemetry
                                         for t in row['temperatures'] if t['name'] == name)
                               for name in ('k10temp', 'amdgpu', 'nvme')},
                    'sampled_peak_gtt_used_bytes': max(row['gpu']['mem_info_gtt_used']
                                                       for row in telemetry)}
                if arm == 'lie':
                    samples = [json.loads(line) for line in path.read_text().splitlines()]
                    for users in USERS:
                        group = [row for row in samples if row.get('event') == 'sample'
                                 and row['users'] == users and not row['warmup']]
                        assert len(group) == 3
                        counters[str(users)] = [{key: row[key] for key in
                                                 ('decode_single_calls', 'decode_batches',
                                                  'decode_batch_rows')} for row in group]
                        if users > 1:
                            assert all(row['decode_single_calls'] == 0 and
                                       row['decode_batches'] == 128 and
                                       row['decode_batch_rows'] == 128*users for row in group)
                        else:
                            assert all(row['decode_single_calls'] == 128 and
                                       row['decode_batches'] == 0 for row in group)

    same_stack = {stack: {arm: report.compare(runs[stack]['lie'], runs[stack][arm])
                          for arm in ('gufo', 'serial')} for stack in ('rocm10', 'rocm7')}
    cross_stack = {arm: report.compare(runs['rocm10'][arm], runs['rocm7'][arm])
                   for arm in ARMS}
    quality = {'same_stack': {stack: {arm: all(row['eligible'] and row['tokens_equal']
                                                and row['pp_frontier_equal']
                                                and row['tg_frontier_equal'] for row in rows)
                                      for arm, rows in peers.items()}
                              for stack, peers in same_stack.items()},
               'cross_stack': {arm: [{'users': row['users'],
                                      'output_equal': row['tokens_equal'],
                                      'prefill_frontier_equal': row['pp_frontier_equal'],
                                      'decode_frontier_equal': row['tg_frontier_equal']}
                                     for row in rows] for arm, rows in cross_stack.items()}}
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    (out/'quality.json').write_text(json.dumps(quality, indent=2)+'\n')
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    (out/'reactive-dispatch.json').write_text(json.dumps(counters, indent=2)+'\n')
    with (out/'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('stack', 'arm', 'users', 'pp_median_tps', 'pp_min_tps',
                         'pp_max_tps', 'tg_median_tps', 'tg_min_tps', 'tg_max_tps'))
        for stack in ('rocm10', 'rocm7'):
            for arm in ARMS:
                for row in runs[stack][arm]['configurations']:
                    writer.writerow((stack, arm, row['users'],
                                     *[row[metric][field] for metric in ('prefill_tps', 'decode_tps')
                                       for field in ('median', 'min', 'max')]))
    with (out/'comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('arm', 'users', 'pp_rocm7_tps', 'pp_rocm10_tps',
                         'pp_change_percent', 'tg_rocm7_tps', 'tg_rocm10_tps',
                         'tg_change_percent', 'output_equal',
                         'prefill_frontier_equal', 'decode_frontier_equal'))
        for arm in ARMS:
            for old, new, check in zip(runs['rocm7'][arm]['configurations'],
                                       runs['rocm10'][arm]['configurations'],
                                       cross_stack[arm], strict=True):
                pp0, pp1 = old['prefill_tps']['median'], new['prefill_tps']['median']
                tg0, tg1 = old['decode_tps']['median'], new['decode_tps']['median']
                writer.writerow((arm, old['users'], pp0, pp1, 100*(pp1/pp0-1),
                                 tg0, tg1, 100*(tg1/tg0-1), check['tokens_equal'],
                                 check['pp_frontier_equal'], check['tg_frontier_equal']))
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-point-rocm10-distrobox-multi-2026-10-02'
    import matplotlib.pyplot as plt
    colors = {'lie': '#1f77b4', 'gufo': '#ff7f0e', 'serial': '#2ca02c'}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for stack, style in (('rocm10', '-'), ('rocm7', '--')):
        for arm in ARMS:
            rows = runs[stack][arm]['configurations']
            for axis, metric in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
                values = [row[metric] for row in rows]
                axis.errorbar(USERS, [v['median'] for v in values],
                              yerr=[[v['median']-v['min'] for v in values],
                                    [v['max']-v['median'] for v in values]],
                              color=colors[arm], linestyle=style, marker='o',
                              capsize=2, label=f'{arm} {stack}')
    for axis, title in ((axes[0], 'Aggregate new prefill tokens/s'),
                        (axes[1], 'Aggregate confirmed decode tokens/s')):
        axis.set(xlabel='Concurrent engine sessions', ylabel=title)
        axis.grid(alpha=.2)
        axis.legend(fontsize=7)
    fig.suptitle('Original UD · direct multi-user engine · PP2048/TG128 per user\n'
                 'Solid: ROCm 10 / kernel 7.1.5 / Distrobox; dashed: ROCm 7.2 / kernel 6.16.3 / Docker')
    fig.savefig(out/'benchmark.svg', metadata={'Date': None})
    fig.savefig(out/'benchmark.png', dpi=160)
    for axis in axes:
        axis.set_ylim(bottom=0)
    fig.savefig(out/'benchmark-zero.svg', metadata={'Date': None})
    fig.savefig(out/'benchmark-zero.png', dpi=160)
    plt.close(fig)
    shutil.rmtree(out/'matplotlib-cache', ignore_errors=True)
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    inputs = [ROOT/'tools/bench-report.py', Path(__file__).resolve(),
              *sorted(p for p in (HERE/'input').rglob('*') if p.is_file()),
              *[OLD/arm/'measurements.jsonl' for arm in ARMS]]
    hashes = {'schema': 'synapse-lie.point-rocm10-distrobox-multi-report.v1',
              'source_sha256': {str(path.relative_to(ROOT)): sha(path) for path in inputs},
              'output_sha256': {path.name: sha(path) for path in sorted(out.iterdir())
                                if path.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps({'status': 'PASSED', 'remote_files_verified': collection['remote_files_verified'],
                      'quality': quality['same_stack'], 'output': str(out)}))


if __name__ == '__main__':
    main()
