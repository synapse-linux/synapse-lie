#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic CPU executor through the REAL C worker/flow/libuv serving path. Not inference."""
import concurrent.futures
import http.client
import json
import math
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BINARY=sys.argv[1]
MODEL='cpu-test-fixture'

def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]

def request(p,path,body=None):
    c=http.client.HTTPConnection('127.0.0.1',p,timeout=5)
    c.request('GET' if body is None else 'POST',path,body,{} if body is None else {'Content-Type':'application/json'})
    r=c.getresponse(); result=(r.status,dict(r.getheaders()),r.read().decode('utf-8',errors='strict')); c.close(); return result

def payload(text='normal',stream=False,tokens=128):
    return {'model':MODEL,'messages':[{'role':'user','content':text}],'max_tokens':tokens,'temperature':0,'stream':stream,
            **({'stream_options':{'include_usage':True}} if stream else {})}

def chat(p,obj): return request(p,'/v1/chat/completions',json.dumps(obj,ensure_ascii=False).encode())

def eventually(fn,seconds=4):
    end=time.monotonic()+seconds
    while True:
        result=fn()
        if result: return result
        if time.monotonic()>end: raise AssertionError('condition deadline')
        time.sleep(.01)

def timings(value,usage):
    t=value['lie_timings']
    assert t['schema']=='synapse-lie.request-timings.v1'
    assert t['scope']=='synchronous_executor_calls' and t['valid'] is True
    assert t['prefill_tokens']==usage['prompt_tokens']==4 and t['prefill_calls']==1
    assert t['decode_tokens']==usage['completion_tokens']
    assert t['decode_calls'] in (t['decode_tokens'],t['decode_tokens']+1)
    for phase in ('prefill','decode'):
        ms=t[phase+'_ms']; rate=t[phase+'_tokens_per_second']
        assert math.isfinite(ms) and ms>=0
        if ms==0: assert rate is None
        else: assert math.isclose(rate,t[phase+'_tokens']*1000/ms,rel_tol=1e-12,abs_tol=1e-12)
    return t

def events(text):
    lines=text.split('\n\n'); assert lines[-1]==''
    assert lines[-2]=='data: [DONE]' and text.count('data: [DONE]')==1
    data=[json.loads(x[6:]) for x in lines[:-2] if x.startswith('data: ')]
    assert len(data)==len(lines)-2
    assert len({x['id'] for x in data})==1
    assert all('NOT-INFERENCE' in x['system_fingerprint'] for x in data)
    assert data[0]['choices'][0]['delta']['role']=='assistant'
    finish=[x['choices'][0]['finish_reason'] for x in data if x.get('choices') and x['choices'][0]['finish_reason'] is not None]
    assert len(finish)==1
    terminal=[x for x in data if 'lie_timings' in x]; assert len(terminal)==1
    assert terminal[0]['choices'][0]['finish_reason'] in ('stop','length')
    timings(terminal[0],data[-1]['usage'])
    return ''.join(x['choices'][0]['delta'].get('content','') for x in data if x.get('choices')),data[-1]['usage'],finish[0]

def slow(p):
    s=socket.socket(); s.settimeout(4); s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024); s.connect(('127.0.0.1',p))
    body=json.dumps(payload('LONG',True,512)).encode()
    s.sendall(f'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(body)}\r\n\r\n'.encode()+body)
    return s

