#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Merge independently verified fresh-server Point cohorts for native reports."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
LEVELS = (1, 2, 4, 6, 8)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(evidence, level, impl, mode, case):
    label = f'point-http-fresh-r7-{mode}-{case}-c{level}-{impl}'
    root = evidence / label
    collection = json.loads((root / 'collection.json').read_text())
    inventory = collection['inventory']
    for key in ('model_stat_unchanged', 'supervisor_absent', 'gpu_child_absent',
                'owned_child_absent', 'lease_free'):
        if inventory.get(key) is not True:
            raise ValueError(f'{label}: incomplete {key}')
    if (collection.get('exit_code') != 0 or inventory.get('result_state') != 'PASSED' or
            inventory.get('result_exit_code') != 0 or
            inventory.get('child_exit_code') != 0 or
            inventory.get('service_exit') != 0 or
            'ActiveState=active' not in inventory.get('service', '')):
        raise ValueError(f'{label}: incomplete execution or service restoration')
    for relative, info in inventory['files'].items():
        path = root / relative
        if path.stat().st_size != info['bytes'] or sha(path) != info['sha256']:
            raise ValueError(f'{label}: collected file drift: {relative}')
    manifest = json.loads((root / 'manifest.json').read_text())
    result = json.loads((root / 'http-multi-result.json').read_text())
    if (manifest.get('http_capacity_policy') != 'fresh-per-level' or
            manifest.get('http_server_sessions') != level or
            manifest.get('http_users') != str(level) or
            manifest.get('http_impl') != impl or
            manifest.get('decode_mode') != mode or
            manifest.get('http_case') != case or
            result.get('state') != 'PASSED' or
            result.get('capacity_policy') != 'fresh-per-level' or
            result.get('server_sessions') != level or
            result.get('users') != str(level) or
            result.get('cohorts') != 4):
        raise ValueError(f'{label}: campaign parameter mismatch')
    measurements = root / 'measurements.jsonl'
    rows = [json.loads(line) for line in measurements.read_text().splitlines()]
    if (rows[-1] != {'event': 'complete', 'exit_code': 0} or
            len(rows) != 6 or rows[0].get('event') != 'identity' or
            rows[0].get('schema') != 'synapse-lie.http-multi-bench.v1' or
            rows[0].get('users') != [level] or
            [(row.get('users'), row.get('rep'), row.get('warmup')) for row in rows[1:-1]] !=
            [(level, 0, True), (level, 1, False), (level, 2, False), (level, 3, False)]):
        raise ValueError(f'{label}: incomplete native cohorts')
    return label, rows, {'manifest_sha256': sha(root/'manifest.json'),
                         'collection_sha256': sha(root/'collection.json'),
                         'measurements_sha256': sha(measurements)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--impl', choices=('lie', 'gufo'), required=True)
    parser.add_argument('--mode', choices=('ar', 'mtp'), required=True)
    parser.add_argument('--case', choices=('prose', 'repetition'), required=True)
    parser.add_argument('--evidence-root', type=Path, default=EVIDENCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'ar' and args.case == 'repetition':
        parser.error('AR repetition has only a C1 reference, not a full curve')
    if args.output.exists() or args.output.with_suffix('.provenance.json').exists():
        parser.error('Refusing to replace merged evidence')
    parts = [load(args.evidence_root, level, args.impl, args.mode, args.case)
             for level in LEVELS]
    first = parts[0][1][0].copy()
    for _, rows, _ in parts[1:]:
        other = rows[0].copy()
        other.pop('users')
        baseline = first.copy()
        baseline.pop('users')
        if other != baseline:
            raise ValueError('Identity drift between fresh server levels')
    first['users'] = list(LEVELS)
    merged = [first]
    for _, rows, _ in parts:
        merged.extend(rows[1:-1])
    merged.append({'event': 'complete', 'exit_code': 0})
    args.output.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                   for row in merged))
    provenance = {'schema': 'synapse-lie.point-http-fresh-merge.v1',
                  'impl': args.impl, 'mode': args.mode, 'case': args.case,
                  'levels': list(LEVELS), 'cohorts': 20,
                  'merged_sha256': sha(args.output),
                  'sources': {label: info for label, _, info in parts}}
    args.output.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'sha256': provenance['merged_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
