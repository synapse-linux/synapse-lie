#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the matched .161 LIE/Gufo eight-depth direct benchmark offline."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    data = {}
    for name in ('lie', 'gufo'):
        root = HERE/'input'/name
        collection = json.loads((root/'collection.json').read_text())
        assert collection['exit_code'] == 0 and collection['inventory']['result_state'] == 'PASSED'
        assert all(collection['inventory'][key] for key in ('supervisor_absent', 'gpu_child_absent', 'lease_free'))
        for file, record in collection['inventory']['files'].items():
            path = root/file
            assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], path
        result = json.loads((root/'result.json').read_text())
        assert result['state'] == 'PASSED' and result['exit_code'] == 0 and result['child_exit_code'] == 0
        assert result['thermal_ceiling_c'] == 100
        assert result['model_stat_unchanged'] and not result['cleanup_failures']
        assert result['service_after']['ActiveState'] == 'active'
        data[name] = root
    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    lie = report.read_result(data['lie']/'measurements.jsonl')
    gufo = report.read_result(data['gufo']/'measurements.jsonl')
    assert lie['identity']['execution'] == 'LIE-reactive-ready-batch'
    assert gufo['identity']['execution'] == 'upstream-native-batch'
    assert all(x['identity']['suite'] == 'single' and x['identity']['repetitions'] == 1 and
               x['identity']['warmups'] == 1 and x['identity']['output_limit'] == 128
               for x in (lie, gufo))
    pairs = report.compare(lie, gufo)
    expected_depths = [0, 4096, 8192, 12288, 16384, 32768, 65536, 131072]
    assert [p['depth'] for p in pairs] == expected_depths
    assert all(p['eligible'] and p['tokens_equal'] and p['pp_frontier_equal'] and
               p['tg_frontier_equal'] for p in pairs)
    out = args.output;out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-full-single-2026-10-02'
    report.export(lie, out, 'LIE .161', gufo, 'Gufo .161')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for label, source in (('LIE .161', lie), ('Gufo .161', gufo)):
        records = source['configurations']
        for axis, key in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
            axis.plot([r['depth'] for r in records], [r[key]['median'] for r in records],
                      marker='o', label=label)
    for axis, name in ((axes[0], 'New prefill token/s'), (axes[1], 'Decode token/s')):
        axis.set(xlabel='Occupied prefix tokens', ylabel=name, ylim=(0, None))
        axis.grid(alpha=.2); axis.legend()
    figure.suptitle('Complete eight-depth original UD, Strix Point .161 · PP2048 / TG128, n=1 per point\n'
                    'Exact input, output and executor frontier identity; zero-based axes')
    figure.savefig(out/'benchmark-zero.svg', metadata={'Date': None})
    figure.savefig(out/'benchmark-zero.png', dpi=160)
    plt.close(figure)
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    resources = {}
    for name, root in data.items():
        telemetry = [json.loads(x) for x in (root/'telemetry.jsonl').read_text().splitlines()]
        resources[name] = {'observations': len(telemetry),
                           'peak_c': {sensor: max(t['value_c'] for row in telemetry for t in row['temperatures']
                                                   if t['name'] == sensor) for sensor in ('k10temp','amdgpu','nvme')},
                           'sampled_peak_gtt_used_bytes': max(row['gpu']['mem_info_gtt_used'] for row in telemetry)}
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    sources = [ROOT/'tools/bench-report.py', Path(__file__).resolve(),
               *sorted((HERE/'input').rglob('*'))]
    manifest = {'schema': 'synapse-lie.point-full-single-report.v1',
                'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources if p.is_file()},
                'output_sha256': {p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'status':'PAIRED_PASS','points':expected_depths,
                      'all_tokens_and_frontiers_equal': True,'output':str(out)}))


if __name__ == '__main__':main()
