#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared-core consumer/accounting fixtures; never model inference."""
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


class CoreBench(unittest.TestCase):
    def run_case(self,root,*args,model=':fixture:',tokens=None,text=None):
        root=Path(root);source=root/'input';output=root/'result.jsonl'
        source.write_text(text if text is not None else json.dumps(tokens or [0,1,2,3]))
        kind='--prompt-file' if text is not None else '--tokens-file'
        p=subprocess.run([BINARY,'--suite','core','--model',model,'--output',str(output),kind,str(source),
                          '--tg','16','--repetitions','2',*args],capture_output=True,text=True,timeout=15)
        return p,output

    def test_real_core_lifecycle_counts_and_replay(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-bench-') as tmp:
            p,path=self.run_case(tmp,'--users','4','--warmups','1')
            self.assertEqual(p.returncode,0,p.stderr)
            r=REPORT['read_result'](path)
            self.assertTrue(r['identity']['synthetic'])
            self.assertEqual(r['identity']['execution'],'shared-reactive-core')
            self.assertEqual(len(r['jobs']),12)
            self.assertEqual(len(r['samples']),3)
            for row in r['jobs']:
                self.assertEqual(row['prefill_tokens'],4)
                self.assertEqual(row['output_tokens'],16)
                self.assertEqual(row['output_ids'],list(range(16)))
            for row in r['samples']:
                self.assertEqual(row['output_tokens'],64)
                self.assertAlmostEqual(row['output_per_total_wall_tps'],64e9/row['wall_ns'])
            self.assertTrue(REPORT['compare'](r,r)[0]['eligible'])

    def test_raw_text_and_early_eos(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-raw-') as tmp:
            p,path=self.run_case(tmp,model=':eos:',text='abc def ghi jkl')
            self.assertEqual(p.returncode,0,p.stderr)
            r=REPORT['read_result'](path)
            self.assertEqual(r['identity']['input_kind'],'raw-text')
            self.assertEqual(r['configurations'][0]['prompt_tokens'],4)
            self.assertFalse(r['configurations'][0]['full_output_budget'])
            self.assertEqual(r['jobs'][0]['output_tokens'],7)
            self.assertEqual(r['jobs'][0]['finish'],'stop')

    def test_failure_preserved_and_no_average(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-failure-') as tmp:
            p,path=self.run_case(tmp,model=':failure:')
            self.assertEqual(p.returncode,1,p.stderr)
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(rows[-1]['event'],'failed')
            with self.assertRaises(ValueError):REPORT['read_result'](path)

    def test_invalid_input_and_exclusive_output(self):
        for tokens in [[-1],[2147483648],[True],[256]]:
            with tempfile.TemporaryDirectory(prefix='lie-core-invalid-') as tmp:
                p,path=self.run_case(tmp,tokens=tokens)
                self.assertNotEqual(p.returncode,0)
                if path.exists():self.assertEqual(json.loads(path.read_text().splitlines()[-1])['event'],'failed')
        with tempfile.TemporaryDirectory(prefix='lie-core-exclusive-') as tmp:
            path=Path(tmp)/'result.jsonl';path.write_text('preserve\n')
            p,_=self.run_case(tmp)
            self.assertEqual(p.returncode,1);self.assertEqual(path.read_text(),'preserve\n')

    def test_report_rejects_corruption_and_scope_mismatch(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-report-') as tmp:
            p,path=self.run_case(tmp);self.assertEqual(p.returncode,0,p.stderr)
            original=[json.loads(x) for x in path.read_text().splitlines()]
            for mode in ['count','hash','ids','time','missing']:
                rows=copy.deepcopy(original)
                if mode=='missing':rows.pop()
                elif mode=='hash':next(r for r in rows if r['event']=='input')['physical_ids_sha256']='bad'
                elif mode=='ids':next(r for r in rows if r['event']=='job')['output_ids'][0]=5
                elif mode=='count':next(r for r in rows if r['event']=='sample')['output_tokens']=0
                else:next(r for r in rows if r['event']=='job')['first_token_ns']=-1
                bad=Path(tmp)/'bad.jsonl';bad.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
                with self.assertRaises(ValueError):REPORT['read_result'](bad)
            result=REPORT['read_result'](path);other=copy.deepcopy(result)
            other['configurations'][0]['prefill_chunk']=1
            with self.assertRaises(ValueError):REPORT['compare'](result,other)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib unavailable')
    def test_core_graphs(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-graphs-') as tmp:
            graphs=Path(tmp)/'charts with spaces'
            p,path=self.run_case(tmp,'--graphs',str(graphs))
            self.assertEqual(p.returncode,0,p.stderr)
            for name in ['summary.json','summary.csv','benchmark.svg','benchmark.png']:
                self.assertGreater((graphs/name).stat().st_size,0)
            self.assertEqual(REPORT['read_result'](path)['identity']['suite'],'core')


if __name__=='__main__':unittest.main()
