#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the exact partition selector trial without inferring model throughput."""
import importlib.util
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)


def main():
    prefix = 'q2-select-partition'
    pp = ROOT/('config/'+prefix+'-plan.json')
    rp = ROOT/('config/'+prefix+'-window-release.json')
    plan, release = curve.read(pp), curve.read(rp)
    curve.require(not release['gpu_reserved'] and not release['kfd'] and
                  release['model_stats_unchanged'], 'Window not closed')
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        curve.require(curve.sha(ROOT/name) == digest, 'Changed fixture: '+name)
    static = curve.read(ROOT/'config/q2-select-partition-static.json')
    curve.require(curve.sha(ROOT/static['include']) == static['include_sha256'],
                  'Derived local selection source differs')
    directory = ROOT/'evidence'/(prefix+'-component-r1')
    result, transport = curve.artifact_integrity(directory)
    exits = [x['exit_code'] for x in result['commands']]
    curve.require(exits == [0, 0, 0] and transport['exit_code'] == 0 and
                  not result['model_access'], 'Component failed')
    rows = [json.loads(s) for s in (directory/'results/03.log').read_text().splitlines()
            if s.startswith('{')]
    counts = Counter(x['event'] for x in rows)
    curve.require(counts == dict(partition_pair=56, partition_timing=88, complete=1),
                  'Coverage differs')
    pairs = [x for x in rows if x['event'] == 'partition_pair']
    curve.require(all(x['exact'] and x['retained_oracle'] and x['partition_oracle'] and
                      x['retained_sha256'] == x['partition_sha256'] for x in pairs)
                  and rows[-1]['pass'], 'Complete mask comparison failed')
    timings = []
    for shape in plan['timing_shapes']:
        arms = {}
        for arm, name in enumerate(('retained', 'partition')):
            selected = [x for x in rows if x['event'] == 'partition_timing' and
                        x['case'] == shape['name'] and x['arm'] == arm and not x['warmup']]
            curve.require(len(selected) == 9 and {x['rep'] for x in selected} == set(range(2, 11))
                          and all(x['complete'] == shape['complete'] for x in selected),
                          'Timing repetitions differ')
            values = [x['completed_wall_us'] for x in selected]
            curve.require(all(x > 0 for x in values), 'Invalid wall duration')
            arms[name] = dict(samples_us=values, median_us=statistics.median(values),
                              range_us=[min(values), max(values)])
        timings.append(dict(**shape, **arms, time_change_percent=100*(
            arms['partition']['median_us']/arms['retained']['median_us']-1)))
    report = dict(schema='synapse-lie.q2-select-partition-results.v1',
        plan_sha256=curve.sha(pp), release_sha256=curve.sha(rp),
        component_receipt_sha256=curve.sha(directory/'results/result.json'),
        archive_sha256=curve.sha(directory/'results.tar.gz'),
        command_exits=exits, cases=len({x['case'] for x in pairs}), events=dict(counts),
        all_masks_exact=True, all_complete_cpu_sort_oracles_pass=True,
        input_hashes_and_guards_pass=True, valid_gpu_event_count=sum(x.get('gpu_event_valid', False) for x in rows),
        timings=timings, scratch_bytes=36864, model_run=False, provider_promoted=False,
        headline_eligible=False,
        decision='Retain the long-context candidate. Partition improves128K, regresses32K/64K. '
                 'No unconditional dispatch; whole-model benefit remains unmeasured.',
        integration_requirements=['Use a bounded deep-context dispatch; captured graphs must observe the live device position.',
            'Account for36864 scratch bytes and their last reader in the owned model/executor lifetime.',
            'Keep existing prefill selector and original2048-token chunks.',
            'Measure complete original native requests before adoption; reuse saved controls.'],
        limits=['Synthetic score rows, not original-model attention scores or token throughput.',
                'Completed host wall time includes HIP graph dispatch and completion; GPU events remain zero.',
                'Kernel percentage cannot be applied to the whole decode step.',
                'Every timed output and the complete host rank/tie mask were checked before overwrite.'])
    output = ROOT/('config/'+prefix+'-results.json')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
