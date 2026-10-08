#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rank unmeasured mechanisms using captured routes and retained device ISA."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    static = module('analyze-q2-iq2-four-wave-static.py')
    sha = static.sha
    routing_path = ROOT/'config/q2-current-routing-v2-results.json'
    routing = json.loads(routing_path.read_text())
    metadata_path = ROOT/'config/q2-ssm-fixed-bounds-static.json'
    metadata = json.loads(metadata_path.read_text())
    assembly_path = ROOT/metadata['candidate_assembly_path']
    assert sha(assembly_path) == metadata['candidate_assembly_sha256']
    parsed = static.group.old.isa.parse(assembly_path)
    kernels = {}
    for width in (16, 48, 64, 128):
        matches = [(symbol, data) for symbol, data in parsed.items()
                   if 'RoutedF16GEMMKernel' in symbol and
                   f'WeightTypeE16ELi128ELi{width}ELi2ELb1ELb0ELb0EEEv' in symbol]
        assert len(matches) == 1
        symbol, data = matches[0]
        kernels[str(width)] = dict(symbol=symbol, resources=data['resources'],
            static_barrier_sites=data['mnemonics']['s_barrier'],
            compiler_comments=static.group.static.compiler_comments(assembly_path.read_text(), symbol))
    eligible = whole = continued = active = 0
    per_layer = []
    for layer in routing['layers']:
        wide, tail, narrow = [], [], []
        parent_wide, parent_tail = [], []
        for expert, n in enumerate(layer['counts']):
            active += n > 0
            groups = (n+63)//64
            parent_wide.extend((expert, j*128, 128) for j in range(groups//2))
            if groups % 2:
                start = (groups-1)*64
                parent_tail.append((expert, start, 64))
                if n-start <= 16:
                    narrow.append((expert, start//16, 16))
                    eligible += 1
                    whole += start == 0
                    continued += start != 0
                else:
                    tail.append((expert, start//64, 64))
            wide.extend((expert, j, 128) for j in range(groups//2))
        # Independent row ownership proof, including nonzero-offset short tails.
        expected = {(expert, row) for expert, n in enumerate(layer['counts']) for row in range(n)}
        actual = []
        for expert, index, width in wide+tail+narrow:
            begin = index*width
            actual.extend((expert, row) for row in range(begin, min(begin+width, layer['counts'][expert])))
        assert len(actual) == len(set(actual)) == 20480 and set(actual) == expected
        assert len(wide)+len(tail)+len(narrow) == len(parent_wide)+len(parent_tail)
        assert [(e, j*128, w) for e, j, w in wide] == parent_wide
        per_layer.append(dict(layer=layer['layer'], wide128=len(wide), tail64=len(tail),
            tail16=len(narrow), logical_tail_capacity_before=len(parent_tail)*64,
            logical_tail_capacity_after=len(tail)*64+len(narrow)*16))
    tail_total = routing['summaries']['tail64_live_rows']['tiles']
    assert eligible == 9016 and tail_total == 12753
    layers = routing['layers']
    chosen = sorted({0, max(per_layer, key=lambda row:row['tail16'])['layer'],
                     min(per_layer, key=lambda row:row['tail16'])['layer']})
    fixtures = dict(schema='synapse-lie.q2-fixed-input-route-fixtures.v1',
        routing_result_sha256=sha(routing_path), binary_sha256=routing['binary_sha256'],
        input_sha256=routing['input_sha256'], experts=512, n_tokens=2048, used=10,
        selection='Layer0 plus minimum/maximum number of <=16-row tails; no performance-based selection',
        layers=[dict(layer=i, counts=layers[i]['counts']) for i in chosen],
        model_operands=False, intended_use='Synthetic kernel operands with measured fixed-input routing counts')
    with (ROOT/'config/q2-fixed-input-route-fixtures.json').open('x') as stream:
        json.dump(fixtures, stream, indent=2)
        stream.write('\n')
    report = dict(schema='synapse-lie.q2-routing-opportunities.v1',
        inputs={str(p.relative_to(ROOT)):sha(p) for p in (routing_path, metadata_path, assembly_path)},
        existing_kernel_metadata=kernels, eligible_tail16=eligible,
        tail16_fraction=eligible/tail_total, whole_short_buckets=whole,
        nonzero_offset_short_tails=continued, active_expert_layer_pairs=active,
        map_proof_layers=48, map_proof_rows=48*20480,
        logical_tail_capacity_before=sum(r['logical_tail_capacity_before'] for r in per_layer),
        logical_tail_capacity_after=sum(r['logical_tail_capacity_after'] for r in per_layer),
        per_layer=per_layer, representative_layers=chosen,
        priority=[
            dict(rank=1, mechanism='Select existing BN16 for tails containing1..16 live rows; '
                 'keep BN128/64 for other descriptors',
                 rationale='Covers70.697% of tail descriptors and changes compile-time resource use: '
                 'VGPR104->86, LDS17536->11392, static barrier sites10->4. No new arithmetic kernel required.',
                 distinction='Earlier short48 selected whole buckets1..48 and regressed; this narrower '
                 'case also remaps nonzero-offset tails in units of16, without changing descriptor count.',
                 risk='Original BN64 already skips empty WMMA fragments and activation stores. '
                 'Resource reductions are not measured occupancy or speed. Extra dispatch and '
                 'separate kernel scheduling can offset them. Component and original model remain required.'),
            dict(rank=2, mechanism='IQ2 BN128 activation-fragment reuse with bounded live accumulators',
                 rationale='92.77% of logical row capacity is used; saved1571 attribution135.808ms. '
                 'Full-width efficiency is a separate problem from short tails.',
                 risk='Four-wave BN64 increased register pressure and regressed whole-model. '
                 'Do not double BN128 accumulators blindly.'),
            dict(rank=3, mechanism='Ordered Q2-down consumer fusion or elimination of an HC full-buffer pass',
                 rationale='Saved attribution161.558ms down plus186.168ms combine/norm/inject offers '
                 'larger absolute scope; retain all ten experts in the original reduction order.',
                 risk='Requires a concrete cross-block ownership design. Unordered atomics change '
                 'arithmetic; ten F32 passes can exceed the current half-buffer traffic.')],
        lower_priority='Four-wave only for tails49..64 reaches761/12753 descriptors (5.967%). '
            'Streaming cache with full residency, further host callbacks and generic SSM predicates '
            'have weaker evidence after measured negatives. No success probabilities are established.',
        performance_gain_measured=False, binary_recompiled=False, gpu_run=False,
        retained_pp=1585.308983, retained_tg=25.16079073, goal_met=False)
    with (ROOT/'config/q2-route-opportunities.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key:report[key] for key in ('eligible_tail16', 'tail16_fraction',
        'whole_short_buckets', 'nonzero_offset_short_tails', 'map_proof_layers',
        'logical_tail_capacity_before', 'logical_tail_capacity_after', 'representative_layers')}))


if __name__ == '__main__':
    main()
