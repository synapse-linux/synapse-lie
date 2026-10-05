#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check isolated shared-down dispatch and immutable source bindings without SSH."""
import argparse
import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('shared_down_remote', ROOT / 'tools/q2-remote.py')
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class SharedDownRuntime(unittest.TestCase):
    def test_only_matched_component_reaches_staging(self):
        with patch.object(sys, 'argv', ['q2-remote.py', 'shared-down-fixed-check', 'q2-shared-down-guard',
                                      '--source-variant', 'shared-down-fixed']), \
                patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                patch.object(remote.subprocess, 'run', side_effect=AssertionError('Unexpected child')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_crossed_provider_and_model_modes_refused(self):
        choices = [('shared-down-fixed-check', 'qualified'),
                   ('ssm-fixed-bounds-check', 'shared-down-fixed'),
                   ('q2-counting-ssm-fixed-bounds', 'shared-down-fixed'),
                   ('cpu', 'shared-down-fixed'), ('q2-bench', 'shared-down-fixed')]
        for mode, variant in choices:
            with self.subTest(mode=mode, variant=variant):
                self.refused([mode, 'q2-shared-down-guard', '--source-variant', variant])

    def refused(self, argv):
        with patch.object(sys, 'argv', ['q2-remote.py', *argv]), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected staging')), \
                patch.object(remote.subprocess, 'run', side_effect=AssertionError('Unexpected child')) as run, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                remote.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_alternative_launch_flags_refused(self):
        for flag in ('--rebuild-mmq', '--detach', '--native-curve', '--point-only'):
            self.refused(['shared-down-fixed-check', 'q2-shared-down-guard',
                          '--source-variant', 'shared-down-fixed', flag])

    def test_actual_provider_inventory_and_provenance(self):
        self.assertEqual(remote.shared_down_source(argparse.ArgumentParser()),
                         '.deps/gufo-q2-shared-down-fixed-run')

    def test_changed_fixture_and_provider_refused(self):
        paths = ['tests/q2_shared_down_mirror.hip', 'config/q2-shared-down-fixed-source.json',
                 '.deps/gufo-q2-shared-down-fixed-run/src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp']
        original = remote.file_sha256
        for name in paths:
            with self.subTest(path=name), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(remote, 'file_sha256', side_effect=lambda p: '0' * 64 if p == ROOT/name else original(p)):
                with self.assertRaises(SystemExit) as error:
                    remote.shared_down_source(argparse.ArgumentParser())
                self.assertEqual(error.exception.code, 2)

    def test_runner_selects_only_component_target(self):
        tree = ast.parse((ROOT / 'tools/q2-runner.py').read_text())
        context = {'mode': 'shared-down-fixed-check', 'mixed_mode': False}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in ('hc_mode', 'hc_target'):
                    context[name] = eval(compile(ast.Expression(node.value), '<runner>', 'eval'), {}, context)
        self.assertTrue(context['hc_mode'])
        self.assertEqual(context['hc_target'], 'q2_shared_down_mirror')


if __name__ == '__main__':
    unittest.main()
