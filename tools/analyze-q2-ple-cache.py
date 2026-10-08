#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare isolated cache capacity diagnostics, including complete output replay."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'ple_diagnostic', Path(__file__).with_name('analyze-q2-ple.py'))
ple = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ple)


def indexed(events, event, keys):
    rows = [e for e in events if e['event'] == event]
    result = {tuple(e[k] for k in keys): e for e in rows}
    if len(rows) != len(result):
        raise ValueError('Duplicate diagnostic observation')
    return result


def compare(reference, candidate):
    re, rr = ple.read(reference)
    ce, cr = ple.read(candidate)
    exact = {}
    for event, keys, digest in (
            ('forward', ('case', 'rep', 'step'), 'frontier_sha256'),
            ('gather', ('case', 'tokens', 'rep'), 'embedding_sha256')):
        a, b = indexed(re, event, keys), indexed(ce, event, keys)
        if a.keys() != b.keys():
            raise ValueError('Unmatched diagnostic observations')
        differences = [k for k in a if a[k][digest] != b[k][digest]]
        if differences:
            raise ValueError('Output replay differs: ' + repr(differences))
        exact[event] = len(a)
    files = sorted(name for name in rr['artifacts'] if name.endswith(('.f32', '.i32')))
    if files != sorted(name for name in cr['artifacts'] if name.endswith(('.f32', '.i32'))):
        raise ValueError('Missing output or input artifact')
    saved = {}
    for name in files:
        a, b = [(root / 'results' / name).read_bytes() for root in (reference, candidate)]
        if a != b:
            raise ValueError('Saved complete buffer differs: ' + name)
        saved[name] = hashlib.sha256(a).hexdigest()
    arms = {name: ple.arm(root) for name, root in
            [('reference', reference), ('candidate', candidate)]}
    for name, expected in [('reference', 16384), ('candidate', 65536)]:
        if len(arms[name]['tables']) != 2 or any(
                t['cache_slots'] != expected or t['type'] != 30 or t['row_bytes'] != 320
                for t in arms[name]['tables']):
            raise ValueError('Unexpected model table or cache capacity')
    comparisons = {}
    for case in ('padding', 'varied'):
        comparisons[case] = {}
        for phase in ('prefill', 'decode'):
            a, b = [arms[name]['model'][case][phase]['repeated_owned_cache']
                    for name in ('reference', 'candidate')]
            comparisons[case][phase] = {
                'reference_ms': a['elapsed_ms_median'],
                'candidate_ms': b['elapsed_ms_median'],
                'elapsed_change_percent': 100 * (b['elapsed_ms_median'] / a['elapsed_ms_median'] - 1),
                'reference_host_blocked_ms': a['blocked_ms_median'],
                'candidate_host_blocked_ms': b['blocked_ms_median'],
                'reference_cache_hit_percent': a['cache_hit_percent'],
                'candidate_cache_hit_percent': b['cache_hit_percent']}
    samples = {name: [{k: e[k] for k in ('case', 'phase', 'rep', 'step', 'seconds')} |
                      {'host_blocked_ms': e['ple']['blocked_ns'] / 1e6}
                      for e in events if e['event'] == 'forward']
               for name, events in [('reference', re), ('candidate', ce)]}
    return dict(
        scope='Instrumented capacity-only model diagnostics; not throughput acceptance',
        limits=['Sequential reference/candidate arms, no shared-page eviction or randomized model order.',
                'Filesystem data was accessed in prior diagnostics; a fresh owned table is not cold storage.',
                'Synthetic varied token IDs and forced decode are not natural-language quality evidence.',
                'Exact output replay is against the experimental Q2 baseline, not an independent full-model teacher.',
                'Host waiting can overlap queued GPU work; do not subtract it from model latency.'],
        exact_observations=exact, exact_saved_files=saved,
        comparisons=comparisons, model_samples=samples, **arms)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = compare(args.reference, args.candidate)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'exact': result['exact_observations'],
                      'saved_files': len(result['exact_saved_files']),
                      'comparisons': result['comparisons']}, indent=2))


if __name__ == '__main__':
    main()
