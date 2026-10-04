#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original-weight Point HTTP fixture, invoked only inside an admitted GPU run.

This checks wire contracts and execution, not model quality or Pi connectivity.
"""
import datetime
import http.client
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


def exchange(port_number, path, payload=None):
    connection = http.client.HTTPConnection('127.0.0.1', port_number, timeout=180)
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    try:
        connection.request('GET' if data is None else 'POST', path, data,
                           {} if data is None else {'Content-Type': 'application/json'})
        response = connection.getresponse()
        body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise RuntimeError('HTTP response exceeds fixture bound')
        row = {'path': path, 'request': payload, 'status': response.status,
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


def main():
    if len(sys.argv) not in (4, 5) or sys.argv[3] not in ('ar', 'mtp') or (len(sys.argv) == 5) != (sys.argv[3] == 'mtp'):
        raise SystemExit('Usage: http-gate.py SERVER MODEL ar|mtp [PREDICTOR]')
    binary, model, mode = sys.argv[1:4]
    api, management = port(), port()
    while management == api:
        management = port()
    result = {'schema': 'synapse-lie.point-http-original.v1', 'state': 'RUNNING',
              'started_at': timestamp(), 'mode': mode, 'passed': [],
              'api_port': api, 'management_port': management}
    command = [binary, '--model', model, '--model-id', MODEL_ID,
               '--host', '127.0.0.1', '--port', str(api),
               '--management-host', '127.0.0.1', '--management-port', str(management),
               '--context', '16384', '--prefill-chunk', '2048', '--max-active', '2',
               '--kv-cache-ram-mb', '0', '--request-timeout-ms', '180000']
    if mode == 'mtp':
        command += ['--model-mtp', sys.argv[4], '--mtp-draft-tokens', '7']
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
