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
