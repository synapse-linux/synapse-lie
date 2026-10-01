#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real C HTTP/worker/flow, synthetic tokens. Not model or Pi qualification."""
import http.client
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def exchange(p, path, body=None):
    c = http.client.HTTPConnection('127.0.0.1', p, timeout=10)
    c.request('GET' if body is None else 'POST', path,
              None if body is None else json.dumps(body).encode(),
              {} if body is None else {'Content-Type': 'application/json'})
    r = c.getresponse()
    result = r.status, r.read().decode('utf-8')
    c.close()
    return result


TOOLS = [{'type': 'function', 'function': {'name': 'read', 'description': 'Read text',
          'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'},
                         'offset': {'type': 'integer'}, 'options': {'type': 'object'}},
                         'required': ['path'], 'additionalProperties': False}}}]


def request(text='TOOL', stream=False):
    return {'model': 'cpu-test-fixture', 'messages': [{'role': 'user', 'content': text}],
            'tools': TOOLS, 'tool_choice': 'auto', 'max_tokens': 512,
            'stream': stream, **({'stream_options': {'include_usage': True}} if stream else {})}


def check_message(message):
    assert message['role'] == 'assistant'
    assert message['content'] == 'Reading.\n'
    calls = message['tool_calls']
    assert len(calls) == 1 and calls[0]['type'] == 'function'
    assert calls[0]['id'] and calls[0]['function']['name'] == 'read'
    args = json.loads(calls[0]['function']['arguments'])
    assert args == {'path': '  caffè 🙂.txt  ', 'offset': 3, 'options': {'raw': True}}, args
    return calls[0]


def main():
    a, m = port(), port()
    while a == m:
        m = port()
    with tempfile.TemporaryDirectory(prefix='lie-tools-http-') as d:
        log = Path(d) / 'server.log'
        with log.open('wb') as f:
            p = subprocess.Popen([sys.argv[1], '--model', ':fixture:', '--port', str(a),
                                  '--management-port', str(m)], stdout=f, stderr=f)
            try:
                deadline = time.monotonic() + 5
                while True:
                    if p.poll() is not None:
                        raise AssertionError(log.read_text())
                    try:
                        if exchange(m, '/actuator/health/readiness')[0] == 200:
                            break
                    except OSError:
                        pass
                    assert time.monotonic() < deadline
                    time.sleep(.01)
                status, body = exchange(a, '/v1/chat/completions', request())
                assert status == 200, (status, body)
                full = json.loads(body)
                assert full['choices'][0]['finish_reason'] == 'tool_calls'
                call = check_message(full['choices'][0]['message'])
                assert full['usage']['completion_tokens'] > 0 and full['lie_timings']['valid']
                status, body = exchange(a, '/v1/chat/completions', request(stream=True))
                assert status == 200, body
                assert body.endswith('data: [DONE]\n\n') and body.count('data: [DONE]') == 1
                chunks = [json.loads(s[6:]) for s in body.split('\n\n') if s.startswith('data: {')]
                merged = {'role': 'assistant', 'content': '', 'tool_calls': []}
                for chunk in chunks:
                    if not chunk['choices']:
                        continue
                    delta = chunk['choices'][0]['delta']
                    merged['content'] += delta.get('content') or ''
                    merged['tool_calls'].extend(delta.get('tool_calls', []))
                check_message(merged)
                assert chunks[-2]['choices'][0]['finish_reason'] == 'tool_calls'
                assert chunks[-1]['usage'] == full['usage']
                assert merged['tool_calls'][0]['index'] == 0
                # Standard OpenAI history, no textual client shim.
                follow = request('TOOL-FOLLOW')
                follow['messages'] += [full['choices'][0]['message'],
                                       {'role': 'tool', 'tool_call_id': call['id'], 'content': 'TOOL-RESULT'}]
                status, body = exchange(a, '/v1/chat/completions', follow)
                assert status == 200, body
                result = json.loads(body)
                assert result['choices'][0]['finish_reason'] == 'stop'
                assert result['choices'][0]['message']['content'] == 'Tool result received.'
                # Incomplete/invalid generated calls are errors, not executable deltas.
                for fixture in ('TOOL-TRUNCATED', 'TOOL-UNKNOWN', 'TOOL-DUPLICATE', 'TOOL-JSON-BAD'):
                    for stream in (False, True):
                        status, body = exchange(a, '/v1/chat/completions', request(fixture, stream))
                        if status == 200:
                            assert stream and '"error"' in body, body
                            assert '"tool_calls"' not in body and '"finish_reason":"stop"' not in body
                        else:
                            assert status == 502, (status, body)
                        assert exchange(m, '/actuator/health/readiness')[0] == 200
                # Refusals before model work and transcript identity checks.
                invalid = []
                q = request(); q['tools'][0]['function']['strict'] = True
                invalid.append(json.loads(json.dumps(q))); del TOOLS[0]['function']['strict']
                q = request(); q['messages'] = [{'role': 'tool', 'tool_call_id': 'orphan', 'content': 'x'}]; invalid.append(q)
                q = request(); q['messages'] += [full['choices'][0]['message']]; invalid.append(q)
                q = request(); q['messages'] += [full['choices'][0]['message'], {'role': 'tool', 'tool_call_id': 'wrong', 'content': 'x'}]; invalid.append(q)
                for q in invalid:
                    status, body = exchange(a, '/v1/chat/completions', q)
                    assert status == 400, (status, body)
                metric = json.loads(exchange(m, '/actuator/metrics/llm.responses.tool_errors')[1])
                assert metric['measurements'] == [{'statistic': 'COUNT', 'value': 8}], metric
                # Cancel a buffered tool turn after headers while its typed input
                # still belongs to the worker; the UI's schema copy must be independent.
                before = json.loads(exchange(m, '/actuator/llm')[1])['scheduler']['cancelled']
                client = http.client.HTTPConnection('127.0.0.1', a, timeout=3)
                client.request('POST', '/v1/chat/completions', json.dumps(request(stream=True)))
                response = client.getresponse(); assert response.status == 200
                response.close(); client.close()
                deadline = time.monotonic() + 3
                while True:
                    state = json.loads(exchange(m, '/actuator/llm')[1])['scheduler']
                    if state['cancelled'] == before + 1 and not state['active'] and not state['queued']:
                        break
                    assert time.monotonic() < deadline, state
                    time.sleep(.01)
                assert exchange(m, '/actuator/health/readiness')[0] == 200
            finally:
                if p.poll() is None:
                    p.terminate()
                try:
                    p.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait(); raise
                print(log.read_text())
                assert p.returncode == 0
        assert 'AddressSanitizer' not in log.read_text() and 'runtime error:' not in log.read_text()
    print('Native HTTP tool round trip: PASS (synthetic CPU fixture, NOT inference)')


if __name__ == '__main__':
    main()
