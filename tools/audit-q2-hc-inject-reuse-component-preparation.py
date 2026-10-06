#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind current HC fixture compilation and preserve the failed remote check."""
import ast
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-hc-inject-reuse-component-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path):
    spec = importlib.util.spec_from_file_location('hc_static', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    source_path = ROOT / 'config/q2-hc-inject-reuse-component-source.json'
    source = json.loads(source_path.read_text())['variants']['hc-inject-reuse-draft']
    for key in ('parent_manifest', 'measured_parent', 'draft_manifest', 'draft_static',
                'numerical_include', 'fixture', 'generator'):
        assert sha(ROOT / source[key]) == source[key + '_sha256'], key
    base = ROOT / source['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == source['files']
    assert len(source['files']) == 1027
    static = load_module(ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    saved = json.loads((ROOT / source['draft_static']).read_text())
    draft_isa = ROOT / saved['candidate_assembly']
    assert sha(draft_isa) == saved['candidate_assembly_sha256']
    fixture_isa = PREP / 'fixture.s'
    a, b = static.old.isa.parse(draft_isa), static.old.isa.parse(fixture_isa)
    assert len(a) == len(b) == 165 and set(a) == set(b)
    a_text, b_text = draft_isa.read_text(), fixture_isa.read_text()
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert static.old.instructions(a_text, name) == static.old.instructions(b_text, name), name
    commands = {}
    for label in ('fixture-host', 'fixture-device', 'fixture-host-v2',
                  'fixture-device-v2', 'source-manifest', 'core-handover'):
        path = PREP / (label + '-command.json')
        command = json.loads(path.read_text())
        assert command['exit_code'] == (255 if label == 'core-handover' else 0)
        commands[label] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
            actual_exit=command['exit_code'], started_at=command['started_at'],
            finished_at=command['finished_at'],
            stdout_sha256=sha(PREP / (label + '-stdout.txt')),
            stderr_sha256=sha(PREP / (label + '-stderr.txt')))
    assert 'No route to host' in (PREP / 'core-handover-stderr.txt').read_text()
    fixtures = ('tests/q2_hc_inject_reuse.hip',
        'experiments/q2-hc-inject-reuse-draft-v3.inc', 'tests/q2_remote_test.py',
        'tools/q2-remote.py', 'tools/q2-runner.py',
        'tools/prepare-q2-hc-inject-reuse-component.py',
        'tools/audit-q2-hc-inject-reuse-component-preparation.py',
        'cmake/hip/CMakeLists.txt', 'CMakeLists.txt')
    for name in fixtures:
        if name.endswith('.py'):
            ast.parse((ROOT / name).read_text(), filename=name)
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-component-preparation.v1',
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_manifest_sha256=sha(source_path), parent_files_exact=1027,
        fixtures={name: sha(ROOT / name) for name in fixtures},
        fixture_assembly=str(fixture_isa.relative_to(ROOT)),
        fixture_assembly_sha256=sha(fixture_isa),
        draft_assembly_sha256=sha(draft_isa),
        all_165_fixture_kernel_bodies_operands_resources_exact_to_draft=True,
        original_production_bodies_exact_to_saved_parent=162,
        current_fixture_commands=['fixture-host-v2', 'fixture-device-v2'],
        superseded_compile_scope='First host/device compiles precede final post-timing output and Q8-arm checks; retained as preparation evidence only',
        compiler_warnings='Two inherited switch warnings and ignored hipFree destructor result; compilation exits remain zero',
        commands=commands, cases=42, replay_sets=57, output_records=200,
        scratch_replay_records=57, timings=42, measured_timings=30,
        rotating_up_weight_bytes=39321600,
        timing_scope='Monotonic full mix/injection cycles including event submission and terminal synchronization; uploads, allocation, hashes and replay comparisons excluded',
        HIP_zero_values_policy='Retain raw elapsed values, reject nonpositive/nonfinite event durations; wall time is labeled complete-cycle wall time, not pure GPU elapsed',
        remote_state='CORE_HANDOVER_CHECK_FAILED_BEFORE_REMOTE_CONNECTION',
        host_checks_run=False, GPU_run=False, GPU_reserved=False,
        model_inference=False, production_provider=False,
        borrowed_executor_scratch_qualified=False, independent_quality=False,
        numerical_acceptance=False, performance_increment_found=False,
        retained_PP=1585.308983, retained_TG=25.16079073,
        fixed_UD_PP=1685.777092, full_curve=False, Q4=False,
        last_verified_release_sha256='e64145d666ce7ebcd470a7587a54979d6b11c8c909b073cc639c3d8071a652db',
        retry_or_waiter_scheduled=False, remote_cleanup=False, goal_met=False)
    with (ROOT / 'config/q2-hc-inject-reuse-component-preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(kernel_bodies_exact=165, parent_files_exact=1027,
        remote_check_exit=255, host_checks_run=False, GPU_run=False, goal_met=False)))


if __name__ == '__main__':
    main()
