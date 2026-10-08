# SPDX-License-Identifier: MIT
"""Offline protocol/refusal oracles. NOT-INFERENCE; no sockets, model or GPU."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


gate = module('tool_transitions', 'tools/strix-point-tool-transition-gate.py')
wire = module('tool_transition_wire', 'tools/strix-point-http-gate.py')
point = module('tool_transition_point', 'tools/strix-point-campaign.py')


def sse(chunks):
    return ''.join('data: '+('[DONE]' if x == '[DONE]' else json.dumps(x))+'\n\n' for x in chunks)


def chat(text, keys, identity='cpu-fixture'):
    calls = [{'id': identity+'-'+str(i), 'type': 'function', 'function': {
        'name': 'get_value', 'arguments': json.dumps({'key': key})}} for i, key in enumerate(keys)]
    return {'choices': [{'index': 0, 'finish_reason': 'tool_calls' if keys else 'stop', 'message': {
        'role': 'assistant', 'content': text or None, 'tool_calls': calls}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 16, 'total_tokens': 26},
        'lie_timings': {'valid': True, 'decode_mode': 'ar', 'mtp_drafted_tokens': 0, 'mtp_accepted_tokens': 0}}


def chat_chunks(value):
    choice = value['choices'][0]
    chunks = []
    if choice['message']['content']:
        chunks.append({'choices': [{'index': 0, 'delta': {'content': choice['message']['content']}}]})
    for index, call in enumerate(choice['message']['tool_calls']):
        chunks.append({'choices': [{'index': 0, 'delta': {'tool_calls': [{
            'index': index, 'id': call['id'], 'type': 'function',
            'function': {'name': call['function']['name'], 'arguments': ''}}]}}]})
        args = call['function']['arguments']
        for piece in (args[:4], args[4:]):
            chunks.append({'choices': [{'index': 0, 'delta': {'tool_calls': [{
                'index': index, 'function': {'arguments': piece}}]}}]})
    chunks += [{'choices': [{'index': 0, 'delta': {}, 'finish_reason': choice['finish_reason']}]},
               {'choices': [], 'usage': value['usage'], 'lie_timings': value['lie_timings']}, '[DONE]']
    return chunks


def response(value, identity='cpu-fixture'):
    message = value['choices'][0]['message']
    items = []
    if message['content']:
        items.append({'type': 'message', 'status': 'completed', 'role': 'assistant', 'id': 'msg-'+identity,
                      'content': [{'type': 'output_text', 'text': message['content']}]})
    for index, call in enumerate(message['tool_calls']):
        items.append(dict(type='function_call', status='completed', id='fc-'+identity+'-'+str(index),
                          call_id=call['id'], **call['function']))
    return {'id': identity, 'status': 'completed', 'output': items,
            'usage': {'input_tokens': 10, 'output_tokens': 16, 'total_tokens': 26}}


def response_chunks(value):
    rows = [{'type': 'response.created', 'response': {'id': value['id']}}]
    for index, item in enumerate(value['output']):
        if item['type'] == 'message':
            rows += [{'type': 'response.output_item.added', 'output_index': index, 'item': dict(item, status='in_progress')},
                     {'type': 'response.output_text.delta', 'delta': item['content'][0]['text']},
                     {'type': 'response.output_item.done', 'output_index': index, 'item': item}]
        else:
            rows.append({'type': 'response.output_item.added', 'output_index': index,
                         'item': dict(item, status='in_progress', arguments='')})
            for piece in (item['arguments'][:4], item['arguments'][4:]):
                rows.append({'type': 'response.function_call_arguments.delta', 'output_index': index,
                             'item_id': item['id'], 'delta': piece})
            rows += [{'type': 'response.function_call_arguments.done', 'output_index': index,
                      'item_id': item['id'], 'name': item['name'], 'arguments': item['arguments']},
                     {'type': 'response.output_item.done', 'output_index': index, 'item': item}]
    rows.append({'type': 'response.completed', 'response': value})
    for sequence, row in enumerate(rows): row['sequence_number'] = sequence
    return rows


class ProtocolFixture:
    """Independent canned output plus call/result correlation state."""
    def __init__(self):
        self.number = 0
        self.retained = {}
        self.requests = []
        self.correlations = 0
        self.drop_prose = False
        self.swap_values = False
        self.refusal_does_work = False
        self.model_work = 0
        self.mode = 'ar'

    def exchange(self, api, path, payload=None, method=None):
        del api, method
        self.requests.append((path, copy.deepcopy(payload)))
        if path == '/actuator/llm':
            return {'status': 200, 'body': json.dumps({'ready': True, 'scheduler': {'active': 0, 'queued': 0,
                    'executor': dict(phase='none', **{k: self.model_work for k in
                        ('prefill_started', 'prefill_returned', 'decode_started', 'decode_returned',
                         'mtp_drafted_tokens', 'mtp_accepted_tokens')})}})}
        if payload is None:
            identity = path.split('/')[-1].split('?')[0]
            return {'status': 200, 'body': self.retained[identity]['wire']}
        self.number += 1
        identity = 'CPU-NOT-INFERENCE-'+str(self.number)
        responses = path == '/v1/responses'
        self.assert_controls(payload, responses)
        history = payload.get('input' if responses else 'messages')
        if type(history) is list:
            pending, values = {}, {}
            if payload.get('previous_response_id'):
                for c in self.retained[payload['previous_response_id']]['calls']:
                    pending[c['id']] = c['parsed_arguments']['key']
            for item in history:
                if responses and item.get('type') == 'function_call':
                    assert item['call_id'] not in pending
                    pending[item['call_id']] = json.loads(item['arguments'])['key']
                elif not responses and item.get('tool_calls'):
                    for c in item['tool_calls']:
                        assert c['id'] not in pending
                        pending[c['id']] = json.loads(c['function']['arguments'])['key']
                elif item.get('type') == 'function_call_output' or item.get('role') == 'tool':
                    call_id = item['call_id' if responses else 'tool_call_id']
                    if call_id not in pending:
                        self.model_work += bool(self.refusal_does_work)
                        return {'status': 400, 'body': '{"error":{"message":"unmatched function result"}}'}
                    values[pending.pop(call_id)] = json.loads(item['output' if responses else 'content'])['value']
                elif item.get('role') == 'user' and pending:
                    self.model_work += bool(self.refusal_does_work)
                    return {'status': 400, 'body': '{"error":{"message":"missing function result"}}'}
            if values:
                assert set(values) == {'alpha', 'beta'}
                # Gate submits results in reverse call order, without embedding
                # expected answers in its question or response schema.
                assert list(values) == ['beta', 'alpha']
                self.correlations += 1
                if self.swap_values: values = {'alpha': values['beta'], 'beta': values['alpha']}
                text, keys = json.dumps(values), ()
            else:
                prompt = history[-1]['content']
                text, keys = self.answer(prompt)
        else:
            text, keys = self.answer(history)
        result = chat(text, keys, identity)
        self.model_work += 1
        result['lie_timings'].update(decode_mode=self.mode,
                                     mtp_drafted_tokens=2 if self.mode == 'mtp' else 0,
                                     mtp_accepted_tokens=1 if self.mode == 'mtp' else 0)
        if responses:
            final = response(result, identity)
            chunks = response_chunks(final)
            body = sse(chunks) if payload['stream'] else json.dumps(final)
            if payload.get('store'):
                self.retained[identity] = {'wire': body, 'calls': gate.normalized(final, True)['calls']}
        else:
            body = sse(chat_chunks(result)) if payload['stream'] else json.dumps(result)
        return {'status': 200, 'body': body}

    def answer(self, prompt):
        if prompt.startswith('Do not call'): return 'READY', ()
        if prompt.startswith('First write'): return '' if self.drop_prose else 'Checking values.', ('alpha',)
        if prompt.startswith('Call get_value exactly twice'): return '', ('alpha', 'beta')
        assert prompt.startswith('Call get_value once'), prompt
        return '', ('alpha',)

    def assert_controls(self, payload, responses):
        assert payload['model'] == 'CPU-NOT-INFERENCE' and payload['seed'] == 123
        assert payload['max_output_tokens' if responses else 'max_tokens'] == 512
        tool = payload['tools'][0] if responses else payload['tools'][0]['function']
        assert tool['strict'] is True
        if payload.get('response_format') or payload.get('text'):
            fmt = payload.get('response_format') or payload['text']['format']
            assert fmt == {'type': 'json_object'}  # No semantic answer in schema.


class Tests(unittest.TestCase):
    def test_complete_inventory_matches_supervisor(self):
        self.assertEqual(len(gate.CHECKS), 71)
        self.assertEqual(gate.CHECKS, point.HTTP_TOOL_TRANSITION_CHECKS)

    def test_complete_offline_gate_and_reversed_result_mapping(self):
        fixture = ProtocolFixture()
        with tempfile.TemporaryDirectory() as temp:
            result = gate.transitions_gate(1, 'CPU-NOT-INFERENCE', fixture.exchange, wire.events, Path(temp),
                                           management=2, mode='ar')
            self.assertEqual(result['state'], 'PASSED')
            self.assertEqual(set(result['passed']), gate.CHECKS)
            self.assertEqual(set(result['witnesses']), gate.CHECKS)
            self.assertEqual(fixture.correlations, 12)
            self.assertEqual(len(fixture.requests), 87)
            self.assertTrue(result['refusals_before_forward_verified'])
            self.assertEqual(json.loads((Path(temp)/'http-tool-transitions-result.json').read_text()), result)

    def test_quality_failure_retains_partial_original_shaped_receipt(self):
        for flag, error in [('drop_prose', 'omitted requested prose'), ('swap_values', 'confused correlated')]:
            fixture = ProtocolFixture(); setattr(fixture, flag, True)
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temp:
                with self.assertRaisesRegex(RuntimeError, error):
                    gate.transitions_gate(1, 'CPU-NOT-INFERENCE', fixture.exchange, wire.events, Path(temp),
                                          management=2, mode='ar')
                result = json.loads((Path(temp)/'http-tool-transitions-result.json').read_text())
                self.assertEqual(result['state'], 'FAILED')
                self.assertEqual(result['failure_kind'], 'model_quality')
                self.assertEqual(result['current_check'], 'greedy_chat_'+(
                    'prose-call_json' if flag == 'drop_prose' else 'correlated_results_json'))
                self.assertTrue(result['passed'])
                self.assertNotEqual(set(result['passed']), gate.CHECKS)

    def test_model_work_on_refused_history_is_a_failure(self):
        fixture = ProtocolFixture(); fixture.refusal_does_work = True
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'performed model work'):
                gate.transitions_gate(1, 'CPU-NOT-INFERENCE', fixture.exchange, wire.events, Path(temp),
                                      management=2, mode='ar')

    def test_mtp_requires_actual_proposals_in_selected_chat_witnesses(self):
        fixture = ProtocolFixture(); fixture.mode = 'mtp'
        with tempfile.TemporaryDirectory() as temp:
            result = gate.transitions_gate(1, 'CPU-NOT-INFERENCE', fixture.exchange, wire.events, Path(temp),
                                           management=2, mode='mtp')
            self.assertGreater(result['observed_chat_drafted_tokens'], 0)
        fixture = ProtocolFixture()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'selected decode-mode counters'):
                gate.transitions_gate(1, 'CPU-NOT-INFERENCE', fixture.exchange, wire.events, Path(temp),
                                      management=2, mode='mtp')

    def test_strict_independent_argument_and_usage_validation(self):
        value = chat('Checking.', ('alpha', 'beta'))
        self.assertEqual(len(gate.normalized(value, False)['calls']), 2)
        mutations = (
            lambda x: x['choices'][0].update(index=False),
            lambda x: x['choices'][0]['message'].update(content=0),
            lambda x: x['usage'].update(completion_tokens=True),
            lambda x: x['usage'].update(total_tokens=27),
            lambda x: x['choices'][0]['message']['tool_calls'][1].update(id=x['choices'][0]['message']['tool_calls'][0]['id']),
            lambda x: x['choices'][0]['message']['tool_calls'][0]['function'].update(arguments='{"key":"alpha","key":"beta"}'),
        )
        for mutate in mutations:
            bad = copy.deepcopy(value); mutate(bad)
            with self.assertRaises(RuntimeError): gate.normalized(bad, False)
        for bad in ('[]', '{"x":NaN}', '{"x":1,"x":2}', 'invalid'):
            with self.assertRaises(RuntimeError): gate.object_json(bad)

    def test_chat_incremental_indices_identities_order_and_terminal(self):
        chunks = chat_chunks(chat('Checking.', ('alpha', 'beta')))
        self.assertEqual(gate.chat_stream(chunks)['text'], 'Checking.')
        variants = []
        bad = copy.deepcopy(chunks); bad[1]['choices'][0]['delta']['tool_calls'][0]['index'] = True; variants.append(bad)
        bad = copy.deepcopy(chunks); bad[2]['choices'][0]['delta']['tool_calls'][0]['index'] = 2; variants.append(bad)
        bad = copy.deepcopy(chunks); bad.insert(3, bad[0]); variants.append(bad)
        bad = copy.deepcopy(chunks); bad.insert(-2, bad[-3]); variants.append(bad)
        variants += [chunks[:-1], chunks+['[DONE]']]
        for bad in variants:
            with self.assertRaises(RuntimeError): gate.chat_stream(bad)

    def test_responses_incremental_item_identity_done_and_terminal(self):
        chunks = response_chunks(response(chat('Checking.', ('alpha', 'beta'))))
        observed, _ = gate.response_stream(chunks)
        self.assertEqual([x['parsed_arguments']['key'] for x in observed['calls']], ['alpha', 'beta'])
        variants = []
        for kind, key, value in (
            ('response.function_call_arguments.delta', 'item_id', 'foreign-item'),
            ('response.function_call_arguments.delta', 'output_index', True),
            ('response.function_call_arguments.done', 'arguments', '{}'),
            ('response.function_call_arguments.done', 'name', 'foreign-function'),
            ('response.completed', 'sequence_number', False),
            ('response.completed', 'type', 'response.incomplete'),
        ):
            bad = copy.deepcopy(chunks); next(x for x in bad if x['type'] == kind)[key] = value; variants.append(bad)
        bad = copy.deepcopy(chunks); final = bad[-1]['response']['output'][1]
        final['call_id'] = 'foreign-call'; variants.append(bad)
        bad = copy.deepcopy(chunks); next(x for x in bad if x['type'] == 'response.output_text.delta')['delta'] = 'drift'; variants.append(bad)
        for bad in variants:
            with self.assertRaises(RuntimeError): gate.response_stream(bad)


if __name__ == '__main__':
    unittest.main()
