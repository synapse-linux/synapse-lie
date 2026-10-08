#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original-input rejection and owned native-session child lifetime, no GPU."""

import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'hc_native_window', ROOT / 'tools/q2-decode-down-rows-native128-performance-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)
SAVED = ROOT / 'evidence/q2-full-prefill128-final-r1/results/full-prefill.jsonl'
REQUESTS = ROOT / 'evidence/q2-full-prefill128-final-r1/results/full-prefill.requests.jsonl'


def reject(path, cases):
    try:
        window.validate_output(path, cases)
    except ValueError:
        return
    raise AssertionError('Invalid native workload was accepted')


def inputs():
    cases = [json.loads(line) for line in REQUESTS.read_text().splitlines()]
    result = window.validate_output(SAVED, cases)
    assert result['decode_tps'] > 0 and result['prefill_tps'] > 0
    with tempfile.TemporaryDirectory(prefix='lie-hc-native-input-') as temp:
        for field, value in [('cached_tokens', 1), ('decode_calls', 128),
                             ('prefill_calls', 63), ('prefill_tokens', 130926)]:
            rows = [json.loads(line) for line in SAVED.read_text().splitlines()]
            samples = [r for r in rows if r.get('event') == 'sample']
            samples[-1]['server_timings'][field] = value
            path = Path(temp) / (field + '.jsonl')
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            reject(path, cases)
        changed = json.loads(json.dumps(cases))
        changed[-1]['body']['max_tokens'] = 128
        reject(SAVED, changed)


def power():
    settings = {'apu_power_mode': 'performance', 'tdp_watts': 120,
                **{f: {'mode': 'curve', 'rampup_curve': '40,50,60,70,82',
                       'rampdown_curve': '35,45,55,65,78'}
                   for f in ('fan1', 'fan2', 'fan3')}}
    valid = {'exit_code': 0, 'stdout': json.dumps(settings)}
    assert window.validate_power(valid) == settings
    invalid = []
    for key, value in (('apu_power_mode', 'balanced'), ('tdp_watts', 85)):
        invalid.append({'exit_code': 0, 'stdout': json.dumps({**settings, key: value})})
    wrong_fan = json.loads(json.dumps(settings))
    wrong_fan['fan2']['rampup_curve'] = '60,70,83,95,97'
    invalid.extend([{'exit_code': 0, 'stdout': json.dumps(wrong_fan)},
                    {**valid, 'exit_code': 1}, {'exit_code': 0, 'stdout': '{}'},
                    {'exit_code': 0, 'stdout': 'invalid'}])
    for receipt in invalid:
        try:
            window.validate_power(receipt)
        except (ValueError, KeyError):
            continue
        raise AssertionError('Mismatched power observation accepted')


def lifetime(exit_code):
    with tempfile.TemporaryDirectory(prefix='lie-hc-native-owned-') as temp:
        root = Path(temp)
        server, client = root / 'server', root / 'client'
        server.write_text('''#!/usr/bin/env python3
import http.server,sys
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"ready":true}')
    def log_message(self,*args): pass
port=int(sys.argv[sys.argv.index('--management-port')+1])
http.server.HTTPServer(('127.0.0.1',port),Handler).serve_forever()
''')
        client.write_text('''#!/usr/bin/env python3
import shutil,sys,time
''' + f'shutil.copyfile({str(SAVED)!r},sys.argv[sys.argv.index("--output")+1])\n'
                          'time.sleep(.2)\n' + f'sys.exit({exit_code})\n')
        server.chmod(0o700)
        client.chmod(0o700)
        work = root / 'results'
        work.mkdir()
        window.ROOT = root
        window.cool = lambda: None
        window.cpu_temp_mc = lambda: 35000
        window.sensor = lambda: {'fixture': True}
        own = []
        plan = {'port': 0, 'candidate_server': {'path': str(server)},
                'client': {'path': str(client)}, 'requests': {'path': str(REQUESTS)},
                'model_stats': [{'path': str(root / 'unopened-model.gguf')}]}
        try:
            result = window.one_arm(plan, 0, 'down-rows', work, own)
            assert exit_code == 0 and result['decode_tps'] > 0
        except ValueError as error:
            assert exit_code == 3 and str(error) == 'Owned client failed'
        children = json.loads((work / '00-down-rows.children.json').read_text())
        assert children['client_exit_code'] == exit_code
        assert children['server_exit_code'] == -15
        assert len(own) == 2
        assert all(row['boot_id'] == window.EXPECTED_BOOT for row in own)
        assert json.loads((work / '00-down-rows.server-start.json').read_text())['pid'] == own[0]['pid']
        assert json.loads((work / '00-down-rows.client-start.json').read_text())['pid'] == own[1]['pid']
        window.assert_retired({'retired_identities': [], 'retired_groups': []}, own)
        assert not (root / 'unopened-model.gguf').exists()


if __name__ == '__main__':
    inputs()
    power()
    lifetime(0)
    lifetime(3)
    print('Native128 CPU fixtures pass: original contract, power/fan rejection, success/failure child retirement.')
