#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Responses protocol through the real reactive C pipeline; synthetic tokens only."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from test_tools_http import exchange, port, TOOLS


def events(body):
    result=[]
    for frame in body.strip().split('\n\n'):
        lines=frame.splitlines()
        assert len(lines)==2 and lines[0].startswith('event: ') and lines[1].startswith('data: '), frame
        item=json.loads(lines[1][6:])
        assert item['type']==lines[0][7:]
        assert item['sequence_number']==len(result)
        result.append(item)
    assert '[DONE]' not in body
    return result


def main():
    a,m=port(),port()
    while a==m: m=port()
    with tempfile.TemporaryDirectory(prefix='lie-responses-') as d:
        with (Path(d)/'server.log').open('wb') as log:
            p=subprocess.Popen([sys.argv[1],'--model',':fixture:','--port',str(a),'--management-port',str(m),'--context','8192'],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+5
                while True:
                    assert p.poll() is None
                    try:
                        if exchange(m,'/actuator/health/readiness')[0]==200: break
                    except OSError: pass
                    assert time.monotonic()<deadline
                    time.sleep(.01)
                base={'model':'cpu-test-fixture','input':'hello','max_output_tokens':32,'store':False}
                code,body=exchange(a,'/v1/responses',base)
                assert code==200,body
                full=json.loads(body)
                assert full['object']=='response' and full['status']=='completed',full
                text=full['output'][0]['content'][0]['text']
                assert text and full['usage']['output_tokens']>0
                code,body=exchange(a,'/v1/responses',dict(base,stream=True))
                assert code==200,body
                ev=events(body)
                assert ev[0]['type']=='response.created' and ev[-1]['type']=='response.completed'
                assert ev[2]['item']['content']==[]
                assert ''.join(x['delta'] for x in ev if x['type']=='response.output_text.delta')==text
                assert ev[-1]['response']['output'][0]['content'][0]['text']==text
                q=dict(base,max_output_tokens=1)
                code,body=exchange(a,'/v1/responses',q)
                assert code==200 and json.loads(body)['status']=='incomplete',body
                flat=[dict(type='function',**t['function']) for t in TOOLS]
                q=dict(base,input='TOOL',tools=flat,max_output_tokens=512)
                code,body=exchange(a,'/v1/responses',q)
                assert code==200,body
                full=json.loads(body); call=full['output'][1]
                assert call['type']=='function_call' and call['name']=='read'
                assert json.loads(call['arguments'])['path']=='  caffè 🙂.txt  '
                code,body=exchange(a,'/v1/responses',dict(q,stream=True))
                assert code==200,body
                ev=events(body)
                assert ev[-1]['response']['output'][1]['type']=='function_call'
                assert any(x['type']=='response.function_call_arguments.done' for x in ev)
                follow=dict(q,input=[{'role':'user','content':'TOOL-FOLLOW'},call,{'type':'function_call_output','call_id':call['call_id'],'output':'TOOL-RESULT'}])
                code,body=exchange(a,'/v1/responses',follow)
                assert code==200,body
                assert json.loads(body)['output'][0]['content'][0]['text']=='Tool result received.'
                code,body=exchange(a,'/v1/responses',dict(q,input='TOOL-UNKNOWN',stream=True))
                assert code==200 and events(body)[-1]['type']=='response.failed',body
                # Worst-case JSON escaping: 4096 confirmed 256-byte tokens.
                # Done events repeat the final projection; each write stays bounded.
                code,body=exchange(a,'/v1/responses',dict(base,input='CONTROL',stream=True,max_output_tokens=4096))
                assert code==200,code
                ev=events(body)
                assert ev[-1]['type']=='response.incomplete'
                assert ev[-1]['response']['output'][0]['content'][0]['text']=='\x01'*(4096*256)
                assert ev[-1]['response']['usage']['output_tokens']==4096
                for extra in ({'store':True},{'background':True},{'previous_response_id':'resp_x'},{'input':[{'role':'user','content':[{'type':'input_image','image_url':'x'}]}]}):
                    code,body=exchange(a,'/v1/responses',dict(base,**extra))
                    assert code==400,body
            finally:
                p.terminate()
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired: p.kill(); p.wait()
            assert p.returncode==0,Path(d,'server.log').read_text()

if __name__=='__main__': main()
