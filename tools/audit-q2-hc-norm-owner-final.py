#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind released RMS component and private ordinary-only source to fixed target."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    spec = importlib.util.spec_from_file_location('curve', ROOT / 'tools/analyze-q2-curve.py')
    curve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(curve)
    result_path = ROOT / 'config/q2-hc-norm-owner-component-results.json'
    plan_path = ROOT / 'config/q2-hc-norm-owner-plan.json'
    release_path = ROOT / 'config/q2-hc-norm-owner-window-release.json'
    result, plan, release = read(result_path), read(plan_path), read(release_path)
    assert result['plan_sha256'] == sha(plan_path) and result['release_sha256'] == sha(release_path)
    assert plan['arms'] == [] and len(plan['fixtures']) == 140 and len(plan['manifests']) == 8
    assert result['numerical_exact'] and result['device_work_safe']
    assert len(result['output_records']) == 120 and all(r['exact'] for r in result['output_records'])
    assert len(result['timings']) == result['invalid_HIP_samples'] == 28
    assert all(r['hip_ms_raw_bits'] == 0 for r in result['timings'])
    assert len(result['inputs']) == 38
    assert not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members']
    assert len(release['retired_identities']) == 1388 and len(release['retired_groups']) == 1111
    assert len(release['leases']) == 4 and all(r['unchanged_free_EX_NB'] for r in release['leases'])
    assert release['model_stats_unchanged'] and len(release['models']) == 7
    commands, artifact_count = [], 0
    for label in (plan['host'], result['label']):
        directory = ROOT / 'evidence' / label
        actual, _ = curve.artifact_integrity(directory)
        assert actual['finished_at'] < release['at'] and not actual['model_access']
        commands.extend(c['exit_code'] for c in actual['commands'])
        artifact_count += len(actual['artifacts'])
    assert commands == [0] * 9 and artifact_count == 11
    csv_path = ROOT / 'docs/figures/q2-hc-norm-owner.csv'
    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == 28 and sum(r['warmup'] == 'False' for r in rows) == 20
    assert all(r['hip_timer_valid'] == 'False' for r in rows)
    source_path = ROOT / 'config/q2-hc-rms-owner-ordinary-source.json'
    source = read(source_path)['variants']['hc-rms-owner-ordinary']
    provider = ROOT / source['source']
    assert {str(p.relative_to(provider)): sha(p) for p in provider.rglob('*')
            if p.is_file()} == source['files'] and len(source['files']) == 1028
    static_path = ROOT / 'config/q2-hc-rms-owner-ordinary-static.json'
    static = read(static_path)
    assert static['source_manifest_sha256'] == sha(source_path)
    assert static['original_production_bodies_exact'] == 162 and static['qualified_ordinary_body_exact']
    assert not static['original_model_run'] and not static['remote_model_variant_registered']
    references_path = ROOT / 'config/q2-fixed-prefill-reference.json'
    assert sha(references_path) == '7f58a7fa19b53338c96f575667f0d853b61d3e8f6af4864319a7a1445b2474d1'
    reference = read(references_path)
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'
    parent = read(parent_path)['model']
    pp = parent['measurements']['prefill_tok_s']['median']
    tg = parent['measurements']['decode_steps_s']['median']
    ud = reference['arms']['ud']['measurements']['prefill_tok_s']['median']
    assert (pp, tg, ud) == (1585.308983, 25.16079073, 1685.777092)
    assert parent['input_sha256'] == reference['input']['sha256']
    paths = [result_path, plan_path, release_path, source_path, static_path,
        parent_path, references_path, csv_path,
        ROOT / 'docs/Q2-HC-RMS-OWNER-RESULTS.md',
        ROOT / 'docs/figures/q2-hc-norm-owner.svg',
        ROOT / 'docs/figures/q2-hc-norm-owner.png']
    prep = ROOT / 'evidence/q2-hc-norm-owner-runtime-preparation'
    receipts = {}
    for label, code in [('core-handover', 255), ('core-handover-r2', 0),
        ('source-generation', 0), ('host-tests-r1', 0), ('host-collection-r1', 0),
        ('freeze-plan', 0), ('helper-transfer', 0), ('admission', 0), ('admission-publish', 0),
        ('gpu-component', 0), ('component-collection', 0), ('release', 0),
        ('release-publish', 0), ('component-analysis', 0), ('component-plot', 0),
        ('ordinary-provider-generation', 0), ('ordinary-provider-assembly', 0),
        ('ordinary-provider-static', 0)]:
        path = prep / (label + '-command.json')
        receipt = read(path)
        assert receipt['exit_code'] == code
        receipts[label] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path), exit_code=code)
    report = dict(schema='synapse-lie.q2-hc-norm-owner-final-audit.v1',
        files={str(p.relative_to(ROOT)): sha(p) for p in paths}, receipts=receipts,
        host_debug=36, host_asan_ubsan=36, primary_command_exits=commands,
        artifacts_verified=11, whole_output_records_exact=120,
        original_source_inventory_exact=1027, candidate_source_inventory_exact=1028,
        original_numerical_bodies_exact=162, qualified_ordinary_body_exact=True,
        release_at=release['at'], release_sha256=sha(release_path),
        retired_identities=1388, retired_groups=1111, original_leases_unchanged_free=4,
        retained_PP=pp, retained_TG=tg, fixed_UD_PP=ud,
        required_PP_increase_percent=100 * (ud / pp - 1),
        required_prefill_saving_ms=1000 * (parent['measurements']['prefill_s']['median'] -
            reference['arms']['ud']['measurements']['prefill_s']['median']),
        model_inference=False, new_model_rate=None, independent_quality=False,
        controls_rerun=False, component_rerun=False, original_model_plan_frozen=False,
        public_C17_ABI_state_metrics_changed=False, new_persistent_bytes=0,
        GPU_reserved=False, current_job=False, waiter=False, restart_scheduled=False,
        remote_cleanup=False, full_curve_run=False, Q4_run=False, goal_met=False)
    with (ROOT / 'config/q2-hc-norm-owner-final-audit.json').open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(artifacts=11, outputs_exact=120, original_bodies_exact=162,
        qualified_ordinary_body_exact=True, retained_PP=pp, fixed_UD_PP=ud, goal_met=False)))


if __name__ == '__main__':
    main()
