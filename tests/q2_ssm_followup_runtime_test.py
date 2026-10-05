#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate prepared SSM launch routing without starting any child process."""
import argparse
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / 'evidence/q2-ssm-followup-runtime-preparation/overlay'
sys.path.insert(0, str(OVERLAY / 'tools'))
spec = importlib.util.spec_from_file_location('ssm_followup_remote', OVERLAY / 'tools/q2-remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
VARIANTS = ('ssm-fixed-shape', 'ssm-fixed-bounds', 'ssm-compact-lds', 'ssm-pingpong')


class FollowupRuntimeTests(unittest.TestCase):
    def refused(self, argv, message=None):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['q2-remote.py', *argv]), \
                patch.object(remote.subprocess, 'run', side_effect=AssertionError('Unexpected process')) as run, \
                patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected staging')) as mkdir, \
                contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as caught:
                remote.main()
            self.assertEqual(caught.exception.code, 2)
            run.assert_not_called()
            mkdir.assert_not_called()
        if message:
            self.assertIn(message, output.getvalue())

    def test_matching_component_and_model_reach_staging_only(self):
        for variant in VARIANTS:
            for mode in (variant + '-check', 'q2-counting-' + variant):
                argv = [mode, 'q2-ssm-followup-guard', '--source-variant', variant]
                if mode.startswith('q2-counting-'):
                    argv += ['--rebuild-mmq']
                with self.subTest(mode=mode), patch.object(sys, 'argv', ['q2-remote.py', *argv]), \
                        patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                        patch.object(remote.subprocess, 'run', side_effect=AssertionError('Unexpected process')) as run:
                    with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                        remote.main()
                    run.assert_not_called()

    def test_crossed_providers_and_unrelated_modes_are_refused(self):
        for variant in VARIANTS:
            modes = ['cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'ssm-row-group-check', 'q2-counting-ssm-row-group']
            modes += [v + '-check' for v in VARIANTS if v != variant]
            modes += ['q2-counting-' + v for v in VARIANTS if v != variant]
            for mode in modes:
                with self.subTest(variant=variant, mode=mode):
                    self.refused([mode, 'q2-ssm-followup-guard', '--source-variant', variant])
            self.refused([variant + '-check', 'q2-ssm-followup-guard'])

    def test_build_and_launch_scope_guards(self):
        for variant in VARIANTS:
            component = [variant + '-check', 'q2-ssm-followup-guard', '--source-variant', variant]
            model = ['q2-counting-' + variant, 'q2-ssm-followup-guard', '--source-variant', variant]
            self.refused(component + ['--rebuild-mmq'], 'builds its numerical kernels directly')
            self.refused(model, 'Historical counting requires a full MMQ rebuild')
            for argv in (component, model + ['--rebuild-mmq']):
                self.refused(argv + ['--detach'], 'Persistent launch is limited')
                self.refused(argv + ['--native-curve'], 'Native curve requires')

    def test_all_providers_and_fixtures_bind_exactly(self):
        parser = argparse.ArgumentParser()
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                self.assertEqual(remote.ssm_followup_source(parser, variant),
                                 '.deps/gufo-q2-' + variant + '-run')

    def test_altered_fixture_parent_and_kernel_are_rejected(self):
        registry = json.loads((OVERLAY / remote.SSM_FOLLOWUP_MANIFEST).read_text())['variants']
        real_sha = remote.file_sha256
        for variant in VARIANTS:
            info = registry[variant]
            paths = list(info['bindings']) + [
                'config/q2-down-register-scatter-model-results.json',
                '.deps/gufo-q2-' + variant + '-run/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp']
            for relative in paths:
                target = OVERLAY / relative
                with self.subTest(variant=variant, altered=relative), \
                        patch.object(remote, 'file_sha256', side_effect=lambda p: '0' * 64 if p == target else real_sha(p)), \
                        contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        remote.ssm_followup_source(argparse.ArgumentParser(), variant)
                    self.assertEqual(caught.exception.code, 2)

    def test_runner_modes_select_expected_existing_and_new_targets(self):
        tree = ast.parse((OVERLAY / 'tools/q2-runner.py').read_text())
        assignments = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ('counting_mode', 'hc_mode', 'hc_target'):
                    assignments[node.targets[0].id] = node.value
        self.assertEqual(set(assignments), {'counting_mode', 'hc_mode', 'hc_target'})
        for variant in VARIANTS:
            for component in (True, False):
                mode = variant + '-check' if component else 'q2-counting-' + variant
                namespace = dict(mode=mode, mixed_mode=False)
                result = {name: eval(compile(ast.Expression(value), '<runner assignment>', 'eval'), namespace)
                          for name, value in assignments.items()}
                self.assertEqual(result['counting_mode'], not component)
                self.assertEqual(result['hc_mode'], component)
                if component:
                    self.assertEqual(result['hc_target'], 'q2_ssm_row_group' if variant in VARIANTS[:2]
                                     else 'q2_ssm_compact_lds')

    def test_original_leases_and_frozen_campaign_unchanged(self):
        def locks(path):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'LOCKS' for t in node.targets):
                    return ast.literal_eval(node.value)
            self.fail('Missing original locks')
        self.assertEqual(locks(OVERLAY / 'tools/q2-runner.py'), locks(ROOT / 'tools/q2-runner.py'))
        plan = json.loads((ROOT / 'config/q2-ssm-row-group-plan.json').read_text())
        for path, digest in {**plan['fixtures'], **plan['manifests'],
                             plan['window_helper']: plan['window_helper_sha256']}.items():
            self.assertEqual(remote.file_sha256(ROOT / path), digest, path)


if __name__ == '__main__':
    unittest.main()
