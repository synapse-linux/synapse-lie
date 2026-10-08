#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Locate HC decode stages by their checked dispatch sequence in retained traces."""
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profile', ROOT/'tools/analyze-q2-scaled-library-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
require = profile.require


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT/'config/q2-scaled-library-profile-results.json'
    parent = json.loads(parent_path.read_text())
    arms = {}
    for name in ('q2','ud'):
        old = parent['arms'][name]
        root = ROOT/old['path']
        dbpath = root/'results/profile/q2_results.db'
        require(digest(dbpath) == old['trace_sha256'], 'Historical trace changed')
        transport = json.loads((root/'transport.json').read_text())
        require(digest(root/'source.tar.gz') == transport['capsule_sha256'], 'Historical source capsule changed')
        with tarfile.open(root/'source.tar.gz') as archive:
            source = archive.extractfile('source/src/models/qwen38_flash_next/kernels/rocm/executor.cpp').read()
        # These calls bracket the scalar up projection in the actual frozen source.
        text = source.decode()
        hc = text[text.index('bool Executor::HcMix('):text.index('bool Executor::PleFetch(')]
        positions = [hc.index(s) for s in ('SiluScale(s_.lo,', 'Dense(m.up, s_.lo,',
                                          'HcMixEpilogue(xn, s_.hc_gate,')]
        require(positions == sorted(positions), 'Frozen launch sequence changed')
        with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True) as db:
            rows = db.execute('''SELECT kd.id,ks.display_name,kd.start,kd.end,
                kd.grid_size_x,kd.grid_size_y,kd.workgroup_size_x,kd.stream_id
                FROM rocpd_kernel_dispatch kd
                JOIN rocpd_info_kernel_symbol ks ON ks.id=kd.kernel_id
                ORDER BY kd.start''').fetchall()
        begin = [r for r in rows if 'Q2ProfileDecodeBegin' in r[1]]
        end = [r for r in rows if 'Q2ProfileDecodeEnd' in r[1]]
        require(len(begin) == len(end) == 1, 'Missing decode boundary')
        rows = [r for r in rows if begin[0][3] <= r[2] and r[3] <= end[0][2]]
        require(len(rows) == old['phases']['decode']['dispatches'] and
                sum(r[3]-r[2] for r in rows) == old['phases']['decode']['kernel_sum_ns'],
                'Complete decode accounting differs')
        overrides, blocks, up_symbols = {}, [], Counter()
        for i, down in enumerate(rows):
            down_name = 'HcDownF16VecKernel' if name == 'q2' else 'qfn_q8_hc_down_kernel'
            if down_name not in down[1]:
                continue
            require(i+4 < len(rows), 'Incomplete HC block')
            silu = rows[i+1]
            require('SiluScaleKernel' in silu[1], 'Missing HC activation')
            j = i+2
            entries = [('hc_down_projection',down),('hc_silu',silu)]
            if 'quantize_q8_1(' in rows[j][1]:
                entries.append(('hc_up_input_quantization',rows[j]));j += 1
            up, epilogue = rows[j:j+2]
            up_name = 'HcUpF16VecKernel' if name == 'q2' else 'mul_mat_vec_q8<1, false, 1, false>'
            require(up_name in up[1] and 'HcMixEpilogueKernel' in epilogue[1], 'HC up sequence differs')
            require((len(entries) == 3) is (name == 'ud'), 'Unexpected activation precision path')
            entries.extend([('hc_up_projection',up),('hc_mix_epilogues',epilogue)])
            require(len({r[7] for _,r in entries}) == 1, 'HC stage crossed streams')
            for k in range(1,len(entries)):
                require(entries[k][1][2] >= entries[k-1][1][3], 'Overlapping/reordered HC operations')
            for group,r in entries:
                require(r[0] not in overrides, 'Duplicate HC attribution')
                overrides[r[0]] = group
            up_symbols[up[1]] += 1
            blocks.append(dict(down_dispatch_id=down[0],up_dispatch_id=up[0],
                               epilogue_dispatch_id=epilogue[0],
                               up_grid=list(up[4:7]),up_ns=up[3]-up[2]))
        require(len(blocks) == 1455, 'Expected 97 HC calls per token across 15 decode steps')
        groups = defaultdict(lambda:dict(calls=0,ns=0))
        for r in rows:
            require(r[3] > r[2], 'Invalid duration')
            group = overrides.get(r[0],profile.category(r[1],set()))
            groups[group]['calls'] += 1; groups[group]['ns'] += r[3]-r[2]
        require(sum(v['calls'] for v in groups.values()) == len(rows) and
                sum(v['ns'] for v in groups.values()) == old['phases']['decode']['kernel_sum_ns'],
                'Lost or double-counted dispatch')
        for value in groups.values():
            value['ms_per_token'] = value['ns']/15/1e6
        arms[name] = dict(trace=str(dbpath.relative_to(ROOT)),trace_sha256=old['trace_sha256'],
            source_capsule_sha256=transport['capsule_sha256'],executor_sha256=hashlib.sha256(source).hexdigest(),
            decode_steps=15,dispatches=len(rows),kernel_sum_ns=sum(r[3]-r[2] for r in rows),
            groups=dict(groups),hc_up_symbols=dict(up_symbols),hc_blocks=blocks)
    groups = set(arms['q2']['groups']) | set(arms['ud']['groups'])
    delta = []
    for group in groups:
        q,u = (arms[a]['groups'].get(group,dict(ns=0,calls=0)) for a in ('q2','ud'))
        delta.append(dict(group=group,q2_ns=q['ns'],ud_ns=u['ns'],q2_calls=q['calls'],
                          ud_calls=u['calls'],delta_ns=q['ns']-u['ns'],
                          delta_ms_per_token=(q['ns']-u['ns'])/15/1e6))
    delta.sort(key=lambda r:-r['delta_ns'])
    require(sum(r['delta_ns'] for r in delta) == parent['deltas']['decode']['kernel_sum_delta_ns'],
            'Changed total deficit')
    report = dict(scope='Reattribution of existing marked pp2048/tg16 traces, 15 timed decode calls; no new GPU run',
        parent=str(parent_path.relative_to(ROOT)),parent_sha256=digest(parent_path),arms=arms,deltas=delta,
        numerical_policy='Historical instrumentation replay only; inherited operator/KL rejection remains',
        limits='Launch sequence identifies HC up inside the generic UD Q8 kernel. Kernel sums are diagnostic and not unprofiled latency, physical bandwidth or a new performance result.',
        goal_met=False,promoted=False)
    output = ROOT/'config/q2-hc-decode-attribution.json'
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (ROOT/'docs/figures/q2-hc-decode-attribution.csv').open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(delta[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(delta)
    print(json.dumps(delta,indent=2))


if __name__ == '__main__':
    main()
