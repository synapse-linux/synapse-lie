#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify one new deferred IQ2 loading model against the unchanged saved comparisons."""
import datetime
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('hc', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = module_from_spec(spec)
spec.loader.exec_module(hc)
prior = hc.prior
require, sha, read = hc.require, hc.sha, hc.read


def main():
    output = ROOT / 'config/q2-iq2-raw-prefetch-model-results.json'
    require(not output.exists(), 'Refusing to overwrite model evidence')
    plan_path = ROOT / 'config/q2-iq2-raw-prefetch-plan-fixed.json'
    plan = read(plan_path)
    require(len(plan['arms']) == 1 and not plan['run_controls'] and
            plan['model_performance_test_despite_numeric_or_timing_rejection'], 'Candidate-only scope changed')
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT / name) == expected, 'Frozen identity changed: ' + name)
    require(sha(ROOT / plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    host_path = ROOT / 'evidence' / plan['host']
    host = hc.curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6, 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 25' in (host_path / 'results' / name).read_text(), 'Missing host gate')
    host_binding = hc.capsule(host_path, plan['fixtures'])
    require(host_binding['capsule_sha256'] == read(ROOT / 'config/q2-iq2-raw-prefetch-host-r2-results.json')['capsule_sha256'],
            'Host capsule changed')
    component_path = ROOT / 'config/q2-iq2-raw-prefetch-component-results.json'
    component = read(component_path)
    require(component['plan_sha256'] == sha(plan_path) and not component['model_inference'] and
            len(component['replay']) == 81 and len(component['timings']) == 42,
            'Component identity or complete timing evidence changed')
    arm = plan['arms'][0]
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
    provider = read(ROOT / 'config/q2-iq2-raw-prefetch-source.json')['variants'][arm['variant']]
    model.update(hc.capsule(path, plan['fixtures'], provider['files']))
    require(model['source_files_verified'] == 1025, 'Provider file count changed')
    model.update(command_exits=[c['exit_code'] for c in receipt['commands']],
                 artifact_count=len(receipt['artifacts']),
                 command_wall_seconds=[(datetime.datetime.fromisoformat(c['finished_at']) -
                     datetime.datetime.fromisoformat(c['started_at'])).total_seconds() for c in receipt['commands']],
                 compilation_excluded_from_pp_tg=True, input_sha256=plan['input_sha256'])
    references, replay = {}, {}
    for key, label, variant in (
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('best_parent', 'q2-iq2-halfbyte-model-r1', 'iq2-halfbyte-perm')):
        ref_path = ROOT / 'evidence' / label
        ref_root, references[key] = prior.shared.arm(ref_path, variant)
        hc.curve.artifacts(ref_path)
        replay[key] = prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'], 'Fixed reference changed')
    parent = read(ROOT / 'config/q2-iq2-halfbyte-model-results.json')
    require(references['best_parent']['measurements'] == parent['model']['measurements'], 'Saved best parent changed')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {metric: 100 * (model['measurements'][metric]['median'] /
                   ref['measurements'][metric]['median'] - 1) for metric in metrics} for key, ref in references.items()}
    release_path = ROOT / 'config/q2-iq2-raw-prefetch-r2-window-release.json'
    release = read(release_path)
    require(release['state'] == 'Q2_IQ2_RAW_PREFETCH_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'] and
            all(row['unchanged_free_EX_NB'] for row in release['leases']), 'GPU window not closed')
    require({row['label'] for row in release['cohorts']} == {plan['host'], plan['component']['label'], arm['label']},
            'Window cohort scope changed')
    checks = {}
    for key, value in replay.items():
        matched = [f for f in value['frontiers'] if f['matched_history']]
        checks[key] = dict(input_exact=value['input_exact'], output_tokens_exact=value['output_tokens_exact'],
                           changed_files=value['changed'],
                           max_matched_history_kl=max((f['kl_p_to_candidate'] for f in matched), default=None))
    report = dict(schema='synapse-lie.q2-iq2-raw-prefetch-model.v1', plan_sha256=sha(plan_path),
                  host=host_binding, component_result_sha256=sha(component_path), table_device_bytes=0,
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
                  'Synthetic whole-output equality is differential only. Historical model comparators do not '
                  'establish contemporaneous repeatability, independent quality, serving or full-curve parity.')
    hc.write(output, report)
    print(json.dumps(dict(measurements=model['measurements'], changes=changes, checks=checks,
                          point_parity=report['observed_pp_tg_point_parity'], goal_met=False)))


if __name__ == '__main__':
    main()
