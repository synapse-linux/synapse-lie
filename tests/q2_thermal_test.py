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
    def sensors(self, root):
        for i, name in enumerate(('amdgpu', 'k10temp')):
            p = root / ('hwmon' + str(i)); p.mkdir()
            (p / 'name').write_text(name)
            (p / 'temp1_input').write_text('50000')

    def test_cpu_limit_does_not_apply_to_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.sensors(root)
            enforce(sample(root))
            (root / 'hwmon0/temp1_input').write_text('101000')
            (root / 'hwmon1/temp1_input').write_text('98000')
            enforce(sample(root))
            gpu, cpu = sample(root)
            self.assertIsNone(gpu['limit_mc'])
            self.assertEqual(gpu['limit_source'], 'no_exposed_gpu_threshold')
            self.assertTrue(cpu['inclusive'])
            self.assertEqual(cpu['limit_source'], 'owner_cpu_limit')
            (root / 'hwmon1/temp1_input').write_text('98001')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))

    def test_lower_hardware_limit_remains_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.sensors(root)
            (root / 'hwmon0/temp1_input').write_text('79000')
            (root / 'hwmon0/temp1_crit').write_text('79000')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))
            self.assertFalse(sample(root)[0]['inclusive'])
            (root / 'hwmon0/temp1_input').write_text('50000')
            (root / 'hwmon1/temp1_input').write_text('98000')
            (root / 'hwmon1/temp1_crit').write_text('98000')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))

    def test_gpu_uses_lowest_exposed_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.sensors(root)
            (root / 'hwmon0/temp1_crit').write_text('110000')
            (root / 'hwmon0/temp1_max').write_text('105000')
            (root / 'hwmon0/temp1_input').write_text('104999')
            enforce(sample(root))
            self.assertEqual(sample(root)[0]['limit_mc'], 105000)
            (root / 'hwmon0/temp1_input').write_text('105000')
            with self.assertRaisesRegex(RuntimeError, 'Thermal limit'):
                enforce(sample(root))
            (root / 'hwmon0/temp1_max').write_text('0')
            self.assertEqual(sample(root)[0]['limit_mc'], 110000)
            enforce(sample(root))

    def test_missing_sensor_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.sensors(root)
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
