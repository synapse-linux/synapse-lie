#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Immutable replay qualification rejection without loading a GPU runtime."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from q2_binary_replay import sha, inventory, verify_replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'current'
        self.label = 'qualified'
        self.old = self.root.parent/self.label
        self.mode = 'q2-counting-iq2-mixed'
        for directory in (self.root, self.old):
            for name in ('source/provider.cpp', 'experiments/counting-baseline/q2_model.cpp',
                         'tests/q2_profile_markers.hip'):
                p = directory/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(name)
        self.binary = self.old/'build/hip/cmake/hip/q2_model'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'owned qualified binary')
        receipt = self.old/'results/result.json'
        receipt.parent.mkdir()
        receipt.write_text(json.dumps(dict(mode=self.mode, finished_at='done',
            state='MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT', commands=[dict(exit_code=0)],
            binary_sha256_after=sha(self.binary))))
        self.expected = dict(mode=self.mode, receipt_sha256=sha(receipt),
            binary_sha256=sha(self.binary), source_files=inventory(self.old/'source'),
            fixture_sha256=sha(self.old/'experiments/counting-baseline/q2_model.cpp'),
            markers_sha256=sha(self.old/'tests/q2_profile_markers.hip'), libraries={'lib': 'qualified'})
        (self.root/'config').mkdir()
        self.manifest = self.root/'config/q2-fixed-binary-replay.json'
        self.manifest.write_text(json.dumps(dict(controls={self.label: self.expected})))

    def check(self):
        return verify_replay(self.root, self.label, self.mode, {},
                             library_reader=lambda *_: {'lib': 'qualified'})

    def test_qualified_exact_replay(self):
        binary, receipt = self.check()
        self.assertEqual(binary, self.binary)
        self.assertEqual(receipt['build_commands'], 0)

    def test_profile_manifest_keeps_source_binary_library_guards(self):
        profile = self.root/'config/q2-fixed-moe-profile-binary.json'
        profile.write_bytes(self.manifest.read_bytes())
        binary, receipt = verify_replay(self.root, self.label, self.mode, {},
            library_reader=lambda *_: {'lib': 'qualified'}, manifest_name=profile.name)
        self.assertEqual(binary, self.binary)
        self.assertEqual(receipt['build_commands'], 0)
        self.binary.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'binary changed'):
            verify_replay(self.root, self.label, self.mode, {},
                library_reader=lambda *_: {'lib': 'qualified'}, manifest_name=profile.name)

    def test_unqualified_manifest_path_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Unqualified replay manifest'):
            verify_replay(self.root, self.label, self.mode, {}, manifest_name='../elsewhere.json')

    def test_mutated_binary_is_rejected(self):
        self.binary.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'binary changed'):
            self.check()

    def test_staged_or_original_source_changes_are_rejected(self):
        for directory in (self.root, self.old):
            with self.subTest(directory=directory):
                p = directory/'source/unrecorded.cpp'
                p.write_text('changed')
                with self.assertRaisesRegex(RuntimeError, 'source changed'):
                    self.check()
                p.unlink()

    def test_library_mismatch_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'library identity changed'):
            verify_replay(self.root, self.label, self.mode, {},
                           library_reader=lambda *_: {'lib': 'different'})

    def test_fixture_and_receipt_mutations_are_rejected(self):
        for name, reason in [('tests/q2_profile_markers.hip', 'fixture changed'),
                             ('results/result.json', 'receipt changed')]:
            p = self.old/name
            saved = p.read_bytes()
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, reason):
                self.check()
            p.write_bytes(saved)


if __name__ == '__main__':
    unittest.main()
