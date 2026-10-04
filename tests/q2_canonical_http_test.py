#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject misleading timing/count evidence before comparing Q2 with UD."""
import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('canonical', ROOT/'tools/q2-canonical-http.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
spec = importlib.util.spec_from_file_location('iq2_curve', ROOT/'tools/analyze-q2-iq2-curve.py')
iq2_curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iq2_curve)


def reply():
    usage = dict(prompt_tokens=6144, completion_tokens=128, total_tokens=6272,
                 prompt_tokens_details=dict(cached_tokens=4096))
    timing = dict(schema='synapse-lie.request-timings.v1', scope='synchronous_executor_calls',
        valid=True, decode_mode='ar', max_decode_output_tokens=1,
        prefill_tokens=2048, cached_tokens=4096, decode_tokens=128, decode_calls=128,
        prefill_ms=1400.0, decode_ms=5000.0, ssd_cached_tokens=0,
        mtp_drafted_tokens=0, mtp_accepted_tokens=0)
    return [dict(choices=[dict(index=0, delta=dict(content='Example'), finish_reason=None)]),
            dict(choices=[dict(index=0, delta={}, finish_reason='length')], lie_timings=timing),
            dict(choices=[], usage=usage), '[DONE]']


class MetricsContract(unittest.TestCase):
    def test_profile_cannot_impersonate_uninstrumented_server(self):
        info = dict(schema='synapse-lie.llm.v1',ready=True,
                    backend=dict(synthetic=False,mtp=False,vision=False,prefix_state=True,
                        model='bench',context_tokens=133760,build_id='q2-canonical-curve-experiment',
                        source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e'),
                    cache=dict(budget_bytes=1024),scheduler=dict(queued=0,active=0,max_active=1))
        client.check_backend(info)
        with self.assertRaises(ValueError):
            client.check_backend(info,True)
        info['backend']['build_id'] = 'q2-canonical-curve-ple-profile'
        client.check_backend(info,True)
        with self.assertRaises(ValueError):
            client.check_backend(info)
        info['backend']['build_id'] = 'q2-canonical-curve-iq2-signs'
        client.check_backend(info,iq2_signs=True)
        for options in ({},{'profile_ple':True},{'profile_ple':True,'iq2_signs':True}):
            with self.assertRaises(ValueError):
                client.check_backend(info,**options)
        info['backend']['build_id'] = 'q2-canonical-curve-experiment'
        with self.assertRaises(ValueError):
            client.check_backend(info,iq2_signs=True)
        info['backend']['build_id'] = 'q2-canonical-curve-ple-cache-first'
        client.check_backend(info,ple_cache_first=True)
        for options in ({}, {'iq2_signs':True}, {'profile_ple':True},
                        {'ple_cache_first':True,'iq2_signs':True},
                        {'ple_cache_first':True,'profile_ple':True}):
            with self.assertRaises(ValueError):
                client.check_backend(info,**options)
        info['backend']['build_id'] = 'q2-canonical-curve-iq2-signs'
        with self.assertRaises(ValueError):
            client.check_backend(info,ple_cache_first=True)

    def test_complete_history_includes_prefix_and_work_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            a,b = [Path(directory)/k for k in ('a','b')]
            a.mkdir();b.mkdir()
            payload = dict(stream=True,messages=[dict(role='user',content='Prefix')])
            rows = [dict(index=i,payload=payload,
                         payload_sha256=hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
                         response=reply()) for i in range(2)]
            for root in (a,b):
                for i,row in enumerate(rows):
                    (root/f'request-{i:04d}.json').write_text(json.dumps(row))
            self.assertTrue(iq2_curve.history(a,b,client)['exact'])
            changed = copy.deepcopy(rows[0])
            changed['response'][0]['choices'][0]['delta']['content'] = 'Changed prefix reply'
            (b/'request-0000.json').write_text(json.dumps(changed))
            self.assertFalse(iq2_curve.history(a,b,client)['exact'])
            changed = copy.deepcopy(rows[0])
            changed['response'][1]['lie_timings']['cached_tokens'] -= 1
            changed['response'][1]['lie_timings']['prefill_tokens'] += 1
            changed['response'][2]['usage']['prompt_tokens_details']['cached_tokens'] -= 1
            (b/'request-0000.json').write_text(json.dumps(changed))
            self.assertFalse(iq2_curve.history(a,b,client)['rows'][0]['counts_exact'])
            (b/'request-0000.json').unlink()
            with self.assertRaisesRegex(ValueError,'Missing/reordered'):
                iq2_curve.history(a,b,client)

    def test_completed_executor_scope(self):
        sample, text = client.parse_reply(reply(), True)
        self.assertEqual(text, 'Example')
        self.assertEqual(sample.prefill_tokens, 2048)
        self.assertEqual(sample.cached_prompt_tokens, 4096)
        self.assertAlmostEqual(sample.decode_tokens_per_second, 25.6)
        self.assertAlmostEqual(sample.prefill_tokens_per_second, 2048/1.4)

    def test_reject_wrong_accounting(self):
        for key, value in [('prefill_tokens', 6144), ('cached_tokens', 4095),
                           ('decode_calls', 127), ('decode_tokens', 127),
                           ('ssd_cached_tokens', 4096), ('mtp_drafted_tokens', 1),
                           ('max_decode_output_tokens', 2), ('decode_ms', 0),
                           ('prefill_ms', float('nan')), ('decode_ms', float('inf')),
                           ('prefill_tokens', True), ('cached_tokens', 4096.0),
                           ('valid', False), ('scope', 'client_wall')]:
            with self.subTest(key=key, value=value):
                chunks = reply()
                chunks[1]['lie_timings'][key] = value
                with self.assertRaises(ValueError):
                    client.parse_reply(chunks, True)

    def test_reject_bad_usage(self):
        for key, value in [('completion_tokens', 127), ('total_tokens', 1),
                           ('prompt_tokens_details', {'cached_tokens': True}),
                           ('prompt_tokens', '6144')]:
            chunks = reply()
            chunks[2]['usage'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                client.parse_reply(chunks, True)

    def test_incomplete_and_duplicate_streams(self):
        cases = [reply()[:-1], reply()[:1]+reply()[2:], reply()+[{}],
                 reply()[:-1]+[reply()[2], '[DONE]'],
                 reply()[:-1]+[reply()[1], '[DONE]'],
                 reply()[:1]+[{'error': {'message': 'failed'}}]]
        for chunks in cases:
            with self.subTest(chunks=chunks), self.assertRaises(ValueError):
                client.parse_reply(chunks, True)

    def test_prefix_nonstream(self):
        chunks = reply()
        item = dict(choices=[dict(index=0, message=dict(content='Example'), finish_reason='length')],
                    usage=chunks[2]['usage'], lie_timings=chunks[1]['lie_timings'])
        sample, text = client.parse_reply([item], False)
        self.assertEqual(sample.completion_tokens, 128)
        self.assertEqual(text, 'Example')

    def test_prefix_eos_check_is_not_a_completed_output_token(self):
        chunks = reply()
        chunks[1]['choices'][0]['finish_reason'] = 'stop'
        chunks[1]['lie_timings']['decode_calls'] = 129
        sample, _ = client.parse_reply(chunks, True)
        self.assertEqual(sample.completion_tokens, 128)
        self.assertEqual(sample.decode_calls, 129)
        self.assertEqual(sample.finish_reason, 'stop')

    def test_loopback_only(self):
        self.assertEqual(client.loopback_url('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000')
        for value in ['https://127.0.0.1:8000', 'http://example.org:8000',
                      'http://user:pass@127.0.0.1:8000', 'http://127.0.0.1:8000/path']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                client.loopback_url(value)


if __name__ == '__main__':
    unittest.main()
