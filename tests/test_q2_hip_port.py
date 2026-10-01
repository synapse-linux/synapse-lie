#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import q2_port as host
import q2_hip_port as hip

class HipPort(unittest.TestCase):
    def setUp(self):
        self.base = {'src/a.cpp': b'old\n', 'LICENSE': b'notice\n'}
        self.owned = b'// SPDX-License-Identifier: MIT\nnew\n'
        self.recipe = {'schema': 'synapse-lie.q2-hip-edits.v1', 'upstream_pin': host.PIN,
                       'host_recipe_sha256': 'base-hash', 'runtime_link_allowed': False,
                       'files': {'src/a.cpp': {'before_sha256': host.sha(b'old\n'),
                           'after_sha256': host.sha(b'new\n'),
                           'edits': [{'old': 'old', 'new': 'new'}]}},
                       'owned_files': {'src/b.h': {'path': 'adapters/gufo-q2/b.h',
                                                  'sha256': host.sha(self.owned)}}}
    def run_recipe(self, recipe=None):
        return hip.checked_variant(self.base, recipe or self.recipe,
                                   lambda n: self.owned, 'base-hash')
    def test_exact_overlay_does_not_mutate_base(self):
        original = dict(self.base)
        out = self.run_recipe()
        self.assertEqual(out, {'src/a.cpp': b'new\n', 'src/b.h': self.owned,
                               'LICENSE': b'notice\n'})
        self.assertEqual(self.base, original)
    def test_identity_and_admission_refusal(self):
        for key, value in [('schema', 'other'), ('upstream_pin', 'other'),
                           ('host_recipe_sha256', 'other'), ('runtime_link_allowed', True),
                           ('runtime_link_allowed', 0)]:
            r = copy.deepcopy(self.recipe); r[key] = value
            with self.assertRaises(ValueError): self.run_recipe(r)
    def test_source_and_result_drift(self):
        for key in ('before_sha256', 'after_sha256'):
            r = copy.deepcopy(self.recipe); r['files']['src/a.cpp'][key] = 'other'
            with self.assertRaises(ValueError): self.run_recipe(r)
        self.base['src/a.cpp'] += b'old\n'
        with self.assertRaises(ValueError): self.run_recipe()
    def test_unknown_or_traversal_destination(self):
        for name in ('src/unknown', '../a', '/tmp/a'):
            r = copy.deepcopy(self.recipe)
            r['files'] = {name: r['files']['src/a.cpp']}
            with self.assertRaises(ValueError): self.run_recipe(r)
    def test_owned_identity_and_license(self):
        self.owned += b'drift'
        with self.assertRaises(ValueError): self.run_recipe()
        self.owned = b'no license'
        self.recipe['owned_files']['src/b.h']['sha256'] = host.sha(self.owned)
        with self.assertRaises(ValueError): self.run_recipe()
    def test_owned_cannot_replace_upstream_or_read_foreign_tree(self):
        r = copy.deepcopy(self.recipe)
        r['owned_files'] = {'LICENSE': r['owned_files']['src/b.h']}
        with self.assertRaises(ValueError): self.run_recipe(r)
        for p in ('../other/x.h', '/tmp/x.h', 'other/x.h'):
            r = copy.deepcopy(self.recipe); r['owned_files']['src/b.h']['path'] = p
            with self.assertRaises(ValueError): self.run_recipe(r)
    def test_symlink_source_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'a').write_bytes(b'a'); (root / 'b').symlink_to('a')
            with self.assertRaises(ValueError): hip.read_regular(root, 'b')
    def test_recipe_footprint_and_owned_inputs(self):
        # No optional upstream checkout required by default CPU CTest.
        r = json.loads(hip.RECIPE.read_text())
        m = json.loads((ROOT / 'third_party/gufo-source.json').read_text())
        h = json.loads(host.RECIPE.read_text())
        self.assertFalse(r['runtime_link_allowed'])
        self.assertEqual(r['host_recipe_sha256'], host.sha(host.RECIPE.read_bytes()))
        self.assertEqual(len(r['files']), 6)
        self.assertTrue(set(r['files']).isdisjoint(h['files']))
        for name, item in r['files'].items():
            self.assertEqual(item['before_sha256'], m['files'][name])
        self.assertEqual(len(r['owned_files']), 3)
        for item in r['owned_files'].values():
            self.assertEqual(item['sha256'], host.sha((ROOT / item['path']).read_bytes()))

if __name__ == '__main__': unittest.main()
