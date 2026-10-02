#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refuse unsafe experiment/archive combinations before any staging or SSH."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'tools/q2-remote.py'
spec = importlib.util.spec_from_file_location('q2_remote', path)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class RemoteGuardTests(unittest.TestCase):
    def refuse(self, argv, reason):
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run, \
             patch.object(Path, 'mkdir', side_effect=AssertionError('No staging may start')) as mkdir, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as result:
                remote.main()
            self.assertEqual(result.exception.code, 2)
            self.assertIn(reason, error.getvalue())
            run.assert_not_called()
            mkdir.assert_not_called()

    def test_changed_executor_header_cannot_reuse_mmq(self):
        for variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-prefetch'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'explicitly rebuild MMQ')

    def test_iq2_entry_requires_correct_source(self):
        self.refuse(['iq2-pair-operators', 'q2-fixture'], 'require the isolated IQ2 source')
        self.refuse(['routed-operators', 'q2-fixture'], 'require the isolated stack source')

    def test_packed_entry_requires_correct_source(self):
        self.refuse(['packed-operators', 'q2-fixture'], 'require the isolated packed source')

    def test_hc_up_entry_requires_correct_source(self):
        self.refuse(['hc-up-operators', 'q2-fixture'], 'require the isolated hc-up-fused source')
        self.refuse(['hc-up-operators', 'q2-fixture', '--source-variant', 'hc-prefetch'],
                    'require the isolated hc-up-fused source')

    def test_q2_source_cannot_replace_ud_control(self):
        for variant in ('packed', 'hc-prefetch'):
            self.refuse(['ud-bench2k', 'q2-fixture', '--source-variant', variant],
                        'Stack source requires')

    def test_rebuild_flag_does_not_silently_apply_elsewhere(self):
        self.refuse(['q2-profile', 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')


if __name__ == '__main__':
    unittest.main()
