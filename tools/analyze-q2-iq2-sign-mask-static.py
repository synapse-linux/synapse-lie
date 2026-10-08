#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain signed-table ISA/resource evidence without inferring throughput."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-sign-mask-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module('analyze-q2-iq2-halfstage-static.py')
prepare = module('prepare-q2-iq2-sign-mask.py')


def main():
    output = ROOT/'config/q2-iq2-sign-mask-static.json'
    if output.exists():
        raise RuntimeError('Refusing to overwrite static evidence')
    manifest_path = ROOT/'config/q2-iq2-sign-mask-source.json'
    variant = json.loads(manifest_path.read_text())['variants']['iq2-sign-mask']
    if prepare.inventory(ROOT/variant['source']) != variant['files']:
        raise RuntimeError('Frozen provider inventory changed')
    for key in ('parent_manifest', 'measured_parent', 'control_include', 'patch'):
        if prior.sha(ROOT/variant[key]) != variant[key+'_sha256']:
            raise RuntimeError('Parent binding changed: '+key)
    paths = dict(parent=ROOT/'evidence/q2-iq2-raw-prefetch-preparation/candidate.s',
                 candidate=OUT/'candidate.s')
    parent, candidate = (prior.parse(paths[key]) for key in ('parent', 'candidate'))
    if parent.keys() != candidate.keys():
        raise RuntimeError('Production kernel inventory changed')
    changed = sorted(s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256'])
    affected = sorted(s for s in parent if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s)
    if len(parent) != 157 or changed != affected or len(affected) != 8:
        raise RuntimeError('Unrelated production kernel changed')
    for s in affected:
        p, c = parent[s], candidate[s]
        if (p['resources']['group_segment_fixed_size'] != c['resources']['group_segment_fixed_size'] or
                c['resources']['private_segment_fixed_size'] != 0):
            raise RuntimeError('LDS or private spill storage changed')
        for name in ('v_wmma_f32_16x16x16_f16', 'v_pk_fma_f16', 'v_pk_add_f16'):
            if p['mnemonics'].get(name, 0) != c['mnemonics'].get(name, 0):
                raise RuntimeError('Ordered arithmetic instruction count changed')
    table_symbols = {}
    for key, path in paths.items():
        table_symbols[key] = {name: int(size) for name, size in
            re.findall(r'^\s*\.size\s+([^,\n]*kIq2Half(?:HighGrid|SignMasks)[^,\n]*),\s*(\d+)',
                       path.read_text(), re.M)}
    report = dict(schema='synapse-lie.q2-iq2-sign-mask-static.v1',
        source_manifest_sha256=prior.sha(manifest_path), source_files_verified=1026,
        kernel_count=157, changed_iq2_bodies=8, unchanged_bodies=149,
        iq2_bodies={s: dict(parent=parent[s], candidate=candidate[s]) for s in affected},
        assemblies={key: dict(path=str(path.relative_to(ROOT)), sha256=prior.sha(path))
                    for key, path in paths.items()},
        table_symbols=table_symbols, table_device_bytes=1024,
        cpu_independent_scalar_format_checks=262144, parent_assembly_rebuilt=False,
        numerical_order_unchanged=True, lds_unchanged=True, private_bytes=0,
        initial_fixture_device_exit=0,
        initial_fixture_device_error=None,
        gpu_run=False, model_inference=False, numerical_acceptance=False, goal_met=False,
        limits='Static code/resources and exhaustive host format evidence only. Fewer table loads/masks and unchanged arithmetic do not prove cache behavior, occupancy or complete-model throughput.')
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    rows = []
    for s in affected:
        p, c = parent[s], candidate[s]
        rows.append(dict(symbol=s, instructions=[p['instructions'], c['instructions']],
            global_load_b64=[p['mnemonics'].get('global_load_b64', 0), c['mnemonics'].get('global_load_b64', 0)],
            vgpr=[p['resources']['next_free_vgpr'], c['resources']['next_free_vgpr']]))
    print(json.dumps(dict(unchanged_bodies=149, affected=rows, table_symbols=table_symbols, gpu_run=False)))


if __name__ == '__main__':
    main()
