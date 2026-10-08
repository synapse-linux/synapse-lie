#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host fixtures only; never invoke fan control commands."""
import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'tools/axb35-fan-curves.py'
spec = importlib.util.spec_from_file_location('fan_curves', path)
fan_curves = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fan_curves)


class FanCurveTests(unittest.TestCase):
    def setUp(self):
        self.config = {f'fan{i}': {'mode': 'curve', 'level': 2,
                       'rampup_curve': '40,50,60,70,82',
                       'rampdown_curve': '35,45,55,65,78'} for i in range(1, 4)}
        self.config['apu_power_mode'] = 'balanced'

    def test_only_fan_curves_are_applied(self):
        original = copy.deepcopy(self.config)
        commands = fan_curves.commands(self.config)
        self.assertEqual(len(commands), 9)
        for i, command in enumerate(commands):
            self.assertEqual(command[:4], ['/usr/bin/axb35-ctl', 'set', 'fan', str(i // 3 + 1)])
            self.assertEqual(command[4], ('rampdown', 'rampup', 'mode')[i % 3])
        self.assertEqual(self.config, original)

    def test_invalid_curves_and_missing_fans(self):
        for value in ('40,50,60,70,82;reboot', '40,50,60,70', '40,50,60,70,101',
                      '40,50,50,70,82', '40,50,60,70,-1', [40, 50, 60, 70, 82]):
            with self.subTest(value=value):
                config = copy.deepcopy(self.config)
                config['fan3']['rampup_curve'] = value
                with self.assertRaises(ValueError): fan_curves.commands(config)
        for value in (None, {}, {'fan1': self.config['fan1']}):
            with self.assertRaises(ValueError): fan_curves.commands(value)

    def test_hysteresis_and_mode(self):
        self.config['fan2']['rampdown_curve'] = '40,50,60,70,82'
        with self.assertRaises(ValueError): fan_curves.commands(self.config)
        self.config['fan2']['rampdown_curve'] = '35,45,55,65,78'
        self.config['fan2']['mode'] = 'fixed'
        with self.assertRaises(ValueError): fan_curves.commands(self.config)


if __name__ == '__main__':
    unittest.main()
