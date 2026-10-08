#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit local-only runtime preparation without admitting or launching GPU work."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-ssm-followup-runtime-preparation'
LOGS = ROOT / 'evidence/q2-ssm-row-group-compose-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    spec = importlib.util.spec_from_file_location('prepare_ssm_followup', ROOT / 'tools/prepare-q2-ssm-followup-runtime.py')
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    prepare.frozen()
    receipt = read(PREP / 'preparation.json')
    assert sha(ROOT / receipt['patch']) == receipt['patch_sha256']
    assert sha(ROOT / receipt['registry']) == receipt['registry_sha256']
    for name, text in prepare.patched_files().items():
        assert sha(ROOT / name) == receipt['original_files'][name], name
        copy = PREP / 'overlay' / name
        assert copy.read_text() == text and sha(copy) == receipt['prepared_files'][name], name
        if name.endswith('.py'):
            ast.parse(text)
    commands = {}
    for label in ('followup-runtime-preparation-r1', 'followup-guards-r1',
                  'followup-existing-guards-r1', 'followup-patch-check-r1', 'followup-staging-r1'):
        path = LOGS / (label + '-command.json')
        command = read(path)
        assert command['exit_code'] == 0, label
        commands[str(path.relative_to(ROOT))] = sha(path)
    assert 'Ran 7 tests' in (LOGS / 'followup-guards-r1-stderr.txt').read_text()
    assert 'Ran 142 tests' in (LOGS / 'followup-existing-guards-r1-stderr.txt').read_text()
    stage = read(ROOT / 'config/q2-ssm-followup-runtime-staging.json')
    expected = {(v, kind) for v in prepare.VARIANTS for kind in ('component', 'model')}
    assert len(stage['arms']) == 8
    assert {(a['variant'], a['kind']) for a in stage['arms']} == expected
    for arm in stage['arms']:
        assert arm['provider_files'] == 1027 and arm['verified_files'] == 1035
        assert arm['ssh_executed'] is False
        assert sha(ROOT / arm['capsule']) == arm['capsule_sha256']
    names = [
        'tools/prepare-q2-ssm-followup-runtime.py', 'tools/stage-q2-ssm-followup-local.py',
        'tools/verify-q2-ssm-followup-runtime.py', 'tests/q2_ssm_followup_runtime_test.py',
        receipt['patch'], receipt['registry'], 'config/q2-ssm-followup-runtime-staging.json',
        'docs/Q2-SSM-FOLLOWUP-RUNTIME.md',
    ]
    report = dict(schema='synapse-lie.q2-ssm-followup-runtime-audit.v1',
                  files={name: sha(ROOT / name) for name in names}, commands=commands,
                  frozen_fixtures=88, frozen_manifests=5, frozen_window_helper_unchanged=True,
                  provider_files_per_arm=1027, verified_capsules=8,
                  focused_test_methods=7, existing_launcher_tests=142,
                  matched_modes=8, source_and_fixture_corruption_rejected=True,
                  syntax_pass=True, patch_applicability_pass=True,
                  original_leases_preserved=True, patch_applied=False,
                  candidate_result_analysis_pending=True, new_campaign_freeze_pending=True,
                  remote_run=False, gpu_run=False, parent_recompiled=False,
                  retained_prefill_tok_s=1580.226725, fixed_ud_prefill_tok_s=1685.777092,
                  remaining_relative_prefill_gain_percent=(1685.777092 / 1580.226725 - 1) * 100,
                  performance_gain=False, numerical_acceptance=False, goal_met=False)
    with (ROOT / 'config/q2-ssm-followup-runtime-preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
