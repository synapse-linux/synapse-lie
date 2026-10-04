#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""256K C HTTP/worker bounds with synthetic token counts; NOT-INFERENCE."""
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

CONTEXT=262144
BODY=8*1024*1024
MODEL='cpu-test-fixture'

def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

def call(port,path,obj=None,body=None):
    if obj is not None:body=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=15)
    try:
        c.request('GET' if body is None else 'POST',path,body,{} if body is None else {'Content-Type':'application/json'})
        r=c.getresponse();return r.status,r.read().decode()
    finally:c.close()

def payload(text):
    return {'model':MODEL,'messages':[{'role':'user','content':text}],'max_tokens':32,'temperature':0}

def main():
    binary=sys.argv[1]
    for option,value in [('--context','1048577'),('--context','-1'),('--context','4294967296'),('--context','1048576x'),('--rope-scaling','yarn3'),('--port','262144')]:
        p=subprocess.run([binary,option,value],capture_output=True,timeout=5)
        assert p.returncode==2,(option,value,p.returncode)
    a,m=port(),port()
    while a==m:m=port()
    with tempfile.TemporaryDirectory(prefix='lie-context-NOT-INFERENCE-') as d:
        with (Path(d)/'server.log').open('wb') as log:
            p=subprocess.Popen([binary,'--model',':fixture:','--context',str(CONTEXT),'--port',str(a),'--management-port',str(m)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+6
                while True:
                    assert p.poll() is None
                    try:
                        if call(m,'/actuator/health/readiness')[0]==200:break
                    except OSError:pass
                    assert time.monotonic()<deadline;time.sleep(.01)
                def state():return json.loads(call(m,'/actuator/llm')[1])
                caps=state()['backend']
                assert (caps['context_tokens'],caps['max_request_bytes'],caps['max_messages'])==(CONTEXT,BODY,1024)
                text='FIXTURE-TOKENS:262112\n'+'x'*(2*1024*1024)
                status,body=call(a,'/v1/chat/completions',payload(text))
                assert status==200,body
                result=json.loads(body)
                assert result['usage']['prompt_tokens']==262112 and result['usage']['completion_tokens']>0
                assert result['lie_timings']['prefill_tokens']==262112 and result['lie_timings']['prefill_calls']==128
                status,body=call(a,'/v1/responses',{'model':MODEL,'input':text,'max_output_tokens':32,'stream':True})
                assert status==200,body
                events=[json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: ')]
                assert events[-1]['type']=='response.completed'
                assert events[-1]['response']['usage']['input_tokens']==262112
                before=state()['scheduler']['executor']['prefill_started']
                for n in [262113,262145]:
                    status,body=call(a,'/v1/chat/completions',payload(f'FIXTURE-TOKENS:{n}\n'))
                    assert status==400 and 'context_budget_exceeded' in body,(status,body)
                assert state()['scheduler']['executor']['prefill_started']==before
                q=payload('')
                padding=BODY-len(json.dumps(q,separators=(',',':')).encode())
                q['messages'][0]['content']='x'*padding
                body=json.dumps(q,separators=(',',':')).encode();assert len(body)==BODY
                assert call(a,'/v1/chat/completions',body=body)[0]==200
                q=payload('normal');q['messages']=[{'role':'user','content':'normal'}]*1024
                assert call(a,'/v1/chat/completions',q)[0]==200
                q['messages'].append({'role':'user','content':'normal'})
                assert call(a,'/v1/chat/completions',q)[0]==400
                with socket.create_connection(('127.0.0.1',a),timeout=3) as s:
                    s.sendall(f'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: {BODY+1}\r\n\r\n'.encode())
                    assert s.recv(4096).startswith(b'HTTP/1.1 413')
            finally:
                if p.poll() is None:p.terminate()
                try:p.wait(timeout=6)
                except subprocess.TimeoutExpired:p.kill();p.wait();raise
            assert p.returncode==0,Path(d,'server.log').read_text()
    print('256K context, >1MiB Chat/Responses, exact body/message bounds and pre-forward overflow refusal: PASS; CPU fixture, NOT-INFERENCE')

if __name__=='__main__':main()
