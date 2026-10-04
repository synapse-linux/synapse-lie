#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only accounting/CLI/report fixtures, never model inference."""
import copy
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

BINARY=str(Path(sys.argv.pop(1)).resolve())
REPORT=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/bench-report.py'))

class SimplifiedBenchmark(unittest.TestCase):
    def run_case(self,*args,model=':fixture:'):
        with tempfile.TemporaryDirectory(prefix='lie-simplified-') as tmp:
            out=Path(tmp)/'rows.jsonl'
            p=subprocess.run([BINARY,'--model',model,'--output',str(out),*args],capture_output=True,text=True,timeout=15)
            self.assertEqual(p.returncode,0,p.stderr)
            result=REPORT['read_result'](out)
            self.assertTrue(result['identity']['synthetic'])
            return result,[json.loads(x) for x in out.read_text().splitlines()]

    def test_depth_is_reused_not_pp_numerator(self):
        result,rows=self.run_case('--depths','0,4096,131072','--repetitions','2')
        self.assertEqual(len(result['configurations']),3)
        for r in [x for x in rows if x['event']=='sample']:
            self.assertLessEqual(abs(r['prefill_tokens_per_user']-2048),32)
            self.assertEqual(r['cache_tokens'],r['depth'])
            self.assertEqual(r['output_tokens_per_user'],128)
        self.assertEqual(result['configurations'][-1]['depth'],131072)

    def test_fresh_full_prompt_counts_and_comparison_keys(self):
        result,rows=self.run_case('--suite','fresh','--sizes','8192,32768,131072,258794','--tg','16','--warmups','0')
        self.assertEqual(len(REPORT['compare'](result,result)),4)
        for r in [x for x in rows if x['event']=='sample']:
            self.assertEqual(r['depth'],0)
            self.assertEqual(r['cache_tokens'],0)
            self.assertEqual(r['prefill_tokens_per_user'],r['prompt_tokens'])
        self.assertGreater(result['configurations'][-1]['prompt_tokens'],258760)
        self.assertEqual(result['configurations'][-1]['context_capacity'],262144)
        for sizes in ['262144','0','131072,131072']:
            p=subprocess.run([BINARY,'--model',':fixture:','--output','unused.jsonl','--suite','fresh','--sizes',sizes],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,2,p.stderr)

    def test_reactive_dispatch_counters(self):
        result,rows=self.run_case('--suite','multi','--users','1,2,4,6,8','--tg','8')
        self.assertEqual(result['identity']['execution'],'LIE-reactive-ready-batch')
        for row in rows:
            if row['event']=='sample':
                self.assertEqual(row['decode_batches'],8 if row['users']>1 else 0)
                self.assertEqual(row['decode_batch_rows'],8*row['users'] if row['users']>1 else 0)
                self.assertEqual(row['decode_single_calls'],8 if row['users']==1 else 0)
        serial,_=self.run_case('--suite','multi','--users','1,2','--tg','8','--execution','serial')
        self.assertEqual(serial['identity']['execution'],'LIE-serial-interleaved')

    def test_multiple_users_use_common_decode_window(self):
        result,rows=self.run_case('--suite','multi','--users','1,2,4,6,8')
        self.assertEqual([r['users'] for r in result['configurations']],[1,2,4,6,8])
        for r in [x for x in rows if x['event']=='sample']:
            self.assertEqual(r['output_tokens'],r['users']*128)

    def test_small_context_calibration_respects_render_bound(self):
        result,_=self.run_case('--suite','multi','--users','1,2',model=':render-bound:')
        self.assertEqual([r['users'] for r in result['configurations']],[1,2])

    def test_eos_retained_without_nominal_token_rate(self):
        result,_=self.run_case('--suite','multi','--users','2',model=':eos:')
        self.assertFalse(result['configurations'][0]['full_output_budget'])

    def test_invalid_arguments_and_unsupported_mtp(self):
        for args in [[],['--depths','1,,2'],['--users','0'],['--users','9'],['--repetitions','0'],['--mode','mtp'],['--suite','nonsense']]:
            p=subprocess.run([BINARY,*args],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,2,p.stderr)

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lie-bench-exclusive-') as tmp:
            out=Path(tmp)/'rows.jsonl';out.write_text('preserve\n')
            p=subprocess.run([BINARY,'--model',':fixture:','--output',str(out)],capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,1);self.assertEqual(out.read_text(),'preserve\n')

    def test_report_rejects_incomplete_or_corrupt_counts(self):
        result,rows=self.run_case('--depths','0')
        with tempfile.TemporaryDirectory(prefix='lie-report-invalid-') as tmp:
            path=Path(tmp)/'bad.jsonl'
            for change in ['incomplete','count','time']:
                bad=copy.deepcopy(rows)
                if change=='incomplete':bad.pop()
                else:
                    row=next(x for x in bad if x['event']=='sample')
                    row['output_tokens' if change=='count' else 'decode_ns']=0
                path.write_text('\n'.join(json.dumps(x) for x in bad)+'\n')
                with self.assertRaises(ValueError):REPORT['read_result'](path)

    def test_mismatched_comparison_refused(self):
        result,_=self.run_case('--depths','0');other=copy.deepcopy(result)
        other['configurations'][0]['physical_ids_sha256']='different'
        with self.assertRaises(ValueError):REPORT['compare'](result,other)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib unavailable')
    def test_cli_graph_export_with_space_in_path(self):
        with tempfile.TemporaryDirectory(prefix='lie-graphs-') as tmp:
            out=Path(tmp)/'rows.jsonl';graphs=Path(tmp)/'graphs with spaces'
            p=subprocess.run([BINARY,'--model',':fixture:','--output',str(out),'--depths','0','--graphs',str(graphs)],capture_output=True,text=True,timeout=15)
            self.assertEqual(p.returncode,0,p.stderr)
            for name in ['summary.json','summary.csv','benchmark.svg','benchmark.png']:
                self.assertGreater((graphs/name).stat().st_size,0)
            self.assertTrue(json.loads((graphs/'summary.json').read_text())['primary']['identity']['synthetic'])

    def test_supervisor_refuses_output_override(self):
        module=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/run-bench.py'))
        for args in [['--output','foreign.jsonl'],['--suite','single','--suite','multi'],['--suite','single','extra']]:
            with self.assertRaises(ValueError):module['validate_args'](args)

if __name__=='__main__':unittest.main()
