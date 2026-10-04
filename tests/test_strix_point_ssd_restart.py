#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only validation of the two-process SSD evidence parser."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'point_ssd_restart', Path(__file__).resolve().parents[1]/'tools/strix-point-ssd-restart-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Tests(unittest.TestCase):
    def rows(self, hot):
        return [
            {'event':'identity','schema':'synapse-lie.core-bench.v1',
             'mode':'mtp','synthetic':False,'cache_policy':'ssd'},
            {'event':'input','physical_ids_sha256':'fixture'},
            {'event':'job','prompt_tokens':8192,'output_tokens':32,
             'output_ids':list(range(32)),'cached_tokens':8192 if hot else 0,
             'ssd_cached_tokens':8192 if hot else 0,'prefill_tokens':0 if hot else 8192,
             'mtp_drafted_tokens':33,'mtp_accepted_tokens':18},
            {'event':'sample','ssd_hits':1 if hot else 0,
             'ssd_writes':1,'ssd_errors':0},
            {'event':'complete','exit_code':0},
        ]

    def test_cold_and_hot_require_distinct_cache_events(self):
        gate.one(self.rows(False), 'mtp', False)
        gate.one(self.rows(True), 'mtp', True)
        wrong = self.rows(True)
        wrong[3]['ssd_hits'] = 0
        with self.assertRaisesRegex(RuntimeError, 'did not read'):
            gate.one(wrong, 'mtp', True)
        wrong = self.rows(False)
        wrong[-1]['exit_code'] = 1
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            gate.one(wrong, 'mtp', False)


if __name__ == '__main__':
    unittest.main()
