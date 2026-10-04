# SPDX-License-Identifier: MIT
"""Offline protocol/error fixtures. NOT-INFERENCE; no sockets, models or GPU."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
controls = module('controls',ROOT/'tools/strix-point-openai-controls.py')
wire = module('wire',ROOT/'tools/strix-point-http-gate.py')
point = module('point',ROOT/'tools/strix-point-campaign.py')

def token(text):
    return {'token':text,'bytes':list(text.encode()),'logprob':-1,
            'top_logprobs':[{'token':x,'bytes':list(x.encode()),'logprob':-i-1}
                            for i,x in enumerate((text,'different','other'))]}

def sse(rows):
    return ''.join('data: '+('[DONE]' if x=='[DONE]' else json.dumps(x))+'\n\n' for x in rows)

class ProtocolFixture:
    """Independent canned wire projections and state; never inference evidence."""
    def __init__(self):
        self.chat = {}; self.responses = {}; self.streams = {}; self.calls = []
    def exchange(self,api,path,payload=None,method=None):
        verb = method or ('GET' if payload is None else 'POST')
        self.calls.append((verb,path,copy.deepcopy(payload)))
        route = urlsplit(path); query=parse_qs(route.query)
        status = 200
        if verb=='DELETE':
            identity=route.path.rsplit('/',1)[-1]
            data={'deleted':True}; self.chat.pop(identity,None); self.responses.pop(identity,None)
        elif route.path.startswith('/v1/chat/completions/cpu-chat'):
            value=self.chat.get('cpu-chat')
            if value is None: status,data=404,{'error':{'message':'missing'}}
            elif route.path.endswith('/messages'): data={'data':[{'role':'user','content':'fixture'}]}
            elif payload is not None:
                value['metadata']=payload['metadata']; data=value
            else: data=value
        elif verb=='GET' and route.path=='/v1/chat/completions':
            assert query['metadata[qualification]']==['openai-controls-original']
            data={'data':list(self.chat.values())}
        elif verb=='POST' and route.path=='/v1/chat/completions':
            if 'audio' in payload: status,data=400,{'error':{'message':'unsupported audio'}}
            else:
                text='4'; logged=None
                if 'logit_bias' in payload:
                    text='4' if payload['logit_bias']['19']>0 else '5'
                    assert ('max_tokens' in payload) != ('max_completion_tokens' in payload)
                elif payload['messages'][0]['content'].startswith('Name'): text='red, green, blue'
                elif payload.get('logprobs'):
                    text='alpha beta gamma.'
                    logged={'content':[token(x) for x in ('alpha',' beta',' gamma.')]}
                    if 'stop' in payload:
                        assert payload['stop']==['alpha beta']; text=''; logged={'content':[]}
                elif 'response_format' in payload:
                    fmt=payload['response_format']
                    if fmt['type']=='json_schema':
                        assert set(fmt['json_schema'])=={'name','strict','schema'}
                    text='{"answer":4}'
                n=payload.get('n',1)
                choices=[{'index':i,'message':{'role':'assistant','content':text},
                          'finish_reason':'stop','logprobs':logged} for i in range(n)]
                generated=max(1,len(text.split()))*n
                usage={'prompt_tokens':10,'completion_tokens':generated,'total_tokens':10+generated}
                data={'id':'cpu-chat','object':'chat.completion','choices':choices,'usage':usage,'metadata':payload.get('metadata',{})}
                if payload.get('store'): self.chat['cpu-chat']=copy.deepcopy(data)
                if payload.get('stream'):
                    chunks=[{'choices':[{'index':c['index'],'delta':{'content':text},'finish_reason':'stop','logprobs':logged}]} for c in choices]
                    chunks += [{'choices':[],'usage':usage},'[DONE]']
                    return {'status':200,'body':sse(chunks)}
        elif route.path=='/v1/responses' and verb=='POST':
            if payload.get('tools'): status,data=400,{'error':{'message':'hosted tools unsupported'}}
            elif isinstance(payload['input'],list) and payload['truncation']=='disabled':
                status,data=400,{'error':{'message':'context overflow'}}
            else:
                text='{"answer":4}' if 'text' in payload else '4'
                data={'id':'cpu-response','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}],
                      'usage':{'input_tokens':10,'output_tokens':3,'total_tokens':13}}
        elif route.path.endswith('/cancel'):
            identity=route.path.split('/')[-2]; self.responses[identity]['status']='cancelled'; data=self.responses[identity]
        elif route.path.endswith('/input_items'): data={'data':[{'type':'message','role':'user'}]}
        else:
            identity=route.path.split('/')[-1]
            if identity not in self.responses: status,data=404,{'error':{'message':'missing'}}
            elif query.get('stream')==['true']:
                after=int(query.get('starting_after',[-1])[0])
                return {'status':200,'body':sse([x for x in self.streams[identity] if x['sequence_number']>after])}
            else: data=self.responses[identity]
        return {'status':status,'body':json.dumps(data)}
    def abandon(self,api,payload):
        identity='cpu-background-'+str(len(self.responses))
        cancel=payload['max_output_tokens']==1024
        value={'id':identity,'status':'in_progress' if cancel else 'completed','output':[],
               'usage':None if cancel else {'output_tokens':3,'input_tokens':10,'total_tokens':13}}
        self.responses[identity]=value
        self.streams[identity]=[
            {'type':'response.created','sequence_number':0,'response':{'id':identity}},
            {'type':'response.output_text.delta','sequence_number':1,'delta':'1'},
            {'type':'response.output_text.delta','sequence_number':2,'delta':',2'},
            {'type':'response.completed','sequence_number':3,'response':copy.deepcopy(value)}]
        return {'id':identity,'sequence_number':1,'delta_bytes':1}

class Tests(unittest.TestCase):
    def test_control_names_match_supervisor_acceptance(self):
        self.assertEqual(controls.CONTROL_CHECKS,point.HTTP_CONTROL_CHECKS)
        self.assertEqual(len(controls.CONTROL_CHECKS),21)
    def test_probability_validation_refuses_invalid_wire_numbers_and_bytes(self):
        good={'logprobs':{'content':[token('alpha')]}}
        controls.probabilities(good)
        special=copy.deepcopy(good)
        special['logprobs']['content'][0]['top_logprobs'][0]={'token':'','bytes':[],'logprob':-2}
        controls.probabilities(special)  # A special alternative is not published text.
        for p in (True,float('nan'),float('inf'),.1):
            bad=copy.deepcopy(good); bad['logprobs']['content'][0]['logprob']=p
            with self.subTest(p=p), self.assertRaises(RuntimeError): controls.probabilities(bad)
        for b in ([],[256],[True],None):
            bad=copy.deepcopy(good); bad['logprobs']['content'][0]['bytes']=b
            with self.subTest(b=b), self.assertRaises(RuntimeError): controls.probabilities(bad)
        with self.assertRaises(RuntimeError): controls.probabilities({'logprobs':None})
    def test_chat_stream_refuses_partial_duplicate_and_wrong_choice_terminals(self):
        good=[{'choices':[{'index':0,'delta':{'content':'4'},'finish_reason':'stop'}]},
              {'choices':[],'usage':{'completion_tokens':1}},'[DONE]']
        self.assertEqual(controls.chat_stream(good,1)[0],{0:'4'})
        for bad in (good[:-1],good+['[DONE]'],good[:1]+good,
                    [{'choices':[{'index':1,'delta':{},'finish_reason':'stop'}]}]+good[1:]):
            with self.assertRaises(RuntimeError): controls.chat_stream(bad,1)
    def test_response_cursor_requires_typed_contiguous_suffix_and_one_terminal(self):
        good=[{'type':'response.output_text.delta','sequence_number':2,'delta':'4'},
              {'type':'response.completed','sequence_number':3,'response':{'id':'fixture'}}]
        self.assertEqual(controls.response_stream(good,1)['id'],'fixture')
        for key,value in [('sequence_number',True),('sequence_number',4),('type','response.failed')]:
            bad=copy.deepcopy(good); bad[-1][key]=value
            with self.subTest(key=key,value=value), self.assertRaises(RuntimeError): controls.response_stream(bad,1)
    def test_all_offline_controls_complete_with_live_usage_null_and_exact_replay(self):
        fixture=ProtocolFixture()
        with tempfile.TemporaryDirectory() as temp:
            checked=controls.controls_gate(1,'CPU-NOT-INFERENCE',fixture.exchange,wire.events,fixture.abandon,Path(temp))
            self.assertEqual(set(checked['passed']),controls.CONTROL_CHECKS)
            self.assertEqual(checked['state'],'PASSED')
            self.assertEqual(json.loads((Path(temp)/'http-controls-result.json').read_text())['state'],'PASSED')
            self.assertEqual(fixture.chat,{})
            self.assertEqual(fixture.responses,{})
            self.assertEqual(checked['witnesses']['chat_choices_sse']['counts'],[2,8])
            for count in ('2','8'):
                usage=checked['witnesses']['chat_choices_json'][count]['usage']
                self.assertEqual(usage['prompt_tokens'],10)
                self.assertEqual(usage['total_tokens'],10+int(count))
    def test_multi_choice_rejects_usage_that_counts_the_prompt_for_each_choice(self):
        fixture=ProtocolFixture(); original=fixture.exchange
        def wrong(*args,**kwargs):
            row=original(*args,**kwargs)
            if args[1]=='/v1/chat/completions' and args[2] and args[2].get('n'):
                body=json.loads(row['body']); usage=body['usage']
                usage['prompt_tokens']*=args[2]['n']
                usage['total_tokens']=usage['prompt_tokens']+usage['completion_tokens']
                row['body']=json.dumps(body)
            return row
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,'count the prompt once'):
                controls.controls_gate(1,'CPU-NOT-INFERENCE',wrong,wire.events,fixture.abandon,Path(temp))
            checked=json.loads((Path(temp)/'http-controls-result.json').read_text())
            self.assertEqual(checked['state'],'FAILED')
            self.assertEqual(checked['passed'],[])
    def test_failed_controls_preserve_partial_witness_and_never_claim_pass(self):
        fixture=ProtocolFixture(); original=fixture.exchange
        def wrong(*args,**kwargs):
            row=original(*args,**kwargs)
            if args[1]=='/v1/chat/completions' and args[2] and args[2].get('logprobs') and not args[2].get('stream'):
                body=json.loads(row['body']); body['choices'][0]['logprobs']['content'][0]['logprob']=float('nan'); row['body']=json.dumps(body)
            return row
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):
                controls.controls_gate(1,'CPU-NOT-INFERENCE',wrong,wire.events,fixture.abandon,Path(temp))
            checked=json.loads((Path(temp)/'http-controls-result.json').read_text())
            self.assertEqual(checked['state'],'FAILED')
            self.assertIn('chat_seed_replay',checked['passed'])
            self.assertNotIn('chat_logprobs',checked['passed'])
    def test_abandon_closes_only_owned_connection_after_actual_delta(self):
        class Response(io.BytesIO): status=200
        response=Response(sse([{'type':'response.created','sequence_number':0,'response':{'id':'fixture'}},
                               {'type':'response.output_text.delta','sequence_number':1,'delta':'4'}]).encode())
        class Connection:
            closed=False
            def request(self,*args): pass
            def getresponse(self): return response
            def close(self): self.closed=True
        connection=Connection()
        with tempfile.TemporaryDirectory() as temp, patch.object(wire,'ROOT',Path(temp)), \
             patch.object(wire.http.client,'HTTPConnection',return_value=connection):
            self.assertEqual(wire.abandon_response_stream(1,{}),{'id':'fixture','sequence_number':1,'delta_bytes':1})
            self.assertTrue(connection.closed)
            self.assertTrue(json.loads((Path(temp)/'http-wire.jsonl').read_text())['abandoned_after_delta'])

if __name__=='__main__': unittest.main()
