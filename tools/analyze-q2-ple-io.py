#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Summarize original-row I/O; never call its rate model throughput."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median


def read(root):
    receipt = json.loads((root / 'results/result.json').read_text())
    if receipt['state'] != 'PLE_ROW_IO_COMPLETE_NO_MODEL_FORWARD' or any(c['exit_code'] for c in receipt['commands']):
        raise ValueError('Original-row diagnostic did not complete')
    for name, meta in receipt['artifacts'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe artifact name')
        data = (root / 'results' / path).read_bytes()
        if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Artifact changed')
    events = []
    for log in sorted((root / 'results').glob('*.log')):
        for line in log.read_text().splitlines():
            if line.startswith('{'):
                events.append(json.loads(line))
    if sum(e['event'] == 'complete' for e in events) != 1:
        raise ValueError('Completion is not unique')
    rows = [e for e in events if e['event'] == 'io']
    is_q2 = rows[0]['type'] == 30
    if len(rows) != (64 if is_q2 else 32):
        raise ValueError('Missing observations')
    for campaign in ('advice', 'capacity') if is_q2 else ('advice',):
        pairs, reps = (8, 2) if campaign == 'advice' else (4, 4)
        for pair in range(pairs):
            values = [e for e in rows if e['campaign'] == campaign and e['pair'] == pair]
            if len({(e['position'], e['rep']) for e in values}) != 2 * reps:
                raise ValueError('Missing/duplicate pair positions')
            if len({e['input_sha256'] for e in values}) != 1 or len({e['embedding_sha256'] for e in values}) != 1:
                raise ValueError('Input or exact row replay differs')
            if {e['candidate'] for e in values} != {False, True}:
                raise ValueError('Missing policy control')
    return rows, receipt


def summary(rows):
    s = [e['ple'] for e in rows]
    return dict(samples=len(rows), median_ms=median(e['seconds'] * 1000 for e in rows),
                min_ms=min(e['seconds'] * 1000 for e in rows), max_ms=max(e['seconds'] * 1000 for e in rows),
                median_resident_before_percent=median(100 * e['resident_before'] / e['page_count'] for e in rows),
                physical_read_mib_mean=sum(e['physical_read_bytes'] for e in rows) / len(rows) / 2**20,
                returned_mib_mean=sum(e['ple']['returned_bytes'] for e in rows) / len(rows) / 2**20,
                cache_hit_percent=100 * sum(e['cache_hits'] for e in s) / sum(e['unique_rows'] for e in s),
                cache_bytes=sorted({e['cache_bytes'] for e in rows}), cache_slots=sorted({e['cache_slots'] for e in rows}))


def arm(root):
    rows, receipt = read(root)
    result = {'root': str(root), 'state': receipt['state'], 'command_exits': [c['exit_code'] for c in receipt['commands']],
              'verified_artifacts': len(receipt['artifacts']), 'binary_sha256': receipt['binary_sha256'], 'advice': {}, 'capacity': {}}
    for name, candidate in [('reference', False), ('candidate', True)]:
        policy = [r for r in rows if r['campaign'] == 'advice' and r['candidate'] == candidate]
        result['advice'][name] = {
            'new_set_first_position': summary([r for r in policy if r['position'] == 0 and r['rep'] == 0]),
            'same_set_second_position': summary([r for r in policy if r['position'] == 1 and r['rep'] == 0]),
            'owned_cache_repeat': summary([r for r in policy if r['rep'] == 1])}
        capacity = [r for r in rows if r['campaign'] == 'capacity' and r['candidate'] == candidate]
        if capacity:
            result['capacity'][name] = {'fresh_owned_cache': summary([r for r in capacity if r['rep'] == 0]),
                                        'owned_cache_repeats': summary([r for r in capacity if r['rep'] > 0])}
    result['first_position_order'] = [{k: e[k] for k in ('pair', 'candidate', 'seconds', 'resident_before', 'page_count', 'physical_read_bytes')}
                                      for e in rows if e['campaign'] == 'advice' and e['position'] == 0 and e['rep'] == 0]
    return result, rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--q2', type=Path, required=True)
    p.add_argument('--ud', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    q2, qr = arm(a.q2); ud, ur = arm(a.ud)
    qinputs = {e['pair']: e['input_sha256'] for e in qr if e['campaign'] == 'advice'}
    uinputs = {e['pair']: e['input_sha256'] for e in ur}
    if qinputs != uinputs:
        raise ValueError('Q2/UD diagnostic inputs differ')
    result = dict(scope='Original-row I/O only; no model forward, no throughput promotion',
                  limits=['First-position policies use distinct ABBA-balanced row sets; they are not identical cold storage states.',
                          'No shared pages are evicted. Mincore reports requested-page residency outside timers.',
                          'The process read_bytes counter is observed around the gather; no model weights occupy GPU/UMA memory.',
                          'Identical second-position reads test byte equality after storage warming.',
                          'Cache capacity is a separate mechanism; timings do not include allocation/destruction.'],
                  input_sha256=qinputs, q2=q2, ud=ud)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    for model in ('q2', 'ud'):
        for name, data in result[model]['advice'].items(): print(model, 'advice', name, json.dumps(data['new_set_first_position']))
        for name, data in result[model]['capacity'].items(): print(model, 'capacity', name, json.dumps(data['owned_cache_repeats']))


if __name__ == '__main__':
    main()
