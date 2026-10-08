#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a candidate-only fixed Q8 model run against preserved Q2/UD results."""
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
    output = ROOT/'config/q2-shared-q8-fixed-model-results.json'
    require(not output.exists(), 'Refusing to overwrite results')
    plan_path = ROOT/'config/q2-shared-q8-fixed-model-plan.json'
    plan = read(plan_path)
    require(len(plan['arms']) == 1 and plan['run_controls'] is False,
            'Candidate-only scope changed')
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT/name) == expected, 'Frozen identity changed: '+name)
    require(sha(ROOT/'tools/q2-shared-q8-fixed-model-window.py') == plan['window_helper_sha256'],
            'Window helper changed')
    host_path = ROOT/'evidence'/plan['host']
    host = curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands']) == 6, 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 23' in (host_path/'results'/name).read_text(),
                'Missing Debug/ASan gate')
    require(sha(ROOT/plan['host_receipt']) == plan['host_receipt_sha256'], 'Host receipt changed')
    arm = plan['arms'][0]
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
    require(source == read(ROOT/'config/q2-shared-q8-producer-source.json')['files'],
            'Q8 candidate provider changed')
    model['command_exits'] = [c['exit_code'] for c in receipt['commands']]
    model['command_wall_seconds'] = [
        (datetime.datetime.fromisoformat(c['finished_at']) -
         datetime.datetime.fromisoformat(c['started_at'])).total_seconds()
        for c in receipt['commands']]
    model['source_files_verified'] = len(source)
    model['compilation_excluded_from_pp_tg'] = True
    model['input_sha256'] = plan['input_sha256']
    references, replay = {}, {}
    for key, label, variant in [
        ('fixed_q2', 'q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2'),
        ('fixed_ud', 'q2-counting-regression-ud-r1', 'qualified'),
        ('latest_q2_before', 'q2-norm-fixed-model-before-r1', 'curve-iq2-mixed-q2'),
        ('latest_q2_after', 'q2-norm-fixed-model-after-r1', 'curve-iq2-mixed-q2'),
        ('latest_ud', 'q2-norm-fixed-model-ud-r1', 'qualified')]:
        ref_root, references[key] = shared.arm(ROOT/'evidence'/label, variant)
        curve.artifacts(ROOT/'evidence'/label)
        replay[key] = prior.comparison(ref_root, root)
        require(replay[key]['input_exact'], 'Historical comparison input differs')
    fixed = read(ROOT/'config/q2-fixed-prefill-reference.json')
    for key, frozen_key in [('fixed_q2', 'mixed'), ('fixed_ud', 'ud')]:
        require(references[key]['measurements'] == fixed['arms'][frozen_key]['measurements'],
                'Frozen reference changed')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    changes = {key: {m: 100*(model['measurements'][m]['median']/
                           reference['measurements'][m]['median']-1) for m in metrics}
               for key, reference in references.items()}
    q2_replay = replay['fixed_q2']
    matched = [f for f in q2_replay['frontiers'] if f['matched_history']]
    report = dict(schema='synapse-lie.q2-shared-q8-fixed-model.v1',
        plan_sha256=sha(plan_path), scope=plan['protocol'], model=model,
        references=references, candidate_median_change_percent=changes, replay=replay,
        controls_rerun=False, contemporaneous_bookends=False,
        candidate_within_arm_exact=model['within_arm_replay'] == dict(checks=9, exact=9),
        candidate_logits_exact_to_fixed_q2=not q2_replay['changed'],
        candidate_tokens_exact_to_fixed_q2=q2_replay['output_tokens_exact'],
        candidate_max_matched_history_kl_to_fixed_q2=max(
            (f['kl_p_to_candidate'] for f in matched), default=None),
        observed_pp_tg_point_parity=all(changes['fixed_ud'][m] >= 0
                                      for m in ('prefill_tok_s', 'decode_steps_s')),
        component_oracle_rejection_retained=True, independent_model_quality=False,
        numerical_acceptance=False, norm_composed=False, promoted=False, goal_met=False,
        full_curve_admitted=False,
        limits='Owner-requested exploratory candidate-only model measurement. Three measured sessions and historical controls do not establish contemporaneous repeatability or independent task quality. Original numerical failures retained; no context curve, concurrency or server qualification.')
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(measurements=model['measurements'], changes=changes,
        changed_files=q2_replay['changed'], output_tokens_exact=q2_replay['output_tokens_exact'],
        point_parity=report['observed_pp_tg_point_parity'], goal_met=False)))


if __name__ == '__main__':
    main()
