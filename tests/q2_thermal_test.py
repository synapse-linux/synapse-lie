#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic thermal fixtures; no real device or policy changes."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from q2_thermal import enforce, sample


class ThermalTests(unittest.TestCase):
    def test_threshold_and_missing_sensor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i, name in enumerate(('amdgpu', 'k10temp')):
                p = root / ('hwmon' + str(i)); p.mkdir()
                (p / 'name').write_text(name)
                (p / 'temp1_input').write_text('50000')
            enforce(sample(root))
            (root / 'hwmon0/temp1_input').write_text('98000')
            enforce(sample(root))
            self.assertTrue(sample(root)[0]['inclusive'])
            (root / 'hwmon0/temp1_input').write_text('98001')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))
            (root / 'hwmon0/temp1_input').write_text('79000')
            (root / 'hwmon0/temp1_crit').write_text('79000')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))
            (root / 'hwmon1/name').write_text('unknown')
            with self.assertRaisesRegex(RuntimeError, 'sensors unavailable'):
                sample(root)

    def test_malformed_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'hwmon0'; p.mkdir()
            (p / 'name').write_text('amdgpu')
            (p / 'temp1_input').write_text('1000000')
            with self.assertRaisesRegex(RuntimeError, 'Invalid thermal'):
                sample(Path(tmp))


if __name__ == '__main__':
    unittest.main()
