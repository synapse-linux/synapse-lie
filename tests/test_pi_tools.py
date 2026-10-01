#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional installed-Pi integration. Native OpenAI provider + real read tool,
synthetic C executor, isolated profile; NEVER an Unsloth/model qualification."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
    binary, pi, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
    output.mkdir()
    a, m = port(), port()
    while a == m:
        m = port()
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PI_OFFLINE='1', PI_SKIP_VERSION_CHECK='1', PI_TELEMETRY='0',
               HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1',
               ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        env.pop(key, None)
    env['NO_PROXY'] = '127.0.0.1,localhost'
    with tempfile.TemporaryDirectory(prefix='lie-pi-cpu-', dir=output) as temporary:
        work = Path(temporary); agent = work / 'agent'; agent.mkdir()
        (work / 'lie-pi-fixture.txt').write_text('LIE-PI-FIXTURE-CONTENT\n', encoding='utf-8')
        models = json.loads((root / 'config/pi-unsloth.models.json').read_text())
        provider = models['providers']['synapse-lie']
        provider['baseUrl'] = f'http://127.0.0.1:{a}/v1'
        provider['models'][0].update(id='cpu-test-fixture', name='CPU fixture NOT INFERENCE', contextWindow=32768, maxTokens=512)
        (agent / 'models.json').write_text(json.dumps(models))
        settings = json.loads((root / 'config/pi-unsloth.settings.json').read_text())
        settings['defaultModel'] = 'cpu-test-fixture'
        settings['enabledModels'] = ['synapse-lie/cpu-test-fixture']
        (agent / 'settings.json').write_text(json.dumps(settings))
        env['PI_CODING_AGENT_DIR'] = str(agent)
        cmd = [pi, '--no-session', '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-themes',
               '--mode', 'json', '--provider', 'synapse-lie', '--model', 'cpu-test-fixture',
               '--thinking', 'off', '--tools', 'read', '--print', 'PI-SYNTHETIC-READ']
        with (output / 'server.log').open('xb') as log:
            server = subprocess.Popen([str(binary), '--model', ':fixture:', '--context', '32768', '--port', str(a), '--management-port', str(m)],
                                      env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 5
                while True:
                    if server.poll() is not None:
                        raise AssertionError((output / 'server.log').read_text())
                    c = http.client.HTTPConnection('127.0.0.1', m, timeout=1)
                    try:
                        c.request('GET', '/actuator/health/readiness')
                        r = c.getresponse(); ready = r.status == 200; r.read()
                        if ready:
                            break
                    except OSError:
                        pass
                    finally:
                        c.close()
                    assert time.monotonic() < deadline
                    time.sleep(.01)
                with (output / 'pi.jsonl').open('xb') as out, (output / 'pi.stderr').open('xb') as err:
                    result = subprocess.run(cmd, cwd=work, env=env, stdout=out, stderr=err, timeout=40)
                (output / 'pi-exit.json').write_text(json.dumps({'argv': cmd, 'exit_code': result.returncode}) + '\n')
                assert result.returncode == 0, (output / 'pi.stderr').read_text()
                events = [json.loads(line) for line in (output / 'pi.jsonl').read_text().splitlines() if line.startswith('{')]
                tools = [e for e in events if e.get('type') == 'tool_execution_end']
                assert len(tools) == 1 and tools[0]['toolName'] == 'read' and not tools[0]['isError'], {'tool_events': tools, 'trace': str(output / 'pi.jsonl')}
                assert 'LIE-PI-FIXTURE-CONTENT' in json.dumps(tools[0])
                assistants = [e['message'] for e in events if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant']
                assert len(assistants) == 2 and assistants[0]['stopReason'] == 'toolUse' and assistants[1]['stopReason'] == 'stop', assistants
                assert ''.join(b.get('text', '') for b in assistants[1]['content'] if b['type'] == 'text') == 'CPU fixture tool result received.', assistants[-1]
                assert (work / 'lie-pi-fixture.txt').read_text() == 'LIE-PI-FIXTURE-CONTENT\n'
            finally:
                if server.poll() is None:
                    server.terminate()
                try:
                    server.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait(); raise
                (output / 'server-exit.json').write_text(json.dumps({'exit_code': server.returncode}) + '\n')
                assert server.returncode == 0
    (output / 'result.json').write_text(json.dumps({'state': 'PI_NATIVE_OPENAI_TOOL_ROUNDTRIP_CPU_FIXTURE_PASS',
        'real_pi_read_tool_executed': True, 'custom_provider_extension': False, 'gpu_run': False, 'model_qualification': False}, indent=2) + '\n')
    print('Native Pi -> C17 server -> real Pi read -> C17 follow-up: PASS; synthetic tokens, NOT Unsloth inference')


if __name__ == '__main__':
    main()
