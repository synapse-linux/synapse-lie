# SPDX-License-Identifier: MIT
"""HOST checking-code fixtures; no model, GPU, remote host or real serving."""

import copy
import hashlib
import importlib.util
import http.server
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


gate = module('recall_gate', ROOT/'tools/strix-point-http-recall-gate.py')
point = module('recall_campaign', ROOT/'tools/strix-point-campaign.py')
NATIVE_CLIENT = os.environ.get('LIE_RECALL_NATIVE_CLIENT')


def config():
    return {'context': 16384, 'rope_scaling': 'native', 'size': 8192,
            'chunk': 256, 'seed': 77, 'request_timeout_seconds': 600,
            'load_timeout_seconds': 900}


def fixture(mode='ar', wrong=False):
    """Deliberately synthetic counters and ledger, never inference evidence."""
    selected = config()
    records = (selected['size']-100)//32
    text = 'Synthetic HOST ledger.\n'
    needles = []
    values = []
    for index in range(3):
        key = 'key_'+hashlib.sha256(f'lie-associative-recall-v1:key:77:{index}'.encode()).hexdigest()[:16]
        value = 'v_'+hashlib.sha256(f'lie-associative-recall-v1:value:77:{index}'.encode()).hexdigest()[:16]
        values.append((key, value))
    positions = (0, records//2, records-1)
    for row in range(records):
        if row in positions:
            index = positions.index(row)
            key, value = values[index]
            needles.append({'region': ('start', 'middle', 'end')[index],
                            'record_index': row, 'prompt_byte_offset': len(text.encode()),
                            'key': key})
            text += f'binding {key} = {value}\n'
        else:
            text += '001 002 003 004 005 006 007 008\n'
    text += 'Return the requested middle key as JSON.'
    expected = [{values[1][0]: values[1][1]}, dict((values[0], values[2]))]
    corpus = {'generator': 'lie-associative-recall-v1', 'seed': 77, 'records': records,
              'prompt_bytes': len(text.encode()), 'needles': needles,
              'position_units': 'zero-based record index and UTF-8 byte offset; not token offsets'}
    body = {'messages': [{'role': 'user', 'content': text}], 'max_tokens': 128}
    followup = 'Return '+values[0][0]+' and '+values[2][0]+' from the original ledger.'
    case = {'id': 'long-context-recall-8192', 'target_prompt_tokens': 8192,
            'expected_prompt_tokens': 100+records*32, 'corpus': corpus, 'body': body,
            'followups': [followup],
            'expected': [{'kind': 'json-object-exact', 'value': e} for e in expected]}
    identity = {'event': 'identity', 'schema': 'synapse-lie.http-bench.v1',
                'model': gate.MODEL_ID, 'server_label': 'LIE', 'cache_policy': 'off',
                'warmups': 0, 'repetitions': 1, 'preset': 'long-context-recall',
                'context_capacity_declared': 16384, 'rope_scaling_declared': 'native',
                'timeout_seconds': 600, 'target_prompt_tokens': [8192], 'corpus_seed': 77,
                'request_options': {}}
    rows = [identity] + [{'event': 'calibration', 'lines': n,
                         'cached_tokens': 0, 'stream_complete': True,
                         'usage': {'prompt_tokens': 100+n*32}} for n in (8, 16, 32)]
    request = {'model': gate.MODEL_ID, 'temperature': 0, **body, 'stream': True,
               'stream_options': {'include_usage': True}}
    for turn in range(2):
        answer = dict(expected[turn])
        if wrong and not turn:
            answer[next(iter(answer))] = 'wrong HOST fixture value'
        assistant = {'role': 'assistant', 'content': json.dumps(answer)}
        pp, tg = case['expected_prompt_tokens']+turn*80, 24+turn*20
        phase = {'schema': 'synapse-lie.request-timings.v1', 'valid': True,
                 'decode_mode': mode, 'prefill_tokens': pp, 'decode_tokens': tg,
                 'prefill_ms': 1000., 'decode_ms': 2000.,
                 'cached_tokens': 0, 'ssd_cached_tokens': 0,
                 'mtp_drafted_tokens': 12 if mode == 'mtp' else 0,
                 'mtp_accepted_tokens': 8 if mode == 'mtp' else 0}
        matched = not wrong or bool(turn)
        rows.append({'event': 'sample', 'case': case['id'], 'turn': turn, 'rep': 0,
                     'warmup': False, 'target_prompt_tokens': 8192 if not turn else None,
                     'corpus': corpus, 'request': request, 'stream_complete': True,
                     'prompt_tokens': pp, 'output_tokens': tg, 'cached_tokens': 0,
                     'usage': {'prompt_tokens': pp, 'completion_tokens': tg},
                     'server_timings': phase, 'finish_reason': 'stop', 'assistant': assistant,
                     'quality': {'kind': 'json-object-exact', 'pass': matched,
                                 'status': 'PASS' if matched else 'FAIL',
                                 'expected': expected[turn], 'output_budget_reached': False}})
        request = {**request, 'messages': body['messages'] +
                   [assistant, {'role': 'user', 'content': followup}]}
    passes = 1 if wrong else 2
    rows.append({'event': 'quality_failed' if wrong else 'complete',
                 'exit_code': 1 if wrong else 0,
                 'quality_summary': {'checks': 2, 'passes': passes, 'warmup_checks': 0,
                                     'warmup_passes': 0, 'exact_match_rate': passes/2}})
    return rows, [case]


class RecallChecks(unittest.TestCase):
    def test_current_profiles_admit_near_capacity_and_reserve_two_turns(self):
        for rope, capacity in gate.PROFILE_LIMITS.items():
            selected = dict(config(), rope_scaling=rope, context=capacity,
                            size=capacity-512, request_timeout_seconds=14400)
            self.assertEqual(gate.settings(selected), selected)
            self.assertEqual(gate.client_timeout(selected), 72030)
            self.assertGreater(gate.container_timeout(selected), gate.client_timeout(selected))
            selected['size'] += 1
            with self.assertRaises(ValueError):
                gate.settings(selected)

    def test_refuse_incomplete_untyped_or_wrong_geometry_settings(self):
        for key in config():
            for bad in (None, True, [], '256'):
                value = dict(config(), **{key: bad})
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                    gate.settings(value)
        value = config(); del value['seed']
        with self.assertRaises(ValueError):
            gate.settings(value)
        for key, bad in (('context', 1048576), ('chunk', 32769), ('seed', 2**64),
                         ('request_timeout_seconds', 14401)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                gate.settings(dict(config(), **{key: bad}))

    def test_commands_use_native_client_exact_capacity_chunk_and_private_ports(self):
        args = types.SimpleNamespace(mode='ar', model='fixture.gguf', predictor=None,
                                     client='native-client', server='native-server')
        server = gate.server_command(args, config(), 41001, 41002)
        client = gate.client_command(args, config(), 41001)
        self.assertNotIn('python', client[0])
        self.assertEqual(server[server.index('--port')+1], '41001')
        self.assertEqual(server[server.index('--management-port')+1], '41002')
        self.assertEqual(server[server.index('--kv-cache-ram-mb')+1], '0')
        self.assertEqual(server[server.index('--prefill-capacity')+1], '256')
        self.assertEqual(server[server.index('--request-timeout-ms')+1], '600000')
        self.assertEqual(client[client.index('--preset')+1], 'long-context-recall')
        self.assertNotIn('--request-options', client)
        self.assertNotIn('--model-mtp', server)
        args.mode, args.predictor = 'mtp', 'fixture-mtp.gguf'
        self.assertIn('fixture-mtp.gguf', gate.server_command(args, config(), 41001, 41002))

    def test_complete_ar_and_actually_proposing_mtp_rows(self):
        for mode in ('ar', 'mtp'):
            rows, cases = fixture(mode)
            proof = gate.validate(rows, cases, config(), mode)
            self.assertEqual(proof['state'], 'PASSED')
            self.assertEqual(proof['quality_summary']['passes'], 2)
            self.assertEqual(proof['mtp_drafted_tokens'], 24 if mode == 'mtp' else 0)

    def test_quality_miss_retains_both_turns_and_is_distinct_from_transport(self):
        rows, cases = fixture(wrong=True)
        proof = gate.validate(rows, cases, config(), 'ar')
        self.assertEqual(proof['state'], 'QUALITY_FAILED')
        self.assertEqual(proof['samples'], 2)
        self.assertEqual(proof['quality_summary']['exact_match_rate'], .5)

    def test_refuse_green_summary_for_wrong_duplicate_or_prose_answers(self):
        rows, cases = fixture()
        expected = cases[0]['expected'][1]['value']
        key, value = next(iter(expected.items()))
        for answer in ('not JSON', json.dumps({key: 'wrong'}),
                       '{'+json.dumps(key)+':'+json.dumps(value)+','+
                       json.dumps(key)+':'+json.dumps(value)+'}'):
            changed = copy.deepcopy(rows)
            changed[5]['assistant']['content'] = answer
            with self.subTest(answer=answer), self.assertRaises(RuntimeError):
                gate.validate(changed, cases, config(), 'ar')

    def test_refuse_changed_history_cached_or_truncated_incomplete_observations(self):
        changes = ((4, 'cached_tokens', 1), (5, 'stream_complete', False),
                   (5, 'prompt_tokens', 8164), (4, 'prompt_tokens', True),
                   (4, 'turn', True), (4, 'rep', True), (4, 'warmup', True))
        for index, key, value in changes:
            rows, cases = fixture(); rows[index][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.validate(rows, cases, config(), 'ar')
        rows, cases = fixture()
        rows[5]['request']['messages'] = rows[5]['request']['messages'][1:]
        with self.assertRaisesRegex(RuntimeError, 'continuation'):
            gate.validate(rows, cases, config(), 'ar')
        rows, cases = fixture(); rows.pop(5)
        with self.assertRaises(RuntimeError):
            gate.validate(rows, cases, config(), 'ar')

    def test_refuse_changed_seed_binding_oracle_and_physical_calibration(self):
        for target in ('seed', 'position', 'binding', 'oracle', 'calibration'):
            rows, cases = fixture()
            if target == 'seed': cases[0]['corpus']['seed'] = 88
            if target == 'position': cases[0]['corpus']['needles'][1]['prompt_byte_offset'] += 1
            if target == 'binding': cases[0]['corpus']['needles'][2]['key'] = 'wrong'
            if target == 'oracle': cases[0]['expected'][1]['value'] = {'key': 'wrong'}
            if target == 'calibration': rows[3]['usage']['prompt_tokens'] += 1
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                gate.validate(rows, cases, config(), 'ar')

    def test_reject_nonfinite_and_duplicate_json_evidence(self):
        for value in ('{"key":1,"key":2}', '{"key":NaN}', '{"key":Infinity}'):
            with self.assertRaises(ValueError):
                gate.strict_json(value)


class OwnedLifecycle(unittest.TestCase):
    def execute(self, wrong=False, timeout=False, readiness_failure=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        rows, cases = fixture(wrong=wrong)
        server, client = unittest.mock.Mock(), unittest.mock.Mock()
        server.poll.return_value = None
        server.wait.return_value = -signal.SIGTERM
        client.poll.return_value = None if timeout else (1 if wrong else 0)
        client.wait.side_effect = ([subprocess.TimeoutExpired('native-client', 3030), -15]
                                  if timeout else [1 if wrong else 0, 1 if wrong else 0])
        args = types.SimpleNamespace(mode='ar', server='native-server', client='native-client',
                                     model='fixture.gguf', predictor=None)

        def launched(argv, **_kwargs):
            if argv[0] == 'native-server': return server
            (root/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (root/'requests.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in cases))
            return client

        with patch.object(gate, 'ROOT', root), patch.object(gate, 'private_ports', return_value=(41001, 41002)), \
             patch.object(gate, 'process_identity', return_value={'pid': 123, 'start_ticks': 456}), \
             patch.object(gate.subprocess, 'Popen', side_effect=launched), \
             patch.object(gate, 'listed_model', side_effect=RuntimeError('fixture load failure')
                          if readiness_failure else None, return_value=True):
            code = gate.run(args, config())
        result = json.loads((root/'http-recall-result.json').read_text())
        return root, result, code, server, client

    def test_actual_quality_exit_and_all_artifacts_retained(self):
        root, result, code, server, client = self.execute(wrong=True)
        self.assertEqual((code, result['client_exit_code'], result['state']), (1, 1, 'QUALITY_FAILED'))
        self.assertEqual(result['quality_summary']['passes'], 1)
        self.assertEqual(result['requests_sha256'], gate.sha(root/'requests.jsonl'))
        self.assertEqual(result['measurements_sha256'], gate.sha(root/'measurements.jsonl'))
        server.terminate.assert_called_once()
        client.terminate.assert_not_called()

    def test_timeout_preserves_actual_retirement_exit_and_partial_files(self):
        root, result, code, server, client = self.execute(timeout=True)
        self.assertEqual((code, result['state'], result['client_exit_code']), (1, 'FAILED', -15))
        self.assertTrue(result['client_timed_out'])
        self.assertTrue((root/'measurements.jsonl').is_file())
        client.terminate.assert_called_once()
        server.terminate.assert_called_once()

    def test_model_readiness_failure_still_retires_only_the_owned_server(self):
        _root, result, code, server, client = self.execute(readiness_failure=True)
        self.assertEqual((code, result['state']), (1, 'FAILED'))
        self.assertNotIn('client_exit_code', result)
        client.wait.assert_not_called()
        server.terminate.assert_called_once()

    def test_owned_unresponsive_child_is_killed_and_actual_exit_retained(self):
        child = unittest.mock.Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('owned', 15), -9]
        self.assertEqual(gate.retire(child), -9)
        child.terminate.assert_called_once()
        child.kill.assert_called_once()


class CampaignBinding(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base/'job'; self.root.mkdir()
        (self.root/'manifest.json').write_text('{}')
        source = ROOT/'tools/strix-point-http-recall-gate.py'
        (self.root/'http-recall-gate.py').write_bytes(source.read_bytes())
        (self.root/'http-recall-settings.json').write_text(json.dumps(config()))
        self.patch_base = patch.object(point, 'BASE', self.base)
        self.patch_base.start(); self.addCleanup(self.patch_base.stop)
        self.campaign = point.Campaign(self.root, {'authorization': 'HOST fixture; no grant'})
        self.campaign.m.update(stack='rocm10-fedora43', transport='distrobox',
                               bench_profile='modern-http-recall', decode_mode='ar',
                               bundle=str(self.base), http_recall=config(),
                               model_plan={'files': [{'name': 'fixture.gguf'}]},
                               http_recall_gate_sha256=point.sha(self.root/'http-recall-gate.py'),
                               http_recall_settings_sha256=point.sha(self.root/'http-recall-settings.json'))

    def child(self, command, _bundle, timeout, _model):
        self.assertEqual(command[:3], ['/usr/bin/python3', '-B', '/work/http-recall-gate.py'])
        self.assertEqual(timeout, gate.container_timeout(config()))
        rows, cases = fixture()
        for name, value in (('measurements.jsonl', rows), ('requests.jsonl', cases)):
            (self.root/name).write_text(''.join(json.dumps(r)+'\n' for r in value))
        result = {'schema': 'synapse-lie.point-http-recall-original.v1', 'mode': 'ar',
                  'settings': config(), 'client_exit_code': 0, 'server_exit_code': -15,
                  'cleanup_errors': [], **gate.validate(rows, cases, config(), 'ar'),
                  'measurements_sha256': point.sha(self.root/'measurements.jsonl'),
                  'requests_sha256': point.sha(self.root/'requests.jsonl')}
        (self.root/'http-recall-result.json').write_text(json.dumps(result))

    def run_campaign(self, child=None):
        with patch.object(self.campaign, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(self.campaign, 'check_model_after') as after, \
             patch.object(self.campaign, 'run_container', side_effect=child or self.child):
            self.campaign.bench()
        return after

    def test_bind_settings_native_complete_rows_and_corpus_hashes(self):
        after = self.run_campaign()
        self.assertEqual(self.campaign.r['bench_result']['profile'], 'modern-http-recall')
        self.assertEqual(self.campaign.r['bench_result']['quality_summary']['passes'], 2)
        self.assertEqual(len(self.campaign.r['http_recall_partial']), 3)
        after.assert_called_once()

    def test_child_failure_keeps_partial_quality_evidence_and_checks_model_stats(self):
        def failed(*args):
            self.child(*args)
            raise RuntimeError('mocked native exit1')
        with patch.object(self.campaign, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(self.campaign, 'check_model_after') as after, \
             patch.object(self.campaign, 'run_container', side_effect=failed), \
             self.assertRaisesRegex(RuntimeError, 'native exit1'):
            self.campaign.bench()
        self.assertEqual(len(self.campaign.r['http_recall_partial']), 3)
        after.assert_called_once()

    def test_wrong_helper_settings_or_large_memory_budget_refuse_before_model_access(self):
        for what in ('helper', 'settings', 'memory', 'predictor'):
            with self.subTest(what=what):
                manifest = copy.deepcopy(self.campaign.m)
                if what == 'helper': self.campaign.m['http_recall_gate_sha256'] = '0'*64
                if what == 'settings': self.campaign.m['http_recall_settings_sha256'] = '0'*64
                if what == 'memory':
                    large = dict(config(), context=1048576, rope_scaling='yarn4', size=1048064)
                    path = self.root/'http-recall-settings.json'; path.write_text(json.dumps(large))
                    self.campaign.m.update(http_recall=large, http_recall_settings_sha256=point.sha(path))
                if what == 'predictor': self.campaign.m['predictor_plan'] = {}
                with patch.object(self.campaign, 'verified_model') as model, \
                     patch.object(self.campaign, 'run_container') as child, self.assertRaises(ValueError):
                    self.campaign.bench()
                model.assert_not_called(); child.assert_not_called()
                self.campaign.m = manifest
                (self.root/'http-recall-settings.json').write_text(json.dumps(config()))


@unittest.skipUnless(NATIVE_CLIENT, 'Optional native-client HOST wire check')
class NativeClientWire(unittest.TestCase):
    """Real C client and loopback bytes; counters/replies remain CPU fixtures."""
    def exercise(self, wrong=False):
        selected = config()
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                messages = body['messages']
                ledger = messages[0]['content']
                bindings = dict(re.findall(r'^binding (key_[a-f0-9]{16}) = (v_[a-f0-9]{16})$',
                                           ledger, re.MULTILINE))
                records = sum(bool(re.fullmatch(r'\d{3}(?: \d{3}){7}', line)) or
                              line.startswith('binding ') for line in ledger.splitlines())
                budget = body['max_tokens']
                question = messages[-1]['content'].rsplit('\n', 1)[-1]
                keys = re.findall(r'key_[a-f0-9]{16}', question)
                answer = {key: bindings[key] for key in keys}
                if wrong and budget != 1 and len(messages) == 1:
                    answer[keys[0]] = 'wrong HOST fixture value'
                content = '{' if budget == 1 else json.dumps(answer)
                pp = 100 + records*32 + (len(messages)-1)*40
                tg = 1 if budget == 1 else 24 if len(messages) == 1 else 44
                usage = {'prompt_tokens': pp, 'completion_tokens': tg, 'total_tokens': pp+tg,
                         'prompt_tokens_details': {'cached_tokens': 0}}
                timing = {'schema': 'synapse-lie.request-timings.v1',
                          'scope': 'synchronous_executor_calls', 'valid': True,
                          'decode_mode': 'ar', 'prefill_tokens': pp, 'decode_tokens': tg,
                          'prefill_calls': 1, 'decode_calls': tg, 'cached_tokens': 0,
                          'ssd_cached_tokens': 0, 'prefill_ms': .05, 'decode_ms': .1,
                          'cache_capture_ms': 0, 'cache_restore_ms': 0, 'ssd_read_ms': 0}
                base = {'id': 'chatcmpl-HOST-recall-fixture', 'object': 'chat.completion.chunk',
                        'created': 0, 'model': gate.MODEL_ID}
                chunks = [{**base, 'choices': [{'index': 0, 'delta':
                          {'role': 'assistant', 'content': content}, 'finish_reason': None}]},
                          {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason':
                                               'length' if tg == budget else 'stop'}],
                           'usage': usage, 'lie_timings': timing}]
                data = ''.join('data: '+json.dumps(row)+'\n\n' for row in chunks)+'data: [DONE]\n\n'
                payload = data.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                args = types.SimpleNamespace(client=str(Path(NATIVE_CLIENT).resolve()))
                with patch.object(gate, 'ROOT', root):
                    argv = gate.client_command(args, selected, server.server_port)
                child = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                destination = os.environ.get('LIE_RECALL_NATIVE_EVIDENCE')
                if destination:
                    evidence = Path(destination)/('quality-failed' if wrong else 'passed')
                    evidence.mkdir(parents=True, exist_ok=False)
                    (evidence/'client.stdout.log').write_bytes(child.stdout)
                    (evidence/'client.stderr.log').write_bytes(child.stderr)
                    (evidence/'fixture-wire.json').write_text(json.dumps({
                        'classification': 'HOST_SYNTHETIC_HTTP_NOT_MODEL_INFERENCE',
                        'client_argv': argv, 'client_exit_code': child.returncode,
                        'actual_fixture_requests': requests}, indent=2)+'\n')
                    for name in ('measurements.jsonl', 'requests.jsonl'):
                        if (root/name).is_file():
                            (evidence/name).write_bytes((root/name).read_bytes())
                self.assertEqual(child.returncode, 1 if wrong else 0, child.stderr.decode())
                for diagnostic in (b'AddressSanitizer', b'LeakSanitizer', b'runtime error:'):
                    self.assertNotIn(diagnostic, child.stderr, child.stderr.decode())
                rows = gate.json_lines(root/'measurements.jsonl', 32*1024*1024)
                cases = gate.json_lines(root/'requests.jsonl', 8*1024*1024)
                self.assertEqual(len(requests), 5)
                self.assertTrue(all('expected' not in body and 'corpus' not in body for body in requests))
                proof = gate.validate(rows, cases, selected, 'ar')
                self.assertEqual(proof['state'], 'QUALITY_FAILED' if wrong else 'PASSED')
                self.assertEqual(rows[5]['request'], requests[-1])
            finally:
                server.shutdown(); thread.join(timeout=5); server.server_close()
                self.assertFalse(thread.is_alive())

    def test_actual_native_client_corpus_and_complete_continuation(self):
        self.exercise()

    def test_actual_native_quality_failure_preserves_the_remaining_turn(self):
        self.exercise(wrong=True)


if __name__ == '__main__':
    unittest.main()
