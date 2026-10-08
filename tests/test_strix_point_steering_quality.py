# SPDX-License-Identifier: MIT
"""HOST checking fixtures, including the real C HTTP client; never inference."""
import copy
import http.server
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('steering_quality', ROOT/'tools/strix-point-steering-quality-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
DATA = json.loads((ROOT/'tests/fixtures/steering-conciseness-v1.json').read_text())
NATIVE = os.environ.get('LIE_STEERING_NATIVE_CLIENT')


def config():
    return {'model_id': 'HOST-fixture', 'fingerprint': 'HOST-fixture',
            'context': 8192, 'chunk': 256, 'seed': 77, 'output_tokens': 256,
            'request_timeout_seconds': 30, 'bank_sha256': '1'*64}


def synthetic_reply(body, identifier):
    selected = config()
    question = body['messages'][0]['content']
    held = next(h for h in DATA['held_out'] if question.startswith(h['question']))
    scale = body.get('dir_steering_plan', [{'ffn': 0}])[0]['ffn']
    words = {-1: 10, -.5: 15, 0: 20, .5: 22, 1: 26, 2: 30}[scale]
    text = json.dumps({'answer': held['answer'], 'explanation': ' '.join(['HOST']*words)})
    pp, tg = 120, 48
    usage = {'prompt_tokens': pp, 'completion_tokens': tg, 'total_tokens': pp+tg,
             'prompt_tokens_details': {'cached_tokens': 0}}
    phase = {'schema': 'synapse-lie.request-timings.v1', 'scope': 'synchronous_executor_calls',
             'valid': True, 'decode_mode': 'ar', 'prefill_tokens': pp, 'decode_tokens': tg,
             'prefill_calls': 1, 'decode_calls': tg+1, 'cached_tokens': 0, 'ssd_cached_tokens': 0,
             'mtp_drafted_tokens': 0, 'mtp_accepted_tokens': 0, 'output_token_limit': selected['output_tokens'],
             'prefill_ms': 10., 'decode_ms': 20., 'cache_capture_ms': 0., 'cache_restore_ms': 0., 'ssd_read_ms': 0.}
    base = {'id': identifier, 'object': 'chat.completion.chunk', 'created': 0,
            'model': selected['model_id'], 'system_fingerprint': selected['fingerprint']}
    chunks = [{**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': text}, 'finish_reason': None}]},
              {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
              {**base, 'choices': [], 'usage': usage, 'lie_timings': phase}]
    snapshot = {'id': identifier, 'object': 'synapse-lie.steering', 'choice': 0, 'pending': False,
                'policy': None, 'schedule': None}
    if 'dir_steering_plan' in body:
        snapshot['policy'] = {'ffn': scale, 'attention': 0, 'completed_positions': pp+tg,
                              'history_epochs': 1, 'combined_scope_sha256': '2'*64, 'image_scope_sha256': '3'*64}
        snapshot['schedule'] = {'count': 1, 'completed': 1, 'applied': 1, 'terminal': True,
                                'steps': [{'position': 0, 'ffn': scale, 'attention': 0,
                                           'attempted': True, 'applied': True, 'status': 0, 'actual_position': 0}]}
    sample = {'event': 'sample', 'turn': 0, 'rep': 0, 'warmup': False, 'request': body,
              'response_chunks': chunks, 'stream_complete': True, 'usage': usage,
              'server_timings': phase, 'finish_reason': 'stop', 'prompt_tokens': pp, 'output_tokens': tg,
              'cached_tokens': 0, 'assistant': {'role': 'assistant', 'content': text}}
    return sample, snapshot


def fixture():
    selected = config()
    cases = {p: gate.requests(DATA, selected, p) for p in ('absent', 'bank')}
    rows, snapshots = {}, {}
    for phase in cases:
        identity = {'event': 'identity', 'schema': 'synapse-lie.http-bench.v1', 'model': selected['model_id'],
                    'server_label': 'LIE', 'cache_policy': 'off', 'warmups': 0, 'repetitions': 1,
                    'request_options': {}, 'context_capacity_declared': selected['context'],
                    'rope_scaling_declared': 'native', 'timeout_seconds': 30,
                    'target_prompt_tokens': None, 'corpus_seed': None}
        rows[phase] = [identity]
        for case in cases[phase]:
            body = {'model': selected['model_id'], **case['body'], 'stream': True, 'stream_options': {'include_usage': True}}
            sample, snap = synthetic_reply(body, 'chat-'+case['id'])
            sample['case'] = case['id']
            rows[phase].append(sample); snapshots[case['id']] = snap
        rows[phase].append({'event': 'complete', 'exit_code': 0})
    return rows, cases, snapshots


def change_answer(row, text):
    row['assistant']['content'] = text
    row['response_chunks'][0]['choices'][0]['delta']['content'] = text


class Review(unittest.TestCase):
    def review(self, rows, cases, snapshots):
        return gate.validate(rows, cases, snapshots, config(), DATA, {'absent': 0, 'bank': 0})

    def test_full_matched_controls_and_predeclared_effect(self):
        proof = self.review(*fixture())
        self.assertEqual(proof['state'], 'PASSED')
        self.assertEqual(proof['samples'], 70)
        self.assertEqual(proof['correct_answers'], 70)
        self.assertEqual(proof['zero_parity_cases'], 10)
        self.assertEqual(proof['conciseness_effect']['negative_ratio_median'], .5)
        self.assertEqual(proof['conciseness_effect']['positive_ratio_median'], 1.5)

    def test_bad_content_is_quality_failure_with_all_samples_preserved(self):
        for text in ('not JSON', '{"answer":"129","answer":"129","explanation":"one"}',
                     '{"answer":"wrong","explanation":"one"}', '{"answer":"129","explanation":"!!!"}'):
            rows, cases, snapshots = fixture()
            change_answer(rows['bank'][1], text)
            proof = self.review(rows, cases, snapshots)
            self.assertEqual(proof['state'], 'QUALITY_FAILED')
            self.assertEqual(proof['samples'], 70)
            self.assertFalse(proof['conciseness_effect']['evaluated'])

    def test_no_effect_is_inconclusive_quality_failure_even_when_answers_correct(self):
        rows, cases, snapshots = fixture()
        for row in rows['bank'][1:-1]:
            source = rows['absent'][1+int(row['case'][-2:])]
            change_answer(row, source['assistant']['content'])
        proof = self.review(rows, cases, snapshots)
        self.assertEqual(proof['correct_answers'], 70)
        self.assertEqual(proof['state'], 'QUALITY_FAILED')
        self.assertFalse(proof['conciseness_effect']['passed'])

    def test_zero_parity_failure_suppresses_style_acceptance(self):
        rows, cases, snapshots = fixture()
        row = rows['bank'][21]
        answer = json.loads(row['assistant']['content']); answer['explanation'] += ' changed'
        change_answer(row, json.dumps(answer))
        proof = self.review(rows, cases, snapshots)
        self.assertEqual(proof['zero_parity_cases'], 9)
        self.assertEqual(proof['state'], 'QUALITY_FAILED')

    def test_refuse_mismatched_wire_and_duplicate_usage_or_identity(self):
        for what in ('answer', 'id', 'usage', 'finish', 'fingerprint', 'tool'):
            rows, cases, snapshots = fixture(); row = rows['bank'][1]
            if what == 'answer': row['assistant']['content'] = 'different assembled text'
            if what == 'id': row['response_chunks'][1]['id'] = 'other'
            if what == 'usage': row['response_chunks'].append(copy.deepcopy(row['response_chunks'][-1]))
            if what == 'finish': row['response_chunks'].insert(2, copy.deepcopy(row['response_chunks'][1]))
            if what == 'fingerprint': row['response_chunks'][0]['system_fingerprint'] = 'other'
            if what == 'tool': row['response_chunks'][0]['choices'][0]['delta']['tool_calls'] = []
            with self.subTest(what=what), self.assertRaises(RuntimeError):
                self.review(rows, cases, snapshots)

    def test_refuse_changed_workload_incomplete_cohort_or_failed_native_exit(self):
        rows, cases, snapshots = fixture()
        for what in ('case', 'request', 'count', 'exit', 'snapshot'):
            changed, wanted, snaps = copy.deepcopy((rows, cases, snapshots))
            if what == 'case': wanted['bank'][0]['body']['seed'] += 1
            if what == 'request': changed['bank'][1]['request']['seed'] += 1
            if what == 'count': changed['bank'].pop(1)
            if what == 'exit': changed['bank'][-1]['exit_code'] = 1
            if what == 'snapshot': snaps.pop('minus1-held-00')
            with self.subTest(what=what), self.assertRaises(RuntimeError): self.review(changed, wanted, snaps)
        with self.assertRaises(RuntimeError):
            gate.validate(rows, cases, snapshots, config(), DATA, {'absent': 0, 'bank': 1})

    def test_declared_scale_cannot_substitute_for_actual_boundary_application(self):
        for key, value in (('applied', False), ('attempted', False), ('actual_position', 1), ('status', 1), ('ffn', 0), ('status', False)):
            rows, cases, snapshots = fixture()
            snapshots['minus1-held-00']['schedule']['steps'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.review(rows, cases, snapshots)

    def test_refuse_cached_speculative_or_untyped_counts(self):
        for key, value in (('cached_tokens', 1), ('ssd_cached_tokens', 1), ('mtp_drafted_tokens', 1),
                           ('mtp_accepted_tokens', 1), ('prefill_calls', True), ('prefill_ms', float('nan'))):
            rows, cases, snapshots = fixture()
            rows['bank'][1]['server_timings'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.review(rows, cases, snapshots)

    def test_complete_length_stop_retained_as_quality_failure(self):
        rows, cases, snapshots = fixture(); row = rows['bank'][1]
        row['finish_reason'] = 'length'; row['response_chunks'][1]['choices'][0]['finish_reason'] = 'length'
        row['server_timings']['decode_calls'] = row['output_tokens']
        proof = self.review(rows, cases, snapshots)
        self.assertEqual(proof['state'], 'QUALITY_FAILED'); self.assertFalse(proof['natural_stops'])

    def test_training_and_held_out_overlap_or_duplicate_is_refused(self):
        for what in ('overlap', 'duplicate', 'pair', 'instruction'):
            data = copy.deepcopy(DATA)
            if what == 'overlap': data['held_out'][0]['question'] = data['training_questions'][0]
            if what == 'duplicate': data['held_out'][1]['id'] = data['held_out'][0]['id']
            if what == 'pair': data['training_questions'].pop()
            if what == 'instruction': data['target_instruction'] = data['contrast_instruction']
            with self.subTest(what=what), self.assertRaises(ValueError): gate.corpus(data)

    def test_owned_preparation_is_exclusive_and_read_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'prepared'; gate.prepare(root, DATA, config())
            for side in ('target', 'contrast'):
                self.assertEqual(len((root/(side+'-prompts.txt')).read_text().splitlines()), 100)
            with self.assertRaises(FileExistsError): gate.prepare(root, DATA, config())
            linked = root/'link'; linked.symlink_to(root/'target-prompts.txt')
            with self.assertRaises(RuntimeError): gate.read(linked)

    def test_typed_bounds_and_strict_json_refuse_ambiguous_generation(self):
        for name, bad in (('seed', 2**63), ('seed', True), ('bank_sha256', 'unknown'), ('chunk', 8193)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.settings({**config(), name: bad})
        for text in ('{"seed":77,"seed":78}', '{"temperature":NaN}'):
            with self.assertRaises((ValueError, RuntimeError)): gate.strict(text)
        rows, cases, snapshots = fixture()
        rows['bank'][1]['request']['temperature'] = False
        with self.assertRaises(RuntimeError): self.review(rows, cases, snapshots)


@unittest.skipUnless(NATIVE, 'Optional real native C HTTP client HOST check')
class NativeClient(unittest.TestCase):
    def test_real_native_client_keeps_all_controls_schema_plan_and_full_sse(self):
        rows, cases, snapshots, counter, handler_errors = {}, {}, {}, [], []
        selected = config()
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    counter.append(body)
                    sample, snap = synthetic_reply(body, 'chat-HOST-'+str(len(counter)))
                    matched = [c for p in ('absent', 'bank') for c in gate.requests(DATA, selected, p)
                               if {'model': selected['model_id'], **c['body'], 'stream': True, 'stream_options': {'include_usage': True}} == body]
                    if len(matched) != 1: raise RuntimeError('Changed native request')
                    snapshots[matched[0]['id']] = snap
                    payload = (''.join('data: '+json.dumps(c)+'\n\n' for c in sample['response_chunks'])+'data: [DONE]\n\n').encode()
                    self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
                except BaseException as error:
                    handler_errors.append(repr(error)); self.close_connection = True
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)/'prepared'; gate.prepare(root, DATA, selected)
                exits = {}
                for phase in ('absent', 'bank'):
                    directory = root/phase
                    run = subprocess.run(gate.client_command(NATIVE, selected, server.server_port, directory), capture_output=True, timeout=90)
                    self.assertEqual(run.returncode, 0, run.stderr.decode())
                    exits[phase] = run.returncode
                    rows[phase] = [gate.strict(line) for line in (directory/'measurements.jsonl').read_text().splitlines()]
                    cases[phase] = [gate.strict(line) for line in (directory/'requests.jsonl').read_text().splitlines()]
                self.assertFalse(handler_errors, handler_errors)
                self.assertEqual(len(counter), 70)
                self.assertEqual(gate.validate(rows, cases, snapshots, selected, DATA, exits)['state'], 'PASSED')
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__': unittest.main()
