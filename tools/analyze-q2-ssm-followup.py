#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Analyze new SSM candidates using the fixed protocol and saved comparisons."""
import argparse
import datetime
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm_original_analysis', ROOT / 'tools/analyze-q2-ssm-row-group-component.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
hc = original.hc
require, read, sha = hc.require, hc.read, hc.sha
REGISTRY = 'config/q2-ssm-followup-runtime-source.json'
VARIANTS = ('ssm-fixed-shape', 'ssm-fixed-bounds', 'ssm-compact-lds', 'ssm-pingpong')
PROTOCOL = dict(
    model_performance_test_despite_numeric_or_timing_rejection=True, run_controls=False,
    input_sha256='75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35',
    context_capacity=9216, chunk=2048, prompt_tokens=2048, output_tokens=128,
    timed_decode_calls=127, warmups=1, repetitions=3, cooldown_seconds=15, mtp=False,
    full_curve=False, dependencies=False, tuning=False, cleanup=False,
    component_guard_failure_stops_device_work=True,
    component_unwritten_failure_stops_device_work=True,
    component_shapes=[1024, 1025, 1057, 2048, 2049],
    component_expected_output_pairs=30, component_expected_oracle_checks=60,
    component_expected_timing_samples=14, component_weight_rotation_bytes=133693440,
    component_output_rows=16384, component_inner=2560, component_rotations=3,
    component_convolution_channels=10240, component_convolution_taps=4,
    provider_file_count=1027, allocation_capacity_unchanged=True,
    safety_or_runtime_failure_exit=2, safe_numeric_failure_exit=1)


def validate_scope(plan, variant):
    require(variant in VARIANTS, 'Unknown new SSM variant')
    require(plan['schema'] == 'synapse-lie.q2-ssm-followup-plan.v1', 'Wrong campaign schema')
    for key, expected in PROTOCOL.items():
        require(type(plan.get(key)) is type(expected) and plan[key] == expected,
                'Fixed protocol changed: ' + key)
    require(len(plan['components']) == len(plan['arms']) == 1, 'Only one new candidate per plan')
    for key, mode in (('components', variant + '-check'), ('arms', 'q2-counting-' + variant)):
        require(plan[key][0]['variant'] == variant and plan[key][0]['mode'] == mode,
                'Mismatched candidate or mode')
    labels = [plan['host'], plan['components'][0]['label'], plan['arms'][0]['label']]
    require(len(set(labels)) == 3 and all(Path(s).name == s and s.startswith('q2-') for s in labels),
            'Invalid or repeated cohort label')


