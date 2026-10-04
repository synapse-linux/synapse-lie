#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two new retained compositions against immutable historical Q2/UD results."""
import datetime
import hashlib
import json
from pathlib import Path
import tarfile

from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = spec_from_file_location(name, ROOT/'tools'/name)
    value = module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prior = module('analyze-q2-norm-fixed-model.py')
shared, audit, curve = prior.shared, prior.audit, prior.curve
require, sha, read = prior.require, prior.sha, prior.read


def main():
    output = ROOT/'config/q2-reaudit-composition-results.json'
    require(not output.exists(), 'Refusing to overwrite results')
    plan_path = ROOT/'config/q2-reaudit-composition-plan.json'
    plan = read(plan_path)
    require(len(plan['arms']) == 2 and plan['run_controls'] is False,
            'Candidate-only scope changed')
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT/name) == expected, 'Frozen identity changed: '+name)
    require(sha(ROOT/'tools/q2-reaudit-composition-window.py') == plan['window_helper_sha256'],
            'Window helper changed')
    host_path = ROOT/'evidence'/plan['host']
    host = curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands']) == 6, 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 23' in (host_path/'results'/name).read_text(),
                'Missing Debug/ASan gate')
    require(sha(ROOT/plan['host_receipt']) == plan['host_receipt_sha256'], 'Host receipt changed')
    host_receipt = read(ROOT/plan['host_receipt'])
    require(sha(host_path/'source.tar.gz') == host_receipt['capsule_sha256'], 'Host capsule changed')
    with tarfile.open(host_path/'source.tar.gz') as archive:
        for name, expected in plan['fixtures'].items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected,
                    'Host-qualified fixture differs: '+name)
    harness = read(ROOT/'config/q2-counting-harness.json')
    require(sha(ROOT/harness['origin']) == harness['origin_sha256'], 'Original tester archive changed')
    with tarfile.open(ROOT/harness['origin']) as archive:
        require(archive.extractfile(harness['origin_member']).read() ==
                (ROOT/harness['source']).read_bytes(), 'Original tester differs')
    models, roots = {}, {}
    for arm in plan['arms']:
        path = ROOT/'evidence'/arm['label']
        root, model = shared.arm(path, arm['variant'])
        receipt = curve.artifacts(path)
        require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4 and
                receipt['model_access'], 'Changed model command scope')
        require('-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
                '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
                receipt['commands'][-1]['argv'][-1] == 'bench2k' and
                not receipt.get('mmq_reuse') and not receipt.get('qualified_binary_replay'),
                'Candidate build or frozen counting scope changed')
        require(sha(root/'pp2048-input.i32') == plan['input_sha256'] and
                (root/'pp2048-input.i32').stat().st_size == 2048*4, 'Fixed input changed')
        with tarfile.open(path/'source.tar.gz') as archive:
            for name, expected in plan['fixtures'].items():
                require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected,
                        'GPU capsule fixture changed: '+name)
            source = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                      for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(source == read(ROOT/'config/q2-reaudit-composition-source.json')['variants'][arm['variant']]['files'],
                'Composition candidate provider changed')
        model['command_exits'] = [c['exit_code'] for c in receipt['commands']]
        model['command_wall_seconds'] = [
            (datetime.datetime.fromisoformat(c['finished_at']) -
             datetime.datetime.fromisoformat(c['started_at'])).total_seconds()
            for c in receipt['commands']]
        model['source_files_verified'] = len(source)
        model['compilation_excluded_from_pp_tg'] = True
        model['input_sha256'] = plan['input_sha256']
        model['norm_composed'] = arm['key'] == 'norm'
        models[arm['key']], roots[arm['key']] = model, root
    references, replay = {}, {}
    model, root = models['exact'], roots['exact']
    for key, label, variant in [
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('latest_q2_before', 'q2-norm-fixed-model-before-r1', 'curve-iq2-mixed-q2'),
        ('latest_q2_after', 'q2-norm-fixed-model-after-r1', 'curve-iq2-mixed-q2'),
        ('latest_ud', 'q2-norm-fixed-model-ud-r1', 'qualified')]:
        ref_root, references[key] = shared.arm(ROOT/'evidence'/label, variant)
        curve.artifacts(ROOT/'evidence'/label)
        for candidate_key in models:
            replay.setdefault(candidate_key, {})[key] = prior.comparison(ref_root, roots[candidate_key])
            require(replay[candidate_key][key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT/'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'],
                'Frozen reference changed')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {candidate_key: {key: {m: 100*(candidate['measurements'][m]['median']/
                            reference['measurements'][m]['median']-1) for m in metrics}
                for key, reference in references.items()} for candidate_key, candidate in models.items()}
    composed_replay = prior.comparison(roots['exact'], roots['norm'])
    for key, label, variant in [
        ('q8', 'q2-shared-q8-fixed-model-candidate-r1', 'shared-q8-producer'),
        ('norm', 'q2-norm-fixed-model-candidate-r1', 'norm-fixed-shape')]:
        old_root, old_model = shared.arm(ROOT/'evidence'/label, variant)
        curve.artifacts(ROOT/'evidence'/label)
        references['retained_'+key] = old_model
        for candidate_key, candidate in models.items():
            replay[candidate_key]['retained_'+key] = prior.comparison(old_root, roots[candidate_key])
            changes[candidate_key]['retained_'+key] = {m:100*(candidate['measurements'][m]['median']/
                old_model['measurements'][m]['median']-1) for m in metrics}
    checks = {}
    for key, candidate in models.items():
        q2_replay = replay[key]['fixed_q2']
        matched = [f for f in q2_replay['frontiers'] if f['matched_history']]
        checks[key] = dict(within_arm_exact=candidate['within_arm_replay'] == dict(checks=9,exact=9),
            logits_exact_to_fixed_q2=not q2_replay['changed'],
            tokens_exact_to_fixed_q2=q2_replay['output_tokens_exact'],
            max_matched_history_kl_to_fixed_q2=max((f['kl_p_to_candidate'] for f in matched),default=None),
            observed_pp_tg_point_parity=all(changes[key]['fixed_ud'][m] >= 0
                                          for m in ('prefill_tok_s','decode_steps_s')))
    report = dict(schema='synapse-lie.q2-reaudit-composition.v1',
        plan_sha256=sha(plan_path),scope=plan['protocol'],model=models,references=references,
        candidate_median_change_percent=changes,replay=replay,checks=checks,
        norm_vs_exact_composition=composed_replay,
        norm_vs_exact_median_change_percent={m:100*(models['norm']['measurements'][m]['median']/
            models['exact']['measurements'][m]['median']-1) for m in metrics},
        controls_rerun=False,contemporaneous_bookends=False,
        retained_component_rejections=True,independent_model_quality=False,
        numerical_acceptance=False,promoted=False,goal_met=False,full_curve_admitted=False,
        limits='Owner-requested exploratory candidate-only compositions. Three measured sessions and historical controls do not establish contemporaneous repeatability or independent task quality. All original numerical failures retained; no context curve, concurrency or server qualification.')
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(measurements={k:v['measurements'] for k,v in models.items()},
        changes=changes,checks=checks,norm_vs_exact_median_change_percent=report['norm_vs_exact_median_change_percent'],
        goal_met=False)))


if __name__ == '__main__':
    main()
