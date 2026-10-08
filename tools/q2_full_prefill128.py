# SPDX-License-Identifier: MIT
"""Replay exact saved prompts; validate full-prefill counts, not tail-only rates."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def inputs(root, depth=None):
    manifest = json.loads((root/'config/q2-full-prefill128-inputs.json').read_text())
    corpus = root/manifest['requests']
    if hashlib.sha256(corpus.read_bytes()).hexdigest() != manifest['requests_sha256']:
        raise ValueError('Saved full-prefill corpus changed')
    cases = [json.loads(line) for line in corpus.read_text().splitlines()]
    if len(cases) != len(manifest['cases']):
        raise ValueError('Saved full-prefill case count differs')
    for case, binding in zip(cases, manifest['cases']):
        if (case['id'] != binding['id'] or
                digest(case['body']['messages']) != binding['messages_sha256'] or
                case['expected_prompt_tokens'] != binding['expected_prompt_tokens']):
            raise ValueError('Saved full-prefill input identity differs')
    if depth is not None:
        if depth not in (65536,131072):
            raise ValueError('Only saved unfinished long prefill depths are selectable')
        selected = [(c,b) for c,b in zip(cases,manifest['cases']) if b['phase'] != 'prefix' or b['depth'] == depth]
        cases = [c for c,b in selected]
        manifest['cases'] = [b for c,b in selected]
        if len(cases) != 4:
            raise ValueError('Expected original preparation plus one complete prefix')
    return corpus, manifest, cases


def client_argv(root, binary, output, depth=None):
    corpus, _, cases = inputs(root, depth)
    if depth is not None:
        corpus = output.with_suffix('.requests.jsonl')
        payload = ''.join(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n' for c in cases)
        if corpus.exists():
            if corpus.read_text() != payload:
                raise ValueError('Existing selected input file differs')
        else:
            with corpus.open('x') as stream:
                stream.write(payload)
    return [str(binary), '--suite', 'http', '--url', 'http://127.0.0.1:8000/v1',
        '--model', 'bench', '--output', str(output), '--server-label', 'retained-full-prefill128',
        '--server-kv-cache', 'on', '--requests', str(corpus), '--context-capacity', '133760',
        '--rope-scaling', 'native', '--warmups', '0', '--repetitions', '1', '--timeout', '1800']


def validate_result(root, path, depth=None):
    _, manifest, cases = inputs(root, depth)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    samples = [e for e in events if e['event'] == 'sample']
    if (events[-1]['event'] != 'complete' or events[-1]['exit_code'] != 0 or
            len(samples) != len(cases)):
        raise ValueError('Full-prefill replay incomplete')
    prefixes = []
    for sample, case, binding in zip(samples, cases, manifest['cases']):
        actual = {k:v for k,v in sample['request'].items() if k not in ('stream','stream_options')}
        expected = {k:v for k,v in case['body'].items() if k not in ('stream','stream_options')}
        if (sample['case'] != case['id'] or actual != expected or
                sample['usage']['prompt_tokens'] != binding['expected_prompt_tokens']):
            raise ValueError('Full-prefill replay changed saved model inputs')
        timing = sample['server_timings']
        if (timing['valid'] is not True or timing['scope'] != 'synchronous_executor_calls' or
                timing['decode_mode'] != 'ar' or timing['mtp_drafted_tokens'] or
                timing['mtp_accepted_tokens'] or timing['ssd_cached_tokens']):
            raise ValueError('Full-prefill replay timing scope differs')
        if binding['phase'] == 'prefix':
            tokens = binding['expected_prompt_tokens']
            if (timing['cached_tokens'] != 0 or timing['prefill_tokens'] != tokens or
                    timing['prefill_calls'] != (tokens+2047)//2048 or timing['prefill_ms'] <= 0):
                raise ValueError('Expected the complete uncached prefill in2048 chunks')
            prefixes.append(dict(case=case['id'], depth=binding['depth'], attempt=binding['attempt'],
                tokens=tokens, calls=timing['prefill_calls'], full_chunks=tokens//2048,
                remainder=tokens%2048, prefill_ms=timing['prefill_ms'],
                prefill_tps=tokens*1000/timing['prefill_ms']))
    return dict(all_saved_inputs_exact=True, context_capacity=133760, chunk_size=2048,
                token_padding=False, samples=len(samples), full_prefixes=prefixes)
