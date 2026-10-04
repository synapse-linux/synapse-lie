#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the existing complete HC fixture against the frozen fixed-shape plan."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT/'config/q2-norm-fixed-results.json'
    samples = ROOT/'docs/figures/q2-norm-fixed-samples.csv'
    if output.exists() or samples.exists():
        raise ValueError('Refusing to overwrite retained results')
    plan_path = ROOT/'config/q2-norm-fixed-plan.json'
    plan = json.loads(plan_path.read_text())
    source_path = ROOT/'config/q2-norm-fixed-shape-source.json'
    assert sha(source_path) == plan['provider_manifest_sha256']
    source = json.loads(source_path.read_text())
    parent_path = ROOT/'config/q2-iq2-mixed-model-source.json'
    assert sha(parent_path) == source['parent_manifest_sha256']
    parent = json.loads(parent_path.read_text())
    for name, expected in plan['fixture_files'].items():
        assert sha(ROOT/name) == expected, name
    spec = importlib.util.spec_from_file_location('hc_sequence_audit', ROOT/'tools/analyze-q2-hc-sequence.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    arms = {}
    for name, label in plan['labels'].items():
        manifest = source if name == 'candidate' else parent
        provider = ROOT/manifest['candidate']
        assert {str(p.relative_to(provider)):sha(p) for p in provider.rglob('*')
                if p.is_file()} == manifest['files']
        transport = json.loads((ROOT/'evidence'/label/'transport.json').read_text())
        assert transport['source_path'] == manifest['candidate']
        arms[name] = audit.arm(label, library=True,
                              expected_library_source=plan['variants'][name],
                              record_output_mismatches=name == 'candidate')
    # Original controls must replay exactly. Candidate differences stay failures
    # in the report rather than preventing collection of their measured timings.
    for name in ('candidate','after'):
        for old,new in zip(arms['before']['replays'],arms[name]['replays']):
            assert old['label'] == new['label']
            for field in ('res','norm','half','down'):
                assert old['reference_'+field+'_sha256'] == new['reference_'+field+'_sha256']
    assert arms['after']['replays'] == arms['before']['replays']
    assert arms['after']['norm_oracles'] == arms['before']['norm_oracles']
    all_exact = all(not a['output_mismatches'] for a in arms.values())
    no_new_norm_failures = all(n['pass'] for a in arms.values() for n in a['norm_oracles'])
    comparisons = []
    selected = all_exact and no_new_norm_failures
    for moe in (False, True):
        def summary(name, paired):
            return next(s for s in arms[name]['summaries'] if s['moe'] == moe and s['paired'] == paired)
        candidate = summary('candidate', True)['median_us']
        reference = {n:summary(n, True)['median_us'] for n in ('before','after')}
        control = {n:summary(n, False)['median_us'] for n in arms}
        drift = 100*(max(control.values())/min(control.values())-1)
        ratios = {n:candidate/value for n,value in reference.items()}
        passing = all(v <= plan['gate']['candidate_paired_cycle_time_ratio_max_against_each_reference']
                      for v in ratios.values()) and drift <= plan['gate']['unchanged_unpaired_control_drift_max_percent']
        selected &= passing
        comparisons.append(dict(moe=moe,candidate_median_us=candidate,
            reference_median_us=reference,candidate_time_change_percent={n:100*(v-1) for n,v in ratios.items()},
            unchanged_unpaired_control_median_us=control,unchanged_control_range_percent=drift,
            frozen_performance_gate_pass=passing))
    report = dict(schema='synapse-lie.q2-norm-fixed-results.v1',
        plan_sha256=sha(plan_path),source_manifest_sha256=sha(source_path),
        scope='Existing complete ordinary/MoE producer and library consumer at2048, original paired reference/candidate/reference; no model throughput.',
        arms=arms,comparisons=comparisons,all_complete_outputs_exact=all_exact,
        all_independent_norm_checks_pass=no_new_norm_failures,
        independent_numerical_pass=all(not a['numerical_failures'] for a in arms.values()),
        disposition='SELECT_FIXED_REFERENCE_MODEL_POINT_WITH_QUALITY_OPEN' if selected else 'NO_MODEL_RUN_FROM_THIS_COMPONENT',
        fixed_reference_improvement_measured=False,model_inference=False,promoted=False,goal_met=False)
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    rows = [dict(arm=name,**t) for name,a in arms.items() for t in a['timings']]
    with samples.open('x') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(comparisons=comparisons,disposition=report['disposition'],
                          independent_numerical_pass=report['independent_numerical_pass'])))


if __name__ == '__main__':
    main()
