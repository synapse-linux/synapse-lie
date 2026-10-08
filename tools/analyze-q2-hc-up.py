#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit complete HC fusion buffers, retaining numerical failures as failures."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


CASES = ((96, 0, True, True), (97, 1, True, True), (129, 0, True, True),
         (129, 2, True, True), (129, 0, False, True),
         (129, 0, True, False), (2048, 0, True, True))
SUCCESS = 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'
END_MARKER = ' synthetic HC up fusion; no model inference'


def compare_buffer(reference, candidate, kind, values):
    width = struct.calcsize('<' + kind)
    if len(reference) != values * width or len(candidate) != values * width:
        raise ValueError('Incomplete output buffer')
    changed = 0
    maximum = error2 = reference2 = 0.0
    for (a,), (b,) in zip(struct.iter_unpack('<' + kind, reference),
                          struct.iter_unpack('<' + kind, candidate)):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('Non-finite output buffer')
        delta = b - a
        changed += a != b
        maximum = max(maximum, abs(delta))
        error2 += delta * delta
        reference2 += a * a
    return {'values': values, 'exact': reference == candidate,
            'changed_values': changed, 'max_absolute_delta': maximum,
            'relative_l2': math.sqrt(error2 / max(reference2, 1e-60))}


def validate_completion(result, log):
    exits = [c['exit_code'] for c in result['commands']]
    if not exits or any(code != 0 for code in exits[:-1]) or exits[-1] not in (0, 1):
        raise ValueError('Incomplete or interrupted operator command')
    if result.get('mode') != 'hc-up-operators' or result.get('model_access') is not False:
        raise ValueError('Different operator scope')
    if result.get('postflight_kfd') != []:
        raise ValueError('Unresolved GPU retirement')
    if not result.get('binary_sha256') or result['binary_sha256'] != result.get('binary_sha256_after'):
        raise ValueError('Binary identity changed or missing')
    for row in [result, *result['commands']]:
        if any(row.get(k) for k in ('thermal_stop', 'postflight_error', 'timeout',
                                   'foreign_kfd', 'lingering_descendants')):
            raise ValueError('Runtime or postflight failure')
    markers = [s for s in log.splitlines() if s in ('PASS' + END_MARKER, 'FAIL' + END_MARKER)]
    expected = 'PASS' if exits[-1] == 0 else 'FAIL'
    if markers != [expected + END_MARKER] or result['state'] != (SUCCESS if exits[-1] == 0 else 'FAILED'):
        raise ValueError('Incomplete fixture or inconsistent terminal state')
    return exits[-1] == 0


def cases(events):
    labels = {f'hc-up-n{n}-p{p}-i{int(i)}-h{int(h)}': (n, i, h)
              for n, p, i, h in CASES}
    if len(events) != len(labels) or {e['label'] for e in events} != set(labels):
        raise ValueError('Different or incomplete operator inventory')
    for e in events:
        n, injection, half = labels[e['label']]
        tokens = {0, n - 1} | {t + d for t in range(0, n, 128)
                  for d in (0, 1, 15, 16, 31, 32, 63, 64, 95, 96, 127) if t + d < n}
        if (e['values'] != n * 2560 or e['mix_oracle_values'] != len(tokens) * 280 or
                e['inject_oracle_values'] != (len(tokens) * 12 if injection else 0)):
            raise ValueError('Incomplete independent oracle coverage')
        metrics = [e[k] for k in ('mix_rrms', 'mix_scaled_max', 'inject_rrms', 'inject_scaled_max')]
        if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in metrics):
            raise ValueError('Invalid independent error metric')
        independent = all(v <= .00002 for v in metrics)
        if type(e['independent_pass']) is not bool or e['independent_pass'] != independent:
            raise ValueError('Inconsistent independent verdict')
        if any(type(e[k]) is not bool for k in ('exact_mixed', 'exact_inject', 'exact_half')):
            raise ValueError('Invalid exact-replay flag')
        if (not injection and (not e['exact_inject'] or any(metrics[2:]))) or (not half and not e['exact_half']):
            raise ValueError('Disabled output differs')
    return labels


def analyze(directory):
    root = directory / 'results'
    result = json.loads((root / 'result.json').read_text())
    for name, meta in result['artifacts'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe artifact path')
        data = (root / path).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact integrity mismatch: ' + name)
    log_names = sorted(name for name in result['artifacts'] if name.endswith('.log'))
    log = '\n'.join((root / name).read_text() for name in log_names)
    success = validate_completion(result, log)
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    events = [e for e in events if e.get('event') == 'hc_up_fused']
    inventory = cases(events)
    outputs, names = [], set()
    for e in events:
        label = e['label']
        n, injection, half = inventory[label]
        streams = [('mixed', '.f32', 'f', n * 2560)]
        if injection:
            streams.append(('inject', '-inject.f32', 'f', n * 12))
        if half:
            streams.append(('half', '.f16', 'e', n * 2560))
        for part, suffix, kind, size in streams:
            left, right = (label + '-' + variant + suffix for variant in ('reference', 'fused'))
            names.update((left, right))
            if left not in result['artifacts'] or right not in result['artifacts']:
                raise ValueError('Output missing from artifact receipt')
            row = compare_buffer((root / left).read_bytes(), (root / right).read_bytes(), kind, size)
            if row['exact'] != e['exact_' + part]:
                raise ValueError('Output bytes disagree with fixture verdict')
            outputs.append(dict(label=label, output=part, **row))
    actual = {p.name for p in root.iterdir() if p.suffix in ('.f32', '.f16')}
    if actual != names:
        raise ValueError('Unexpected binary output inventory')
    passed = all(row['exact'] for row in outputs) and all(e['independent_pass'] for e in events)
    if passed != success:
        raise ValueError('Numerical results disagree with process outcome')
    return {'scope': 'Synthetic HC up fusion only; no model quality or performance verdict',
            'path': str(directory), 'state': result['state'], 'command_exits': [c['exit_code'] for c in result['commands']],
            'verified_artifacts': len(result['artifacts']), 'cases': events, 'buffers': outputs,
            'all_exact': all(row['exact'] for row in outputs), 'numerical_pass': passed,
            'promotion': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = analyze(args.directory)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(report['cases']), 'buffers': len(report['buffers']),
                      'numerical_pass': report['numerical_pass']}))
    raise SystemExit(0 if report['numerical_pass'] else 1)


if __name__ == '__main__':
    main()
