# SPDX-License-Identifier: MIT
"""Diagnostic replay of the original preparation and one complete prefix.

No prompt generation, model change, or throughput-reference replacement.
"""
import hashlib
import json
from q2_full_prefill128 import inputs as original_inputs


TARGETS = {32768: (32711, 16), 131072: (130925, 64)}


def inputs(root, profile_depth=32768):
    if profile_depth not in TARGETS:
        raise ValueError('Unsupported original profile depth')
    corpus, manifest, cases = original_inputs(root)
    selected = [(i, c, b) for i, (c, b) in enumerate(zip(cases, manifest['cases']))
                if b['phase'] != 'prefix' or b['depth'] == profile_depth]
    if (len(selected) != 4 or selected[-1][2]['expected_prompt_tokens'] != TARGETS[profile_depth][0]
            or selected[-1][2]['phase'] != 'prefix'):
        raise ValueError('Expected original preparation and one complete profile prefix')
    return corpus, selected


def client_argv(root, binary, output, depth=None, profile_depth=32768):
    if depth is not None:
        raise ValueError('The diagnostic has a fixed original profile prefix')
    corpus, selected = inputs(root, profile_depth)
    raw = corpus.read_bytes().splitlines(keepends=True)
    payload = b''.join(raw[i] for i, _, _ in selected)
    target = output.with_suffix('.requests.jsonl')
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError('Existing diagnostic inputs differ')
    else:
        with target.open('xb') as stream:
            stream.write(payload)
    return [str(binary), '--suite', 'http', '--url', 'http://127.0.0.1:8000/v1',
            '--model', 'bench', '--output', str(output),
            '--server-label', f'diagnostic-retained-prefix{profile_depth//1024}k-not-throughput',
            '--server-kv-cache', 'on', '--requests', str(target),
            '--context-capacity', '133760', '--rope-scaling', 'native',
            '--warmups', '0', '--repetitions', '1', '--timeout', '1800']


def validate_result(root, path, depth=None, profile_depth=32768):
    if depth is not None:
        raise ValueError('The diagnostic has a fixed original profile prefix')
    corpus, selected = inputs(root, profile_depth)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    samples = [e for e in events if e['event'] == 'sample']
    if (not events or events[-1]['event'] != 'complete'
            or events[-1]['exit_code'] != 0 or len(samples) != len(selected)):
        raise ValueError('Diagnostic replay incomplete')
    for sample, (_, case, binding) in zip(samples, selected):
        strip = lambda body: {k: v for k, v in body.items()
                              if k not in ('stream', 'stream_options')}
        if (sample['case'] != case['id'] or strip(sample['request']) != strip(case['body'])
                or sample['usage']['prompt_tokens'] != binding['expected_prompt_tokens']):
            raise ValueError('Diagnostic changed original model inputs')
        timing = sample['server_timings']
        if (timing['valid'] is not True or timing['scope'] != 'synchronous_executor_calls'
                or timing['decode_mode'] != 'ar' or timing['mtp_drafted_tokens']
                or timing['mtp_accepted_tokens'] or timing['ssd_cached_tokens']):
            raise ValueError('Diagnostic timing scope differs')
        if binding['phase'] == 'prefix' and (
                timing['cached_tokens'] != 0 or timing['prefill_tokens'] != TARGETS[profile_depth][0]
                or timing['prefill_calls'] != TARGETS[profile_depth][1] or timing['prefill_ms'] <= 0):
            raise ValueError('Expected complete uncached profile prefill')
    return dict(original_inputs_exact=True, corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),
                physical_tokens=TARGETS[profile_depth][0], capacity=133760, chunk=2048, cached_tokens=0,
                headline_eligible=False, diagnostic_only=True,
                timed_scope='Profiler-instrumented kernel/API attribution; not unprofiled throughput')


def profiler_argv(profiler, directory, server_argv, profile_depth=32768):
    # rocprofv3 execs the server, so Popen owns the actual server PID. Its normal
    # SIGTERM handler drains libuv and lets the profiler flush at process exit.
    if profile_depth not in TARGETS:
        raise ValueError('Unsupported original profile depth')
    return [str(profiler), '--kernel-trace', '--hip-trace', '--memory-copy-trace',
            '-d', str(directory), '-o', f'prefix{profile_depth//1024}k', '--', *server_argv]
