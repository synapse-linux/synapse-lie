# SPDX-License-Identifier: MIT
"""Bounded HTTP lifecycle checks, called ONLY by an admitted supervisor or CPU test.
Not a benchmark, GPU admission mechanism, numerical oracle or standalone runner.
"""
import http.client
import json
import math
import socket
import time

LIMIT = 1024 * 1024
SCHEMA = 'synapse-lie.serving-checks.v1'


class Inconclusive(RuntimeError):
    """A required dispatch/pressure window was not demonstrated; never a PASS."""


def original_profile():
    return {
        'peer': 'What is 2 + 2? Reply with only the digit, without punctuation or explanation.',
        'peer_expected': '4',
        'prefill': ('Reference material follows.\n' +
                    'The quick brown fox jumps over the lazy dog.\n' * 240 +
                    '\nList the integers from 1 to 10000, one per line. Start at 1.'),
        'decode': 'List the integers from 1 to 10000, one integer per line. Start immediately at 1 and continue. Do not add an introduction, summary or code fence.',
        'blocked': 'List the integers from 1 to 10000, one integer per line. Start immediately at 1 and continue. Do not add an introduction, summary or code fence.',
    }


def validate_scheduler(s):
    e = s['executor']
    if (e['scope'] != 'owner_dispatch_intervals' or e['phase'] not in ('none', 'prefill', 'decode') or
            s['mode'] != 'single-owner-interleaved-single-row' or s['max_active'] != 2):
        raise ValueError('unexpected scheduler configuration')
    for key in ('active', 'queued', 'output_blocked', 'completed', 'cancelled', 'failed', 'generated_tokens'):
        if type(s[key]) is not int or s[key] < 0:
            raise ValueError('invalid scheduler counter: ' + key)
    if not 0 <= s['output_blocked'] <= s['active'] <= 2 or s['active'] + s['queued'] > 8:
        raise ValueError('invalid scheduler occupancy')
    for key in ('prefill_started', 'prefill_returned', 'decode_started', 'decode_returned',
                'cancel_during_prefill', 'cancel_during_decode'):
        if type(e[key]) is not int or e[key] < 0:
            raise ValueError('invalid executor counter: ' + key)
    for phase in ('prefill', 'decode'):
        if e[phase + '_started'] - e[phase + '_returned'] != (e['phase'] == phase):
            raise ValueError('invalid executor dispatch balance')
    return s


