#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profile',ROOT/'tools/analyze-q2-curve-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
BINARY = sys.argv.pop(1)


class ProfileContract(unittest.TestCase):
    def test_threaded_writer_and_failed_forward(self):
        result = subprocess.run([BINARY], capture_output=True, text=True, check=True)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 2)
        rows = profile.records(lines[0])
        self.assertEqual((rows[0]['position'],rows[0]['tokens']), (4096,2))
        self.assertEqual(rows[0]['ple']['cache_hits'], 32)
        self.assertEqual(rows[0]['ple']['unique_rows'], 32)
        self.assertFalse(json.loads(lines[1])['completed'])
        with self.assertRaises(ValueError):
            profile.records(result.stderr)
        invalid = copy.deepcopy(rows[0])
        invalid['ple']['cache_hits'] = 33
        with self.assertRaises(ValueError):
            profile.records(json.dumps(invalid,separators=(',',':')))

    def test_http_interval_and_frontier_alignment(self):
        events = []
        position = 10
        for index in range(129):
            tokens = 2 if index == 0 else 1
            events.append(dict(prefill=index==0,position=position,tokens=tokens,
                started_ns=1000+index*1000,ended_ns=1500+index*1000,
                process_read_bytes=0,ple={k:0 for k in profile.METRICS}))
            position += tokens
        sample = SimpleNamespace(cached_prompt_tokens=10,prefill_tokens=2,
                                 decode_calls=128,completion_tokens=128,prefill_ms=1,decode_ms=1)
        request = dict(started_ns=0,ended_ns=200000)
        row = profile.attribute(events,request,sample)
        self.assertEqual(row['prefill']['tokens'],2)
        self.assertEqual(row['decode']['calls'],128)
        with self.assertRaises(ValueError):
            profile.attribute(events[:-1],request,sample)
        broken = copy.deepcopy(events)
        broken[0]['started_ns'] = -1
        with self.assertRaises(ValueError):
            profile.attribute(broken,request,sample)
        broken = copy.deepcopy(events)
        broken[30]['position'] += 1
        with self.assertRaises(ValueError):
            profile.attribute(broken,request,sample)


if __name__ == '__main__':
    unittest.main()
