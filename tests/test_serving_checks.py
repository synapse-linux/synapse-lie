#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU contract and real TCP fixture tests for the admitted serving checker. NOT-INFERENCE."""
import copy
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lie_serving_checks', ROOT / 'tools/serving_checks.py')
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
PROVIDER = 'cpu-test-fixture-NOT-INFERENCE'


def rejects(call):
    try: call()
    except (ValueError, KeyError, TypeError): return
    raise AssertionError('invalid metadata accepted')


def unit():
    s = {'executor': {'scope': 'owner_dispatch_intervals', 'phase': 'none', 'prefill_started': 1, 'prefill_returned': 1,
                     'decode_started': 2, 'decode_returned': 2, 'cancel_during_prefill': 0, 'cancel_during_decode': 0},
         'mode': 'single-owner-interleaved-single-row', 'max_active': 2, 'active': 0, 'queued': 0,
         'output_blocked': 0, 'completed': 1, 'cancelled': 0, 'failed': 0, 'generated_tokens': 2}
    checks.validate_scheduler(s)
    for key, value in [('output_blocked', 1), ('active', 3), ('queued', -1), ('completed', True), ('max_active', 1)]:
        broken = copy.deepcopy(s); broken[key] = value
        rejects(lambda: checks.validate_scheduler(broken))
    for key, value in [('phase', 'decode'), ('prefill_returned', 2), ('decode_started', True), ('scope', 'gpu_time')]:
        broken = copy.deepcopy(s); broken['executor'][key] = value
        rejects(lambda: checks.validate_scheduler(broken))
    obj = {'object': 'chat.completion', 'system_fingerprint': PROVIDER,
           'choices': [{'finish_reason': 'length', 'message': {'role': 'assistant', 'content': 'X'}}],
           'usage': {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6},
           'lie_timings': {'schema': 'synapse-lie.request-timings.v1', 'scope': 'synchronous_executor_calls', 'valid': True,
                           'prefill_tokens': 4, 'decode_tokens': 2, 'prefill_calls': 1, 'decode_calls': 2,
                           'prefill_ms': 1, 'decode_ms': 2, 'prefill_tokens_per_second': 4000, 'decode_tokens_per_second': 1000}}
    checks.validate_completion(obj, PROVIDER)
    for key, value in [('valid', False), ('prefill_tokens', 8), ('decode_calls', 1), ('decode_ms', 0),
                       ('decode_ms', float('nan')), ('decode_tokens_per_second', float('inf')),
                       ('decode_tokens_per_second', 999), ('prefill_calls', True)]:
        broken = copy.deepcopy(obj); broken['lie_timings'][key] = value
        rejects(lambda: checks.validate_completion(broken, PROVIDER))
    broken = copy.deepcopy(obj); broken['usage']['total_tokens'] = 7
    rejects(lambda: checks.validate_completion(broken, PROVIDER))
    rejects(lambda: checks.validate_completion(obj, 'wrong-provider'))
    from unittest.mock import patch
    recorded = []
    def interrupted(): raise RuntimeError('operator_interruption')
    with patch.object(checks.http.client, 'HTTPConnection', side_effect=AssertionError('unexpected network')):
        try: checks.run(1, 2, 'fixture', PROVIDER, recorded.append, interrupted)
        except RuntimeError as ex: assert str(ex) == 'operator_interruption'
        else: raise AssertionError('interrupted check passed')
    assert recorded[-1]['event'] == 'failed' and recorded[-1]['outcome'] == 'FAILED'
    assert not any(e['event'] == 'complete' for e in recorded)


def port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def main():
    unit()
    binary = sys.argv[1]
    info = json.loads(subprocess.check_output([binary, '--build-info'], text=True, timeout=5))
    assert info['engine'] == PROVIDER and info['ownership'] == 'synthetic-test-fixture'
    api, management = port(), port()
    while api == management: management = port()
    with tempfile.TemporaryDirectory(prefix='lie-serving-checks-NOT-INFERENCE-') as directory:
        log_path = Path(directory) / 'server.log'; events = []
        with log_path.open('xb') as log:
            proc = subprocess.Popen([binary, '--port', str(api), '--management-port', str(management),
                                     '--model', ':fixture:', '--max-active', '2'], stdout=log, stderr=log)
            def check():
                if proc.poll() is not None: raise RuntimeError('fixture exited: ' + log_path.read_text())
            try:
                deadline = time.monotonic() + 6
                while True:
                    check(); c = http.client.HTTPConnection('127.0.0.1', management, timeout=2)
                    try:
                        c.request('GET', '/actuator/health/readiness'); r = c.getresponse(); r.read()
                        if r.status == 200: break
                    except OSError: pass
                    finally: c.close()
                    if time.monotonic() > deadline: raise TimeoutError('fixture startup')
                    time.sleep(.01)
                profile = {'peer': 'normal', 'peer_expected': 'fixture: 🙂"\\\n��', 'prefill': 'SLOW-PREFILL',
                           'decode': 'SLOW-DECODE', 'blocked': 'LONG'}
                result = checks.run(api, management, 'cpu-test-fixture', PROVIDER, events.append, check, profile)
                assert result['synthetic'] is True and not result['native_batching']
                assert result['final']['cancelled'] == result['final']['completed'] == 3
                assert result['final']['failed'] == 0 and result['final']['executor']['cancel_during_prefill'] == 1
                assert result['final']['executor']['cancel_during_decode'] >= 1
                assert [e['case'] for e in events if e['event'] == 'case_pass'] == ['prefill_cancel', 'decode_cancel', 'backpressure_and_peer']
                assert events[-1]['event'] == 'complete'
                print(json.dumps(result, indent=2))
                # Early EOS cannot be reinterpreted as a successful cancellation.
                missed = []
                try:
                    checks.run(api, management, 'cpu-test-fixture', PROVIDER, missed.append, check,
                               dict(profile, prefill='EMPTY'))
                except checks.Inconclusive: pass
                else: raise AssertionError('missed dispatch window passed')
                assert missed[-1]['event'] == 'failed' and missed[-1]['outcome'] == 'INCONCLUSIVE'
                assert not any(e['event'] == 'complete' for e in missed)
            except BaseException:
                print(json.dumps(events[-20:], indent=2)); raise
            finally:
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=6)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(); raise
                print(log_path.read_text()); assert proc.returncode == 0
    print('HTTP lifecycle checker metadata refusals and real TCP fixtures: PASS (NOT-INFERENCE)')


if __name__ == '__main__': main()
