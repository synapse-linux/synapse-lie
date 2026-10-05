#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify local SSM composition preparation without claiming GPU evidence."""
import ast
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-ssm-row-group-compose-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    plan_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    plan = read(plan_path)
    bindings = {**plan['fixtures'], **plan['manifests']}
    assert len(plan['fixtures']) == 88 and len(plan['manifests']) == 5
    for rel, digest in bindings.items():
        assert sha(ROOT / rel) == digest, rel
    assert sha(ROOT / plan['window_helper']) == plan['window_helper_sha256']
    assert sha(ROOT / plan['previous_release']) == plan['previous_release_sha256']
    helper = (ROOT / plan['window_helper']).read_text()
    assert "state='Q2_SSM_ROW_GROUP_WINDOW_ADMITTED'" in helper
    assert "else 'Q2_SSM_ROW_GROUP_WINDOW_RELEASED'" in helper
    assert 'Q2_DOWN_REGISTER_SCATTER_WINDOW' not in helper
    assert 'q2-ssm-row-group-host-r1/tools' in helper
    assert not plan['run_controls'] and not plan['full_curve']
    assert plan['model_performance_test_despite_numeric_or_timing_rejection']
    selected_path = ROOT / plan['source_variant_manifest']
    selected = read(selected_path)['variants']['ssm-row-group']
    assert len(selected['files']) == plan['provider_file_count'] == 1027
    for rel, digest in selected['files'].items():
        assert sha(ROOT / selected['source'] / rel) == digest, rel
    for key in ('parent_manifest', 'measured_parent', 'parent_disposition',
                'standalone_manifest', 'control_include', 'patch', 'fixture',
                'oracle', 'fixture_contract'):
        assert sha(ROOT / selected[key]) == selected[key + '_sha256'], key
    assert selected['parent_prefill_tok_s'] == plan['parent_measured_prefill'] == 1580.226725
    parent = read(ROOT / selected['parent_manifest'])['variants']['down-register-scatter']
    changed = [p for p, digest in selected['files'].items() if digest != parent['files'][p]]
    assert changed == selected['changed_files'] == [
        'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp']
    static_path = ROOT / 'config/q2-ssm-row-group-compose-static.json'
    static = read(static_path)
    assert static['source_manifest_sha256'] == sha(selected_path)
    assert static['other_kernels_instruction_operand_resource_exact'] == 161
    assert static['inherited_down_register_scatter_bodies_exact']
    assert static['literal_control_current_parent_exact']
    for arm in ('parent', 'candidate'):
        assert sha(ROOT / static[arm + '_assembly_path']) == static[arm + '_assembly_sha256']
    commands = {p.name.removesuffix('-command.json'): read(p)
                for p in sorted(OUT.glob('*-command.json'))}
    expected_failures = {'analysis-guards': 1}
    for name, command in commands.items():
        assert command['exit_code'] == expected_failures.get(name, 0), name
    for name in ('generation', 'assembly', 'fixture-host', 'fixture-device',
                 'static', 'launcher-guards', 'analysis-guards-corrected',
                 'freeze-plan', 'staging'):
        assert name in commands and commands[name]['exit_code'] == 0, name
    for name, count in (('launcher-guards', 142), ('analysis-guards-corrected', 8)):
        log = (OUT / (name + '-stderr.txt')).read_text()
        assert 'Ran ' + str(count) + ' tests' in log and '\nOK\n' in log
    assert 'FAILED (errors=5)' in (OUT / 'analysis-guards-stderr.txt').read_text()
    initial_test = (OUT / 'analysis-test-initial.py').read_text()
    current_test = (ROOT / 'tests/q2_ssm_row_group_analysis_test.py').read_text()
    assert initial_test.count('self.assertRaises(RuntimeError)') == 5
    assert initial_test.replace('self.assertRaises(RuntimeError)',
                                'self.assertRaises(ValueError)') == current_test
    staging_path = ROOT / 'config/q2-ssm-row-group-staging.json'
    staging = read(staging_path)
    assert len(staging['arms']) == 2
    assert {r['mode'] for r in staging['arms']} == {
        'ssm-row-group-check', 'q2-counting-ssm-row-group'}
    for row in staging['arms']:
        assert row['provider_files'] == 1027 and row['fixture_files'] == 88
        assert row['ssh_executed'] is False
        archive = ROOT / row['capsule_path']
        assert sha(archive) == row['capsule_sha256']
        with tarfile.open(archive) as capsule:
            for rel, digest in bindings.items():
                assert hashlib.sha256(capsule.extractfile(rel).read()).hexdigest() == digest, rel
            for rel, digest in selected['files'].items():
                assert hashlib.sha256(capsule.extractfile('source/' + rel).read()).hexdigest() == digest, rel
    helpers = ['tools/q2-remote.py', 'tools/q2-runner.py', plan['window_helper'],
               'tools/freeze-q2-ssm-row-group-plan.py',
               'tools/prepare-q2-ssm-row-group-compose.py',
               'tools/analyze-q2-ssm-row-group-compose-static.py',
               'tools/analyze-q2-ssm-row-group-component.py',
               'tools/analyze-q2-ssm-row-group-model.py',
               'tools/verify-q2-ssm-row-group-compose-preparation.py',
               'tests/q2_ssm_row_group_analysis_test.py']
    for rel in helpers:
        ast.parse((ROOT / rel).read_text(), filename=rel)
    report = dict(schema='synapse-lie.q2-ssm-row-group-preparation.v1',
                  plan_sha256=sha(plan_path), selected_source_sha256=sha(selected_path),
                  static_sha256=sha(static_path), staging_sha256=sha(staging_path),
                  fixtures_verified=88, manifests_verified=5, provider_files_verified=1027,
                  launcher_guards=142, analysis_guards=8,
                  helper_files={p: sha(ROOT / p) for p in helpers}, local_commands=commands,
                  preserved_failure='Initial parser negative tests expected RuntimeError; '
                  'existing shared require raises ValueError. Correct only those five '
                  'test expectations; all source and actual failures retained.',
                  historical_verifier_restored=True,
                  initial_preparation_report_sha256=sha(ROOT / 'config/q2-ssm-row-group-compose-preparation-initial.json'),
                  remote_host_checks_pending=True, core_handover_required=True,
                  gpu_admission_pending=True, gpu_run=False, model_inference=False,
                  numerical_acceptance=False, goal_met=False)
    with (ROOT / 'config/q2-ssm-row-group-compose-preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(fixtures=88, manifests=5, provider_files=1027,
                          launcher_guards=142, analysis_guards=8,
                          local_commands=len(commands), gpu_run=False)))


if __name__ == '__main__':
    main()
