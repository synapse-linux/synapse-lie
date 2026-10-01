#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import q2_port as host
import q2_hip_port as hip
import q2_test_grid as grid

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
        self.assertEqual(len(r['files']), 8)
        self.assertTrue(set(r['files']).isdisjoint(h['files']))
        for name, item in r['files'].items():
            self.assertEqual(item['before_sha256'], m['files'][name])
        self.assertEqual(len(r['owned_files']), 3)
        for item in r['owned_files'].values():
            self.assertEqual(item['sha256'], host.sha((ROOT / item['path']).read_bytes()))

    def test_executor_profile_is_checked_before_construction_or_hip(self):
        r = json.loads(hip.RECIPE.read_text())
        entries = r['files']['src/models/qwen38_flash_next/kernels/rocm/executor.cpp']['edits']
        early = [e['new'] for e in entries if 'lie_q2_profile_make(' in e['new']
                 and 'std::unique_ptr<Executor> e(new Executor());' in e['old']]
        self.assertEqual(len(early), 1, 'profile must precede construction/first HIP call')
        text = early[0]
        self.assertLess(text.index('lie_q2_profile_make('),
                        text.index('std::unique_ptr<Executor> e(new Executor());'))
        for role in ('gate', 'up', 'down'):
            self.assertIn('lie_q2_type(static_cast<int>(l.ffn_' + role + '_exps.type))', text)
        self.assertIn('t.experts', text)
        self.assertIn('!t.empty()', text)
        self.assertIn('c.num_layers', text)
        self.assertIn('model.has_mtp()', text)
        self.assertIn('model.layers().size() > descriptors.size()', text)
        self.assertNotIn('hipMalloc', text)
        reserves = [e['new'] for e in entries if 'lie_q2_workspace_prepare(' in e['new']]
        self.assertEqual(len(reserves), 1)
        self.assertNotIn('lie_q2_plan_make(', reserves[0])
        self.assertNotIn('lie_q2_profile_make(', reserves[0])

    def test_codebook_generator_hash_geometry_and_exclusive_output(self):
        values = ['0x0808080808080808'] * 256
        values[2] = '0x0808080808081919'
        data = ('GGML_TABLE_BEGIN(uint64_t, iq2xxs_grid, 256)\n' +
                ',\n'.join(values) + ',\nGGML_TABLE_END()').encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source' / grid.TABLE
            source.parent.mkdir(parents=True)
            source.write_bytes(data)
            (root / 'third_party').mkdir()
            manifest = root / 'third_party/gufo-source.json'
            with patch.object(grid, 'ROOT', root):
                manifest.write_text(json.dumps({'files': {grid.TABLE: host.sha(data)}}))
                output = root / 'oracle.inc'
                self.assertEqual(grid.generate(root / 'source', output), host.sha(data))
                self.assertEqual(output.read_text().count('ULL,'), 256)
                with self.assertRaises(FileExistsError):
                    grid.generate(root / 'source', output)
                source.write_bytes(data + b'drift')
                with self.assertRaisesRegex(ValueError, 'source drift'):
                    grid.generate(root / 'source', root / 'other.inc')
                bad = data.replace(b'1919', b'1918')
                source.write_bytes(bad)
                manifest.write_text(json.dumps({'files': {grid.TABLE: host.sha(bad)}}))
                with self.assertRaisesRegex(ValueError, 'goldens mismatch'):
                    grid.generate(root / 'source', root / 'other.inc')
                bad = data.replace(b'0x0808080808080808,', b'0x0808080808080008,', 1)
                source.write_bytes(bad)
                manifest.write_text(json.dumps({'files': {grid.TABLE: host.sha(bad)}}))
                with self.assertRaises(ValueError):
                    grid.generate(root / 'source', root / 'other.inc')

    def test_q2_mma_products_use_existing_fp32_capacity(self):
        r = json.loads(hip.RECIPE.read_text())
        edits = r['files']['src/models/qwen38_flash_next/kernels/rocm/mmq/mmq.hpp']['edits']
        self.assertEqual(len(edits), 4)
        for entry in edits[:2]:
            self.assertIn('make_float2(base_dm.x*', entry['new'])
            self.assertIn('reinterpret_cast<float2 *>', entry['new'])
            self.assertIn('#else\n#ifdef FAST_FP16_AVAILABLE', entry['new'])
        self.assertIn('reinterpret_cast<const float2 *>', edits[2]['new'])
        pitch = 2 * 32 + 32 + 4
        self.assertEqual(pitch % 2, 0)
        self.assertLessEqual(2 * 32 + 2 * 16, pitch)

    def test_iq2_fractional_scale_fix_is_scoped(self):
        r = json.loads(hip.RECIPE.read_text())
        edits = r['files']['src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp']['edits']
        self.assertEqual(len(edits), 1)
        self.assertIn('sumi = sumi * ls / 8;', edits[0]['old'])
        self.assertIn('float(sumi * ls) * 0.125f', edits[0]['new'])
        self.assertNotIn('sumi * ls / 8', edits[0]['new'])
        self.assertLess(32 * 43 * 128 * 31, 2**24)
        self.assertEqual(3175 / 8 / 1024, 0.3875732421875)
        self.assertEqual((3175 // 8) / 1024, 0.38671875)

if __name__ == '__main__': unittest.main()
