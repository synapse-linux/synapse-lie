#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the released HC result, collected evidence and unchanged fixed target."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
    curve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(curve)
    result_path = ROOT / 'config/q2-hc-inject-reuse-component-results.json'
    result = load(result_path)
    plan_path = ROOT / 'config/q2-hc-inject-reuse-plan.json'
    release_path = ROOT / 'config/q2-hc-inject-reuse-window-release.json'
    plan, release = load(plan_path), load(release_path)
    assert sha(plan_path) == result['plan_sha256']
    assert sha(release_path) == result['release_sha256']
    assert plan['arms'] == [] and not release['gpu_reserved']
    assert not release['kfd'] and not release['owned_group_members']
    assert len(release['retired_identities']) == 1377 and len(release['retired_groups']) == 1102
    assert len(release['leases']) == 4 and all(r['unchanged_free_EX_NB'] for r in release['leases'])
    assert release['model_stats_unchanged'] and len(release['models']) == 7
    remote, transport = curve.artifact_integrity(ROOT / 'evidence' / result['label'])
    assert [c['exit_code'] for c in remote['commands']] == [0, 0, 1]
    assert remote['finished_at'] < release['at'] and not remote['model_access']
    assert sha(ROOT / 'evidence' / result['label'] / 'results.tar.gz') == result['archive_sha256']
    assert result['device_work_safe'] and len(result['output_records']) == 200
    assert sum(r['exact'] for r in result['output_records']) == 140
    assert result['invalid_HIP_samples'] == 42 and len(result['timings']) == 42
    assert not result['model_inference'] and not result['borrowed_executor_scratch_qualified']
    difference_path = ROOT / 'config/q2-hc-inject-reuse-difference-audit.json'
    difference = load(difference_path)
    assert difference['component_results_sha256'] == sha(result_path)
    assert len(difference['rows']) == 60 and not difference['full_model_harmlessness_proven']
    assert difference['maximum_abs'] == 4.76837158203125e-7
    csv_path = ROOT / 'docs/figures/q2-hc-inject-reuse.csv'
    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == 42 and sum(r['warmup'] == 'False' for r in rows) == 30
    assert all(r['hip_timer_valid'] == 'False' for r in rows)
    host_path = ROOT / 'config/q2-hc-inject-reuse-host-results.json'
    host = load(host_path)
    assert host['plan_sha256'] == sha(plan_path) and host['debug'] == host['asan_ubsan'] == 35
    assert host['regression_methods'] == 12
    references_path = ROOT / 'config/q2-fixed-prefill-reference.json'
    assert sha(references_path) == '7f58a7fa19b53338c96f575667f0d853b61d3e8f6af4864319a7a1445b2474d1'
    references = load(references_path)
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'
    parent = load(parent_path)['model']
    pp = parent['measurements']['prefill_tok_s']['median']
    tg = parent['measurements']['decode_steps_s']['median']
    ud = references['arms']['ud']['measurements']['prefill_tok_s']['median']
    assert (pp, tg, ud) == (1585.308983, 25.16079073, 1685.777092)
    assert parent['input_sha256'] == references['input']['sha256']
    commands = {}
    prep = ROOT / 'evidence/q2-hc-inject-reuse-component-preparation'
    for label, exit_code in (('component-analysis', 0), ('difference-audit', 0),
                             ('component-plot', 1), ('component-plot-r2', 0)):
        path = prep / (label + '-command.json')
        command = load(path)
        assert command['exit_code'] == exit_code
        commands[label] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path), exit_code=exit_code)
    files = [result_path, plan_path, release_path, difference_path, csv_path, host_path,
        references_path, parent_path, ROOT / 'config/q2-hc-inject-reuse-numerical-differences.json',
        ROOT / 'docs/figures/q2-hc-inject-reuse.svg', ROOT / 'docs/figures/q2-hc-inject-reuse.png',
        ROOT / 'docs/Q2-HC-INJECTION-REUSE-RESULTS.md']
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-final-audit.v1',
        files={str(p.relative_to(ROOT)): sha(p) for p in files}, commands=commands,
        component_exits=[0, 0, 1], component_artifacts=124, host_debug=35, host_asan_ubsan=35,
        retired_identities=1377, retired_groups=1102, original_leases_unchanged_free=4,
        release_at=release['at'], release_sha256=sha(release_path),
        retained_PP=pp, retained_TG=tg, fixed_UD_PP=ud,
        required_PP_increase_percent=100 * (ud / pp - 1),
        required_prefill_saving_ms=1000 * (parent['measurements']['prefill_s']['median'] -
            references['arms']['ud']['measurements']['prefill_s']['median']),
        numerical_acceptance=False, independent_quality=False, controls_rerun=False,
        borrowed_executor_scratch_qualified=False, new_model_rate=None,
        public_C17_contracts_changed=False, source_provider_changed=False,
        Q4_run=False, full_curve_run=False, goal_met=False, GPU_reserved=False,
        current_job=False, waiter=False, restart_scheduled=False, remote_cleanup=False)
    with (ROOT / 'config/q2-hc-inject-reuse-final-audit.json').open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(artifacts=124, outputs=200, timings=42, release=release['at'],
                         retained_PP=pp, fixed_UD_PP=ud, goal_met=False)))


if __name__ == '__main__':
    main()
