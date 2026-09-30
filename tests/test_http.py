#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real HTTP/monitor CPU tests. Never inference/quality/GPU evidence."""
import concurrent.futures
import copy
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

SERVER, MONITOR = sys.argv[1:]


def available_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def request(port, path, method='GET', body=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
    c.request(method, path, body=body)
    r = c.getresponse()
    result = (r.status, dict(r.getheaders()), r.read().decode())
    c.close()
    return result


def raw(port, data):
    with socket.create_connection(('127.0.0.1', port), timeout=4) as s:
        s.sendall(data)
        result = b''
        while chunk := s.recv(8192): result += chunk
        return result


def independent_prometheus(text):
    # Separate stdlib parser for this export subset; promtool remains the official check.
    assert text.endswith('\n')
    seen = set(); groups = {}
    for line in text.splitlines():
        if line.startswith('#'):
            assert re.match(r'^# (HELP|TYPE) [a-zA-Z_:][a-zA-Z0-9_:]* .+$', line)
            continue
        m = re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(\{.*\})? ([-+0-9.eE]+)', line)
        assert m, line
        name, labels, value = m.groups(); value = float(value)
        pairs = re.findall(r'(\w+)="((?:[^"\\]|\\[\\n"])*)"', labels or '')
        assert len(dict(pairs)) == len(pairs)
        key = (name, tuple(sorted(pairs))); assert key not in seen; seen.add(key)
        labels = dict(pairs)
        if name.endswith('_bucket'):
            bound = float(labels.pop('le')); base = name[:-7]
            groups.setdefault((base, tuple(sorted(labels.items()))), {})[bound] = value
    for (base, labels), buckets in groups.items():
        ordered = sorted(buckets.items())
        assert all(a[1] <= b[1] for a, b in zip(ordered, ordered[1:]))
        count_line = base + '_count'
        assert (count_line, labels) in seen
        for line in text.splitlines():
            if line.startswith(count_line):
                pairs = dict(re.findall(r'(\w+)="((?:[^"\\]|\\[\\n"])*)"', line))
                if tuple(sorted(pairs.items())) == labels:
                    assert buckets[float('inf')] == float(line.rsplit(' ', 1)[1])
    assert len(groups) == 9


def main():
    api, management = available_port(), available_port()
    while api == management: management = available_port()
    with tempfile.TemporaryDirectory(prefix='synapse-lie-http-') as temporary:
        d = Path(temporary); log = (d / 'server.log').open('wb')
        p = subprocess.Popen([SERVER, '--port', str(api), '--management-port', str(management)], stdout=log, stderr=log)
        clients = []
        try:
            deadline = time.monotonic() + 6
            while True:
                if p.poll() is not None: raise AssertionError((d / 'server.log').read_text())
                try:
                    if request(management, '/actuator/health/liveness')[0] == 200: break
                except OSError: pass
                if time.monotonic() > deadline: raise TimeoutError('startup')
                time.sleep(.02)
            status, headers, text = request(management, '/actuator/metrics')
            assert status == 200 and headers['Content-Type'] == 'application/vnd.spring-boot.actuator.v3+json'
            names = json.loads(text)['names']; assert len(names) == 6
            assert request(api, '/actuator')[0] == 404
            assert request(management, '/v1/models')[0] == 404
            assert json.loads(request(api, '/v1/models')[2])['data'] == []
            for _ in range(3):
                response = request(api, '/v1/chat/completions', 'POST', '{"stream":true,"messages":[]}')
                assert response[0] == 503 and 'backend_unavailable' in response[2] and 'event-stream' not in response[1]['Content-Type']
            for endpoint in ('/actuator/health', '/actuator/health/readiness'):
                assert request(management, endpoint)[0] == 503
            assert request(management, '/actuator/info')[0] == 200
            assert json.loads(request(management, '/actuator/llm')[2])['throughput'] is None
            assert 'No inference backend connected' in request(management, '/monitor')[2]
            path = '/actuator/metrics/http.server.requests'
            detail = json.loads(request(management, path + '?tag=method%3AGET')[2])
            assert [x['statistic'] for x in detail['measurements']] == ['COUNT', 'TOTAL_TIME', 'MAX']
            assert [x['tag'] for x in detail['availableTags']] == ['status']
            assert json.loads(request(management, path + '?tag=method:GET&tag=status:2xx')[2])['availableTags'] == []
            assert request(management, path + '?tag=method:NO')[0] == 404
            for query in ('?tag=method:GET&tag=method:POST', '?bad=x', '?tag=%00x:y', '?tag=method:%GG', '?tag=method:GET&'):
                assert request(management, path + query)[0] == 400, query
            assert request(management, path, 'POST', '{}')[0] == 405
            assert raw(api, b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: 70000\r\n\r\n').startswith(b'HTTP/1.1 413')
            assert raw(api, b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\n{}x').startswith(b'HTTP/1.1 400')
            assert raw(management, b'GET /actuator HTTP/1.1\r\nHost: x\r\nX: ' + b'a' * 18000 + b'\r\n\r\n').startswith(b'HTTP/1.1 431')
            # Slow incomplete clients cannot block management. Close is network cancellation only.
            for _ in range(8):
                s = socket.create_connection(('127.0.0.1', api)); s.sendall(b'POST /v1/chat/completions HTTP/1.1\r\n'); clients.append(s)
            start = time.monotonic(); assert request(management, '/actuator/health/liveness')[0] == 200
            assert time.monotonic() - start < 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                statuses = list(pool.map(lambda _: request(management, '/actuator/info')[0], range(80)))
            assert statuses == [200] * 80
            status, headers, prom = request(management, '/actuator/prometheus')
            assert headers['Content-Type'] == 'text/plain; version=0.0.4; charset=utf-8'
            independent_prometheus(prom)
            if tool := shutil.which('promtool'):
                subprocess.run([tool, 'check', 'metrics'], input=prom, text=True, check=True, capture_output=True)
                print('promtool: PASS')
            else: print('promtool: NOT_INSTALLED; independent Python and C subset validators used')
            url = f'http://127.0.0.1:{management}'
            def monitor(args, expected=0):
                r = subprocess.run([MONITOR, *args], text=True, capture_output=True, timeout=15)
                assert r.returncode == expected, (args, r.returncode, r.stdout, r.stderr)
                return r
            assert 'OUT_OF_SERVICE' in monitor(['check', '--url', url]).stdout
            monitor(['check', '--url', url, '--require-ready'], 3)
            run = d / 'run.jsonl'
            monitor(['record', '--url', url, '--output', str(run), '--duration', '.6', '--interval', '.15'])
            rows = [json.loads(line) for line in run.read_text().splitlines()]
            assert len(rows) >= 2 and rows[0]['generated_tokens_per_second'] is None
            assert rows[-1]['generated_tokens_per_second'] == 0 and rows[-1]['delta_status'] == 'valid'
            monitor(['record', '--url', url, '--output', str(run)], 1)
            assert 'n/d' in monitor(['watch', '--url', url, '--duration', '.2', '--interval', '.1']).stdout
            fixture = d / 'fixture.json'; fixture.write_text(json.dumps(rows[0]))
            monitor(['check', '--file', str(fixture)])
            for mutation in ('missing_metric', 'histogram_corrupt', 'statistic', 'missing_prom', 'duplicate_sample', 'trailing_json'):
                obj = copy.deepcopy(rows[0])
                if mutation == 'missing_metric': obj['names']['names'].remove('runtime.ready')
                elif mutation == 'histogram_corrupt': obj['prometheus'] = re.sub(r'(le="\+Inf"\}) [0-9.eE+-]+', r'\1 9999999', obj['prometheus'], count=1)
                elif mutation == 'statistic': obj['details']['http.server.requests']['measurements'][0]['statistic'] = 'VALUE'
                elif mutation == 'missing_prom': del obj['prometheus']
                elif mutation == 'duplicate_sample': obj['prometheus'] += 'runtime_ready 0\n'
                fixture.write_text(json.dumps(obj) + ('{}' if mutation == 'trailing_json' else ''))
                monitor(['check', '--file', str(fixture)], 1)
            # Shutdown with live parsers and queued writes: ASan/UBSan cover callback lifetimes.
            p.terminate(); p.wait(timeout=8); assert p.returncode == 0
        finally:
            for c in clients: c.close()
            if p.poll() is None: p.terminate(); p.wait(timeout=8)
            log.close()
            output = (d / 'server.log').read_text()
            assert 'AddressSanitizer' not in output and 'runtime error:' not in output, output
    print('HTTP management, framing, bounds, concurrent clients, filters, unavailable inference, monitor modes/fixtures: PASS (CPU only)')


if __name__ == '__main__': main()
