#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare saved component route geometry with the fixed-input model trace."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = {name:ROOT/path for name,path in {
        'profile':'config/q2-current-best-profile-results.json',
        'component':'config/q2-iq2-four-wave-component-results.json',
        'parent':'config/q2-ssm-fixed-bounds-model-results.json',
        'fixed':'config/q2-fixed-prefill-reference.json',
    }.items()}
    records = {name:json.loads(path.read_text()) for name,path in paths.items()}
    profile = records['profile']
    layers = profile['routing']['layers']
    assert len(layers)==48 and [r['layer'] for r in layers]==list(range(48))
    geometry = {key:dict(min=min(v),median=statistics.median(v),max=max(v),total=sum(v))
                for key in ('iq2_128_tiles','iq2_64_tiles','q2_48_tiles')
                for v in ([r[key] for r in layers],)}
    components = []
    for case in ('mixed-e64','mixed-e128','mixed-e512'):
        rows = [r for r in records['component']['timings'] if r['case']==case]
        assert len(rows)==14
        values = {(r['active_experts'],r['wide_tiles'],r['narrow_tiles']) for r in rows}
        assert len(values)==1
        experts,wide,narrow = values.pop()
        components.append(dict(case=case,active_experts=experts,iq2_128_tiles=wide,iq2_64_tiles=narrow))
    kernels = profile['phases']['prefill']['kernels']
    def cost(fragment):
        matches = [k for k in kernels if fragment in k['kernel']]
        assert len(matches)==1,fragment
        return matches[0]['total_ns']/1e6
    costs = dict(iq2_bn128=cost('WeightType)16, 128, 128, 2, true, false, false>'),
                 iq2_bn64=cost('WeightType)16, 128, 64, 2, true, false, false>'),
                 q2_down=cost('RoutedQ2HalfStorageKernel<'))
    parent = records['parent']['model']['measurements']['prefill_tok_s']['median']
    ud = records['fixed']['arms']['ud']['measurements']['prefill_tok_s']['median']
    gap_ms = 1000*(2048/parent-2048/ud)
    report = dict(schema='synapse-lie.q2-iq2-routing-coverage.v1',
        inputs={name:dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                for name,path in paths.items()},
        retained_pp=parent,fixed_ud_pp=ud,required_pp_gain_percent=100*(ud/parent-1),
        required_prefill_time_reduction_ms=gap_ms,profiled_variant='half-consumer-eight',
        profiled_saved_pp=1571.716479,profiled_layers=48,model_geometry=geometry,
        component_geometry=components,profiled_expert_ms=costs,
        sensitivity_scenarios=[dict(expert_time_reduction_fraction=f,
            saving_on_saved_trace_ms=f*sum(costs.values()),measured_gain=False) for f in (.1,.2)],
        finding='The512-expert component has zero wide tiles; every saved model layer has128..159 wide '
            'tiles plus89..359 narrow tiles. Expert cardinality alone does not reproduce the model workload.',
        next_required_observation='Capture or recover exact per-expert counts for the fixed input and retained '
            'provider; the saved dispatch geometry alone cannot identify one/two/three/four live16-row tail fragments.',
        prioritized_hypotheses=[
            'Use the real tail distribution to decide whether the four-wave route belongs only to sufficiently '
            'full tiles; preserve the original path for small tails. This is unimplemented and requires measurement.',
            'Reduce IQ2 BN128 repeated activation/dequantization work without doubling its accumulator live range; '
            'blindly extending four-wave BN64 is not justified by its negative model result.',
            'Remove Q2-down/expert-consumer materialization with deterministic per-expert accumulation ownership; '
            'previous layout-only and unordered-atomic proposals do not establish a saving.'
        ],
        limits='Saved trace costs are attribution on1571, not new1585 timings. Geometry mismatch does not isolate '
            'the cause of the four-wave model regression or prove any new candidate faster. No probability of '
            'success is measured. The original exact2048/tg128 acceptance benchmark is unchanged.',
        gpu_run=False,control_rerun=False,full_curve=False,goal_met=False)
    out = ROOT/'config/q2-iq2-routing-coverage.json'
    with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({key:report[key] for key in ('required_prefill_time_reduction_ms',
        'model_geometry','component_geometry','profiled_expert_ms','sensitivity_scenarios')}))


if __name__=='__main__':
    main()
