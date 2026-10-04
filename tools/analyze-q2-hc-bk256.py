#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit retained HC components and the new fixed2048 model; never rerun controls."""
import datetime
import hashlib
import json
from pathlib import Path
import tarfile
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = spec_from_file_location(name, ROOT/'tools'/name)
    value = module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-norm-fixed-model.py')
shared, curve = prior.shared, prior.curve
require, sha, read = prior.require, prior.sha, prior.read


def capsule(path, fixtures, expected_source=None):
    with tarfile.open(path/'source.tar.gz') as archive:
        for name, expected in fixtures.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected,
                    'Frozen capsule fixture differs: '+name)
        files = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                 for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
    if expected_source is not None:
        require(files == expected_source, 'Frozen provider inventory differs')
    return dict(capsule_sha256=sha(path/'source.tar.gz'),
                archive_sha256=sha(path/'results.tar.gz'),
                fixture_files_verified=len(fixtures), source_files_verified=len(files))


def component(path, variant, plan, sources):
    receipt, transport = curve.artifact_integrity(path)
    require(transport['exit_code'] == 1 and transport['source_variant'] == variant and
            not transport['rebuild_mmq'], 'Component transport scope changed')
    require(receipt['state'] == 'FAILED' and receipt['mode'] == plan['component_mode'] and
            [c['exit_code'] for c in receipt['commands']] == [0, 0, 1] and
            not receipt['model_access'], 'Strict component rejection lost')
    require(receipt['binary_sha256'] == receipt['binary_sha256_after'] and
            receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4 and
            not receipt['preflight_kfd'] and not receipt['postflight_kfd'],
            'Binary or GPU ownership changed')
    root = path/'results'
    log = (root/'03.log').read_text()
    require(log.endswith('FAIL strict HC library replay; component timing retained; no model inference\n'),
            'Fixture aborted before final guards or timing')
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{')]
    timings = [e for e in events if e.get('event') == 'hc_bk256_timing']
    replay = [e for e in events if e.get('event') == 'hc_sequence_replay']
    norms = [e for e in events if e.get('event') == 'hc_sequence_norm_oracle']
    require(len(timings) == 56 and len(replay) == 22 and len(norms) == 20,
            'Incomplete component evidence')
    require(all(e['tokens'] == 2048 and e['iterations'] == 16 and
                e['weight_bytes'] == plan['weight_rotation_bytes'] and
                e['us_per_iteration'] > 0 for e in timings), 'Timing shape changed')
    require(all(e['res_exact'] and e['norm_exact'] and e['half_exact'] and
                e['scalar_half_exact'] and not e['down_exact'] for e in replay) and
            all(e['pass'] for e in norms), 'Unexpected replay or independent norm verdict')
    stats = []
    for moe in (False, True):
        for complete in (False, True):
            pair = {}
            for native in (False, True):
                samples = [e for e in timings if e['moe'] == moe and
                           e['complete'] == complete and e['native'] == native]
                require([e['rep'] for e in samples] == list(range(7)) and
                        [e['warmup'] for e in samples] == [True, True]+[False]*5 and
                        all(e['native'] == ((e['rep']+e['order']) % 2 != 0) for e in samples),
                        'Alternating arm order or repetition changed')
                pair['native' if native else 'library'] = shared.common.stats(
                    [e['us_per_iteration'] for e in samples if not e['warmup']])
            stats.append(dict(moe=moe, complete=complete, **pair,
                native_time_change_percent=100*(pair['native']['median']/pair['library']['median']-1)))
    tensors = {p.name: sha(p) for p in root.iterdir() if p.suffix in ('.f32', '.f16')}
    require(len(tensors) == 40, 'Saved full-tensor inventory changed')
    return dict(label=path.name, variant=variant,
        **capsule(path, plan['fixtures'], sources['variants'][variant]['files']),
        command_exits=[0, 0, 1], artifact_count=len(receipt['artifacts']),
        timings=timings, summaries=stats, replay=replay, independent_norm_checks=norms,
        saved_tensors=tensors, invalid_requests_per_shape=7,
        completion_verifies_guards_and_input_immutability=True,
        numeric_error_fields_precision='Original cout fixed2: rounded 0.00 is not zero error',
        numeric_error_fields_usable=False, timing_quantization_us=0.01,
        retained_strict_rejection=True)


def write(path, report):
    with path.open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+'\n')


