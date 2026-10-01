#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private loopback HTTP client/accounting fixtures; NOT model inference."""
import http.server
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest

BINARY=str(Path(sys.argv.pop(1)).resolve())
MODULE=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/bench-http.py'))

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(body)
        prompt=32+sum(m.get('content','').count(MODULE['PAD'])*13 for m in body['messages'])
        prompt+=len(body['messages'])-1
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        rows=[{'choices':[{'index':0,'delta':{'role':'assistant'},'finish_reason':None}]},
              {'choices':[{'index':0,'delta':{'content':'READY'},'finish_reason':None}]},
              {'choices':[{'index':0,'delta':{},'finish_reason':'length'}],'usage':{'prompt_tokens':prompt,'completion_tokens':1,'total_tokens':prompt+1}}]
        if self.server.failure=='usage':rows[-1]['usage']['completion_tokens']=999999
        for row in rows:self.wfile.write(b'data: '+json.dumps(row).encode()+b'\n\n');self.wfile.flush()
        if self.server.failure!='truncated':self.wfile.write(b'data: [DONE]\n\n')

class HttpBench(unittest.TestCase):
    def setUp(self):
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.requests=[];self.server.failure=None
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.tmp=tempfile.TemporaryDirectory(prefix='lie-http-bench-');self.root=Path(self.tmp.name)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def command(self,*args):
        return subprocess.run([BINARY,'--suite','http','--url',f'http://127.0.0.1:{self.server.server_port}/v1','--model','NOT-INFERENCE','--output',str(self.root/'out.jsonl'),'--server-label','CPU wire fixture','--cache-policy','off','--repetitions','2',*args],capture_output=True,text=True,timeout=20)
    def test_physical_full_prefill_and_export(self):
        p=self.command('--preset','prefill','--sizes','8192,131072','--export-requests',str(self.root/'corpus.jsonl'))
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        rows=[json.loads(x) for x in (self.root/'out.jsonl').read_text().splitlines()]
        summary=MODULE['summarize'](rows);self.assertEqual(len(summary['cases']),2)
        for row in [x for x in rows if x['event']=='sample']:
            self.assertEqual(row['usage']['completion_tokens'],1)
            self.assertAlmostEqual(row['prompt_over_wall_tps'],row['usage']['prompt_tokens']/row['wall_seconds'])
            self.assertLessEqual(row['first_output_seconds'],row['wall_seconds'])
        self.assertEqual(len((self.root/'corpus.jsonl').read_text().splitlines()),2)
    def test_actual_assistant_history_followup_and_short_eos(self):
        corpus=self.root/'corpus.jsonl';corpus.write_text(json.dumps({'id':'dialogue','body':{'messages':[{'role':'user','content':'one'}],'max_tokens':32},'followups':['two']})+'\n')
        p=self.command('--requests',str(corpus));self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        self.assertEqual(self.server.requests[1]['messages'][1],{'role':'assistant','content':'READY'})
        self.assertEqual(self.server.requests[1]['messages'][2]['content'],'two')
        rows=[json.loads(x) for x in (self.root/'out.jsonl').read_text().splitlines()]
        self.assertFalse(MODULE['summarize'](rows)['cases'][0]['full_output_budget'])
    def test_truncated_stream_and_bad_usage_preserve_failure(self):
        for failure in ['truncated','usage']:
            self.server.failure=failure;p=self.command('--preset','decode')
            self.assertEqual(p.returncode,1,p.stderr+p.stdout)
            rows=[json.loads(x) for x in (self.root/'out.jsonl').read_text().splitlines()]
            self.assertEqual(rows[-1]['event'],'failed')
            with self.assertRaises(ValueError):MODULE['summarize'](rows)
            (self.root/'out.jsonl').rename(self.root/(failure+'.jsonl'))
    def test_no_overwrite_or_invalid_bound_requests(self):
        (self.root/'out.jsonl').write_text('preserve\n')
        p=self.command('--preset','decode');self.assertNotEqual(p.returncode,0)
        self.assertEqual((self.root/'out.jsonl').read_text(),'preserve\n');self.assertFalse(self.server.requests)
        p=self.command('--preset','prefill','--sizes','-1');self.assertEqual(p.returncode,2)

if __name__=='__main__':unittest.main()
