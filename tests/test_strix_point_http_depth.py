# SPDX-License-Identifier: MIT
"""CPU-only contract checks for the cold HTTP campaign."""

import importlib.util
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


gate = module(ROOT/'tools/strix-point-http-depth-gate.py')
report = module(ROOT/'tools/strix-point-http-depth-report.py')


class HttpDepthContract(unittest.TestCase):
    def test_lie_server_bounds_and_disabled_cache(self):
        args = types.SimpleNamespace(impl='lie', mode='ar', server='server',
                                     model='model', predictor=None)
        argv = gate.server_command(args, 9001)
        self.assertEqual(argv[argv.index('--context')+1], '262144')
        self.assertEqual(argv[argv.index('--kv-cache-ram-mb')+1], '0')
        self.assertEqual(argv[argv.index('--request-timeout-ms')+1], '1800000')

    def test_gufo_only_cache_option_normalization(self):
        request = {'model': 'm', 'messages': [{'role': 'user', 'content': 'a'}]}
        self.assertEqual(report.normalized(request, 'lie'), request)
        self.assertEqual(report.normalized({**request, 'cache_prompt': False}, 'gufo'), request)
        with self.assertRaises(ValueError):
            report.normalized(request, 'gufo')

    def test_reject_cached_or_partial_sample(self):
        args = types.SimpleNamespace(impl='lie', size=8192, repetitions=2)
        sample = {'event': 'sample', 'warmup': False, 'prompt_tokens': 8192,
                  'cached_tokens': 0, 'output_tokens': 128,
                  'full_output_budget': True, 'stream_complete': True,
                  'server_timings': {'prefill_tokens': 8192, 'prefill_ms': 2000,
                                     'decode_ms': 12000}}
        rows = [{'event': 'identity', 'schema': 'synapse-lie.http-bench.v1',
                 'cache_policy': 'off', 'context_capacity_declared': 262144,
                 'rope_scaling_declared': 'native'}, sample, sample.copy(),
                {'event': 'complete', 'exit_code': 0}]
        self.assertEqual(gate.validate(rows, args), 2)
        rows[2]['cached_tokens'] = 1
        with self.assertRaises(RuntimeError):
            gate.validate(rows, args)


if __name__ == '__main__':
    unittest.main()
