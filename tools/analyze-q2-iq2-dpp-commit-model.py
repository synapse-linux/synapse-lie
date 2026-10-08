#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify one new Q2 IQ2 fixed bounds model against the unchanged saved comparisons."""
import datetime
import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = module_from_spec(spec)
spec.loader.exec_module(hc)
prior = hc.prior
require, sha, read = hc.require, hc.sha, hc.read


def main():
    variant = sys.argv[1]
    require(variant == 'iq2-dpp-commit', 'Unknown new variant')
    output = ROOT / ('config/q2-'+variant+'-model-results.json')
    require(not output.exists(), 'Refusing to overwrite model evidence')
    plan_path = ROOT / 'config/q2-iq2-dpp-commit-plan.json'
    plan = read(plan_path)
    require(len(plan['arms']) == 1 and len(plan['components']) == 1 and not plan['run_controls'] and
            not plan['component_rerun'] and not plan['controls_rebuilt_or_rerun'], 'Candidate-only scope changed')
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT / name) == expected, 'Frozen identity changed: ' + name)
    require(sha(ROOT / plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    host_path = ROOT / 'evidence' / plan['host']
    host = hc.curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6, 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 36' in (host_path / 'results' / name).read_text(), 'Missing host gate')
    host_binding = hc.capsule(host_path, plan['fixtures'])
    require(sha(host_path / 'results/result.json') == plan['host_result_sha256'],
            'Actual host receipt changed')
    component_path = ROOT / 'config/q2-iq2-dpp-commit-component-results.json'
    component = read(component_path)
    require(component['command_exits'] in ([0, 0, 0], [0, 0, 1]) and component['device_work_safe'] and
            len(component['replay']) == 113 and component['release_sha256'] == sha(ROOT / plan['release_path']),
            'New component safety or release binding differs')
    component_cohort = ROOT / 'evidence' / plan['components'][0]['label']
    hc.curve.artifact_integrity(component_cohort)
    arm = next(a for a in plan['arms'] if a['variant'] == variant)
    path = ROOT / 'evidence' / arm['label']
    root, model = prior.shared.arm(path, arm['variant'])
    receipt = hc.curve.artifacts(path)
    require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4 and receipt['model_access'],
            'Changed model command scope')
    require('-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
            '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
            receipt['commands'][-1]['argv'][-1] == 'bench2k' and not receipt.get('mmq_reuse') and
            not receipt.get('qualified_binary_replay'), 'Original tester or fresh candidate build changed')
    require(sha(root / 'pp2048-input.i32') == plan['input_sha256'] and
            (root / 'pp2048-input.i32').stat().st_size == 2048 * 4, 'Fixed input changed')
    provider = read(ROOT / 'config/q2-iq2-dpp-commit-source.json')['variants'][arm['variant']]
    model.update(hc.capsule(path, plan['fixtures'], provider['files']))
    require(model['source_files_verified'] == 1029, 'Provider file count changed')
    model.update(command_exits=[c['exit_code'] for c in receipt['commands']],
                 artifact_count=len(receipt['artifacts']),
                 command_wall_seconds=[(datetime.datetime.fromisoformat(c['finished_at']) -
                     datetime.datetime.fromisoformat(c['started_at'])).total_seconds() for c in receipt['commands']],
                 compilation_excluded_from_pp_tg=True, input_sha256=plan['input_sha256'])
    references, replay = {}, {}
    for key, label, reference_variant in (
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('stable_parent', 'q2-ssm-fixed-bounds-model-r1', 'ssm-fixed-bounds'),
        ('best_parent', 'q2-iq2-fixed-bounds-model-r1', 'iq2-fixed-bounds')):
        ref_path = ROOT / 'evidence' / label
        ref_root, references[key] = prior.shared.arm(ref_path, reference_variant)
        hc.curve.artifacts(ref_path)
        replay[key] = prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'], 'Fixed reference changed')
    parent = read(ROOT / 'config/q2-iq2-fixed-bounds-model-results.json')
    require(references['best_parent']['measurements'] == parent['model']['measurements'] and
            references['best_parent']['samples'] == parent['model']['samples'] and
            references['best_parent']['binary_sha256'] == parent['model']['binary_sha256'], 'Saved best parent changed')
    load_events = [json.loads(line) for line in (root/'04.log').read_text().splitlines()
                   if line.startswith('{"event":"loaded"')]
    parent_log = ROOT/'evidence/q2-ssm-fixed-bounds-model-r1/results/04.log'
    parent_load = [json.loads(line) for line in parent_log.read_text().splitlines()
                   if line.startswith('{"event":"loaded"')]
    require(len(load_events) == len(parent_load) == 1, 'Missing actual load event')
    require(load_events[0]['resident_bytes'] == parent_load[0]['resident_bytes'] == 43156012544,
            'Compact model resident memory changed')
    require(load_events[0]['max_context'] == plan['context_capacity'] and
            load_events[0]['prefill_chunk'] == plan['chunk'] and not load_events[0]['mtp'],
            'Actual model capacity/chunk/MTP changed')
    require(all(load_events[0][key] == parent_load[0][key] for key in
                ('resident_bytes', 'deferred_scratch_bytes', 'mtp', 'max_context', 'prefill_chunk')),
            'Actual model load state changed')
    require(all(sample['prompt_tokens'] == 2048 and sample['output_tokens'] == 128 and
                sample['decode_steps'] == 127 and sample['session_bytes'] == 376777748
                for sample in model['samples']), 'Fixed counting sample scope changed')
    model['loaded'] = load_events[0]

    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {metric: 100 * (model['measurements'][metric]['median'] /
                   ref['measurements'][metric]['median'] - 1) for metric in metrics} for key, ref in references.items()}
    release_path = ROOT / 'config/q2-iq2-dpp-commit-window-release.json'
    release = read(release_path)
    require(release['state'] == 'Q2_IQ2_DPP_COMMIT_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'] and
            all(row['unchanged_free_EX_NB'] for row in release['leases']), 'GPU window not closed')
    require({row['label'] for row in release['cohorts']} == {plan['host'], *(a['label'] for a in plan['components']), *(a['label'] for a in plan['arms'])},
            'Window cohort scope changed')
    checks = {}
    for key, value in replay.items():
        matched = [f for f in value['frontiers'] if f['matched_history']]
        checks[key] = dict(input_exact=value['input_exact'], output_tokens_exact=value['output_tokens_exact'],
                           changed_files=value['changed'],
                           max_matched_history_kl=max((f['kl_p_to_candidate'] for f in matched), default=None))
    report = dict(schema='synapse-lie.q2-iq2-dpp-commit-model.v1', plan_sha256=sha(plan_path),
                  host=host_binding, component_result_sha256=sha(component_path), source_variant=variant, additional_table_device_bytes=0,
                  model=model, references=references, replay=replay, checks=checks,
                  candidate_median_change_percent=changes,
                  within_arm_exact=model['within_arm_replay'] == dict(checks=9, exact=9),
                  observed_pp_tg_point_parity=all(changes['fixed_ud'][metric] >= 0
                      for metric in ('prefill_tok_s', 'decode_steps_s')),
                  release_at=release['at'], release_sha256=sha(release_path),
                  controls_rerun=False, component_rerun=False, contemporaneous_bookends=False,
                  original_tester_unchanged=True, numerical_acceptance=False,
                  independent_model_quality=False, promoted=False, goal_met=False, full_curve_admitted=False,
                  limits='One new candidate on original exact2048/tg128; complete samples and logits retained. '
                  'Only unpacked IQ2 four-lane integer transport at m640/k2560 BN64/128 changes; inherited fixed bounds remain. Scalar/decode and allocations/lifetimes remain unchanged. The inherited F16 representation still lacks independent task-quality qualification. Historical model comparators do not '
                  'establish contemporaneous repeatability, independent quality, serving or full-curve parity.')
    hc.write(output, report)
    print(json.dumps(dict(measurements=model['measurements'], changes=changes, checks=checks,
                          point_parity=report['observed_pp_tg_point_parity'], goal_met=False)))


if __name__ == '__main__':
    main()