def bound_plan(path, variant):
    plan = read(path)
    validate_scope(plan, variant)
    bindings = {**plan['fixtures'], **plan['manifests']}
    require(REGISTRY in bindings and 'tools/analyze-q2-ssm-followup.py' in bindings and
            'tools/analyze-q2-ssm-row-group-component.py' in bindings,
            'Missing source registry or analysis binding')
    for name, digest in bindings.items():
        require(sha(ROOT / name) == digest, 'Frozen identity changed: ' + name)
    require(sha(ROOT / plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    info = read(ROOT / REGISTRY)['variants'][variant]
    require(plan['source_variant_manifest'] == info['manifest'], 'Wrong source manifest')
    for name, digest in info['bindings'].items():
        section = plan['manifests'] if name == info['manifest'] else plan['fixtures']
        require(section.get(name) == digest and sha(ROOT / name) == digest,
                'Source/fixture not frozen: ' + name)
    source = read(ROOT / info['manifest'])['variants'][variant]
    for key, digest in source.items():
        if key.endswith('_sha256'):
            require(sha(ROOT / source[key[:-7]]) == digest, 'Source ancestry changed: ' + key)
    require(len(source['files']) == 1027, 'Source inventory count changed')
    return plan, info, source


def analyze_events(events, plan, variant, exit_code):
    require(variant in VARIANTS, 'Unknown SSM source identity')
    prefix = 'ssm_row_group' if variant in VARIANTS[:2] else 'ssm_compact_lds'
    kinds = ('replay', 'oracle', 'timing', 'complete')
    allowed = {prefix + '_' + kind for kind in kinds}
    resource_events = [row for row in events if row.get('event') == prefix + '_resources']
    if prefix == 'ssm_compact_lds':
        allowed.add(prefix + '_resources')
        require(len(resource_events) == 2 and
                [row['candidate'] for row in resource_events] == [False, True],
                'Missing or duplicated resource metadata')
        for row in resource_events:
            require(row['measured_active_blocks'] is False and type(row['candidate']) is bool,
                    'Theoretical resource limits presented as active occupancy')
            for key in ('shared_bytes', 'local_bytes', 'registers', 'max_blocks_per_multiprocessor',
                        'device_shared_bytes_per_multiprocessor'):
                require(type(row[key]) is int and row[key] >= (0 if key == 'local_bytes' else 1),
                        'Invalid resource field: ' + key)
        require(resource_events[0]['device_shared_bytes_per_multiprocessor'] ==
                resource_events[1]['device_shared_bytes_per_multiprocessor'], 'Different resource devices')
    require(all(row.get('event') in allowed for row in events), 'Unexpected fixture event family')
    normalized = [dict(row, event='ssm_row_group_' + row['event'][len(prefix) + 1:])
                  for row in events if row['event'] != prefix + '_resources']
    result = original.analyze_events(normalized, plan, exit_code)
    for kind, field in (('replay', 'replay'), ('oracle', 'oracle'), ('timing', 'timings')):
        result[field] = [row for row in events if row['event'] == prefix + '_' + kind]
    require([(row['rep'], row['order']) for row in result['timings']] ==
            [(rep, order) for rep in range(7) for order in range(2)], 'Timing chronology changed')
    result.update(source_variant=variant, fixture_event_prefix=prefix, resources=resource_events,
                  resource_scope='HIP theoretical launch limits; active occupancy was not measured',
                  original_inputs_immutable_at_fixture_completion=True)
    return result


def component(path, plan, info, source, variant):
    arm = plan['components'][0]
    cohort = ROOT / 'evidence' / arm['label']
    receipt, transport = hc.curve.artifact_integrity(cohort)
    exits = [c['exit_code'] for c in receipt['commands']]
    require(exits in ([0, 0, 0], [0, 0, 1]) and receipt['finished_at'] and
            transport['exit_code'] == exits[-1] and receipt['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == variant and not transport['rebuild_mmq'] and
            not receipt['model_access'] and receipt['binary_sha256'] == receipt['binary_sha256_after'],
            'Incomplete, unsafe or mismatched component')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
            not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Component ownership changed')
    capsule = hc.capsule(cohort, plan['fixtures'], source['files'])
    events = [json.loads(line) for line in (cohort / 'results/03.log').read_text().splitlines()
              if line.startswith('{"event"')]
    analysis = analyze_events(events, plan, variant, exits[-1])
    require(analysis['fixture_event_prefix'] == info['event_prefix'], 'Wrong fixture family')
    return dict(schema='synapse-lie.q2-ssm-followup-component.v1', **capsule, **analysis,
                plan_sha256=sha(path), source_manifest_sha256=sha(ROOT / info['manifest']),
                device_work_safe=True, command_exits=exits, artifact_count=len(receipt['artifacts']),
                binary_sha256=receipt['binary_sha256'], model_inference=False,
                independent_model_quality_qualification=False, full_model_speedup=False,
                goal_met=False, timing_scope=plan['component_time_scope'])


def measurement_changes(model, references):
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {}
    for key, reference in references.items():
        changes[key] = {}
        for metric in metrics:
            candidate = model['measurements'][metric]['median']
            baseline = reference['measurements'][metric]['median']
            require(math.isfinite(candidate) and candidate > 0 and math.isfinite(baseline) and baseline > 0,
                    'Invalid model timing')
            changes[key][metric] = 100 * (candidate / baseline - 1)
    return changes


def model(path, plan, info, source, variant):
    host_path = ROOT / 'evidence' / plan['host']
    host = hc.curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            len(host['commands']) == 6, 'Host gate incomplete')
    for log, key in (('03.log', 'debug'), ('06.log', 'asan_ubsan')):
        require(plan['host_test_counts'][key] >= 27 and
                '100% tests passed out of ' + str(plan['host_test_counts'][key]) in
                (host_path / 'results' / log).read_text(), 'Missing host gate')
    host_binding = hc.capsule(host_path, plan['fixtures'])
    # Revalidate raw component artifacts now; a report flag alone cannot admit it.
    component_path = ROOT / ('config/q2-' + variant + '-component-results.json')
    require(read(component_path) == component(path, plan, info, source, variant),
            'Component report differs from retained raw evidence')
    arm = plan['arms'][0]
    cohort = ROOT / 'evidence' / arm['label']
    root, candidate = hc.prior.shared.arm(cohort, variant)
    receipt = hc.curve.artifacts(cohort)
    require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4 and receipt['model_access'],
            'Changed model command scope')
    require('-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
            '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
            receipt['commands'][-1]['argv'][-1] == 'bench2k' and not receipt.get('mmq_reuse') and
            not receipt.get('qualified_binary_replay'), 'Original tester or candidate build changed')
    require(sha(root / 'pp2048-input.i32') == plan['input_sha256'] and
            (root / 'pp2048-input.i32').stat().st_size == 2048 * 4, 'Fixed input changed')
    candidate.update(hc.capsule(cohort, plan['fixtures'], source['files']))
    candidate.update(command_exits=[c['exit_code'] for c in receipt['commands']],
                     artifact_count=len(receipt['artifacts']), input_sha256=plan['input_sha256'],
                     command_wall_seconds=[(datetime.datetime.fromisoformat(c['finished_at']) -
                         datetime.datetime.fromisoformat(c['started_at'])).total_seconds() for c in receipt['commands']],
                     compilation_excluded_from_pp_tg=True)
    references, replay = {}, {}
    for key, label, source_variant in (
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('best_parent', 'q2-down-register-scatter-model-r1', 'down-register-scatter')):
        ref_path = ROOT / 'evidence' / label
        ref_root, references[key] = hc.prior.shared.arm(ref_path, source_variant)
        hc.curve.artifacts(ref_path)
        replay[key] = hc.prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in (('fixed_q2', 'mixed'), ('fixed_ud', 'ud')):
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'], 'Fixed reference changed')
    parent = read(ROOT / 'config/q2-down-register-scatter-model-results.json')
    require(references['best_parent']['measurements'] == parent['model']['measurements'], 'Saved parent changed')
    loads = [json.loads(line) for line in (root / '04.log').read_text().splitlines()
             if line.startswith('{"event":"loaded"')]
    require(len(loads) == 1 and loads[0]['resident_bytes'] == 43156012544 and
            loads[0]['max_context'] == plan['context_capacity'] and loads[0]['prefill_chunk'] == plan['chunk'] and
            not loads[0]['mtp'], 'Model allocation, capacity, chunk or MTP changed')
    candidate['loaded'] = loads[0]
    release_path = ROOT / plan['release_path']
    release = read(release_path)
    require(release['state'] == 'Q2_SSM_FOLLOWUP_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and release['model_stats_unchanged'] and
            len(release['leases']) == 4 and all(r['unchanged_free_EX_NB'] for r in release['leases']),
            'GPU window not closed')
    require({row['label'] for row in release['cohorts']} ==
            {plan['host'], plan['components'][0]['label'], arm['label']}, 'Wrong release cohorts')
    changes = measurement_changes(candidate, references)
    checks = {key: dict(input_exact=value['input_exact'], output_tokens_exact=value['output_tokens_exact'],
                       changed_files=value['changed'],
                       max_matched_history_kl=max((f['kl_p_to_candidate'] for f in value['frontiers']
                                                  if f['matched_history']), default=None))
              for key, value in replay.items()}
    return dict(schema='synapse-lie.q2-ssm-followup-model.v1', plan_sha256=sha(path),
                source_variant=variant, source_manifest_sha256=sha(ROOT / info['manifest']),
                mechanism=source['mechanism'], host=host_binding, component_result_sha256=sha(component_path),
                model=candidate, references=references, replay=replay, checks=checks,
                candidate_median_change_percent=changes,
                within_arm_exact=candidate['within_arm_replay'] == dict(checks=9, exact=9),
                observed_pp_tg_point_parity=all(changes['fixed_ud'][metric] >= 0
                    for metric in ('prefill_tok_s', 'decode_steps_s')),
                release_at=release['at'], release_sha256=sha(release_path),
                controls_rerun=False, component_rerun=False, contemporaneous_bookends=False,
                numerical_acceptance=False, independent_model_quality=False, promoted=False,
                goal_met=False, full_curve_admitted=False,
                limits='One new candidate on unchanged exact2048/tg128. Historical comparisons, '
                'full samples and logits retained. Inherited F16 task quality, serving, concurrency '
                'and complete context-curve parity remain unqualified.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('component', 'model'))
    parser.add_argument('variant', choices=VARIANTS)
    parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args()
    output = ROOT / ('config/q2-' + args.variant + '-' + args.phase + '-results.json')
    require(not output.exists(), 'Refusing to overwrite candidate results')
    plan, info, source = bound_plan(args.plan, args.variant)
    analyze = component if args.phase == 'component' else model
    report = analyze(args.plan, plan, info, source, args.variant)
    hc.write(output, report)
    summary = dict(output=str(output.relative_to(ROOT)), source_variant=args.variant,
                   phase=args.phase, goal_met=False)
    if args.phase == 'component':
        summary.update(parent_exact=report['parent_exact'],
                       independent_operator_pass=report['independent_operator_pass'],
                       summaries=report['summaries'], resources=report['resources'])
    else:
        summary.update(measurements=report['model']['measurements'],
                       references={key: value['measurements'] for key, value in report['references'].items()},
                       changes=report['candidate_median_change_percent'], checks=report['checks'],
                       point_parity=report['observed_pp_tg_point_parity'])
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
