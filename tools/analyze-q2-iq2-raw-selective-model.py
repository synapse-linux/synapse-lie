#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify selective Q2 model throughput, whole logits and actual routing scope."""
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
    output = ROOT / 'config/q2-iq2-raw-selective-model-results.json'
    require(not output.exists(), 'Refusing to overwrite model evidence')
    plan_path = ROOT / 'config/q2-iq2-raw-selective-plan.json'
    plan = read(plan_path)
    require(len(plan['arms']) == 1 and not plan['run_controls'] and
            plan['model_performance_test_despite_numeric_rejection'], 'Candidate-only scope changed')
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
    require(host_binding['capsule_sha256'] == read(ROOT / 'config/q2-iq2-raw-selective-host-results.json')['capsule_sha256'],
            'Host capsule changed')
    require(not plan['run_component'] and sha(ROOT / plan['retained_component']) ==
            plan['retained_component_sha256'], 'Retained component or no-rerun scope changed')
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
    provider = read(ROOT / 'config/q2-iq2-raw-selective-source.json')['variants'][arm['variant']]
    model.update(hc.capsule(path, plan['fixtures'], provider['files']))
    require(model['source_files_verified'] == 1027, 'Provider file count changed')
    model.update(command_exits=[c['exit_code'] for c in receipt['commands']],
                 artifact_count=len(receipt['artifacts']),
                 command_wall_seconds=[(datetime.datetime.fromisoformat(c['finished_at']) -
                     datetime.datetime.fromisoformat(c['started_at'])).total_seconds() for c in receipt['commands']],
                 compilation_excluded_from_pp_tg=True, input_sha256=plan['input_sha256'])
    events = [json.loads(line) for line in (root / '04.log').read_text().splitlines()
              if line.startswith('{"event"')]
    complete_index = next(i for i, event in enumerate(events) if event['event'] == 'complete')
    usage = [e for e in events if e['event'] == 'q2_scaled_tile_usage']
    route = [e for e in events if e['event'] == 'q2_scaled_tile_map']
    require(len(usage) == 1 and usage[0]['calls'] == usage[0]['records'] == 192 and
            usage[0]['capacity'] == 256 and len(route) == 192 and
            all(e['event'].startswith('q2_scaled_tile_') for e in events[complete_index+1:]),
            'Routing records missing, truncated, or emitted in timed model scope')
    require(all(e['event'] not in ('q2_scaled_tile_usage', 'q2_scaled_tile_map')
                for e in events[:complete_index]), 'Routing I/O occurred before complete event')
    for i, row in enumerate(route):
        require(row['index'] == i and len(row['histogram']) == 6 and
                sum(row['histogram']) == 512 and 0 < row['max_rows'] <= 2048 and
                0 <= row['selected_experts'] <= 512 and 0 <= row['selected_rows'] <= 20480 and
                row['original_reserved_rows'] == 48*row['original_tiles'] and
                row['reserved_rows'] == 48*row['narrow'] + 64*row['wide'] and
                row['reserved_rows'] <= row['original_reserved_rows'] and
                row['narrow'] + row['wide'] <= row['original_tiles'],
                'Changed expert histogram, selected capacity or row reservation')
    route_summary = dict(calls=192, layers=48, sessions=4,
        io_after_original_complete=True, selector_preparation_in_pp_timer=True,
        selected_expert_buckets=sum(r['selected_experts'] for r in route),
        selected_rows=sum(r['selected_rows'] for r in route),
        actual_rows=192*20480, narrow_tiles=sum(r['narrow'] for r in route),
        wide_tiles=sum(r['wide'] for r in route),
        original_tiles=sum(r['original_tiles'] for r in route),
        original_reserved_rows=sum(r['original_reserved_rows'] for r in route),
        reserved_rows=sum(r['reserved_rows'] for r in route),
        first_session=route[:48],
        all_sessions_histograms_exact=all({k:v for k,v in row.items() if k!='index'} ==
            {k:v for k,v in route[i%48].items() if k!='index'} for i,row in enumerate(route)))
    references, replay = {}, {}
    for key, label, variant in (
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('best_parent', 'q2-iq2-raw-prefetch-model-r1', 'iq2-raw-prefetch')):
        ref_path = ROOT / 'evidence' / label
        ref_root, references[key] = prior.shared.arm(ref_path, variant)
        hc.curve.artifacts(ref_path)
        replay[key] = prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'], 'Fixed reference changed')
    parent = read(ROOT / 'config/q2-iq2-raw-prefetch-model-results.json')
    require(references['best_parent']['measurements'] == parent['model']['measurements'], 'Saved best parent changed')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {metric: 100 * (model['measurements'][metric]['median'] /
                   ref['measurements'][metric]['median'] - 1) for metric in metrics} for key, ref in references.items()}
    release_path = ROOT / 'config/q2-iq2-raw-selective-window-release.json'
    release = read(release_path)
    require(release['state'] == 'Q2_IQ2_RAW_SELECTIVE_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'] and
            all(row['unchanged_free_EX_NB'] for row in release['leases']), 'GPU window not closed')
    require({row['label'] for row in release['cohorts']} == {plan['host'], arm['label']},
            'Window cohort scope changed')
    checks = {}
    for key, value in replay.items():
        matched = [f for f in value['frontiers'] if f['matched_history']]
        checks[key] = dict(input_exact=value['input_exact'], output_tokens_exact=value['output_tokens_exact'],
                           changed_files=value['changed'],
                           max_matched_history_kl=max((f['kl_p_to_candidate'] for f in matched), default=None))
    report = dict(schema='synapse-lie.q2-iq2-raw-selective-model.v1', plan_sha256=sha(plan_path),
                  host=host_binding, retained_component_result_sha256=plan['retained_component_sha256'],
                  model=model, references=references, replay=replay, checks=checks,
                  routing_records=route, routing_summary=route_summary,
                  candidate_median_change_percent=changes,
                  within_arm_exact=model['within_arm_replay'] == dict(checks=9, exact=9),
                  observed_pp_tg_point_parity=all(changes['fixed_ud'][metric] >= 0
                      for metric in ('prefill_tok_s', 'decode_steps_s')),
                  release_at=release['at'], release_sha256=sha(release_path),
                  controls_rerun=False, component_rerun=False, contemporaneous_bookends=False,
                  original_tester_unchanged=True, numerical_acceptance=False,
                  independent_model_quality=False, promoted=False, goal_met=False, full_curve_admitted=False,
                  limits='One new candidate on original exact2048/tg128; complete samples and logits retained. '
                  'Retained component failures are not relaxed. Historical model comparators do not '
                  'establish contemporaneous repeatability, independent quality, serving or full-curve parity.')
    hc.write(output, report)
    print(json.dumps(dict(measurements=model['measurements'], changes=changes, checks=checks,
                          routing={k:v for k,v in route_summary.items() if k!='first_session'},
                          point_parity=report['observed_pp_tg_point_parity'], goal_met=False)))


if __name__ == '__main__':
    main()
