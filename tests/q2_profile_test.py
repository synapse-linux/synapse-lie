#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only profile accounting fixtures, independent of GPU availability."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('profile_analysis',
    Path(__file__).resolve().parents[1] / 'tools/analyze-q2-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


spec = importlib.util.spec_from_file_location('resource_analysis',
    Path(__file__).resolve().parents[1] / 'tools/q2-resource-report.py')
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class ProfileTests(unittest.TestCase):
    def test_union_is_not_sum(self):
        result = profile.summarize([('a', 10, 30), ('b', 20, 40), ('a', 50, 60)])
        self.assertEqual(result['kernel_sum_ns'], 50)
        self.assertEqual(result['gpu_busy_union_ns'], 40)
        self.assertEqual(result['kernel_span_ns'], 50)
        self.assertEqual(result['inter_kernel_gap_ns'], 10)
        self.assertEqual(result['kernels'][0]['calls'], 2)
        self.assertEqual(result['kernels'][0]['kernel_time_percent'], 60)

    def test_invalid_time_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid dispatch'):
            profile.summarize([('a', 20, 10)])

    def test_markers_exclude_loading_and_smoke(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'profile.db'
            with sqlite3.connect(path) as db:
                db.executescript('''CREATE TABLE rocpd_info_kernel_symbol (id INTEGER, display_name TEXT);
                    CREATE TABLE rocpd_kernel_dispatch (kernel_id INTEGER, start INTEGER, end INTEGER);''')
                rows = [('loading', 1, 1000), ('smoke', 1100, 2000),
                        ('Q2ProfilePrefillBegin()', 2100, 2110), ('pp', 2200, 2500),
                        ('Q2ProfilePrefillEnd()', 2510, 2520),
                        ('Q2ProfileDecodeBegin()', 2600, 2610), ('tg', 2700, 2800),
                        ('Q2ProfileDecodeEnd()', 2810, 2820)]
                for index, (name, start, end) in enumerate(rows):
                    db.execute('INSERT INTO rocpd_info_kernel_symbol VALUES (?,?)', (index, name))
                    db.execute('INSERT INTO rocpd_kernel_dispatch VALUES (?,?,?)', (index, start, end))
            result = profile.analyze(path)
            self.assertEqual(result['phases']['prefill']['kernel_sum_ns'], 300)
            self.assertEqual(result['phases']['decode']['kernel_sum_ns'], 100)
            with sqlite3.connect(path) as db:
                db.execute('DELETE FROM rocpd_kernel_dispatch WHERE kernel_id=7')
            with self.assertRaisesRegex(ValueError, 'exactly one Decode End'):
                profile.analyze(path)


class ResourceTests(unittest.TestCase):
    def test_phase_resources_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'resources.db'
            with sqlite3.connect(path) as db:
                db.executescript('''CREATE TABLE rocpd_info_kernel_symbol (id INTEGER, display_name TEXT);
                    CREATE TABLE rocpd_kernel_dispatch (kernel_id INTEGER, start INTEGER, end INTEGER,
                    private_segment_size INTEGER, group_segment_size INTEGER,
                    workgroup_size_x INTEGER, workgroup_size_y INTEGER, workgroup_size_z INTEGER);''')
                rows = [('loading', 1, 1000, 999), ('Q2ProfilePrefillBegin()', 1100, 1110, 0),
                        ('q2', 1200, 1300, 320), ('q2', 1300, 1400, 320),
                        ('q2', 1400, 1450, 0), ('Q2ProfilePrefillEnd()', 1500, 1510, 0),
                        ('Q2ProfileDecodeBegin()', 1600, 1610, 0), ('tg', 1700, 1800, 0),
                        ('Q2ProfileDecodeEnd()', 1900, 1910, 0)]
                for index, (name, start, end, private) in enumerate(rows):
                    db.execute('INSERT INTO rocpd_info_kernel_symbol VALUES (?,?)', (index, name))
                    db.execute('INSERT INTO rocpd_kernel_dispatch VALUES (?,?,?,?,?,?,?,?)',
                               (index, start, end, private, 30336, 32, 4, 1))
            result = resources.report(path)['phases']
            self.assertEqual(len(result['prefill']), 2)
            q2 = result['prefill'][0]
            self.assertEqual((q2['kernel'], q2['calls'], q2['total_ns']), ('q2', 2, 200))
            self.assertEqual(q2['private_bytes_per_work_item'], 320)
            self.assertEqual(q2['shared_bytes_per_work_group'], 30336)
            self.assertEqual(q2['work_items_per_group'], 128)
            self.assertEqual(result['decode'][0]['total_ns'], 100)
            with sqlite3.connect(path) as db:
                db.execute('UPDATE rocpd_kernel_dispatch SET private_segment_size=-1 WHERE kernel_id=2')
            with self.assertRaisesRegex(ValueError, 'Invalid dispatch metadata'):
                resources.report(path)
            with sqlite3.connect(path) as db:
                db.execute('DELETE FROM rocpd_kernel_dispatch WHERE kernel_id IN (2,3,4)')
            with self.assertRaisesRegex(ValueError, 'Empty marked phase'):
                resources.report(path)


if __name__ == '__main__':
    unittest.main()
