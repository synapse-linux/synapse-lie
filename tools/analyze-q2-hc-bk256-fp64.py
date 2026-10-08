#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recover unrounded small-shape HC errors from retained GPU arrays; no inference."""
from array import array
import hashlib
import json
from pathlib import Path
import struct
import sys
import math

ROOT = Path(__file__).resolve().parents[1]
K = 10240
M = 320


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edges(count, tile):
    return sorted({0, count-1} | {base+delta for base in range(0, count, tile)
        for delta in (0, 1, 15, 16, 31, 32, 63, 64, 127)
        if delta < tile and base+delta < count})


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def weight_rows():
    # Exact deterministic original fixture: xorshift32 seed1967; RNE F32
    # division by997, exact /64, then RNE half. These are synthetic weights,
    # not original model weights or a captured historical weight payload.
    wanted = set(edges(M, 64))
    rows = {}
    state = 1967
    mask = 0xffffffff
    for row in range(M):
        values = array('d') if row in wanted else None
        for _ in range(K):
            state ^= (state << 13) & mask
            state ^= state >> 17
            state ^= (state << 5) & mask
            if values is not None:
                value = f32((state%2001-1000)/997.0)/64.0
                values.append(struct.unpack('<e', struct.pack('<e', value))[0])
        if values is not None:
            rows[row] = values
    return rows


def tensors(folder, name, code, count, receipt):
    path = folder/name
    data = path.read_bytes()
    metadata = receipt['artifacts'][name]
    if len(data) != count*struct.calcsize(code) or sha(path) != metadata['sha256']:
        raise ValueError('Retained tensor changed: '+name)
    result = [v[0] for v in struct.iter_unpack('<'+code, data)]
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Nonfinite retained tensor')
    return result


def main():
    if sys.byteorder != 'little':
        raise ValueError('Recorded fixture host is little-endian')
    output = ROOT/'config/q2-hc-bk256-small-fp64-results.json'
    if output.exists():
        raise ValueError('Refusing to overwrite independent replay')
    paths = {key: ROOT/'evidence'/('q2-hc-bk256-'+key+'-component-r1')/'results'
             for key in ('initial', 'bounded')}
    receipts = {key: json.loads((p/'result.json').read_text()) for key,p in paths.items()}
    shared = []
    for name, meta in receipts['initial']['artifacts'].items():
        if name.endswith(('.f16', '.f32')):
            if receipts['bounded']['artifacts'][name] != meta or sha(paths['initial']/name) != meta['sha256'] or sha(paths['bounded']/name) != meta['sha256']:
                raise ValueError('Unroll siblings change complete saved output: '+name)
            shared.append(name)
    weights = weight_rows()
    rows = []
    folder = paths['bounded']
    for n, pattern in ((96, 0), (97, 1), (129, 2)):
        for moe in (0, 1):
            prefix = 'hc-bk256-n'+str(n)+'-p'+str(pattern)+'-moe'+str(moe)
            half = tensors(folder, prefix+'-reference-half.f16', 'e', n*K, receipts['bounded'])
            control = tensors(folder, prefix+'-reference-down.f32', 'f', n*M, receipts['bounded'])
            native = tensors(folder, prefix+'-paired-down.f32', 'f', n*M, receipts['bounded'])
            errors = {key: dict(error2=0., expected2=0., maximum=0., peak=0., values=0)
                      for key in ('library', 'native')}
            samples = []
            for t in edges(n, 128):
                activation = half[t*K:(t+1)*K]
                for m,w in weights.items():
                    expected = 0.
                    for x,y in zip(w, activation):
                        expected += x*y
                    observed = dict(library=control[t*M+m], native=native[t*M+m])
                    samples.append(dict(token=t, row=m, expected=expected, **observed))
                    for key,value in observed.items():
                        e = errors[key]
                        delta = value-expected
                        e['error2'] += delta*delta
                        e['expected2'] += expected*expected
                        e['maximum'] = max(e['maximum'], abs(delta))
                        e['peak'] = max(e['peak'], abs(expected))
                        e['values'] += 1
            summary = {key: dict(relative_rms=math.sqrt(e['error2']/max(e['expected2'],1e-60)),
                error_over_peak=e['maximum']/max(e['peak'],1e-30), samples=e['values'])
                for key,e in errors.items()}
            for value in summary.values():
                value['pass_original_limits'] = value['relative_rms'] <= .00002 and value['error_over_peak'] <= .00002
            sample_path = ROOT/'evidence/q2-hc-bk256-run-preparation'/(prefix+'-fp64.json')
            with sample_path.open('x') as stream:
                stream.write(json.dumps(samples, indent=2, allow_nan=False)+'\n')
            rows.append(dict(tokens=n, pattern=pattern, moe=bool(moe), summary=summary,
                sample_file=str(sample_path.relative_to(ROOT)), sample_sha256=sha(sample_path)))
    report = dict(schema='synapse-lie.q2-hc-bk256-small-fp64.v1', cases=rows,
        script_sha256=sha(Path(__file__)), sibling_saved_tensors_exact=len(shared),
        source_receipts={key:sha(p/'result.json') for key,p in paths.items()},
        original_limits=dict(relative_rms=.00002,error_over_peak=.00002),
        reason='hipBLASLt changed cout to fixed2; component error fields are rounded. Replay recovers small-shape errors without another GPU run.',
        weight_identity='Deterministic synthetic fixture source reconstruction, not captured old payload hash',
        arithmetic='Sequential FP64 dot over retained original half bits, matching existing analytic edges',
        covered_tokens=[96,97,129], covers_2048=False, model_forward=False,
        independent_model_quality=False, numeric_exact_library_rejection_preserved=True,
        new_gpu_run=False, goal_met=False)
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(sibling_saved_tensors_exact=len(shared), cases=[dict(tokens=r['tokens'],
        moe=r['moe'],summary=r['summary']) for r in rows], gpu_rerun=False)))


if __name__ == '__main__':
    main()
