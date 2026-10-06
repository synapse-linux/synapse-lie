#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record syntax/source identities only; never run tests or access a model."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-hc-inject-reuse-component-preparation'
CHECKPOINT = '349f6252cd34af62e3e101699d559319de480a70'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    previous_path = ROOT / 'config/q2-hc-inject-reuse-component-preparation-v2.json'
    previous = read(previous_path)
    # Preserve the old qualified scope rather than comparing its hashes to
    # today's intentionally changed launcher/CMake wiring.
    for name, digest in previous['fixtures'].items():
        raw = subprocess.check_output(['git', 'show', CHECKPOINT + ':' + name], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == digest, name
    files = ('CMakeLists.txt', 'tools/q2-remote.py',
        'tools/analyze-q2-hc-inject-reuse-component.py',
        'tools/freeze-q2-hc-inject-reuse-plan.py', 'tools/q2-hc-inject-reuse-window.py',
        'tools/q2-hc-inject-reuse-phase.py', 'tools/q2_window_registry.py',
        'tests/q2_hc_inject_reuse_analysis_test.py',
        'tools/audit-q2-hc-inject-reuse-runtime-preparation.py',
        'docs/Q2-HC-QUALIFICATION-PREPARATION.md')
    trees = {name: ast.parse((ROOT / name).read_text(), filename=name)
             for name in files if name.endswith('.py')}
    tests = trees['tests/q2_hc_inject_reuse_analysis_test.py']
    methods = {node.name: [method.name for method in node.body
                          if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')]
               for node in tests.body if isinstance(node, ast.ClassDef)}
    assert {key: len(value) for key, value in methods.items()} == {
        'CounterRegressionTest': 5, 'AdmissionRegressionTest': 5}
    launcher_strings = {node.value for node in ast.walk(trees['tools/q2-remote.py'])
                        if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    for name in files[2:7]:
        assert name in launcher_strings, name
    cmake = (ROOT / 'CMakeLists.txt').read_text()
    assert 'NAME q2_hc_inject_reuse_analysis' in cmake
    assert len(re.findall(r'^add_test\(NAME', cmake, re.M)) == 32
    assert all(name in cmake for name in ('reader|core/gguf_reader', 'dequant|core/ggml_dequant',
                                          'config|models/qwen38_flash_next/config'))
    manifest_path = ROOT / 'config/q2-hc-inject-reuse-component-source-v2.json'
    variant = read(manifest_path)['variants']['hc-inject-reuse-draft']
    for key in ('parent_manifest', 'measured_parent', 'draft_manifest', 'draft_static',
                'numerical_include', 'fixture', 'generator'):
        assert sha(ROOT / variant[key]) == variant[key + '_sha256'], key
    provider = ROOT / variant['source']
    assert {str(p.relative_to(provider)): sha(p) for p in provider.rglob('*') if p.is_file()} == variant['files']
    assert len(variant['files']) == 1027
    assert sha(ROOT / previous['fixture_assembly']) == previous['fixture_assembly_sha256']
    attempts = {}
    for label in ('core-handover', 'core-handover-r2', 'core-handover-r3'):
        command_path = PREP / (label + '-command.json')
        command = read(command_path)
        assert command['exit_code'] == 255
        assert 'No route to host' in (PREP / (label + '-stderr.txt')).read_text()
        attempts[label] = dict(**command, path=str(command_path.relative_to(ROOT)),
            sha256=sha(command_path), stderr_sha256=sha(PREP / (label + '-stderr.txt')),
            stdout_sha256=sha(PREP / (label + '-stdout.txt')))
    release_path = ROOT / 'config/q2-down-register-palette-v2-window-release.json'
    assert sha(release_path) == 'e64145d666ce7ebcd470a7587a54979d6b11c8c909b073cc639c3d8071a652db'
    parent = read(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json')['model']
    refs = read(ROOT / 'config/q2-fixed-prefill-reference.json')
    pp = parent['measurements']['prefill_tok_s']['median']
    tg = parent['measurements']['decode_steps_s']['median']
    ud = refs['arms']['ud']['measurements']['prefill_tok_s']['median']
    assert (pp, tg, ud) == (1585.308983, 25.16079073, 1685.777092)
    assert parent['input_sha256'] == refs['input']['sha256']
    gap = (parent['measurements']['prefill_s']['median'] -
           refs['arms']['ud']['measurements']['prefill_s']['median']) * 1000
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-runtime-preparation.v1',
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        previous_preparation_sha256=sha(previous_path), historical_checkpoint=CHECKPOINT,
        historical_fixture_hashes_verified=len(previous['fixtures']),
        files={name: sha(ROOT / name) for name in files}, syntax_parsed=len(trees),
        regression_methods=methods, planned_host_counts=dict(debug=35, asan_ubsan=35),
        host_tests_executed=False, regression_tests_executed=False,
        provider_files_exact=1027, numerical_fixture_assembly_unchanged=True,
        remote_attempts=attempts, last_verified_release_sha256=sha(release_path),
        network_failure_before_connection=True, remote_job_started=False,
        GPU_run=False, GPU_reserved=False, production_provider_changed=False,
        model_inference=False, borrowed_executor_scratch_qualified=False,
        numerical_acceptance=False, independent_quality=False, performance_increment_found=False,
        retained_PP=pp, retained_TG=tg, fixed_UD_PP=ud,
        required_prefill_saving_ms=gap, required_PP_increase_percent=100 * (ud / pp - 1),
        model_plan_frozen=False, component_plan_frozen=False, full_curve=False,
        Q4=False, saved_comparators_rebuilt_or_rerun=False, goal_met=False,
        retry_or_waiter_scheduled=False, remote_cleanup=False)
    with (ROOT / 'config/q2-hc-inject-reuse-runtime-preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(provider_files_exact=1027, syntax_parsed=len(trees),
        regression_methods=10, tests_run=False, remote_exits=[255, 255, 255], GPU_run=False)))


if __name__ == '__main__':
    main()
