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
spec = importlib.util.spec_from_file_location('routes',ROOT/'tools/analyze-q2-route-profile.py')
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)
BINARY = sys.argv.pop(1)


class RouteContract(unittest.TestCase):
    def test_real_writer_and_geometry(self):
        run = subprocess.run([BINARY],capture_output=True,text=True,check=True)
        rows = routes.records(run.stderr)
        self.assertEqual(len(rows),2)
        mixed,small = [r['geometry'] for r in rows[0]['layers']]
        self.assertEqual((mixed['mixed_128_tiles'],mixed['mixed_64_tiles']), (7,4))
        self.assertEqual(mixed['live_16_row_fragments'],64)
        self.assertEqual(mixed['reserved_16_row_fragments'],88)
        self.assertEqual(mixed['mixed_reserved_16_row_fragments'],72)
        self.assertEqual(small['mixed_128_tiles'],0)
        self.assertEqual(small['mixed_64_tiles'],64)
        self.assertEqual(rows[1]['layers'],[])
        failed = subprocess.run([BINARY,'incomplete'],capture_output=True,text=True,check=True)
        with self.assertRaises(ValueError):
            routes.records(failed.stderr)
        original = [json.loads(x) for x in run.stderr.splitlines()]
        for index,key,value in [(0,'layer',1),(0,'forward_id',1),(0,'gate_rows',64),
                                (0,'gate_tiles',10),(0,'iq2_wmma',False),
                                (0,'at_ns',0),(2,'observed_layers',1),(2,'tokens',1023),
                                (3,'id',3),(3,'position',-1)]:
            bad = copy.deepcopy(original);bad[index][key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):
                routes.records('\n'.join(json.dumps(r,separators=(',',':')) for r in bad))
        for bad in (original[:-1], original[:1], original[1:]):
            # Dropping only a complete final decode does not break the log itself;
            # request attribution below detects missing completed work.
            if bad == original[:-1]:
                continue
            with self.assertRaises(ValueError):
                routes.records('\n'.join(json.dumps(r,separators=(',',':')) for r in bad))
        with self.assertRaises(ValueError):
            routes.records(run.stderr+'{"event":"q2_route_error"}\n')

    def test_counts_reject_missing_or_duplicate_assignments(self):
        for counts,tokens,used in [([1,2],2,1),([3,-1],2,1),([True,1],2,1),
                                   ([3,1],2,2),([],2,1),([1,1],2,3)]:
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                routes.geometry(counts,tokens,used)

    def test_http_alignment_requires_all_decode_and_prefill(self):
        events = [dict(id=i,prefill=i==0,position=4096+(1024 if i else 0)+max(0,i-1),
                       tokens=1024 if i==0 else 1,started_ns=10+i*10,ended_ns=15+i*10,
                       layers=[]) for i in range(129)]
        sample = SimpleNamespace(cached_prompt_tokens=4096,prefill_tokens=1024,
                                 decode_calls=128,completion_tokens=128)
        request = dict(started_ns=1,ended_ns=1400)
        self.assertEqual(routes.attribute(events,request,sample)['decode_calls'],128)
        for bad in (events[:-1],events[1:]):
            with self.assertRaises(ValueError):routes.attribute(bad,request,sample)
        bad=copy.deepcopy(events);bad[5]['position']+=1
        with self.assertRaises(ValueError):routes.attribute(bad,request,sample)
        with self.assertRaises(ValueError):routes.attribute(events,dict(started_ns=11,ended_ns=1400),sample)


if __name__ == '__main__':
    unittest.main()
