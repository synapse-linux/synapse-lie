#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close local preparation without claiming remote or numerical qualification."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-down-register-scatter-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT/'config/q2-down-register-scatter-plan.json'
    plan = json.loads(plan_path.read_text())
    for group in ('fixtures', 'manifests'):
        for rel,digest in plan[group].items():
            assert sha(ROOT/rel) == digest, rel
    assert len(plan['fixtures']) == 85 and len(plan['manifests']) == 4
    assert sha(ROOT/plan['window_helper']) == plan['window_helper_sha256']
    helper = (ROOT/plan['window_helper']).read_text()
    assert "state='Q2_DOWN_REGISTER_SCATTER_WINDOW_ADMITTED'" in helper
    assert "else 'Q2_DOWN_REGISTER_SCATTER_WINDOW_RELEASED'" in helper
    assert 'Q2_PRODUCER_Q8_WINDOW' not in helper
    initial_plan = json.loads((ROOT/plan['supersedes_plan']).read_text())
    assert sha(ROOT/plan['supersedes_plan']) == plan['supersedes_plan_sha256']
    assert sha(OUT/'window-initial.py') == initial_plan['window_helper_sha256']
    assert initial_plan['fixtures'] == plan['fixtures'] and initial_plan['manifests'] == plan['manifests']
    assert sha(ROOT/plan['previous_release']) == plan['previous_release_sha256']
    commands = {p.name.removesuffix('-command.json'):json.loads(p.read_text())
                for p in sorted(OUT.glob('*-command.json'))}
    expected_failures = {'shared-format':1, 'changed-format':1, 'staging-final':2}
    for name,command in commands.items():
        assert command['exit_code'] == expected_failures.get(name,0), name
    for name in ('assembly-pair','fixture-host-final','fixture-device-final',
                 'launcher-guards-final','changed-format-corrected','static-analysis',
                 'freeze-plan-final','staging-corrected'):
        assert name in commands and commands[name]['exit_code'] == 0
    guards = (OUT/'launcher-guards-final-stderr.txt').read_text()
    assert 'Ran 140 tests' in guards and '\nOK\n' in guards
    formats = (OUT/'shared-format-stdout.txt').read_text()+(OUT/'shared-format-stderr.txt').read_text()
    findings = {}
    for path in re.findall(r'([^\n ]+):\d+:\d+: error:', formats):
        findings[path] = findings.get(path,0)+1
    selected_path = ROOT/plan['source_variant_manifest']
    selected = json.loads(selected_path.read_text())['variants']['down-register-scatter']
    parent = json.loads((ROOT/selected['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    assert len(findings) == 7 and sum(findings.values()) == 88
    for rel in findings:
        assert selected['files'][rel] == parent['files'][rel], rel
    staging_path = ROOT/'config/q2-down-register-scatter-staging.json'
    staging = json.loads(staging_path.read_text())
    assert len(staging['arms']) == 2
    for row in staging['arms']:
        assert row['provider_files'] == 1027 and row['fixture_files'] == 85
        assert row['ssh_executed'] is False
    source = (ROOT/'tests/q2_down_register_scatter.hip').read_text()
    assert 'return pass ? 0 : 1;' in source and '    return 2;' in source
    assert source.count('pass = Case("mixed-w48-e512"') == 1
    assert 'for (unsigned active' not in source
    for rel in ('tools/q2-remote.py','tools/q2-runner.py',plan['window_helper'],
                'tools/freeze-q2-down-register-scatter-plan.py',
                'tools/analyze-q2-down-register-scatter-static.py',
                'tools/prepare-q2-down-register-scatter.py',
                'tools/verify-q2-down-register-scatter-preparation.py'):
        ast.parse((ROOT/rel).read_text(), filename=rel)
    report = dict(schema='synapse-lie.q2-down-register-scatter-preparation.v1',
        plan_sha256=sha(plan_path), selected_source_sha256=sha(selected_path),
        static_sha256=sha(ROOT/'config/q2-down-register-scatter-static.json'),
        staging_sha256=sha(staging_path), fixtures_verified=85, manifests_verified=4,
        launcher_guards=140, final_fixture_sha256=sha(ROOT/'tests/q2_down_register_scatter.hip'),
        shared_format_unchanged_file_findings=findings,
        initial_changed_format_failure='Checker stripped only formatted output newline; texts already identical. Initial command/helper retained, corrected check exits0; no source change.',
        local_commands=commands, predecessor_release_sha256=plan['previous_release_sha256'],
        remote_host_checks_pending=True, root_cpu_window_requires_closure=True,
        gpu_admission_pending=True, gpu_run=False, model_inference=False,
        numerical_acceptance=False, goal_met=False)
    with (ROOT/'config/q2-down-register-scatter-preparation.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(fixtures=85,manifests=4,launcher_guards=140,
        local_commands=len(commands),preserved_failures=expected_failures,gpu_run=False)))


if __name__ == '__main__':
    main()