def validate_timings(u, t):
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        if type(u[key]) is not int or u[key] < 0:
            raise ValueError('invalid usage count')
    if u['total_tokens'] != u['prompt_tokens'] + u['completion_tokens']:
        raise ValueError('usage sum mismatch')
    if t['schema'] != 'synapse-lie.request-timings.v1' or t['scope'] != 'synchronous_executor_calls' or t['valid'] is not True:
        raise ValueError('request timings unavailable/incompatible')
    if t['prefill_tokens'] != u['prompt_tokens'] or t['decode_tokens'] != u['completion_tokens']:
        raise ValueError('physical timing/usage mismatch (fresh sessions required)')
    for phase in ('prefill', 'decode'):
        for suffix in ('_tokens', '_calls'):
            if type(t[phase + suffix]) is not int or t[phase + suffix] < 0:
                raise ValueError('invalid timing count')
        ms, rate = t[phase + '_ms'], t[phase + '_tokens_per_second']
        if type(ms) not in (int, float) or not math.isfinite(ms) or ms <= 0:
            raise ValueError('positive completed-call time required')
        expected = t[phase + '_tokens'] * 1000 / ms
        if type(rate) not in (int, float) or not math.isfinite(rate) or not math.isclose(rate, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError('timing rate mismatch')
    if not t['prefill_calls'] or t['decode_calls'] not in (u['completion_tokens'], u['completion_tokens'] + 1):
        raise ValueError('invalid completed-call count')


def validate_completion(obj, provider):
    if obj.get('system_fingerprint') != provider or obj.get('object') != 'chat.completion':
        raise ValueError('completion provider/type mismatch')
    if len(obj['choices']) != 1 or obj['choices'][0]['finish_reason'] not in ('stop', 'length'):
        raise ValueError('invalid completion outcome')
    u = obj['usage']; validate_timings(u, obj['lie_timings'])
    message = obj['choices'][0]['message']
    if message['role'] != 'assistant' or not isinstance(message['content'], str):
        raise ValueError('invalid assistant message')
    return {'content': message['content'], 'usage': u, 'finish': obj['choices'][0]['finish_reason']}


def run(api_port, management_port, model, provider, record, check, profile=None):
    """Loopback only. Caller owns lease/server/timeout/identity, not this client.
    Record callback must retain every event. No retry of a model request. Polling
    reads management only. Failed/missed windows retain their evidence and fail.
    """
    profile = original_profile() if profile is None else profile
    if not all(type(p) is int and 1 <= p <= 65535 for p in (api_port, management_port)) or api_port == management_port:
        raise ValueError('invalid loopback ports')
    sockets = []
    def event(kind, **data):
        record({'event': kind, 'monotonic': time.monotonic(), **data})
    def payload(text, stream, budget):
        obj = {'model': model, 'messages': [{'role': 'user', 'content': text}], 'temperature': 0,
               'max_tokens': budget, 'stream': stream, 'chat_template_kwargs': {'enable_thinking': False}}
        if stream:
            obj['stream_options'] = {'include_usage': True}
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        if len(body) > 65536:
            raise ValueError('request body bound')
        return body
    def get_json(port, path, body=None):
        check()
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        try:
            c.request('GET' if body is None else 'POST', path, body, {} if body is None else {'Content-Type': 'application/json'})
            r = c.getresponse(); raw = r.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError('response bound')
            obj = json.loads(raw)
            event('http', path=path, status=r.status, body=obj)
            if r.status != 200:
                raise RuntimeError('HTTP check failed: ' + str(r.status))
            return obj
        finally:
            c.close()
    def state():
        obj = get_json(management_port, '/actuator/llm')
        if obj.get('ready') is not True or obj['backend']['engine'] != provider:
            raise RuntimeError('backend unavailable/identity drift')
        return validate_scheduler(obj['scheduler'])
    def poll(predicate, description, seconds=30):
        deadline = time.monotonic() + seconds
        while True:
            s = state()
            if predicate(s):
                return s
            if time.monotonic() >= deadline:
                raise Inconclusive(description + ': required window not observed')
            time.sleep(.02)
    def quiescent(s):
        return s['active'] == s['queued'] == s['output_blocked'] == 0 and s['executor']['phase'] == 'none'
    def peer():
        obj = get_json(api_port, '/v1/chat/completions', payload(profile['peer'], False, 16))
        value = validate_completion(obj, provider)
        if value['content'].strip() != profile['peer_expected'] or not 0 < value['usage']['completion_tokens'] <= 16:
            raise RuntimeError('predeclared peer output mismatch')
        return value
    def stream(text):
        check(); c = http.client.HTTPConnection('127.0.0.1', api_port, timeout=10); sockets.append(c)
        c.request('POST', '/v1/chat/completions', payload(text, True, 512), {'Content-Type': 'application/json'})
        r = c.getresponse(); sockets.append(r)
        event('stream_headers', status=r.status, headers=dict(r.getheaders()))
        if r.status != 200 or 'text/event-stream' not in r.getheader('Content-Type', ''):
            raise RuntimeError('stream admission failed')
        return c, r
    def close_stream(c, r):
        r.close(); sockets.remove(r); c.close(); sockets.remove(c)
    def first_content(r):
        used = 0
        while used <= LIMIT:
            check(); line = r.readline(16385); used += len(line)
            if not line or len(line) > 16384:
                raise RuntimeError('invalid/bounded stream before cancellation')
            if line == b'\n':
                continue
            if not line.startswith(b'data: ') or line.strip() == b'data: [DONE]':
                raise Inconclusive('decode ended before cancellation window')
            obj = json.loads(line[6:]); event('stream_frame', body=obj)
            if obj.get('system_fingerprint') != provider or 'error' in obj:
                raise RuntimeError('stream provider/error mismatch')
            for choice in obj['choices']:
                if choice.get('finish_reason') is not None:
                    raise Inconclusive('decode ended before cancellation window')
                if choice.get('delta', {}).get('content'):
                    return
        raise ValueError('stream response bound')
    try:
        event('begin', schema=SCHEMA, profile=profile)
        initial = state()
        if not quiescent(initial):
            raise RuntimeError('isolated quiescent server required')
        reference = peer()
        poll(lambda s: quiescent(s) and s['completed'] == initial['completed'] + 1, 'baseline retirement')
        for phase in ('prefill', 'decode'):
            before = state(); event('case_begin', case=phase + '_cancel')
            c, r = stream(profile[phase])
            if phase == 'decode':
                first_content(r)
            def dispatch(s):
                if s['failed'] != before['failed'] or s['cancelled'] != before['cancelled']:
                    raise RuntimeError('unexpected failure/cancellation before client cancellation')
                if s['completed'] != before['completed']:
                    raise Inconclusive(phase + ' request completed before dispatch cancellation window')
                return (s['executor']['phase'] == phase and
                        s['executor'][phase + '_started'] > before['executor'][phase + '_started'])
            poll(dispatch, phase + ' dispatch')
            close_stream(c, r)
            after = poll(lambda s: quiescent(s) and s['cancelled'] == before['cancelled'] + 1, phase + ' cancellation retirement')
            if (after['completed'] != before['completed'] or after['failed'] != before['failed'] or
                    after['executor']['cancel_during_' + phase] != before['executor']['cancel_during_' + phase] + 1):
                raise Inconclusive(phase + ' cancellation did not demonstrate the dispatch interval')
            event('case_pass', case=phase + '_cancel', before=before, after=after)
        before = state(); event('case_begin', case='backpressure_and_peer')
        held = socket.socket(); sockets.append(held)
        held.settimeout(10); held.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        held.connect(('127.0.0.1', api_port)); body = payload(profile['blocked'], True, 512)
        held.sendall(f'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body)
        # No recv: a real TCP window stall, not a synthetic server switch.
        blocked = poll(lambda s: s['output_blocked'] == 1 and s['executor']['phase'] == 'none', 'output backpressure')
        if not 0 < blocked['generated_tokens'] - before['generated_tokens'] < 512:
            raise Inconclusive('long request did not reach pressure before completion')
        for _ in range(5):
            time.sleep(.1); s = state()
            if (s['output_blocked'] != 1 or s['generated_tokens'] != blocked['generated_tokens'] or
                    s['executor']['decode_started'] != blocked['executor']['decode_started']):
                raise Inconclusive('no sustained decode admission stall')
        if peer() != reference:
            raise RuntimeError('interleaved peer differs from fresh reference')
        poll(lambda s: s['completed'] == before['completed'] + 1 and s['active'] == 1 and s['output_blocked'] == 1,
             'peer retirement with stalled client')
        held.close(); sockets.remove(held)
        after = poll(lambda s: quiescent(s) and s['cancelled'] == before['cancelled'] + 1, 'stalled client retirement')
        event('case_pass', case='backpressure_and_peer', before=before, after=after)
        if peer() != reference:
            raise RuntimeError('post-cancellation recovery differs from fresh reference')
        final = poll(lambda s: quiescent(s) and s['completed'] == initial['completed'] + 3, 'final retirement')
        if final['cancelled'] != initial['cancelled'] + 3 or final['failed'] != initial['failed']:
            raise RuntimeError('unexpected request accounting / foreign request')
        result = {'schema': SCHEMA, 'state': 'HTTP_LIFECYCLE_PASS_NOT_NUMERICAL_OR_PERFORMANCE_QUALIFICATION',
                  'provider': provider, 'synthetic': 'NOT-INFERENCE' in provider, 'initial': initial, 'final': final,
                  'native_batching': False, 'gpu_kernel_preemption_proved': False}
        event('complete', result=result); return result
    except BaseException as ex:
        event('failed', outcome='INCONCLUSIVE' if isinstance(ex, Inconclusive) else 'FAILED', error=repr(ex))
        raise
    finally:
        for s in reversed(sockets):
            s.close()


def run_openai(api_port, management_port, model, record, check):
    """Additional original-weight API cases; caller already owns GPU admission.
    Protocol, seeded sampling and a native function round trip, not benchmarks.
    """
    def exchange(path, body):
        check()
        c=http.client.HTTPConnection('127.0.0.1',api_port,timeout=120)
        try:
            c.request('POST',path,json.dumps(body),{'Content-Type':'application/json'})
            r=c.getresponse(); text=r.read().decode('utf-8')
            record({'case':'openai','path':path,'request':body,'status':r.status,'body':text})
            if r.status!=200: raise RuntimeError('OpenAI case refused: '+text)
            return text
        finally: c.close()
    q={'model':model,'input':'Reply with exactly READY and nothing else.','max_output_tokens':32,'store':False}
    full=json.loads(exchange('/v1/responses',q))
    if full['status']!='completed' or full['output'][0]['content'][0]['text'].strip()!='READY':
        raise RuntimeError('Responses original-weight content mismatch')
    stream=exchange('/v1/responses',dict(q,stream=True))
    events=[]
    for frame in stream.strip().split('\n\n'):
        rows=frame.splitlines(); item=json.loads(rows[1][6:])
        if rows[0]!='event: '+item['type'] or item['sequence_number']!=len(events): raise RuntimeError('Responses SSE ordering')
        events.append(item)
    text=''.join(i['delta'] for i in events if i['type']=='response.output_text.delta')
    if text.strip()!='READY' or events[-1]['type']!='response.completed' or '[DONE]' in stream:
        raise RuntimeError('Responses SSE terminal/content mismatch')
    sample={'model':model,'messages':[{'role':'user','content':'Write one short sentence about mountains.'}],
            'max_tokens':32,'temperature':.7,'top_p':.9,'frequency_penalty':.2,'presence_penalty':.1,'seed':42}
    pair=[json.loads(exchange('/v1/chat/completions',sample)) for _ in range(2)]
    if pair[0]['choices']!=pair[1]['choices'] or pair[0]['usage']!=pair[1]['usage']:
        raise RuntimeError('fresh-session seeded sampling mismatch')
    tool={'type':'function','function':{'name':'read','description':'Read a named text file.',
          'parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}}}
    q={'model':model,'messages':[{'role':'user','content':'Call read with path lie-gpu-fixture.txt. Do not answer in text; use the function.'}],
       'tools':[tool],'tool_choice':{'type':'function','function':{'name':'read'}},'parallel_tool_calls':False,'max_tokens':128}
    reply=json.loads(exchange('/v1/chat/completions',q))
    message=reply['choices'][0]['message']; calls=message.get('tool_calls') or []
    if reply['choices'][0]['finish_reason']!='tool_calls' or len(calls)!=1 or calls[0]['function']['name']!='read' or json.loads(calls[0]['function']['arguments'])!={'path':'lie-gpu-fixture.txt'}:
        raise RuntimeError('original-weight native function call mismatch')
    q['messages'] += [message,{'role':'tool','tool_call_id':calls[0]['id'],'content':'File content: LIE-GPU-TOOL-OK. Reply with this exact marker and nothing else.'}]
    q['tool_choice']='none'
    final=json.loads(exchange('/v1/chat/completions',q))
    if final['choices'][0]['message']['content'].strip()!='LIE-GPU-TOOL-OK':
        raise RuntimeError('original-weight native function result mismatch')
    return {'state':'PASS','responses_json_sse':True,'seeded_sampling':True,'native_tool_roundtrip':True,'independent_numerical_qualification':False}


def performance_summary(samples, groups):
    """No warmups, failed requests, synthetic substitutions or outlier trimming."""
    import statistics
    def stats(values):
        if not values:
            return None
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in values):
            raise ValueError('invalid performance measurement')
        ordered=sorted(values)
        return {'n':len(values),'median':statistics.median(values),'min':ordered[0],
                'max':ordered[-1],'p95_nearest_rank':ordered[max(0,math.ceil(.95*len(values))-1)],'all':values}
    result=[]
    keys=sorted({(r['api'],r['label'],r['stream'],r['concurrency']) for r in samples if not r['warmup']})
    for api,label,stream,concurrency in keys:
        rows=[r for r in samples if not r['warmup'] and (r['api'],r['label'],r['stream'],r['concurrency'])==(api,label,stream,concurrency)]
        if any(r['status']!=200 for r in rows): raise ValueError('failed request in performance configuration')
        batch=[g for g in groups if not g['warmup'] and (g['api'],g['label'],g['stream'],g['concurrency'])==(api,label,stream,concurrency)]
        result.append({'api':api,'label':label,'stream':stream,'concurrency':concurrency,
                       'requests':len(rows),'prompt_tokens':sorted({r['usage']['prompt_tokens'] for r in rows}),
                       'output_tokens':[r['usage']['completion_tokens'] for r in rows],
                       'end_to_end_ms':stats([r['total_ms'] for r in rows]),
                       'first_text_ms':stats([r['first_text_ms'] for r in rows if r['first_text_ms'] is not None]),
                       'first_output_ms':stats([r['first_output_ms'] for r in rows if r['first_output_ms'] is not None]),
                       'headers_ms':stats([r['headers_ms'] for r in rows]),
                       'executor_prefill_tps':stats([r['timings']['prefill_tokens_per_second'] for r in rows if r['timings']]),
                       'executor_decode_tps':stats([r['timings']['decode_tokens_per_second'] for r in rows if r['timings']]),
                       'aggregate_output_tps':stats([g['output_tokens']*1000/g['elapsed_ms'] for g in batch]),
                       'transport_delta_gap_ms':stats([v for r in rows for v in r['delta_gaps_ms']])})
    return result


def run_performance(api_port, management_port, model, provider, record, check, profile):
    """Closed-loop loopback client. GPU admission and telemetry belong to caller.
    TTFT means first nonempty text delta, not headers; JSON has no observable
    first-token timestamp. Percentiles are descriptive for this finite sample.
    """
    import concurrent.futures
    import threading
    import hashlib
    reps=profile['repetitions']; budget=profile['output_tokens']; prompts=profile['prompts']
    if type(reps) is not int or not 1<=reps<=10 or type(budget) is not int or not 1<=budget<=128 or not 1<=len(prompts)<=3:
        raise ValueError('invalid performance profile')
    for p in prompts:
        if type(p['padding_lines']) is not int or not 0<=p['padding_lines']<=1024 or type(p['prompt_tokens']) is not int or not 1<=p['prompt_tokens']<9216-budget:
            raise ValueError('invalid physical prompt profile')
    def padding(n):
        return ('Reference material follows. Ignore it for the counting task.\n'+
                'The quick brown fox jumps over the lazy dog.\n'*n+
                '\nList the integers from 1 to 10000, one integer per line. Start immediately at 1 and continue. Do not add an introduction, summary or code fence.')
    def sample(api,label,prompt,expected,stream,concurrency,warmup,rep,barrier,tools=False):
        if api=='chat':
            payload={'model':model,'messages':[{'role':'user','content':prompt}],'max_tokens':budget,'temperature':0,'stream':stream}
            if stream: payload['stream_options']={'include_usage':True}
            path='/v1/chat/completions'
        else:
            payload={'model':model,'input':prompt,'max_output_tokens':budget,'temperature':0,'stream':stream,'store':False}
            path='/v1/responses'
        if tools:
            payload['tools']=[{'type':'function','function':{'name':'read','description':'Read a named text file.',
                'parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}}}]
            payload['tool_choice']={'type':'function','function':{'name':'read'}}; payload['parallel_tool_calls']=False
        c=http.client.HTTPConnection('127.0.0.1',api_port,timeout=120)
        barrier.wait(timeout=15); started=time.monotonic_ns()
        row={'event':'performance_sample','api':api,'label':label,'stream':stream,'concurrency':concurrency,
             'warmup':warmup,'rep':rep,'request':payload,'started_ns':started,'first_text_ms':None,
             'first_output_ms':None,'timings':None,'delta_gaps_ms':[],'transport_events':[]}
        try:
            c.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'})
            r=c.getresponse(); row['status']=r.status; row['headers_ms']=(time.monotonic_ns()-started)/1e6
            content=[]; last_text=None; usage=None; final=None; chunks=[]
            if not stream or r.status!=200:
                body=r.read(32*1024*1024+1)
                if len(body)>32*1024*1024: raise ValueError('performance response bound')
                obj=json.loads(body); row['body']=obj
                if r.status==200:
                    if api=='chat': final=obj; usage=obj['usage']; content=[obj['choices'][0]['message'].get('content') or '']
                    else: final=obj; usage={'prompt_tokens':obj['usage']['input_tokens'],'completion_tokens':obj['usage']['output_tokens'],'total_tokens':obj['usage']['total_tokens']}; content=[p['text'] for i in obj['output'] if i['type']=='message' for p in i['content'] if p['type']=='output_text']
            else:
                count=0; sequence=0; saw_done=False; terminal_count=0
                while True:
                    line=r.readline(1024*1024+1)
                    if not line: break
                    count+=len(line)
                    if len(line)>1024*1024 or count>32*1024*1024: raise ValueError('performance stream bound')
                    if not line.startswith(b'data: '): continue
                    at=(time.monotonic_ns()-started)/1e6; raw=line[6:].strip()
                    if raw==b'[DONE]': saw_done=True; continue
                    item=json.loads(raw); chunks.append(item); row['transport_events'].append({'at_ms':at,'value':item})
                    text=''; output=False
                    if api=='chat':
                        if item.get('usage'): usage=item['usage']
                        if item.get('lie_timings'): row['timings']=item['lie_timings']
                        if item.get('error'): raise ValueError('performance stream error')
                        if item['choices']:
                            choice=item['choices'][0]; delta=choice['delta']; text=delta.get('content') or ''; output=bool(delta.get('tool_calls')) or bool(text)
                            if choice.get('finish_reason'): terminal_count+=1
                    else:
                        if item['sequence_number']!=sequence: raise ValueError('performance Responses sequence')
                        sequence+=1
                        if item['type']=='response.output_text.delta': text=item['delta']; output=bool(text)
                        if item['type']=='response.function_call_arguments.delta': output=True
                        if item['type'] in ('response.completed','response.incomplete','response.failed'):
                            terminal_count+=1; final=item['response']; u=final['usage']
                            if u: usage={'prompt_tokens':u['input_tokens'],'completion_tokens':u['output_tokens'],'total_tokens':u['total_tokens']}
                    if output and row['first_output_ms'] is None: row['first_output_ms']=at
                    if text:
                        content.append(text)
                        if row['first_text_ms'] is None: row['first_text_ms']=at
                        if last_text is not None: row['delta_gaps_ms'].append(at-last_text)
                        last_text=at
                if terminal_count!=1 or (api=='chat' and not saw_done) or (api=='responses' and saw_done): raise ValueError('performance terminal ordering')
                if api=='chat':
                    endings=[x['choices'][0]['finish_reason'] for x in chunks if x.get('choices') and x['choices'][0].get('finish_reason')]
                    calls=[call for x in chunks if x.get('choices') for call in x['choices'][0]['delta'].get('tool_calls',[])]
                    final={'choices':[{'finish_reason':endings[0],'message':{'content':''.join(content),'tool_calls':calls}}]}
            ended=time.monotonic_ns(); row['ended_ns']=ended; row['total_ms']=(ended-started)/1e6
            if row['status']!=200: raise ValueError('performance request refused')
            if not usage or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens'] or not 0<=usage['completion_tokens']<=budget:
                raise ValueError('performance usage mismatch')
            if expected is not None and usage['prompt_tokens']!=expected: raise ValueError('performance physical prompt mismatch')
            row['usage']=usage
            if api=='chat':
                finish=final['choices'][0]['finish_reason']; message=final['choices'][0]['message']; calls=message.get('tool_calls') or []
                if tools:
                    if finish!='tool_calls' or len(calls)!=1 or calls[0]['function']['name']!='read' or json.loads(calls[0]['function']['arguments'])!={'path':'lie-gpu-fixture.txt'}: raise ValueError('performance function output mismatch')
                elif finish not in ('stop','length'): raise ValueError('performance completion outcome')
                if not stream: row['timings']=final['lie_timings']
                validate_timings(usage,row['timings'])
            elif final['status'] not in ('completed','incomplete'): raise ValueError('performance Responses outcome')
            text=''.join(content); row['output_sha256']=hashlib.sha256(text.encode()).hexdigest(); row['output']=text
            return row
        except BaseException as ex:
            row['error']=repr(ex); row.setdefault('ended_ns',time.monotonic_ns()); row.setdefault('total_ms',(row['ended_ns']-started)/1e6)
            return row
        finally: c.close()
    samples=[]; groups=[]
    configs=[('chat',p['label'],padding(p['padding_lines']),p['prompt_tokens'],stream,n,False) for p in prompts for stream in (False,True) for n in (1,2)]
    p=prompts[len(prompts)//2]
    configs += [('responses',p['label'],padding(p['padding_lines']),p['prompt_tokens'],stream,1,False) for stream in (False,True)]
    if profile.get('measure_tools',True):
        configs += [('chat','native_function','Call read with path lie-gpu-fixture.txt. Do not answer in text; use the function.',None,stream,1,True) for stream in (False,True)]
    for rep in range(reps+1):
        ordered=list(reversed(configs)) if rep%2==0 and rep else configs
        for api,label,prompt,expected,stream,n,tools in ordered:
            check(); barrier=threading.Barrier(n)
            record({'event':'performance_group_begin','api':api,'label':label,'stream':stream,'concurrency':n,'warmup':rep==0,'rep':rep})
            with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
                futures=[pool.submit(sample,api,label,prompt,expected,stream,n,rep==0,rep,barrier,tools) for _ in range(n)]
                rows=[f.result() for f in futures]
            for row in rows: record(row); samples.append(row)
            if any('error' in row for row in rows): raise RuntimeError('performance sample failed; retained raw evidence')
            elapsed=(max(r['ended_ns'] for r in rows)-min(r['started_ns'] for r in rows))/1e6
            group={'event':'performance_group','api':api,'label':label,'stream':stream,'concurrency':n,'warmup':rep==0,'rep':rep,
                   'elapsed_ms':elapsed,'output_tokens':sum(r['usage']['completion_tokens'] for r in rows)}
            groups.append(group); record(group)
    overload=None
    if profile.get('measure_overload',True):
        check(); n=24; barrier=threading.Barrier(n); p=prompts[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
            rows=[f.result() for f in [pool.submit(sample,'chat','admission_burst',padding(p['padding_lines']),p['prompt_tokens'],False,n,False,0,barrier) for _ in range(n)]]
        for row in rows: row['event']='admission_sample'; record(row)
        if any(row['status'] not in (200,429) or (row['status']==200 and 'error' in row) for row in rows):
            raise RuntimeError('unexpected admission burst failure')
        overload={'requests':n,'completed':sum(row['status']==200 for row in rows),'capacity_rejected':sum(row['status']==429 for row in rows),
                  'scope':'one simultaneous burst; rejected requests retained, excluded from latency/throughput averages'}
    deadline=time.monotonic()+30
    while True:
        check(); c=http.client.HTTPConnection('127.0.0.1',management_port,timeout=10)
        try: c.request('GET','/actuator/llm'); r=c.getresponse(); state=json.loads(r.read())['scheduler']
        finally: c.close()
        if not state['active'] and not state['queued']: break
        if time.monotonic()>deadline: raise RuntimeError('performance retirement deadline')
        time.sleep(.05)
    return {'state':'PASS','scope':'closed-loop loopback serving; no independent backend comparison or reactive speedup',
            'warmup_requests':sum(r['warmup'] for r in samples),'measured_requests':sum(not r['warmup'] for r in samples),
            'configurations':performance_summary(samples,groups),'admission_burst':overload,'final_scheduler':state}
