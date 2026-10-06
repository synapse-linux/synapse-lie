#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Quantify already collected HC differences without changing acceptance gates."""
import array
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def ordered(bits):
    return 0x80000000 - (bits & 0x7fffffff) if bits >> 31 else 0x80000000 + bits


def main():
    if sys.byteorder != 'little':
        raise ValueError('Saved GPU arrays require little-endian decoding')
    result_path = ROOT / 'config/q2-hc-inject-reuse-component-results.json'
    result = load(result_path)
    release = ROOT / 'config/q2-hc-inject-reuse-window-release.json'
    if sha(release) != result['release_sha256'] or not result['device_work_safe']:
        raise ValueError('Expected released and safe collected component')
    closure = load(release)
    if closure['gpu_reserved'] or closure['kfd'] or closure['owned_group_members']:
        raise ValueError('Window is not released')
    rows = []
    for record in result['output_records']:
        if record['exact']:
            continue
        if record['field'] not in ('inject', 'post-inject'):
            raise ValueError('Unexpected differing output')
        arrays, bit_arrays = [], []
        for suffix in ('reference', 'candidate'):
            path = ROOT / 'evidence' / result['label'] / 'results' / (
                f"{record['case']}-{record['field']}-{record['rotation']}-{suffix}.bin")
            data = path.read_bytes()
            if (sha(path) != record[suffix + '_sha256'] or
                    len(data) != record['bytes'] + 128 or
                    data[:64] != b'\xa5' * 64 or data[-64:] != b'\xa5' * 64):
                raise ValueError('Saved difference identity or guards changed')
            values, bits = array.array('f'), array.array('I')
            values.frombytes(data[64:-64])
            bits.frombytes(data[64:-64])
            if len(values) != len(bits) or not all(math.isfinite(v) for v in values):
                raise ValueError('Nonfinite or malformed saved array')
            arrays.append(values)
            bit_arrays.append(bits)
        reference, candidate = arrays
        differences = [float(b) - float(a) for a, b in zip(reference, candidate)]
        squared_error = math.fsum(d * d for d in differences)
        squared_reference = math.fsum(float(a) * float(a) for a in reference)
        rows.append(dict(case=record['case'], field=record['field'],
            rotation=record['rotation'], values=len(reference),
            changed=sum(a != b for a, b in zip(*bit_arrays)),
            max_abs=max(abs(d) for d in differences),
            RMSE=math.sqrt(squared_error / len(reference)),
            relative_L2=math.sqrt(squared_error / squared_reference),
            max_ULP=max(abs(ordered(a) - ordered(b)) for a, b in zip(*bit_arrays))))
    if len(rows) != 60 or sum(r['exact'] for r in result['output_records']) != 140:
        raise ValueError('Complete replay count changed')

    # Inspect the frozen original ISA, rather than infer contraction from C++.
    static = load(ROOT / 'config/q2-ssm-fixed-bounds-static.json')
    assembly_path = ROOT / static['candidate_assembly_path']
    if sha(assembly_path) != static['candidate_assembly_sha256']:
        raise ValueError('Original ISA identity changed')
    assembly = assembly_path.read_text()
    symbol = next(m for m in re.finditer(r'^([^ \n:]+):.*$', assembly, re.M)
                  if 'HcMixEpilogueVec4KernelIfLb0EE' in m.group(1))
    body = assembly[symbol.end():assembly.index('.Lfunc_end', symbol.end())]
    anchors = ('global_load_b128 v[1:4], v[19:20], off',
               'global_load_b128 v[20:23], v[17:18], off',
               'v_mul_f32_e32 v21, v2, v21',
               'v_fmac_f32_e32 v21, v1, v20',
               'v_fmac_f32_e32 v21, v3, v22',
               'v_fmac_f32_e32 v21, v4, v23')
    if not all(anchor in body for anchor in anchors):
        raise ValueError('Pinned original operand trace changed')
    draft_path = ROOT / 'experiments/q2-hc-inject-reuse-draft-v3.inc'
    draft = draft_path.read_text()
    if draft.count('dot[o] = __fmul_rn(q.x, v.x);') != 2:
        raise ValueError('Frozen private first product changed')
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-difference-audit.v1',
        component_results_sha256=sha(result_path), release_sha256=sha(release),
        rows=rows, maximum_abs=max(r['max_abs'] for r in rows),
        maximum_relative_L2=max(r['relative_L2'] for r in rows),
        maximum_ULP=max(r['max_ULP'] for r in rows),
        exact_other_outputs=140, differing_injection_outputs=60,
        original_assembly=str(assembly_path.relative_to(ROOT)),
        original_assembly_sha256=sha(assembly_path), original_symbol=symbol.group(1),
        original_operand_trace=list(anchors),
        original_first_output_product_order=['q.y*v.y', 'q.x*v.x', 'q.z*v.z', 'q.w*v.w'],
        draft_first_output_product_order=['q.x*v.x', 'q.y*v.y', 'q.z*v.z', 'q.w*v.w'],
        draft_include_sha256=sha(draft_path),
        source_order_alone_does_not_preserve_original_compiler_contraction=True,
        exact_full_difference_cause_proven=False, model_inference=False,
        full_model_harmlessness_proven=False, numerical_acceptance=False,
        tolerances_changed=False, independent_quality=False)
    output = ROOT / 'config/q2-hc-inject-reuse-difference-audit.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(outputs=len(rows), max_abs=report['maximum_abs'],
        max_relative_L2=report['maximum_relative_L2'],
        original_first_two_products_reversed=True, GPU_run=False)))


if __name__ == '__main__':
    main()
