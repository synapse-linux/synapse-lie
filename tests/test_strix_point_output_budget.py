#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only independent wire witnesses for the optional GPU budget gate."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('budget', Path(__file__).resolve().parents[1]/
                                             'tools/strix-point-output-budget-gate.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class Tests(unittest.TestCase):
    def value(self, responses):
        text = json.dumps({'value': ' '.join(['alpha']*180)})
        if responses:
            return {'status': 'completed', 'max_output_tokens': 4096,
                    'usage': {'input_tokens': 700, 'output_tokens': 200},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                'usage': {'prompt_tokens': 700, 'completion_tokens': 200},
                'lie_timings': {'output_token_limit': 4096}}

    def test_completion_requires_real_past128_output_and_resolved_budget(self):
        for responses in (False, True):
            value = self.value(responses)
            self.assertEqual(budget.validate_completion(value, responses, 16384, 4096)['output_tokens'], 200)
            count = 'output_tokens' if responses else 'completion_tokens'
            prompt = 'input_tokens' if responses else 'prompt_tokens'
            for malformed in (0, 128, True, 200.0, 4097):
                wrong = copy.deepcopy(value);wrong['usage'][count] = malformed
                with self.subTest(responses=responses, malformed=malformed):
                    with self.assertRaises(RuntimeError):budget.validate_completion(wrong,responses,16384,4096)
            wrong = copy.deepcopy(value);wrong['usage'][prompt] = 16200
            with self.assertRaisesRegex(RuntimeError, 'exceeds available context'):
                budget.validate_completion(wrong,responses,16384,4096)
            wrong = copy.deepcopy(value)
            if responses:wrong['max_output_tokens'] = 128
            else:wrong['lie_timings']['output_token_limit'] = 128
            with self.assertRaisesRegex(RuntimeError, 'Resolved automatic budget'):
                budget.validate_completion(wrong,responses,16384,4096)

    def test_completion_refuses_truncation_and_partial_text(self):
        for responses in (False, True):
            wrong = self.value(responses)
            if responses:wrong['status'] = 'incomplete'
            else:wrong['choices'][0]['finish_reason'] = 'length'
            with self.assertRaises(RuntimeError):budget.validate_completion(wrong,responses,16384,4096)
            wrong = self.value(responses)
            if responses:wrong['output'][0]['content'][0]['text'] = '{"value":"alpha"}'
            else:wrong['choices'][0]['message']['content'] = '{"value":"alpha"}'
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                budget.validate_completion(wrong,responses,16384,4096)

    def run_gate(self, root, corrupt_stream=False, corrupt_metadata=False):
        calls = []
        def exchange(_api, path, body=None):
            calls.append((path, body))
            if path.startswith('/v1/models'):
                model = {'id': 'fixture', 'context_length': 16384, 'max_output_tokens': 4096}
                if corrupt_metadata and path != '/v1/models':model['context_length'] = 262144
                value = {'data': [model]} if path == '/v1/models' else model
                return {'status': 200, 'body': json.dumps(value)}
            responses = path == '/v1/responses'
            key = 'max_output_tokens' if responses else 'max_tokens'
            self.assertEqual(body['temperature'],0)
            self.assertFalse(body['store'])
            value = self.value(responses)
            if not body.get('stream'):
                self.assertNotIn(key,body)
                return {'status':200,'body':json.dumps(value)}
            self.assertIn(key,body);self.assertIsNone(body[key])
            text = budget.TEXT
            delta = json.dumps({'value': text})
            if corrupt_stream:delta = delta[:-2]
            if responses:
                chunks = [{'type':'response.output_text.delta','delta':delta},
                          {'type':'response.completed','response':value}]
            else:
                chunks = [{'choices':[{'index':0,'delta':{'content':delta}}]},
                          {'choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                           'lie_timings':{'output_token_limit':4096}},
                          {'choices':[],'usage':value['usage']},'[DONE]']
            return {'status':200,'body':json.dumps(chunks)}
        result = budget.output_budget_gate(1,'fixture',exchange,json.loads,root)
        self.assertEqual(len(calls),6)
        return result

    def test_gate_pairs_omission_json_and_null_sse_on_both_apis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_gate(root)
            self.assertEqual(result['state'],'PASSED')
            self.assertEqual(set(result['passed']),budget.OUTPUT_BUDGET_CHECKS)
            self.assertEqual(json.loads((root/'http-output-budget-result.json').read_text()),result)

    def test_gate_preserves_stream_failure_without_passing_later_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):self.run_gate(root,corrupt_stream=True)
            result = json.loads((root/'http-output-budget-result.json').read_text())
            self.assertEqual(result['state'],'FAILED')
            self.assertEqual(result['passed'],['models_context_output_limits'])

    def test_gate_refuses_model_metadata_drift_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):self.run_gate(root,corrupt_metadata=True)
            result = json.loads((root/'http-output-budget-result.json').read_text())
            self.assertEqual(result['state'],'FAILED')
            self.assertEqual(result['passed'],[])


if __name__ == '__main__':
    unittest.main()
