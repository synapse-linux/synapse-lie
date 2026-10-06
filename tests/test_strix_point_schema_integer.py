#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent HOST wire/refusal controls; no model forward or GPU evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('integer', Path(__file__).resolve().parents[1]/
                                             'tools/strix-point-schema-integer-gate.py')
integer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integer)


class Tests(unittest.TestCase):
    def test_exact_large_values_and_negative_zero(self):
        for n in (0, -7, 2**63, 1000000000000000128, integer.BIG, integer.MAXIMUM):
            self.assertEqual(integer.validate_text('{"value":'+str(n)+'}', n, n)['value'], n)
        self.assertEqual(integer.validate_text('{"value":-0}', 0, 0)['lexeme'], '-0')
        self.assertEqual(len(str(integer.MAXIMUM)), 309)

    def test_refuses_wrong_bounds_and_noninteger_json(self):
        for text in ('{"value":6}', '{"value":8}', '{"value":7.0}', '{"value":7e0}',
                     '{"value":true}', '{"value":"7"}', '{"value":NaN}',
                     '{"value":7,"value":7}', '{"value":7,"extra":0}',
                     '{"value":07}', '{"value":7', '7', '{}', '[]', '{"value":null}'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                integer.validate_text(text, 7, 7)
        with self.assertRaises(RuntimeError):
            integer.validate_text('{"value":1000000000000000100}',
                                  1000000000000000128, 1000000000000000128)

    @staticmethod
    def completion(text, responses):
        if responses:
            return {'status': 'completed', 'usage': {'input_tokens': 20, 'output_tokens': 4},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 4}}

    def chunks(self, text, responses):
        value = self.completion(text, responses)
        if responses:
            return [{'type': 'response.created', 'sequence_number': 0},
                    {'type': 'response.output_text.delta', 'sequence_number': 1, 'delta': text},
                    {'type': 'response.completed', 'sequence_number': 2, 'response': value}]
        return [{'choices': [{'index': 0, 'delta': {'content': text}}]},
                {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
                {'choices': [], 'usage': value['usage']}, '[DONE]']

    def test_streams_require_complete_exact_witnesses(self):
        for responses in (False, True):
            self.assertEqual(integer.streaming(self.chunks('{"value":7}', responses), responses)[0],
                             '{"value":7}')
            bad = self.chunks('{"value":7}', responses)
            if responses:
                bad[1]['sequence_number'] = 2
            else:
                bad[-2]['usage']['completion_tokens'] = True
            with self.assertRaises(RuntimeError): integer.streaming(bad, responses)
            bad = self.chunks('{"value":7}', responses)
            if responses:
                bad[-1]['response']['status'] = 'incomplete'
            else:
                bad[1]['choices'][0]['finish_reason'] = 'length'
            with self.assertRaises(RuntimeError): integer.streaming(bad, responses)
        bad = self.chunks('{"value":7}', True); bad[1]['delta'] = '{"value":8}'
        with self.assertRaisesRegex(RuntimeError, 'delta/final'): integer.streaming(bad, True)
        bad = self.chunks('{"value":7}', False); bad.insert(-1, {'choices': [{'index': 0, 'delta': {'content': 'x'}}]})
        with self.assertRaises(RuntimeError): integer.streaming(bad, False)

    def fixture_gate(self, root, corrupt=False):
        # Canned values keyed by declared schema, not LIE/compiler output.
        values = {json.dumps(bounds): low for _, bounds, low, _ in integer.CASES}
        refusals = {json.dumps(bounds) for _, bounds in integer.REFUSALS}
        calls = []
        def exchange(_api, path, body):
            responses = path == '/v1/responses'
            fmt = body['text']['format'] if responses else body['response_format']['json_schema']
            schema = fmt['schema']; prop = schema['properties']['value']
            self.assertEqual(prop['type'], 'integer'); self.assertNotIn('enum', prop)
            self.assertNotIn('const', prop); self.assertEqual(body['temperature'], 0)
            self.assertEqual(body['max_output_tokens' if responses else 'max_tokens'], 512)
            self.assertFalse(body['store'])
            key = json.dumps({k: v for k, v in prop.items() if k != 'type'})
            calls.append((path, key, body['stream']))
            if key in refusals:
                return {'status': 400, 'body': json.dumps({'error': {'message': 'Declared invalid schema'}})}
            n = values[key]
            text = '{"value":'+str(n)+'}'
            if corrupt and body['stream']: text = '{"value":'+str(n+1)+'}'
            value = self.chunks(text, responses) if body['stream'] else self.completion(text, responses)
            return {'status': 200, 'body': json.dumps(value)}
        result = integer.integer_gate(1, 'host_fixture', exchange, json.loads, root)
        self.assertEqual(len(calls), 66)
        return result

    def test_complete_host_gate_and_all_failure_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); result = self.fixture_gate(root)
            self.assertEqual(result['state'], 'PASSED')
            self.assertEqual(len(result['passed']), 66)
            self.assertEqual(set(result['passed']), integer.CHECKS)
            self.assertEqual(set(result['witnesses']), integer.CHECKS)
            self.assertEqual(json.loads((root/'http-schema-integer-result.json').read_text()), result)

    def test_failure_retains_partial_witnesses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError): self.fixture_gate(root, corrupt=True)
            result = json.loads((root/'http-schema-integer-result.json').read_text())
            self.assertEqual(result['state'], 'FAILED')
            self.assertEqual(result['passed'], ['chat_json_positive-inclusive'])


if __name__ == '__main__':
    unittest.main()
