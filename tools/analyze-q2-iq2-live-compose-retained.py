#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify saved live-stage component artifacts without any runtime rerun."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc',ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    path = ROOT/'config/q2-live-stage-results.json'
    saved = hc.read(path)
    source = hc.read(ROOT/'config/q2-iq2-live-compose-source.json')['variants']['iq2-live-compose']
    hc.require(hc.sha(path) == source['retained_component_sha256'], 'Saved component changed')
    plan_path = ROOT/'config/q2-live-stage-plan.json'
    plan = hc.read(plan_path)
    hc.require(saved['plan_sha256'] == hc.sha(plan_path) and saved['exact'] and
               saved['numerical_pass'] and not saved['model_inference'], 'Retained scope changed')
    for name,digest in plan['source_manifests'].items():
        hc.require(hc.sha(ROOT/'config'/name) == digest, 'Historical source manifest changed')
    arms = {}
    for key,row in zip(('before','stage','after'),plan['arms']):
        directory = ROOT/'evidence'/row['label']
        receipt = hc.curve.artifacts(directory)
        hc.require(not receipt['model_access'] and len(receipt['commands']) == 3 and
                   len(receipt['artifacts']) == 106, 'Retained component scope changed')
        arm = saved['arms'][key]
        hc.require(arm['source_variant'] == row['variant'] and len(arm['checks']) == 51 and
                   arm['completion']['numerical_pass'], 'Retained operator checks changed')
        # Bind old fixture bytes to their old capsule, never to modified current fixtures.
        binding = hc.capsule(directory,plan['fixtures'])
        hc.require(binding['source_files_verified'] == 1020, 'Retained provider inventory changed')
        pairs = saved['pairs']['stage' if key == 'before' else key]
        hc.require(len(pairs) == 102, 'Retained output coverage changed')
        for name,output in pairs.items():
            f = directory/'results'/name
            digest = output['reference_sha256' if key == 'before' else 'sha256']
            hc.require(output['exact'] and f.stat().st_size == output['values']*4 and
                       hc.sha(f) == digest, 'Retained output changed: '+name)
        arms[key] = dict(label=row['label'],**binding,command_exits=[c['exit_code'] for c in receipt['commands']],
                         artifacts=106,outputs=102,independent_checks=51)
    report = dict(schema='synapse-lie.q2-iq2-live-compose-retained.v1',
        retained_component_result_sha256=hc.sha(path),retained_plan_sha256=hc.sha(plan_path),
        arms=arms,cells=saved['cells'],saved_samples=saved['samples'],
        historical_selection=saved['disposition'],historical_selection_unchanged=True,
        retained_component_rerun=False,new_composition_qualified=False,
        gpu_run=False,model_inference=False,goal_met=False)
    hc.write(ROOT/'config/q2-iq2-live-compose-retained-results.json',report)
    print(json.dumps(dict(saved_arms=3,saved_artifacts=318,saved_outputs_per_arm=102,
        saved_independent_checks_per_arm=51,retained_component_rerun=False,new_composition_qualified=False)))


if __name__ == '__main__':
    main()
