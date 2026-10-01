#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic source variant contract. No build/model/GPU execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('q2_port', ROOT / 'tools/q2_port.py')
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)


class PortTest(unittest.TestCase):
    def fixture(self):
        data = b'alpha beta gamma'
        expected = b'alpha two gamma'
        manifest = {'commit': port.PIN, 'repository': 'https://github.com/gufo-org/gufo',
                    'files': {'src/file.cpp': port.sha(data)}}
        recipe = {'schema': 'synapse-lie.q2-host-edits.v1', 'upstream_pin': port.PIN,
                  'runtime_link_allowed': False, 'files': {'src/file.cpp': {
                      'before_sha256': port.sha(data), 'after_sha256': port.sha(expected),
                      'edits': [{'old': 'beta', 'new': 'two'}]}}}
        return data, expected, manifest, recipe

    def test_exact_original_coordinates_no_cascading(self):
        self.assertEqual(port.transform(b'ab cd', [{'old': 'ab', 'new': 'cd'},
                                                 {'old': 'cd', 'new': 'ef'}]), b'cd ef')

    def test_empty_missing_duplicate_and_overlapping_edits_refused(self):
        for data, edits in [(b'abc', [{'old': '', 'new': 'x'}]),
                            (b'abc', [{'old': 'absent', 'new': 'x'}]),
                            (b'abc abc', [{'old': 'abc', 'new': 'x'}]),
                            (b'abc', [{'old': 'abc', 'new': 'x'}, {'old': 'bc', 'new': 'y'}])]:
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                port.transform(data, edits)

    def test_positive_identity_and_data_unchanged(self):
        data, expected, manifest, recipe = self.fixture()
        before = copy.deepcopy(recipe)
        self.assertEqual(port.checked_variant(manifest, recipe, lambda _: data), {'src/file.cpp': expected})
        self.assertEqual(before, recipe)

    def test_drift_and_permissions_refused(self):
        data, _, manifest, recipe = self.fixture()
        with self.assertRaisesRegex(ValueError, 'pristine source drift'):
            port.checked_variant(manifest, recipe, lambda _: data + b'!')
        for field in ('before_sha256', 'after_sha256'):
            bad = copy.deepcopy(recipe); bad['files']['src/file.cpp'][field] = '0' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                port.checked_variant(manifest, bad, lambda _: data)
        for value in (True, 0, None):
            bad = copy.deepcopy(recipe); bad['runtime_link_allowed'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'runtime linkage'):
                port.checked_variant(manifest, bad, lambda _: data)
        for field in ('schema', 'upstream_pin'):
            bad = copy.deepcopy(recipe); bad[field] = 'other'
            with self.assertRaisesRegex(ValueError, 'recipe identity'):
                port.checked_variant(manifest, bad, lambda _: data)
        for field in ('commit', 'repository'):
            bad = copy.deepcopy(manifest); bad[field] = 'other'
            with self.assertRaisesRegex(ValueError, 'manifest identity'):
                port.checked_variant(bad, recipe, lambda _: data)

    def test_unknown_target_and_traversal_refused_before_load(self):
        data, _, manifest, recipe = self.fixture()
        bad = copy.deepcopy(recipe); bad['files']['src/other.cpp'] = bad['files'].pop('src/file.cpp')
        with self.assertRaisesRegex(ValueError, 'unknown source'):
            port.checked_variant(manifest, bad, lambda _: self.fail('unexpected load'))
        for path in ('../escape', '/absolute', 'src/../escape', './relative'):
            m, r = copy.deepcopy(manifest), copy.deepcopy(recipe)
            m['files'] = {path: port.sha(data)}
            r['files'] = {path: r['files']['src/file.cpp']}
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'member path'):
                port.checked_variant(m, r, lambda _: self.fail('unexpected load'))

    def test_materialization_refuses_reuse_and_symlink_output(self):
        # Small controlled result avoids copying the upstream tree in a unit test.
        with tempfile.TemporaryDirectory(prefix='lie-q2-source-NOT-INFERENCE-') as tmp:
            base = Path(tmp)
            with patch.object(port, 'checked_variant', return_value={'src/test.cpp': b'fixture'}):
                r = port.prepare(base / 'unused', base / 'source')
                self.assertFalse(r['runtime_link_allowed'])
                self.assertEqual((base / 'source/src/test.cpp').read_bytes(), b'fixture')
                with self.assertRaises(FileExistsError):
                    port.prepare(base / 'unused', base / 'source')
                (base / 'alias').symlink_to(base / 'source', target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'symlink output'):
                    port.prepare(base / 'unused', base / 'alias/subdirectory')

    def test_real_recipe_has_exact_pinned_footprint(self):
        m = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        r = json.loads(port.RECIPE.read_text())
        # Default CPU CTest must not require the optional upstream checkout.
        # verify-q2-host.py additionally applies/verifies every pinned source byte.
        self.assertEqual(len(r['files']), 6)
        self.assertFalse(r['runtime_link_allowed'])
        for name, change in r['files'].items():
            self.assertEqual(change['before_sha256'], m['files'][name])
            self.assertRegex(change['after_sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(change['edits'])
        device = r['files']['src/models/qwen38_flash_next/kernels/rocm/device_model.cpp']
        self.assertEqual(len(device['edits']), 1)
        self.assertIn('LIE Q2 HIP execution is not implemented', device['edits'][0]['new'])
        self.assertIn('return false;', device['edits'][0]['new'])


if __name__ == '__main__':
    unittest.main()
