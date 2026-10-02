#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the original-weight .161 256K-capacity loading receipt offline."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    roots = {'lie': HERE/'input', 'gufo': HERE/'input/gufo'}
    for root in roots.values():
        collection = json.loads((root/'collection.json').read_text())
        assert collection['exit_code'] == 0 and collection['inventory']['result_state'] == 'PASSED'
        assert all(collection['inventory'][key] for key in ('supervisor_absent', 'gpu_child_absent', 'lease_free'))
        for name, identity in collection['inventory']['files'].items():
            path = root/name
            assert path.stat().st_size == identity['bytes'] and sha(path) == identity['sha256'], name
        result = json.loads((root/'result.json').read_text())
        assert result['state'] == 'PASSED' and result['child_exit_code'] == 0 and result['exit_code'] == 0
        assert result['model_stat_unchanged'] and not result['cleanup_failures']
        assert result['service_after']['ActiveState'] == 'active'
    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    bench = importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
    data = {name: bench.read_result(root/'measurements.jsonl') for name, root in roots.items()}
    assert all(x['identity']['suite'] == 'loading' and not x['identity']['synthetic'] and
               len(x['loading']) == 1 and x['loading'][0]['context_capacity'] == 262144
               for x in data.values())
    out = args.output;out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-strix-point-loading-2026-10-02'
    bench.export(data['lie'], out, 'LIE .161', data['gufo'], 'Gufo .161')
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    resources = {}
    for name, root in roots.items():
        telemetry = [json.loads(x) for x in (root/'telemetry.jsonl').read_text().splitlines()]
        resources[name] = {'observations':len(telemetry),
                           'peak_c':{sensor:max(t['value_c'] for row in telemetry for t in row['temperatures']
                                                if t['name']==sensor) for sensor in ('k10temp','amdgpu','nvme')},
                           'sampled_peak_gtt_used_bytes':max(row['gpu']['mem_info_gtt_used'] for row in telemetry),
                           'minimum_system_mem_available_bytes':min(row['memory']['MemAvailable'] for row in telemetry)}
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    manifest = {'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
                              (Path(__file__).resolve(),ROOT/'tools/bench-report.py',
                               *sorted(p for p in (HERE/'input').rglob('*') if p.is_file()))},
                'output_sha256':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'status':'PAIRED_PASS','capacity':262144,
                      'lie_load_ns':data['lie']['loading'][0]['model_load_ns'],
                      'gufo_load_ns':data['gufo']['loading'][0]['model_load_ns'],
                      'output':str(out)}))


if __name__ == '__main__':main()
