#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the ROCm 10 Distrobox eight-depth result and ROCm 7 comparison."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASELINE = HERE.parent/'full-single/input/lie/measurements.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New output directory')
    args = parser.parse_args()
    inp = HERE/'input'
    receipt = json.loads((inp/'collection.json').read_text())
    assert receipt['schema'] == 'synapse-lie.point-rocm10-distrobox-single.v1'
    assert receipt['remote_files_verified'] == 27 and receipt['hash_mismatches'] == 0
    assert receipt['focused_sanitizer_exit_code'] == 0
    assert 'ActiveState=active' in receipt['postflight']
    assert 'lease_exit:0' in receipt['postflight']
    remote_hashes = {}
    for line in (inp/'remote-sha256.txt').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        remote_hashes[relative] = digest
    assert len(remote_hashes) == 27
    for number, state, code in ((1, 'FAILED', 1), (2, 'PASSED', 0)):
        run = inp/f'r{number}'
        result = json.loads((run/'result.json').read_text())
        assert result['state'] == state and result['exit_code'] == code
        assert int((run/'supervisor.exit').read_text()) == code
        assert result['model_stat_unchanged'] and not result['cleanup_failures']
        assert result['service_after']['ActiveState'] == 'active'
        assert result['lease_released_at']
        for path in run.iterdir():
            if path.name == 'supervisor.exit':
                continue
            remote = f'rocm10-point-distrobox-single-kernel715-r{number}/{path.name}'
            assert sha(path) == remote_hashes[remote], path
        if number == 1:
            assert result['child_exit_code'] == 1
            assert not (run/'measurements.jsonl').exists()
        else:
            assert result['child_exit_code'] == 0
            assert result['bench_result']['samples'] == 16

    spec = importlib.util.spec_from_file_location('lie_bench_report', ROOT/'tools/bench-report.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    newer = report.read_result(inp/'r2/measurements.jsonl')
    older = report.read_result(BASELINE)
    assert newer['identity']['execution'] == older['identity']['execution'] == 'LIE-reactive-ready-batch'
    assert newer['identity']['suite'] == older['identity']['suite'] == 'single'
    depths = [0, 4096, 8192, 12288, 16384, 32768, 65536, 131072]
    comparisons = report.compare(newer, older)
    assert [row['depth'] for row in comparisons] == depths
    assert all(not row['eligible'] and not row['tokens_equal'] and
               not row['pp_frontier_equal'] and not row['tg_frontier_equal']
               for row in comparisons)

    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str((out/'matplotlib-cache').resolve())
    os.environ['SOURCE_DATE_EPOCH'] = '1790899200'
    import matplotlib
    matplotlib.use('Agg')
    matplotlib.rcParams['svg.hashsalt'] = 'synapse-lie-point-rocm10-distrobox-2026-10-02'
    report.export(newer, out, 'ROCm 10 / kernel 7.1.5 / Distrobox',
                  older, 'ROCm 7.2 / kernel 6.16.3 / Docker')

    with (out/'comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('depth', 'prompt_tokens', 'pp_rocm7_tps', 'pp_rocm10_tps',
                         'pp_change_percent', 'tg_rocm7_tps', 'tg_rocm10_tps',
                         'tg_change_percent', 'first_output_difference_index',
                         'output_equal', 'prefill_frontier_equal', 'decode_frontier_equal'))
        for a, b in zip(older['configurations'], newer['configurations'], strict=True):
            first = next((i for i, (x, y) in enumerate(zip(a['output_ids'], b['output_ids'], strict=True))
                          if x != y), None)
            writer.writerow((a['depth'], a['prompt_tokens'], a['prefill_tps']['median'],
                             b['prefill_tps']['median'],
                             100*(b['prefill_tps']['median']/a['prefill_tps']['median']-1),
                             a['decode_tps']['median'], b['decode_tps']['median'],
                             100*(b['decode_tps']['median']/a['decode_tps']['median']-1),
                             first, a['output_ids'] == b['output_ids'],
                             a['prefill_logits_sha256'] == b['prefill_logits_sha256'],
                             a['decode_logits_sha256'] == b['decode_logits_sha256']))

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for label, data in (('ROCm 10 / 7.1.5 / Distrobox', newer),
                        ('ROCm 7.2 / 6.16.3 / Docker', older)):
        rows = data['configurations']
        for axis, key in ((axes[0], 'prefill_tps'), (axes[1], 'decode_tps')):
            axis.plot([r['depth'] for r in rows], [r[key]['median'] for r in rows],
                      marker='o', label=label)
    for axis, title in ((axes[0], 'New prefill tokens/s'),
                        (axes[1], 'Confirmed decode tokens/s')):
        axis.set(xlabel='Occupied prefix tokens', ylabel=title, ylim=(0, None))
        axis.grid(alpha=.2)
        axis.legend()
    fig.suptitle('Original UD · direct C1 · PP2048/TG128 · one measured sample per depth\n'
                 'Cross-stack outputs/frontiers differ; kernel and container mode also changed')
    fig.savefig(out/'benchmark-zero.svg', metadata={'Date': None})
    fig.savefig(out/'benchmark-zero.png', dpi=160)
    plt.close(fig)
    telemetry = [json.loads(x) for x in (inp/'r2/telemetry.jsonl').read_text().splitlines()]
    resources = {'observations': len(telemetry),
                 'peak_c': {name: max(t['value_c'] for row in telemetry for t in row['temperatures']
                                      if t['name'] == name) for name in ('k10temp', 'amdgpu', 'nvme')},
                 'sampled_peak_gtt_used_bytes': max(row['gpu']['mem_info_gtt_used'] for row in telemetry)}
    (out/'resources.json').write_text(json.dumps(resources, indent=2)+'\n')
    for path in out.iterdir():
        if path.suffix in ('.svg', '.csv'):
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    sources = [ROOT/'tools/bench-report.py', Path(__file__).resolve(), BASELINE,
               *sorted(p for p in inp.rglob('*') if p.is_file())]
    hashes = {'schema': 'synapse-lie.point-rocm10-distrobox-report.v1',
              'input_sha256': {str(path.relative_to(ROOT)): sha(path) for path in sources},
              'output_sha256': {path.name: sha(path) for path in sorted(out.iterdir()) if path.is_file()}}
    (out/'artifact-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps({'status': 'ROCM10_PASS_CROSS_STACK_PARITY_DIFFERENT',
                      'samples': 16, 'depths': depths, 'output': str(out)}))


if __name__ == '__main__':
    main()
