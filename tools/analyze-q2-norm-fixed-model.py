#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the owner-requested exact2048 full-model experiment without promotion."""
import hashlib
import json
import datetime
from pathlib import Path
import tarfile

from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = spec_from_file_location(name, ROOT/'tools'/name)
    value = module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
audit = module('analyze-q2-combined.py')
curve = module('analyze-q2-curve.py')
require = shared.require
sha = audit.digest


def read(path):
    return json.loads(path.read_text())


def comparison(a, b):
    row = shared.compare(a, b)
    row['input_exact'] = not any(n.endswith('.i32') for n in row['changed'])
    row['output_tokens_exact'] = not any(n.endswith('.u32') for n in row['changed'])
    for frontier in row['frontiers']:
        name = frontier['name']
        prefix, kind = name.rsplit('-', 1)
        stem = prefix.rsplit('-', 1)[0]
        same_input = (a/(stem+'-input.i32')).read_bytes() == (b/(stem+'-input.i32')).read_bytes()
        same_history = same_input and (kind == 'prefill.f32' or
            (a/(prefix+'-output.u32')).read_bytes()[:-4] ==
            (b/(prefix+'-output.u32')).read_bytes()[:-4])
        frontier['matched_history'] = same_history
        if not same_history:
            frontier.pop('kl_p_to_candidate', None)
    return row


