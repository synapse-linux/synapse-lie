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


if __name__ == '__main__':
    unittest.main()
