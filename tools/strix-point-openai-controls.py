#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Additional original-weight HTTP gates; no model-quality/performance claim."""
import json
import math
from pathlib import Path
import time
from urllib.parse import urlencode

CONTROL_CHECKS = frozenset({
    'chat_choices_json', 'chat_choices_sse', 'chat_seed_replay',
    'chat_logprobs', 'chat_logprobs_sse', 'chat_bias_positive', 'chat_bias_negative',
    'chat_stop_json', 'chat_stop_sse', 'chat_json_object', 'chat_json_schema',
    'responses_json_object', 'responses_json_schema', 'chat_store_crud', 'responses_background_disconnect',
    'responses_cursor_replay', 'responses_input_pagination',
    'responses_cancel_after_output', 'responses_delete',
    'responses_truncation', 'unsupported_fields',
})


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def probabilities(choice):
    logged = choice.get('logprobs')
    require(isinstance(logged,dict), 'Missing chosen-token logprobs')
    content = logged.get('content')
    require(isinstance(content, list) and content, 'Missing chosen-token logprobs')
    for token in content:
        require(isinstance(token.get('token'), str), 'Missing probability token')
        alternatives = token.get('top_logprobs')
        require(isinstance(alternatives,list), 'Invalid probability alternatives')
        values = [token] + alternatives
        require(1 <= len(values) <= 4, 'Unexpected top-logprob count')
        for value in values:
            require(isinstance(value.get('token'),str), 'Missing probability token')
            p = value.get('logprob')
            b = value.get('bytes')
            require(type(p) in (int, float) and math.isfinite(p) and p <= 1e-6,
                    'Invalid normalized token logprob')
            require(isinstance(b, list) and (b or (value is not token and value['token']=='')) and
                    all(type(x) is int and 0 <= x <= 255 for x in b),
                    'Invalid probability token bytes')
    return content


def chat_stream(chunks, count):
    require(chunks and chunks[-1] == '[DONE]' and chunks.count('[DONE]') == 1,
            'Chat terminal sentinel mismatch')
    text, finishes, usage = {i: '' for i in range(count)}, {}, []
    for chunk in chunks[:-1]:
        require(isinstance(chunk, dict), 'Non-object Chat SSE data')
        if chunk.get('usage') is not None:
            usage.append(chunk['usage'])
        for choice in chunk.get('choices', []):
            i = choice.get('index')
            require(type(i) is int and i in text, 'Unknown Chat choice index')
            require(i not in finishes, 'Chat choice data after its terminal')
            delta = choice.get('delta', {}).get('content')
            require(delta is None or isinstance(delta, str), 'Invalid Chat text delta')
            text[i] += delta or ''
            if choice.get('finish_reason') is not None:
                finishes[i] = choice['finish_reason']
    require(set(finishes) == set(text) and len(usage) == 1,
            'Incomplete choices or duplicate/missing usage')
    return text, finishes, usage[0]


def response_stream(chunks, after=-1):
    require(chunks and all(isinstance(x, dict) for x in chunks),
            'Malformed Responses stream')
    require(all(type(x.get('sequence_number')) is int for x in chunks),
            'Invalid Responses sequence type')
    require([x.get('sequence_number') for x in chunks] ==
            list(range(after+1, after+1+len(chunks))),
            'Responses replay sequence discontinuity')
    terminals = [x for x in chunks if x.get('type') in
                 ('response.completed', 'response.incomplete', 'response.failed')]
    require(len(terminals) == 1 and terminals[0] is chunks[-1] and
            terminals[0]['type'] != 'response.failed', 'Responses terminal mismatch')
    return chunks[-1]['response']