def main():
    output = ROOT/'config/q2-norm-fixed-model-results.json'
    require(not output.exists(), 'Refusing to overwrite results')
    plan_path = ROOT/'config/q2-norm-fixed-model-plan.json'
    plan = read(plan_path)
    for name, expected in {**plan['manifests'], **plan['fixture_identities']}.items():
        require(sha(ROOT/name) == expected, 'Frozen identity changed: '+name)
    require(sha(ROOT/'tools/q2-norm-fixed-model-window.py') == plan['window_helper_sha256'],
            'Window helper changed')
    host_path = ROOT/'evidence'/plan['host']
    host = curve.artifacts(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            not host['model_access'] and len(host['commands']) == 6, 'Host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 22' in (host_path/'results'/name).read_text(),
                'Missing complete Debug/ASan gate')
    host_receipt = read(ROOT/plan['host_receipt'])
    require(sha(ROOT/plan['host_receipt']) == plan['host_result_sha256'] and
            sha(host_path/'source.tar.gz') == host_receipt['capsule_sha256'], 'Host identity changed')
    with tarfile.open(host_path/'source.tar.gz') as archive:
        for name, expected in host_receipt['fixtures'].items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected,
                    'Host-qualified fixture differs: '+name)
    harness = read(ROOT/'config/q2-counting-harness.json')
    require(sha(ROOT/harness['origin']) == harness['origin_sha256'], 'Historical archive changed')
    with tarfile.open(ROOT/harness['origin']) as archive:
        require(archive.extractfile(harness['origin_member']).read() ==
                (ROOT/harness['source']).read_bytes(), 'Historical tester differs')

    parent = read(ROOT/'config/q2-iq2-mixed-model-source.json')
    candidate = read(ROOT/'config/q2-norm-fixed-shape-source.json')
    old_plan = read(ROOT/'config/q2-counting-regression-plan.json')
    models, roots = {}, {}
    for arm in plan['arms']:
        key = arm['key']
        path = ROOT/'evidence'/arm['label']
        root, model = shared.arm(path, arm['variant'])
        receipt = curve.artifacts(path)
        require(receipt['mode'] == arm['mode'] and len(receipt['commands']) == 4 and
                receipt['model_access'], 'Changed model command scope')
        require('-DQ2_COUNTING_BASELINE=ON' in receipt['commands'][0]['argv'] and
                '-DQ2_CURVE_SERVER=ON' not in receipt['commands'][0]['argv'] and
                receipt['commands'][-1]['argv'][-1] == 'bench2k' and
                not receipt.get('mmq_reuse'), 'Frozen counting scope or MMQ rebuild changed')
        require(sha(root/'pp2048-input.i32') == plan['input_sha256'] and
                (root/'pp2048-input.i32').stat().st_size == 2048*4,
                'Fixed physical input changed')
        model['validation'] = audit.audit_capsule(path, list(plan['fixture_identities']))
        expected = (candidate['files'] if key == 'candidate' else
                    old_plan['historical_ud_provider_files'] if key == 'ud' else parent['files'])
        with tarfile.open(path/'source.tar.gz') as archive:
            files = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                     for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(files == expected, 'Provider inventory differs: '+key)
        model['source_inventory_sha256'] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        model['command_exits'] = [c['exit_code'] for c in receipt['commands']]
        model['command_wall_seconds'] = [
            (datetime.datetime.fromisoformat(c['finished_at']) -
             datetime.datetime.fromisoformat(c['started_at'])).total_seconds()
            for c in receipt['commands']]
        model['compilation_excluded_from_pp_tg'] = True
        model['input_sha256'] = plan['input_sha256']
        models[key], roots[key] = model, root

    old_root, old_q2 = shared.arm(ROOT/'evidence/q2-counting-regression-mixed-r1', 'curve-iq2-mixed-q2')
    old_ud_root, old_ud = shared.arm(ROOT/'evidence/q2-counting-regression-ud-r1', 'qualified')
    replay = dict(before_vs_historical_q2=comparison(old_root, roots['before']),
                  repeated_q2=comparison(roots['before'], roots['after']),
                  candidate_vs_before=comparison(roots['before'], roots['candidate']),
                  candidate_vs_after=comparison(roots['after'], roots['candidate']),
                  fresh_ud_vs_historical=comparison(old_ud_root, roots['ud']),
                  candidate_vs_ud=comparison(roots['ud'], roots['candidate']))
    for key in ('before_vs_historical_q2', 'repeated_q2', 'fresh_ud_vs_historical'):
        require(not replay[key]['changed'], 'Unchanged control replay differs: '+key)
    require(all(r['input_exact'] for r in replay.values()), 'Comparison input differs')
    metrics = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
    references = {**{k:models[k] for k in ('before','after','ud')},
                  'fixed_q2':old_q2, 'fixed_ud':old_ud}
    changes = {ref:{m:100*(models['candidate']['measurements'][m]['median']/
                          model['measurements'][m]['median']-1) for m in metrics}
               for ref,model in references.items()}
    drift = {m:100*(models['after']['measurements'][m]['median']/
                   models['before']['measurements'][m]['median']-1) for m in metrics}
    fixed = read(ROOT/'config/q2-fixed-prefill-reference.json')
    for key, historic in (('mixed',old_q2),('ud',old_ud)):
        require(historic['measurements'] == fixed['arms'][key]['measurements'],
                'Frozen reference measurement changed')
    component = read(ROOT/'config/q2-norm-fixed-results.json')
    report = dict(schema='synapse-lie.q2-norm-fixed-model.v1',plan_sha256=sha(plan_path),
        scope='Unchanged exact2048 counting input and direct-executor tester, original Q2/UD weights on .157; one warmup/three identical-input measurements per sequential arm.',
        model=models,historical=dict(q2=old_q2,ud=old_ud),replay=replay,
        candidate_median_change_percent=changes,unchanged_q2_drift_percent=drift,
        candidate_within_arm_exact=models['candidate']['within_arm_replay'] == dict(checks=9,exact=9),
        candidate_logits_exact_to_control=not replay['candidate_vs_before']['changed'],
        candidate_max_matched_history_kl_to_control=max(
            f['kl_p_to_candidate'] for f in replay['candidate_vs_before']['frontiers']
            if f['matched_history']),
        observed_pp_tg_point_parity=all(changes[k][m]>=0 for k in ('ud','fixed_ud')
                                      for m in ('prefill_tok_s','decode_steps_s')),
        retained_component_disposition=component['disposition'],
        numerical_acceptance=False,independent_model_quality=False,promoted=False,goal_met=False,
        full_curve_admitted=False,
        limits='Exploratory model run explicitly requested after component rejection. Three measured sessions are descriptive, not statistical zero-margin acceptance. Byte/logit/greedy replay cannot waive independent numeric/task-quality gates. No context sweep, concurrency or server qualification.')
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(medians={k:{m:v['measurements'][m]['median'] for m in metrics}
                                  for k,v in models.items()},
        candidate_median_change_percent=changes,control_drift_percent=drift,
        changed_files={k:v['changed'] for k,v in replay.items()},
        point_parity=report['observed_pp_tg_point_parity'],goal_met=False)))


if __name__ == '__main__':
    main()
