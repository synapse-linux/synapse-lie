#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close the retained attention-load scheduling component; no model claim."""
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
    prefix = 'q2-attention-v-stage'
    plan = curve.read(ROOT/('config/'+prefix+'-plan.json'))
    release_path = ROOT/('config/'+prefix+'-window-release.json')
    release = curve.read(release_path)
    curve.require(not release['gpu_reserved'] and not release['kfd'] and
                  release['model_stats_unchanged'], 'Window not released')
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        curve.require(curve.sha(ROOT/name) == digest, 'Fixture changed: '+name)
    directory = ROOT/'evidence'/(prefix+'-component-r1')
    result, transport = curve.artifact_integrity(directory)
    exits = [c['exit_code'] for c in result['commands']]
    curve.require(exits == [0, 0, 0] and transport['exit_code'] == 0 and
                  not result['model_access'], 'Component did not pass')
    rows = [json.loads(line) for line in (directory/'results/03.log').read_text().splitlines()
            if line.startswith('{')]
    counts = Counter(x['event'] for x in rows)
    curve.require(counts == dict(attention_stage_timing=56, attention_stage_oracle=12,
                                attention_stage_pair=30, complete=1), 'Coverage differs')
    pairs = [x for x in rows if x['event'] == 'attention_stage_pair']
    oracles = [x for x in rows if x['event'] == 'attention_stage_oracle']
    curve.require(all(x['exact'] and x['early_sha256'] == x['late_sha256'] for x in pairs)
                  and all(x['pass'] for x in oracles) and rows[-1]['pass'], 'Numerics differ')
    shapes = []
    for shape in plan['timing_shapes']:
        arms = {}
        for late in (False, True):
            selected = [x for x in rows if x['event'] == 'attention_stage_timing' and
                        x['case'] == shape['name'] and x['late'] == late and not x['warmup']]
            curve.require(len(selected) == 5 and all(x['rows'] == 2048 and
                          x['start_pos'] == shape['pos'] for x in selected), 'Timing scope differs')
            values = [x['completed_wall_us'] for x in selected]
            curve.require(all(x > 0 for x in values), 'Invalid completed wall time')
            arms['late' if late else 'early'] = dict(samples_us=values,
                median_us=statistics.median(values), range_us=[min(values), max(values)])
        shapes.append(dict(**shape, **arms,
            late_time_change_percent=100*(arms['late']['median_us']/arms['early']['median_us']-1)))
    report = dict(schema='synapse-lie.q2-attention-v-stage-results.v1',
        plan_sha256=curve.sha(ROOT/('config/'+prefix+'-plan.json')),
        release_sha256=curve.sha(release_path), component_receipt_sha256=curve.sha(directory/'results/result.json'),
        archive_sha256=curve.sha(directory/'results.tar.gz'), command_exits=exits,
        events=dict(counts), all_pairs_exact=True, input_hashes_and_guards_pass=True,
        maximum_sampled_fp64_absolute_error=max(x['max_absolute_error'] for x in oracles),
        fp64_absolute_limit=0.01, valid_gpu_event_count=sum(x.get('gpu_event_valid', False) for x in rows),
        timings=shapes, provider_promoted=False, model_run=False, headline_eligible=False,
        decision='Keep existing dispatch. Late V regresses16K/32K;64K/128K ranges overlap. No model trial.',
        limits=['Synthetic masks and isolated kernel, not measured full-model token throughput.',
                'All GPU event times are zero; only completed host wall times are used.',
                'The FP64 check samples outputs; every output is checked for finiteness and exact pair equality.',
                'No unchanged model control, Q4, full curve or cleanup was run.'])
    output = ROOT/('config/'+prefix+'-results.json')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