def controls_gate(api, model_id, exchange, events, abandon_stream, root=Path('/work')):
    result = {'schema': 'synapse-lie.point-openai-controls.v1', 'state': 'RUNNING',
              'passed': [], 'witnesses': {}, 'scope': 'Original-weight wire/lifecycle controls, not independent numerical quality'}
    def passed(name, witness=None):
        result['passed'].append(name)
        if witness is not None: result['witnesses'][name] = witness
        save()
    def save():
        (root/'http-controls-result.json').write_text(json.dumps(result, indent=2)+'\n')
    def request(path, body=None, method=None, expected=200):
        row = exchange(api, path, body, method=method)
        require(row['status'] == expected, 'Unexpected HTTP status for '+path+': '+str(row['status']))
        return json.loads(row['body'])
    def chat(**extra):
        body = {'model': model_id, 'messages': [{'role':'user', 'content':'What is 2 + 2? Reply with only the digit.'}],
                'temperature':0, 'max_tokens':16, 'store':False}
        body.update(extra)
        if 'max_completion_tokens' in extra: body.pop('max_tokens')
        return body
    def response(**extra):
        body = {'model':model_id, 'input':'What is 2 + 2? Reply with only the digit.',
                'temperature':0, 'max_output_tokens':16, 'store':False}
        body.update(extra)
        return body
    def poll(identity, predicate, deadline=180):
        end = time.monotonic()+deadline
        while True:
            value = request('/v1/responses/'+identity)
            if predicate(value): return value
            require(value['status'] not in ('completed','incomplete','failed','cancelled'),
                    'Response retired before requested observation')
            require(time.monotonic()<end, 'Response observation deadline')
            time.sleep(.05)
    save()
    try:
        baseline = request('/v1/chat/completions',chat())
        prompt_tokens = baseline['usage']['prompt_tokens']
        choice_witnesses = {}
        for count in (2,8):
            body = chat(n=count)
            value = request('/v1/chat/completions', body)
            choices = value['choices']
            require(len(choices)==count and sorted(x['index'] for x in choices)==list(range(count)),
                    'Multi-choice JSON index mismatch')
            expected = {x['index']:x['message']['content'] for x in choices}
            require(all(isinstance(t,str) and t for t in expected.values()), 'Empty original choices')
            usage = value['usage']
            require(all(type(usage.get(k)) is int and usage[k]>0 for k in
                        ('prompt_tokens','completion_tokens','total_tokens')) and
                    usage['prompt_tokens']==prompt_tokens and
                    usage['total_tokens']==prompt_tokens+usage['completion_tokens'],
                    'Multi-choice usage must count the prompt once and sum the generated tokens')
            choice_witnesses[str(count)] = {'usage':usage,'choices':expected}
            row = exchange(api,'/v1/chat/completions',dict(body,stream=True,stream_options={'include_usage':True}))
            require(row['status']==200, 'Multi-choice SSE refused')
            text, finishes, streamed_usage = chat_stream(events(row['body']),count)
            require(text==expected and streamed_usage==usage and
                    finishes=={x['index']:x['finish_reason'] for x in choices}, 'JSON/SSE multi-choice drift')
        passed('chat_choices_json', choice_witnesses)
        passed('chat_choices_sse', {'counts':[2,8]})

        seeded = chat(messages=[{'role':'user','content':'Name three colors, briefly.'}],
                      temperature=.8,top_p=.8,frequency_penalty=.15,presence_penalty=.2,seed=77)
        first = request('/v1/chat/completions',seeded)
        second = request('/v1/chat/completions',seeded)
        require(first['choices']==second['choices'] and first['usage']==second['usage'], 'Seeded same-mode replay drift')
        passed('chat_seed_replay', {'choices':first['choices'],'usage':first['usage']})

        logged = chat(messages=[{'role':'user','content':'Repeat exactly: alpha beta gamma.'}],
                      max_tokens=32,logprobs=True,top_logprobs=3)
        value = request('/v1/chat/completions',logged)
        choice = value['choices'][0]
        tokens = probabilities(choice)
        require(len(tokens)>=2 and all(len(t['top_logprobs'])==3 for t in tokens), 'Insufficient probability alternatives')
        passed('chat_logprobs', {'chosen_tokens':len(tokens),'usage':value['usage']})
        row = exchange(api,'/v1/chat/completions',dict(logged,stream=True,stream_options={'include_usage':True}))
        require(row['status']==200, 'Probability SSE refused')
        chunks = events(row['body']); text, finishes, usage = chat_stream(chunks,1)
        streamed_tokens = [token for chunk in chunks[:-1] for item in chunk.get('choices',[])
                           for token in (item.get('logprobs') or {}).get('content',[])]
        require(text=={0:choice['message']['content']} and usage==value['usage'] and streamed_tokens==tokens,
                'Probability JSON/SSE drift')
        probabilities({'logprobs':{'content':streamed_tokens}})
        passed('chat_logprobs_sse')
        # Qualification is deliberately Qwen-specific: original digit IDs are
        # independently witnessed by positive and negative bias behavior.
        positive = request('/v1/chat/completions',chat(
            messages=[{'role':'user','content':'Reply with the word elephant.'}],
            max_completion_tokens=1,logit_bias={'19':100}))
        require(positive['choices'][0]['message']['content']=='4' and
                positive['usage']['completion_tokens']==1, 'Qwen positive digit bias did not force token 19')
        passed('chat_bias_positive', {'token_id':19,'text':'4'})
        negative = request('/v1/chat/completions',chat(max_tokens=1,logit_bias={'19':-100}))
        require(negative['choices'][0]['message']['content']!='4', 'Negative digit bias ignored')
        passed('chat_bias_negative', {'text':negative['choices'][0]['message']['content']})

        prefix, stop, pieces = bytearray(), None, 0
        for pieces, item in enumerate(tokens,1):
            prefix.extend(item['bytes'])
            if len(prefix)>256: break
            if pieces<2: continue
            try: stop=prefix.decode('utf-8')
            except UnicodeDecodeError: continue
            break
        require(stop and stop in choice['message']['content'] and len(stop.encode())<=256,
                'No valid cross-token stop witness')
        stopped = dict(logged,stop=[stop])
        value = request('/v1/chat/completions',stopped)
        expected_text = choice['message']['content'].split(stop,1)[0]
        require(value['choices'][0]['finish_reason']=='stop' and
                value['choices'][0]['message']['content']==expected_text, 'Cross-token stop JSON mismatch')
        passed('chat_stop_json', {'stop':stop,'removed_token_pieces':pieces,'usage':value['usage']})
        row = exchange(api,'/v1/chat/completions',dict(stopped,stream=True,stream_options={'include_usage':True}))
        require(row['status']==200, 'Stop SSE refused')
        text, finishes, usage = chat_stream(events(row['body']),1)
        require(text=={0:expected_text} and finishes=={0:'stop'} and usage==value['usage'], 'Stop JSON/SSE drift')
        passed('chat_stop_sse')

        literal = 'Return only a JSON object containing answer equal to 4.'
        value = request('/v1/chat/completions',chat(
            messages=[{'role':'user','content':literal}],max_tokens=64,response_format={'type':'json_object'}))
        require(isinstance(json.loads(value['choices'][0]['message']['content']),dict) and
                value['choices'][0]['finish_reason']=='stop', 'Chat JSON object incomplete/invalid')
        passed('chat_json_object')
        value = request('/v1/responses',response(input=literal,max_output_tokens=64,text={'format':{'type':'json_object'}}))
        output = ''.join(part['text'] for item in value['output'] if item['type']=='message'
                         for part in item['content'] if part['type']=='output_text')
        require(value['status']=='completed' and isinstance(json.loads(output),dict), 'Responses JSON object incomplete/invalid')
        passed('responses_json_object')

        schema = {'type':'object','properties':{'answer':{'type':'integer','enum':[4]}},
                  'required':['answer'],'additionalProperties':False}
        fmt = {'type':'json_schema','name':'answer','strict':True,'schema':schema}
        value = request('/v1/chat/completions',chat(max_tokens=64,response_format={
            'type':'json_schema','json_schema':{k:v for k,v in fmt.items() if k!='type'}}))
        require(json.loads(value['choices'][0]['message']['content'])=={'answer':4} and
                value['choices'][0]['finish_reason']=='stop', 'Chat strict schema incomplete/invalid')
        passed('chat_json_schema')
        value = request('/v1/responses',response(max_output_tokens=64,text={'format':fmt}))
        output = ''.join(part['text'] for item in value['output'] if item['type']=='message'
                         for part in item['content'] if part['type']=='output_text')
        require(value['status']=='completed' and json.loads(output)=={'answer':4}, 'Responses strict schema incomplete/invalid')
        passed('responses_json_schema')

        tag = 'openai-controls-original'
        value = request('/v1/chat/completions',chat(store=True,metadata={'qualification':tag}))
        identity = value['id']; path = '/v1/chat/completions/'+identity
        require(request(path)['choices']==value['choices'], 'Stored Chat changed')
        listing = request('/v1/chat/completions?'+urlencode({'model':model_id,'metadata[qualification]':tag,'limit':1}))
        require(any(x['id']==identity for x in listing['data']), 'Filtered Chat list omitted its record')
        messages = request(path+'/messages?limit=1&order=asc')
        require(messages['data'], 'Stored Chat message page empty')
        require(request(path,{'metadata':{'qualification':tag,'checked':'yes'}})['metadata']['checked']=='yes', 'Chat metadata update lost')
        require(request(path,method='DELETE')['deleted'] is True, 'Chat delete failed')
        request(path,expected=404)
        passed('chat_store_crud')

        background = response(input='Count from 1 to 100 in order, separated by commas.',
                              background=True,store=True,stream=True,max_output_tokens=64)
        abandoned = abandon_stream(api,background)
        final = poll(abandoned['id'],lambda x:x['status'] in ('completed','incomplete'))
        require(final['usage']['output_tokens']>1, 'Background output did not continue after disconnect')
        passed('responses_background_disconnect', {'id':final['id'],'status':final['status'],'usage':final['usage']})
        path = '/v1/responses/'+final['id']
        row = exchange(api,path+'?stream=true')
        require(row['status']==200, 'Background stream replay refused')
        full = events(row['body']); replayed = response_stream(full)
        require(replayed==final, 'Replay terminal differs from retained response')
        cursor = abandoned['sequence_number']
        row = exchange(api,path+'?stream=true&starting_after='+str(cursor))
        require(row['status']==200, 'Cursor replay refused')
        suffix = events(row['body']); response_stream(suffix,cursor)
        require(suffix==[x for x in full if x['sequence_number']>cursor], 'Cursor replay differs from original suffix')
        passed('responses_cursor_replay', {'after':cursor,'events':len(suffix)})
        page = request(path+'/input_items?limit=1&order=asc')
        require(page['data'] and len(page['data'])==1, 'Responses input page invalid')
        passed('responses_input_pagination')

        value = abandon_stream(api,response(input='Count from 1 to 1000 in order, separated by commas.',
                                            background=True,store=True,stream=True,max_output_tokens=1024))
        active = request('/v1/responses/'+value['id'])
        require(active['status']=='in_progress', 'Background retired before post-output cancellation')
        cancelled = request('/v1/responses/'+value['id']+'/cancel',{})
        require(cancelled['status']=='cancelled', 'Background cancel did not retire')
        again = request('/v1/responses/'+value['id']+'/cancel',{})
        require(again['status']=='cancelled', 'Repeated cancel not idempotent')
        passed('responses_cancel_after_output', {'confirmed_delta_sequence':value['sequence_number'],
                                                'confirmed_delta_bytes':value['delta_bytes'],
                                                'status':cancelled['status']})
        require(request(path,method='DELETE')['deleted'] is True, 'Responses delete failed')
        request(path,expected=404)
        request('/v1/responses/'+value['id'],method='DELETE')
        passed('responses_delete')

        history = [{'role':'user','content':' '.join('record%05d_key_%05d'%(i,i) for i in range(10000))},
                   {'role':'assistant','content':'Previous records received.'},
                   {'role':'user','content':'What is 2 + 2? Reply with only the digit.'}]
        refused = request('/v1/responses',response(input=history,truncation='disabled'),expected=400)
        require('error' in refused, 'Overflow did not return an API error')
        value = request('/v1/responses',response(input=history,truncation='auto'))
        require(value['status']=='completed' and 0<value['usage']['input_tokens']<16384-16,
                'Automatic truncation failed admission')
        passed('responses_truncation', {'admitted_input_tokens':value['usage']['input_tokens']})
        for path,body in [('/v1/chat/completions',chat(audio={'voice':'alloy','format':'wav'})),
                          ('/v1/responses',response(tools=[{'type':'web_search'}]))]:
            require('error' in request(path,body,expected=400), 'Unsupported field silently ignored')
        passed('unsupported_fields')
        require(set(result['passed'])==CONTROL_CHECKS, 'Incomplete declared OpenAI control set')
        result['state']='PASSED'
    except BaseException as exc:
        result.update(state='FAILED',error=repr(exc))
        raise
    finally:
        save()
    return result
