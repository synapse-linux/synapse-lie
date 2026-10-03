#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify consumer-side narrowing, retained controls and paired component timing."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import struct


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    root = path / 'results'
    result = json.loads((root / 'result.json').read_text())
    require(result.get('finished_at') and not result.get('thermal_stop'), 'Incomplete/thermal run')
    require(result['binary_sha256'] == result['binary_sha256_after'], 'Binary changed')
    for name, metadata in result['artifacts'].items():
        payload = (root / name).read_bytes()
        require(len(payload) == metadata['bytes'] and hashlib.sha256(payload).hexdigest() == metadata['sha256'],
                'Artifact changed: ' + name)
    events = [json.loads(line) for log in sorted(root.glob('*.log'))
              for line in log.read_text().splitlines() if line.startswith('{"event":')]
    return root, result, events


def stats(values):
    require(values and all(math.isfinite(value) and value > 0 for value in values), 'Invalid timings')
    return dict(samples=values, min=min(values), median=statistics.median(values), max=max(values))


def model_report(paths):
    spec = importlib.util.spec_from_file_location('hc_model', Path(__file__).with_name('analyze-q2-hc.py'))
    hc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hc)
    report, roots = {}, []
    for label, variant, path in zip(('reference', 'candidate', 'ud'),
                                    ('affine-palette', 'hc-input', 'qualified'), paths):
        root, events, meta = hc.read(path, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        transport = json.loads((path / 'transport.json').read_text())
        require(transport['exit_code'] == 0 and transport['rebuild_mmq']
                and transport['source_variant'] == variant, 'Model source/rebuild identity differs')
        loaded = [e for e in events if e['event'] == 'loaded']
        require(len(loaded) == 1 and loaded[0]['mtp'] is False
                and loaded[0]['max_context'] == 9216 and loaded[0]['prefill_chunk'] == 2048,
                'Model capability/configuration differs')
        samples = [e for e in events if e['event'] == 'sample' and e['label'] == 'pp2048']
        idle = [e for e in events if e['event'] == 'cooldown']
        require(len(idle) == 4 and all(e['seconds'] == 15 and e['before_rep'] == i
                                      for i, e in enumerate(idle)), 'Changed idle protocol')
        require([e['rep'] for e in samples] == list(range(4))
                and [e['warmup'] for e in samples] == [True, False, False, False]
                and all(e['prompt_tokens'] == 2048 and e['decode_steps'] == 127
                        and e['output_tokens'] == 128 and not e['eos'] for e in samples),
                'Incomplete or incomparable model samples')
        report[label] = dict(meta, measurements={key:stats([e[key] for e in samples if not e['warmup']])
            for key in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')})
        roots.append(root)
    report['frontiers'] = hc.frontiers(*roots[:2], logits=True)
    tokens = sorted(p.name for p in roots[0].iterdir() if p.suffix in ('.i32', '.u32'))
    require(len(tokens) == 9, 'Unexpected token-file inventory')
    report['token_files'] = tokens
    report['changed_tokens'] = {label:[name for name in tokens if
        (roots[0] / name).read_bytes() != (root / name).read_bytes()]
        for label, root in zip(('candidate', 'ud'), roots[1:])}
    report['within_arm_replay'] = {}
    for label, root in zip(('reference', 'candidate', 'ud'), roots):
        exact = sum((root / f'pp2048-0-{suffix}').read_bytes() ==
                    (root / f'pp2048-{i}-{suffix}').read_bytes()
                    for suffix in ('prefill.f32', 'last.f32', 'output.u32') for i in (1, 2, 3))
        report['within_arm_replay'][label] = dict(checks=9, exact=exact)
    report['relative_medians'] = {control:{key:
        report['candidate']['measurements'][key]['median'] / report[control]['measurements'][key]['median']
        for key in ('prefill_tok_s', 'decode_steps_s')} for control in ('reference', 'ud')}
    report['limit'] = 'Sequential C1 pp2048/tg128, one warmup and three samples with untimed 15s idle; not long-context, sustained-serving, independent quality or parity qualification'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--native-reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', type=Path, nargs=3, metavar=('REFERENCE', 'CANDIDATE', 'UD'))
    args = parser.parse_args()
    root, result, events = read(args.run)
    ref_root, ref_result, ref_events = read(args.native_reference)
    require(result['mode'] == 'hc-input-bench' and not result['model_access'], 'Wrong diagnostic scope')
    require(ref_result['mode'] == 'hc-pp-bench', 'Wrong native control scope')
    native = [e for e in events if e['event'] == 'pp_operator']
    original = [e for e in ref_events if e['event'] == 'pp_operator']
    require(len(native) == 22 and native == original, 'Original sampled oracle/full-output controls changed')
    for name in ref_result['artifacts']:
        if name.endswith(('.f32', '.u32')):
            require((root / name).read_bytes() == (ref_root / name).read_bytes(), 'Original saved control changed')
    summaries = [e for e in events if e['event'] == 'hc_input_summary']
    require(len(summaries) == 1, 'Missing complete new summary')
    summary = summaries[0]
    operators = [e for e in events if e['event'] == 'hc_input_operator']
    expected = [(n, 0) for n in (96, 97, 127, 128, 129, 257, 2048)] + [(129, p) for p in (1, 2, 3)]
    require([(e['n'], e['pattern']) for e in operators] == expected, 'Incomplete independent cases')
    failures = 0
    for op in operators:
        a = (root / (op['label'] + '-reference.f32')).read_bytes()
        b = (root / (op['label'] + '-candidate.f32')).read_bytes()
        require(len(a) == len(b) == op['n'] * 320 * 4, 'Unexpected full-output extent')
        require(all(math.isfinite(v[0]) for raw in (a, b) for v in struct.iter_unpack('<f', raw)),
                'Non-finite saved frontier')
        require(op['exact'] == (a == b), 'Exact-output flag disagrees')
        require(all(math.isfinite(op[key]) and op[key] >= 0 for key in ('relative_rms', 'error_over_peak')),
                'Invalid independent numerical metrics')
        numeric = op['relative_rms'] <= 2e-5 and op['error_over_peak'] <= 2e-5
        require(op['numeric_ok'] == numeric, 'Independent limits changed')
        failures += not (op['exact'] and numeric and op['row_differences'] == 0)
        op['reference_sha256'] = hashlib.sha256(a).hexdigest()
        op['candidate_sha256'] = hashlib.sha256(b).hexdigest()
    replays = [e for e in events if e['event'] == 'hc_input_bench_replay']
    require([e['rep'] for e in replays] == list(range(5)), 'Missing post-timing replays')
    require(summary == dict(event='hc_input_summary', cases=10, failures=failures,
                           bench_exact=all(e['exact'] for e in replays), original_failures=4),
            'Summary disagrees with retained checks')
    timings = [e for e in events if e['event'] == 'hc_input_timing']
    require(len(timings) == 10, 'Incomplete timing samples')
    arms = {}
    for fused, name in ((False, 'separate'), (True, 'fused')):
        rows = [e for e in timings if e['fused'] == fused]
        require([e['rep'] for e in rows] == list(range(5)), 'Duplicate or missing timing')
        require(all(e['fused'] == ((e['rep'] + e['order']) % 2 != 0)
                    and e['n'] == 2048 and e['launches'] == 16 and e['weight_bytes'] == 100 << 20
                    for e in rows), 'Timing scope/order changed')
        arms[name] = stats([e['us_per_launch'] for e in rows])
    control = [e for e in events if e['event'] == 'pp_microbench']
    require(len(control) == 5 and all(e['m'] == 10240 and e['k'] == 320 for e in control),
            'Missing unchanged up control')
    require([c['exit_code'] for c in result['commands']] == [0, 0, 1], 'Unexpected command exits')
    require(json.loads((args.run / 'transport.json').read_text())['exit_code'] == 1,
            'Transport does not preserve original numerical failure')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4
            and not result['preflight_kfd'] and not result['postflight_kfd'], 'Unresolved lease/KFD receipt')
    report = dict(scope='Synthetic complete HC down input-preparation/projection path; not model throughput',
        run=str(args.run), native_reference=str(args.native_reference), promotion=False,
        actual_exit=1, finished_at=result['finished_at'], binary_sha256=result['binary_sha256'],
        original_cases_exact=22, original_numerical_failures=4, operators=operators,
        new_failures=failures, timing_replays=replays, timings=timings, arms=arms,
        paired_time_ratios=[b / a for a, b in zip(arms['separate']['samples'], arms['fused']['samples'])],
        median_time_ratio=arms['fused']['median'] / arms['separate']['median'],
        unchanged_up_us=stats([e['us_per_launch'] for e in control]),
        benefit_requires='Useful component gain, exact replay and unchanged independent limits before complete matched models')
    report['failed_on_exact_reference_too'] = [op['label'] for op in operators if op['exact'] and not op['numeric_ok']]
    if args.models:
        report['model'] = model_report(args.models)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ('original_cases_exact', 'new_failures', 'arms', 'median_time_ratio')}, indent=2))
    if args.models:
        print(json.dumps(report['model']['relative_medians'], indent=2))


if __name__ == '__main__':
    main()