def main():
    a,m=port(),port()
    while a==m: m=port()
    with tempfile.TemporaryDirectory(prefix='lie-synthetic-serving-') as directory:
        log_path=Path(directory)/'server.log'; clients=[]
        with log_path.open('wb') as log:
            proc=subprocess.Popen([BINARY,'--port',str(a),'--management-port',str(m),'--model',':fixture:',
                                   '--max-active','2','--request-timeout-ms','2000'],stdout=log,stderr=log)
            try:
                def ready():
                    if proc.poll() is not None: raise AssertionError(log_path.read_text())
                    try: return request(m,'/actuator/health/readiness')[0]==200
                    except OSError: return False
                eventually(ready)
                info=json.loads(request(m,'/actuator/info')[2]); assert info['backend']['synthetic'] and not info['inference_verified']
                assert not info['backend']['hardware_qualified'] and info['backend']['ownership']=='synthetic-test-fixture'
                assert json.loads(request(a,'/v1/models')[2])['data'][0]['id']==MODEL
                def state(): return json.loads(request(m,'/actuator/llm')[2])['scheduler']
                baseline_fds=len(list(Path(f'/proc/{proc.pid}/fd').iterdir()))
                for text,tokens in [('normal',128),('normal',3),('EMPTY',128)]:
                    status,_,body=chat(a,payload(text,False,tokens)); assert status==200,body
                    full=json.loads(body); assert 'NOT-INFERENCE' in full['system_fingerprint']
                    t=timings(full,full['usage'])
                    assert t['decode_calls']==(1 if text=='EMPTY' else 3 if tokens==3 else 9)
                    status,headers,body=chat(a,payload(text,True,tokens)); assert status==200 and 'text/event-stream' in headers['Content-Type']
                    content,usage,finish=events(body)
                    assert content==full['choices'][0]['message']['content']
                    assert usage==full['usage'] and finish==full['choices'][0]['finish_reason']
                    if text=='normal' and tokens==128: assert content=='fixture: 🙂"\\\n��',repr(content)
                    if text=='EMPTY': assert usage['completion_tokens']==0 and content==''
                # Timings accompany the finish, even when usage was not requested.
                obj=payload('normal',True,3); obj.pop('stream_options')
                status,_,body=chat(a,obj); assert status==200
                data=[json.loads(x[6:]) for x in body.split('\n\n') if x.startswith('data: {')]
                assert not any('usage' in x for x in data)
                assert sum('lie_timings' in x for x in data)==1
                timings(data[-1],{'prompt_tokens':4,'completion_tokens':3})
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    results=list(pool.map(lambda i:chat(a,payload('normal',bool(i%2),8)),range(16)))
                assert all(r[0]==200 for r in results)
                for field,value in [('tools',[]),('temperature',.5),('max_tokens',513),('stream',1),('model','not-loaded')]:
                    obj=payload(); obj[field]=value; assert chat(a,obj)[0]==400
                obj=payload(); obj['messages']=[{'role':'user','content':'\0'}]; assert chat(a,obj)[0]==400
                assert request(a,'/v1/chat/completions',b'{bad')[0]==400
                assert chat(a,payload('OVERSIZED'))[0]==400
                # Chunked request, split inside UTF-8. Parser must assemble before dispatch.
                body=json.dumps(payload('€🙂'),ensure_ascii=False).encode(); split=body.index('€'.encode())+1
                with socket.create_connection(('127.0.0.1',a),timeout=5) as s:
                    s.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n')
                    for chunk in (body[:split],body[split:]): s.sendall(f'{len(chunk):x}\r\n'.encode()+chunk+b'\r\n')
                    s.sendall(b'0\r\n\r\n'); reply=b''
                    while part:=s.recv(8192): reply+=part
                    assert reply.startswith(b'HTTP/1.1 200'),reply
                # Backpressure reaches decode admission; peer and management remain responsive.
                before=state()['generated_tokens']; held=slow(a); clients.append(held)
                eventually(lambda:state()['active']==1); time.sleep(.25)
                one=state()['generated_tokens']; time.sleep(.15); two=state()['generated_tokens']
                assert before<one==two<before+512,(before,one,two)
                start=time.monotonic(); assert request(m,'/actuator/health/liveness')[0]==200
                assert chat(a,payload())[0]==200 and time.monotonic()-start<1
                held.close(); clients.remove(held); eventually(lambda:state()['active']==0)
                # Explicit request deadline; no fake successful terminal after cancellation.
                held=slow(a); clients.append(held); cancelled=state()['cancelled']
                eventually(lambda:state()['cancelled']>cancelled,4); held.close(); clients.remove(held)
                eventually(lambda:state()['active']==0)
                # Fill all eight admissions, including queued requests; refuse ninth.
                for _ in range(8): clients.append(slow(a))
                eventually(lambda:state()['queued']==6 and state()['active']==2)
                assert chat(a,payload())[0]==429
                for s in clients: s.close()
                clients.clear(); eventually(lambda:state()['active']==0 and state()['queued']==0)
                eventually(lambda:len(list(Path(f'/proc/{proc.pid}/fd').iterdir()))<=baseline_fds+2)
                # Poison is terminal for this runtime, not a fallback/retry.
                status,_,body=chat(a,payload('FAULT')); assert status==503,body
                assert json.loads(body)['error']['code']=='inference_failed' and 'lie_timings' not in body,body
                assert request(m,'/actuator/health/readiness')[0]==503
                assert json.loads(request(a,'/v1/models')[2])['data']==[]
                assert chat(a,payload())[0]==503
            finally:
                for s in clients: s.close()
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=6)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(); raise
                print(log_path.read_text())
                assert proc.returncode==0,proc.returncode
        # Shutdown with live work/writes, using a fresh owned child.
        with log_path.open('ab') as log:
            proc=subprocess.Popen([BINARY,'--port',str(a),'--management-port',str(m),'--model',':fixture:'],stdout=log,stderr=log)
            held=None
            try:
                eventually(ready); held=slow(a); time.sleep(.02); proc.terminate(); proc.wait(timeout=6)
                assert proc.returncode==0
            finally:
                if held: held.close()
                if proc.poll() is None: proc.kill(); proc.wait()
                print(log_path.read_text())
        # Streaming failure cannot be rendered as a successful length/stop terminal.
        with log_path.open('ab') as log:
            proc=subprocess.Popen([BINARY,'--port',str(a),'--management-port',str(m),'--model',':fixture:'],stdout=log,stderr=log)
            try:
                eventually(ready)
                status,headers,body=chat(a,payload('FAULT',True))
                if status==200:
                    assert 'event-stream' in headers['Content-Type'] and '"error"' in body
                    assert body.endswith('data: [DONE]\n\n') and '"finish_reason":"length"' not in body and '"finish_reason":"stop"' not in body
                    assert 'lie_timings' not in body and '"usage"' not in body
                else: assert status==503 and json.loads(body)['error']['code']=='inference_failed',body
            finally:
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=6)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(); raise
                assert proc.returncode==0
                print(log_path.read_text())
        assert 'AddressSanitizer' not in log_path.read_text() and 'runtime error:' not in log_path.read_text()
    print('HTTP/SSE real transport with synthetic CPU fixture: PASS; NOT MODEL INFERENCE')

if __name__=='__main__': main()
