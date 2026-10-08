#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit paired HC up chains against exact buffers, FP64 checks and full paths."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


up = module('up', 'analyze-q2-hc-up.py')
up.CASES = (*up.CASES, (127, 0, True, True), (128, 0, True, True),
            (257, 0, True, True), (129, 3, True, True))
models = module('model_checks', 'analyze-q2-hc-input.py')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def stats(values):
    require(values and all(math.isfinite(v) and v > 0 for v in values), 'Invalid timing')
    return dict(samples=values, min=min(values), median=statistics.median(values), max=max(values))


def analyze(path, variant):
    root, result, events = models.read(path)
    transport = json.loads((path / 'transport.json').read_text())
    exits = [row['exit_code'] for row in result['commands']]
    require(result['mode'] == 'hc-up-chain-bench' and not result['model_access'], 'Wrong component scope')
    require(transport['source_variant'] == variant, 'Wrong source variant')
    require(exits[:2] == [0, 0] and len(exits) == 3 and exits[-1] in (0, 1)
            and transport['exit_code'] == exits[-1], 'Incomplete or inconsistent command exits')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4
            and not result['preflight_kfd'] and not result['postflight_kfd'], 'Unresolved lease/GPU status')
    cases = [e for e in events if e['event'] == 'hc_up_fused']
    inventory = up.cases(cases)
    buffers, files = [], set()
    for case in cases:
        name = case['label']
        n, injection, half = inventory[name]
        outputs = [('mixed', '.f32', 'f', n * 2560)]
        if injection:
            outputs.append(('inject', '-inject.f32', 'f', n * 12))
        if half:
            outputs.append(('half', '.f16', 'e', n * 2560))
        for label, suffix, kind, size in outputs:
            left, right = (name + '-' + arm + suffix for arm in ('reference', 'fused'))
            files.update((left, right))
            a, b = (root / left).read_bytes(), (root / right).read_bytes()
            check = up.compare_buffer(a, b, kind, size)
            require(check['exact'] == case['exact_' + label], 'Saved output disagrees with fixture')
            if name == 'hc-up-n129-p3-i1-h1' and label == 'mixed':
                width = 2560 * 4
                require(all(b[t * width:(t + 1) * width] == b[:width] for t in range(n)),
                        'Repeated input rows differ by token position')
            buffers.append(dict(label=name, output=label, **check,
                reference_sha256=hashlib.sha256(a).hexdigest(), candidate_sha256=hashlib.sha256(b).hexdigest()))
    require(files == {p.name for p in root.iterdir() if p.suffix in ('.f32', '.f16')}, 'Unexpected saved outputs')
    timings = [e for e in events if e['event'] == 'hc_up_chain_timing']
    require(len(timings) == 10, 'Incomplete timing sequence')
    arms = {}
    for fused, name in ((False, 'separate_control'), (True, 'fused')):
        rows = [e for e in timings if e['fused'] == fused]
        require([e['rep'] for e in rows] == list(range(5)), 'Missing/duplicate timing')
        require(all(e['fused'] == ((e['rep'] + e['order']) % 2 != 0)
                    and e['n'] == 2048 and e['launches'] == 16 and e['weight_bytes'] == 100 << 20
                    for e in rows), 'Changed timing/rotation protocol')
        arms[name] = stats([e['us_per_launch'] for e in rows])
    replays = [e for e in events if e['event'] == 'hc_up_chain_replay']
    require([e['rep'] for e in replays] == list(range(5)), 'Missing post-timing replay')
    failures = sum(not (e['independent_pass'] and e['exact_mixed'] and e['exact_inject']
                       and e['exact_half']) for e in cases)
    summary = [e for e in events if e['event'] == 'hc_up_chain_summary']
    require(summary == [dict(event='hc_up_chain_summary', cases=11, failures=failures,
                            bench_exact=all(e['exact'] for e in replays))], 'Incomplete fixture summary')
    passed = not failures and all(e['exact'] for e in replays)
    require(exits[-1] == int(not passed), 'Failure not preserved')
    require(result['state'] == ('SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
                               if passed else 'FAILED'), 'Inconsistent terminal state')
    return dict(path=str(path), source_variant=variant, state=result['state'], command_exits=exits,
        artifacts=len(result['artifacts']), binary_sha256=result['binary_sha256'], cases=cases,
        buffers=buffers, timings=timings, replays=replays, arms=arms, numerical_pass=passed), files


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--models', nargs=3, type=Path, metavar=('REFERENCE', 'CANDIDATE', 'UD'))
    args = p.parse_args()
    a, files = analyze(args.reference, 'affine-palette')
    b, candidate_files = analyze(args.candidate, 'hc-up-chains')
    require(files == candidate_files, 'Cross-source output inventory differs')
    changed = [name for name in sorted(files) if (args.reference / 'results' / name).read_bytes()
               != (args.candidate / 'results' / name).read_bytes()]
    report = dict(scope='Independent synthetic HC up/mix checks and full-path component timings',
        goal_met=False, promotion=False, reference=a, candidate=b, cross_source_files=len(files),
        changed_files=changed, relative_medians={name:b['arms'][name]['median'] / a['arms'][name]['median']
            for name in ('fused', 'separate_control')},
        limit='Component gain requires matched complete-model confirmation; strict FP64 limits remain unchanged')
    if args.models:
        report['model'] = models.model_report(args.models, ('affine-palette', 'hc-up-chains', 'qualified'))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ('cross_source_files', 'changed_files', 'relative_medians')}, indent=2))
    if args.models:
        print(json.dumps(report['model']['relative_medians'], indent=2))


if __name__ == '__main__':
    main()