def main():
    outputs = [ROOT/'config/q2-hc-bk256-component-results.json',
               ROOT/'config/q2-hc-bk256-fixed-model-results.json']
    require(not any(p.exists() for p in outputs), 'Refusing to overwrite results')
    plan_path = ROOT/'config/q2-hc-bk256-run-plan.json'
    plan = read(plan_path)
    require(sha(ROOT/plan['source_manifest']) == plan['source_manifest_sha256'] and
            sha(ROOT/plan['fixed_reference']) == plan['fixed_reference_sha256'] and
            sha(ROOT/plan['window_helper']) == plan['window_helper_sha256'] and
            sha(ROOT/plan['host_receipt']) == plan['host_receipt_sha256'], 'Frozen plan identity changed')
    sources = read(ROOT/plan['source_manifest'])
    host_path = ROOT/'evidence'/plan['host']
    host = curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands']) == 6 and
            all(c['exit_code'] == 0 for c in host['commands']), 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 23' in (host_path/'results'/name).read_text(),
                'Missing Debug/ASan gate')
    host_binding = capsule(host_path, plan['fixtures'])
    require(host_binding['capsule_sha256'] == read(ROOT/plan['host_receipt'])['capsule_sha256'],
            'Host capsule changed')
    components = {arm['key']: component(ROOT/'evidence'/arm['label'], arm['variant'], plan, sources)
                  for arm in plan['component_arms']}
    require(components['initial']['saved_tensors'] == components['bounded']['saved_tensors'] and
            components['initial']['replay'] == components['bounded']['replay'],
            'Unroll siblings changed whole-buffer outputs')
    selection = read(ROOT/'config/q2-hc-bk256-component-selection.json')
    require(selection['plan_sha256'] == sha(plan_path), 'Selection plan differs')
    selected = min(components, key=lambda k: sum(s['native']['median']
                   for s in components[k]['summaries'] if s['complete']))
    require(selected == selection['selected_key'], 'Faster complete-cycle selection differs')
    arm = selection['selected_model_arm']
    require(arm in plan['model_arms'] and arm['key'] == selected, 'Selected model arm differs')
    other_arms = [a for a in plan['model_arms'] if a['key'] != selected]
    require(not any((ROOT/'evidence'/a['label']/'results/result.json').exists() for a in other_arms),
            'More than one model candidate executed')
    fp64_path = ROOT/'config/q2-hc-bk256-small-fp64-results.json'
    fp64 = read(fp64_path)
    require(sha(ROOT/'tools/analyze-q2-hc-bk256-fp64.py') == fp64['script_sha256'] and
            fp64['original_limits'] == dict(relative_rms=2e-5, error_over_peak=2e-5) and
            not fp64['covers_2048'], 'FP64 replay scope changed')
    for case in fp64['cases']:
        require(sha(ROOT/case['sample_file']) == case['sample_sha256'], 'FP64 sample evidence changed')
    component_report = dict(schema='synapse-lie.q2-hc-bk256-component.v1',
        plan_sha256=sha(plan_path), host=host_binding, arms=components,
        selected_key=selected, sibling_saved_tensors_exact=40, sibling_full_replay_exact=22,
        fp64_recovery_report=str(fp64_path.relative_to(ROOT)), fp64_recovery_sha256=sha(fp64_path),
        strict_rejections_retained=True, numeric_thresholds_changed=False,
        controls_rerun=False, model_inference=False, numerical_acceptance=False, goal_met=False)
    path = ROOT/'evidence'/arm['label']
    root, model = shared.arm(path, arm['variant'])
    receipt = curve.artifacts(path)
    require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4 and
            all(c['exit_code'] == 0 for c in receipt['commands']) and receipt['model_access'] and
            '-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
            '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
            receipt['commands'][-1]['argv'][-1] == 'bench2k' and
            not receipt.get('mmq_reuse') and not receipt.get('qualified_binary_replay'),
            'Changed model build or timer scope')
    require(sha(root/'pp2048-input.i32') == plan['input_sha256'] and
            (root/'pp2048-input.i32').stat().st_size == 8192, 'Original physical input changed')
    harness = read(ROOT/'config/q2-counting-harness.json')
    require(sha(ROOT/harness['origin']) == harness['origin_sha256'], 'Original tester archive changed')
    with tarfile.open(ROOT/harness['origin']) as archive:
        require(archive.extractfile(harness['origin_member']).read() ==
                (ROOT/harness['source']).read_bytes(), 'Original tester changed')
    model.update(capsule(path, plan['fixtures'], sources['variants'][arm['variant']]['files']))
    model.update(command_exits=[c['exit_code'] for c in receipt['commands']],
        command_wall_seconds=[(datetime.datetime.fromisoformat(c['finished_at'])-
                               datetime.datetime.fromisoformat(c['started_at'])).total_seconds()
                              for c in receipt['commands']], compilation_excluded_from_pp_tg=True,
        artifact_count=len(receipt['artifacts']), input_sha256=plan['input_sha256'])
    references, replay = {}, {}
    for key, label, variant in [
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('parent_q8_row', 'q2-reaudit-exact-model-r1', 'reaudit-q8-row'),
        ('retained_q8_row_norm', 'q2-reaudit-norm-model-r1', 'reaudit-q8-row-norm')]:
        ref_path = ROOT/'evidence'/label
        ref_root, references[key] = shared.arm(ref_path, variant)
        curve.artifacts(ref_path)
        replay[key] = prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical model input differs')
    fixed = read(ROOT/plan['fixed_reference'])
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'],
                'Fixed reference measurements changed')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {m:100*(model['measurements'][m]['median']/ref['measurements'][m]['median']-1)
                     for m in metrics} for key, ref in references.items()}
    matched = [f for f in replay['fixed_q2']['frontiers'] if f['matched_history']]
    release_path = ROOT/'config/q2-hc-bk256-run-window-release.json'
    release = read(release_path)
    require(release['state'] == 'Q2_HC_BK256_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'], 'Window not released')
    report = dict(schema='synapse-lie.q2-hc-bk256-fixed-model.v1',
        plan_sha256=sha(plan_path), model=model, references=references, replay=replay,
        candidate_median_change_percent=changes,
        within_arm_exact=model['within_arm_replay'] == dict(checks=9, exact=9),
        output_tokens_exact_to_fixed_q2=replay['fixed_q2']['output_tokens_exact'],
        logits_exact_to_fixed_q2=not replay['fixed_q2']['changed'],
        max_matched_history_kl_to_fixed_q2=max(f['kl_p_to_candidate'] for f in matched),
        observed_pp_tg_point_parity=all(changes['fixed_ud'][m] >= 0 for m in metrics[:2]),
        component_report=str(outputs[0].relative_to(ROOT)),
        release_sha256=sha(release_path), release_at=release['at'],
        controls_rerun=False, contemporaneous_bookends=False, original_tester_unchanged=True,
        numerical_acceptance=False, independent_model_quality=False, promoted=False,
        goal_met=False, full_curve_admitted=False,
        limits='One new candidate, three measured sessions, unchanged exact2048 input and direct-executor timers. Historical references only. Same greedy tokens do not qualify task quality; changed logits and strict component failures are retained. No long-context, concurrency or serving claim.')
    write(outputs[0], component_report)
    write(outputs[1], report)
    print(json.dumps(dict(measurements=model['measurements'], changes=changes,
        changed_files=replay['fixed_q2']['changed'], tokens_exact=report['output_tokens_exact_to_fixed_q2'],
        max_matched_history_kl=report['max_matched_history_kl_to_fixed_q2'], goal_met=False)))


if __name__ == '__main__':
    main()
