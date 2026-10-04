#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original-weight Point HTTP fixture, invoked only inside an admitted GPU run.

This checks wire contracts and execution, not model quality or Pi connectivity.
"""
import datetime
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path('/work')
LIMIT = 2 * 1024 * 1024
MODEL_ID = 'qwen3.8-flash-next'


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def exchange(port_number, path, payload=None, method=None):
    connection = http.client.HTTPConnection('127.0.0.1', port_number, timeout=180)
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    try:
        verb = method or ('GET' if data is None else 'POST')
        connection.request(verb, path, data,
                           {} if data is None else {'Content-Type': 'application/json'})
        response = connection.getresponse()
        body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise RuntimeError('HTTP response exceeds fixture bound')
        row = {'method': verb, 'path': path, 'request': payload, 'status': response.status,
               'headers': dict(response.getheaders()), 'body': body.decode('utf-8')}
        with (ROOT/'http-wire.jsonl').open('a') as out:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
        return row
    finally:
        connection.close()


def events(body):
    rows = []
    for frame in body.strip().split('\n\n'):
        if frame == 'data: [DONE]':
            rows.append('[DONE]')
            continue
        lines = frame.splitlines()
        data = next((line[6:] for line in lines if line.startswith('data: ')), None)
        if data is None:
            raise RuntimeError('Malformed SSE frame')
        rows.append(json.loads(data))
    return rows


def abandon_response_stream(api, payload):
    """Close only this connection after a witnessed original text delta."""
    connection = http.client.HTTPConnection('127.0.0.1', api, timeout=180)
    partial = bytearray()
    frames = []
    try:
        connection.request('POST','/v1/responses',json.dumps(payload).encode(),
                           {'Content-Type':'application/json'})
        response = connection.getresponse()
        if response.status != 200: raise RuntimeError('Background SSE refused')
        frame = bytearray()
        identity = None
        while True:
            line = response.readline(LIMIT+1)
            if not line or len(partial)+len(line)>LIMIT:
                raise RuntimeError('No bounded original background text delta')
            partial.extend(line); frame.extend(line)
            if line == b'\n':
                current = events(frame.decode('utf-8'))
                if len(current)!=1 or not isinstance(current[0],dict):
                    raise RuntimeError('Background frame malformed')
                item = current[0]; frames.append(item); frame.clear()
                if item['type']=='response.created': identity=item['response']['id']
                if item['type']=='response.output_text.delta' and item['delta']:
                    if not identity: raise RuntimeError('Background delta preceded identity')
                    return {'id':identity,'sequence_number':item['sequence_number'],
                            'delta_bytes':len(item['delta'].encode('utf-8'))}
                if item['type'] in ('response.completed','response.incomplete','response.failed'):
                    raise RuntimeError('Background retired before original text')
    finally:
        connection.close()
        with (ROOT/'http-wire.jsonl').open('a') as out:
            out.write(json.dumps({'method':'POST','path':'/v1/responses','request':payload,
                                  'abandoned_after_delta':bool(frames and frames[-1].get('type')=='response.output_text.delta'),
                                  'body':partial.decode('utf-8',errors='replace')})+'\n')


def function_call(call, responses):
    fn = call if responses else call['function']
    identity = call['call_id' if responses else 'id']
    if (not identity or fn['name'] != 'get_value' or
            json.loads(fn['arguments']) != {'key': 'answer'}):
        raise RuntimeError('Function identity/arguments mismatch')
    return identity


def tool_gate(api, result):
    schema = {'type': 'object', 'properties': {'key': {'type': 'string', 'enum': ['answer']}},
              'required': ['key'], 'additionalProperties': False}
    fn = {'name': 'get_value', 'description': 'Get the answer identified by its key.',
          'parameters': schema, 'strict': True}
    prompt = 'Call get_value with key answer. Do not explain.'
    chat = {'model': MODEL_ID, 'messages': [{'role': 'user', 'content': prompt}],
            'tools': [{'type': 'function', 'function': fn}],
            'tool_choice': {'type': 'function', 'function': {'name': 'get_value'}},
            'temperature': 0, 'max_tokens': 512, 'store': False}
    plain = exchange(api, '/v1/chat/completions', chat)
    if plain['status'] != 200:
        raise RuntimeError('Chat function JSON failed')
    choice = json.loads(plain['body'])['choices'][0]
    message = choice['message']
    calls = message.get('tool_calls', [])
    if choice['finish_reason'] != 'tool_calls' or len(calls) != 1:
        raise RuntimeError('Chat function did not commit exactly one call')
    call_id = function_call(calls[0], False)
    result['passed'].append('chat_function_json')
    streamed = exchange(api, '/v1/chat/completions', dict(chat, stream=True))
    chunks = events(streamed['body'])
    arguments, identity, fragments, finishes = '', None, 0, 0
    for chunk in chunks:
        if chunk == '[DONE]':
            continue
        for item in chunk.get('choices', []):
            if item.get('finish_reason') == 'tool_calls':
                finishes += 1
            for part in item['delta'].get('tool_calls', []):
                if part['index'] != 0:
                    raise RuntimeError('Chat function index changed')
                if 'id' in part:
                    if identity or part['function']['name'] != 'get_value':
                        raise RuntimeError('Repeated/incorrect Chat function start')
                    identity = part['id']
                delta = part['function'].get('arguments', '')
                if not identity:
                    raise RuntimeError('Chat arguments preceded their call start')
                arguments += delta
                fragments += bool(delta)
    if (streamed['status'] != 200 or not chunks or chunks[-1] != '[DONE]' or
            chunks.count('[DONE]') != 1 or finishes != 1 or fragments < 2):
        raise RuntimeError('Chat incremental function SSE failed')
    function_call({'id': identity, 'function': {'name': 'get_value', 'arguments': arguments}}, False)
    result['passed'].append('chat_function_sse')
    followup = dict(chat, tool_choice='none', max_tokens=64,
                    messages=chat['messages']+[message,
                        {'role': 'tool', 'tool_call_id': call_id, 'content': '{"value":4}'},
                        {'role': 'user', 'content': 'Reply with the value returned by the function.'}])
    row = exchange(api, '/v1/chat/completions', followup)
    if row['status'] != 200 or not json.loads(row['body'])['choices'][0]['message']['content']:
        raise RuntimeError('Correlated Chat tool result failed')
    result['passed'].append('chat_tool_result')

    response = {'model': MODEL_ID, 'input': prompt,
                'tools': [dict(fn, type='function')],
                'tool_choice': {'type': 'function', 'name': 'get_value'},
                'temperature': 0, 'max_output_tokens': 512, 'store': False}
    row = exchange(api, '/v1/responses', response)
    if row['status'] != 200:
        raise RuntimeError('Responses function JSON failed')
    output = json.loads(row['body'])
    calls = [item for item in output['output'] if item['type'] == 'function_call']
    if output['status'] != 'completed' or len(calls) != 1:
        raise RuntimeError('Responses did not commit exactly one function')
    function_call(calls[0], True)
    result['passed'].append('responses_function_json')
    row = exchange(api, '/v1/responses', dict(response, stream=True, store=True))
    chunks = events(row['body'])
    if (row['status'] != 200 or not chunks or chunks[-1]['type'] != 'response.completed' or
            [x['sequence_number'] for x in chunks] != list(range(len(chunks)))):
        raise RuntimeError('Responses function SSE terminal/sequence mismatch')
    deltas = [x for x in chunks if x['type'] == 'response.function_call_arguments.delta']
    done = [x for x in chunks if x['type'] == 'response.function_call_arguments.done']
    final = chunks[-1]['response']
    calls = [x for x in final['output'] if x['type'] == 'function_call']
    if len(deltas) < 2 or len(done) != 1 or len(calls) != 1:
        raise RuntimeError('Responses function arguments not streamed incrementally')
    arguments = ''.join(x['delta'] for x in deltas)
    if done[0]['arguments'] != arguments or calls[0]['arguments'] != arguments:
        raise RuntimeError('Responses argument deltas differ from committed JSON')
    call_id = function_call(calls[0], True)
    result['passed'].append('responses_function_sse')
    replay = exchange(api, '/v1/responses/'+final['id']+'?stream=true')
    if replay['status'] != 200 or replay['body'] != row['body']:
        raise RuntimeError('Retired Responses function journal changed during replay')
    result['passed'].append('responses_tool_replay')
    continuation = {'model': MODEL_ID, 'previous_response_id': final['id'],
                    'input': [{'type': 'function_call_output', 'call_id': call_id, 'output': '{"value":4}'},
                              {'role': 'user', 'content': 'Reply with the value returned by the function.'}],
                    'temperature': 0, 'max_output_tokens': 64, 'store': False}
    followup = exchange(api, '/v1/responses', continuation)
    if followup['status'] != 200 or not json.loads(followup['body'])['output']:
        raise RuntimeError('Correlated retained Responses function result failed')
    result['passed'].append('responses_tool_result')
    restricted = dict(chat, tools=chat['tools']+[{'type': 'function', 'function': dict(fn, name='unused')}],
                      tool_choice={'type': 'allowed_tools', 'allowed_tools': {
                          'mode': 'required', 'tools': [{'type': 'function', 'function': {'name': 'get_value'}}]}})
    row = exchange(api, '/v1/chat/completions', restricted)
    if row['status'] != 200:
        raise RuntimeError('Allowed function subset request failed')
    choice = json.loads(row['body'])['choices'][0]
    calls = choice['message'].get('tool_calls', [])
    if choice['finish_reason'] != 'tool_calls' or len(calls) != 1:
        raise RuntimeError('Allowed function subset did not commit one call')
    function_call(calls[0], False)
    result['passed'].append('allowed_tools')


def main():
    args = sys.argv[1:]
    flags = set()
    while args and args[-1] in ('--tools','--controls'):
        flag = args.pop()
        if flag in flags: raise SystemExit('Duplicate HTTP gate flag')
        flags.add(flag)
    check_tools, check_controls = '--tools' in flags, '--controls' in flags
    if len(args) not in (3, 4) or args[2] not in ('ar', 'mtp') or (len(args) == 4) != (args[2] == 'mtp'):
        raise SystemExit('Usage: http-gate.py SERVER MODEL ar|mtp [PREDICTOR] [--tools] [--controls]')
    binary, model, mode = args[:3]
    api, management = port(), port()
    while management == api:
        management = port()
    result = {'schema': 'synapse-lie.point-http-original.v1', 'state': 'RUNNING',
              'started_at': timestamp(), 'mode': mode, 'passed': [],
              'api_port': api, 'management_port': management}
    command = [binary, '--model', model, '--model-id', MODEL_ID,
               '--host', '127.0.0.1', '--port', str(api),
               '--management-host', '127.0.0.1', '--management-port', str(management),
               '--context', '16384', '--prefill-chunk', '2048', '--max-active', '8' if check_controls else '2',
               '--kv-cache-ram-mb', '0', '--request-timeout-ms', '180000']
    if mode == 'mtp':
        command += ['--model-mtp', args[3], '--mtp-draft-tokens', '7']
    result['server_argv'] = command
    server = None
    try:
        with (ROOT/'server.log').open('xb') as log:
            server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            (ROOT/'http-started.marker').write_text(str(server.pid) + '\n')
            deadline = time.monotonic() + 900
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Server exited during model load')
                try:
                    health = exchange(management, '/actuator/health/readiness')
                    if health['status'] == 200:
                        break
                except (OSError, http.client.HTTPException):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Original-weight model readiness deadline')
                time.sleep(.25)
            state = exchange(management, '/actuator/llm')
            if state['status'] != 200 or not json.loads(state['body']).get('ready'):
                raise RuntimeError('Ready backend state missing')
            listed = exchange(api, '/v1/models')
            if listed['status'] != 200 or MODEL_ID not in {item['id'] for item in json.loads(listed['body'])['data']}:
                raise RuntimeError('Model list identity mismatch')
            result['passed'].append('models')
            chat = {'model': MODEL_ID, 'messages': [{'role': 'user', 'content': 'What is 2 + 2? Reply with only the digit.'}],
                    'temperature': 0, 'max_tokens': 32,
                    'chat_template_kwargs': {'enable_thinking': False}}
            plain = exchange(api, '/v1/chat/completions', chat)
            if plain['status'] != 200:
                raise RuntimeError('Chat JSON failed')
            completion = json.loads(plain['body'])
            text = completion['choices'][0]['message']['content']
            if (completion['object'] != 'chat.completion' or not isinstance(text, str) or
                    not text.strip() or completion['usage']['completion_tokens'] < 1):
                raise RuntimeError('Chat JSON contract failed')
            result['passed'].append('chat_json')
            stream = exchange(api, '/v1/chat/completions', dict(chat, stream=True,
                              stream_options={'include_usage': True}))
            chunks = events(stream['body'])
            if (stream['status'] != 200 or chunks[-1] != '[DONE]' or
                    ''.join(chunk['choices'][0]['delta'].get('content') or '' for chunk in chunks[:-1]
                            if chunk.get('choices')) != text or
                    not any(isinstance(chunk, dict) and chunk.get('usage') for chunk in chunks[:-1])):
                raise RuntimeError('Chat SSE contract/output mismatch')
            result['passed'].append('chat_sse')
            response_request = {'model': MODEL_ID, 'input': 'What is 2 + 2? Reply with only the digit.',
                                'temperature': 0, 'max_output_tokens': 32,
                                'store': False}
            plain = exchange(api, '/v1/responses', response_request)
            if plain['status'] != 200:
                raise RuntimeError('Responses JSON failed')
            response = json.loads(plain['body'])
            response_text = response['output'][0]['content'][0]['text']
            if (response['object'] != 'response' or response['status'] != 'completed' or
                    not isinstance(response_text, str) or not response_text.strip() or
                    response['usage']['output_tokens'] < 1):
                raise RuntimeError('Responses JSON contract failed')
            result['passed'].append('responses_json')
            stream = exchange(api, '/v1/responses', dict(response_request, stream=True))
            chunks = events(stream['body'])
            if (stream['status'] != 200 or chunks[0]['type'] != 'response.created' or
                    chunks[-1]['type'] != 'response.completed' or
                    chunks[-1]['response']['output'][0]['content'][0]['text'] != response_text):
                raise RuntimeError('Responses SSE contract/output mismatch')
            result['passed'].append('responses_sse')
            if check_tools:
                tool_gate(api, result)
            if check_controls:
                spec = importlib.util.spec_from_file_location('original_controls',ROOT/'http-controls.py')
                controls = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(controls)
                checked = controls.controls_gate(api,MODEL_ID,exchange,events,abandon_response_stream,ROOT)
                result['passed'].extend(checked['passed'])
            result['chat_text'] = text
            result['responses_text'] = response_text
            result['state'] = 'PASSED'
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        if server is not None:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            result['server_exit_code'] = server.returncode
        result['ended_at'] = timestamp()
        (ROOT/'http-result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return 0 if result['state'] == 'PASSED' and result.get('server_exit_code') == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
