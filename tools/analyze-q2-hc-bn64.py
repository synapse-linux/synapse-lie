#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify two new BN64 component candidates and select at most one model."""
import json
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = spec_from_file_location(name,ROOT/'tools'/name)
    value = module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


hc = module('analyze-q2-hc-bk256.py')
require,sha,read = hc.require,hc.sha,hc.read


def ratio(arm):
    scopes = [s for s in arm['summaries'] if s['complete']]
    return sum(s['native']['median'] for s in scopes)/sum(s['library']['median'] for s in scopes)


def main():
    output = ROOT/'config/q2-hc-bn64-component-results.json'
    selection_path = ROOT/'config/q2-hc-bn64-selection.json'
    require(not output.exists() and not selection_path.exists(),'Refusing to overwrite results')
    plan_path = ROOT/'config/q2-hc-bn64-plan.json'
    plan = read(plan_path)
    for name,key in [('source_manifest','source_manifest_sha256'),
                     ('host_receipt','host_receipt_sha256'),
                     ('component_parent','component_parent_sha256'),
                     ('model_parent','model_parent_sha256'),
                     ('fixed_reference','fixed_reference_sha256'),
                     ('window_helper','window_helper_sha256')]:
        require(sha(ROOT/plan[name])==plan[key],'Frozen identity changed: '+name)
    host_path = ROOT/'evidence'/plan['host']
    host = hc.curve.artifacts(host_path)
    require(host['state']=='CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands'])==6,'Host gate incomplete')
    for name in ('03.log','06.log'):
        require('100% tests passed out of 23' in (host_path/'results'/name).read_text(),
                'Missing Debug/ASan gate')
    host_binding=hc.capsule(host_path,plan['fixtures'])
    require(host_binding['capsule_sha256']==read(ROOT/plan['host_receipt'])['capsule_sha256'],
            'Host capsule changed')
    sources=read(ROOT/plan['source_manifest'])
    arms={arm['key']:hc.component(ROOT/'evidence'/arm['label'],arm['variant'],plan,sources,
                                 rounded_errors=False) for arm in plan['component_arms']}
    parent=read(ROOT/plan['component_parent'])['arms']['bounded']
    parent_replay={e['label']:e for e in parent['replay']}
    for key,arm in arms.items():
        arm['normalized_complete_cycle_ratio']=ratio(arm)
        arm['parent_saved_tensors_exact']=sum(arm['saved_tensors'].get(n)==v
                                             for n,v in parent['saved_tensors'].items())
        arm['parent_full_replay_hashes_exact']=sum(
            all(e.get(k)==parent_replay[e['label']].get(k)
                for k in e if k.endswith('_sha256')) for e in arm['replay'])
        arm['down_fp64_checks']=[dict(label=e['label'],
            consumer='library' if e['label'].endswith('-reverse') else 'native',
            relative_rms=e['down_rrms'],error_over_peak=e['down_peak_scaled'],
            samples=e['down_oracle_values'],pass_original_limits=
                e['down_rrms']<=2e-5 and e['down_peak_scaled']<=2e-5) for e in arm['replay']]
    best=min(arms,key=lambda k:sum(s['native']['median'] for s in arms[k]['summaries'] if s['complete']))
    parent_ratio=ratio(parent)
    model_selected=arms[best]['normalized_complete_cycle_ratio']<parent_ratio
    selected_arm=next(a for a in plan['model_arms'] if a['key']==best) if model_selected else None
    selection=dict(schema='synapse-lie.q2-hc-bn64-selection.v1',
        plan_sha256=sha(plan_path),component_parent_sha256=plan['component_parent_sha256'],
        selected_key=best,selected_model_arm=selected_arm,model_selected=model_selected,
        parent_normalized_complete_cycle_ratio=parent_ratio,
        new_normalized_complete_cycle_ratio=arms[best]['normalized_complete_cycle_ratio'],
        relative_normalized_time_change_percent=100*(arms[best]['normalized_complete_cycle_ratio']/parent_ratio-1),
        at_most_one_new_model=True,qualified_model_controls_rerun=False,
        strict_numeric_rejection_retained=True,numeric_thresholds_changed=False,goal_met=False)
    report=dict(schema='synapse-lie.q2-hc-bn64-component.v1',plan_sha256=sha(plan_path),
        host=host_binding,arms=arms,parent_label=parent['label'],
        parent_saved_timings=parent['summaries'],selection=selection,
        sibling_saved_tensors_exact=sum(arms['token']['saved_tensors'].get(n)==v
                                       for n,v in arms['output']['saved_tensors'].items()),
        original_down_limits=dict(relative_rms=2e-5,error_over_peak=2e-5),
        controls_rerun=False,strict_rejections_retained=True,numerical_acceptance=False,
        independent_model_quality=False,model_forward=False,goal_met=False)
    hc.write(output,report)
    hc.write(selection_path,selection)
    print(json.dumps(dict(selection=selection,arms={key:dict(summaries=arm['summaries'],
        parent_saved_tensors_exact=arm['parent_saved_tensors_exact'],
        parent_full_replay_hashes_exact=arm['parent_full_replay_hashes_exact'],
        down_fp64_checks=arm['down_fp64_checks']) for key,arm in arms.items()})))


if __name__=='__main__':
    main()
