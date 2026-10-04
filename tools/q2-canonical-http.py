#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the pinned Gufo prose depth recipe against an owned C17 HTTP endpoint.

This client does not acquire a GPU lease or start a server. The coordinated
supervisor must own the endpoint and its model. LIE executor-call timing is
labelled separately from published Gufo scheduler timing.
"""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_REPLY = 2 * 1024 * 1024
DEPTHS = [0, 4096, 8192, 12288, 16384, 32768, 65536, 131072]
TIMING_SCOPE = 'synchronous_executor_calls'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(obj, key, integer=False):
    value = obj.get(key)
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'Missing or invalid nonnegative metric: ' + key)
    require(not integer or type(value) is int, 'Non-integral count: ' + key)
    return value


def observation(usage, timing, text, finish):
    require(isinstance(usage, dict) and isinstance(timing, dict), 'Missing server metrics')
    require(timing.get('schema') == 'synapse-lie.request-timings.v1' and
            timing.get('scope') == TIMING_SCOPE and timing.get('valid') is True,
            'Wrong or invalid server timing scope')
    require(timing.get('decode_mode') == 'ar' and
            number(timing, 'max_decode_output_tokens', True) == 1,
            'Canonical AR measurement cannot use speculative decoding')
    prompt = number(usage, 'prompt_tokens', True)
    output = number(usage, 'completion_tokens', True)
    cached = number(timing, 'cached_tokens', True)
    prefill = number(timing, 'prefill_tokens', True)
    require(prompt == cached + prefill and output == number(timing, 'decode_tokens', True),
            'Usage and completed stage counts disagree')
    require(number(usage, 'total_tokens', True) == prompt + output, 'Wrong total token count')
    details = usage.get('prompt_tokens_details', {})
    require(isinstance(details, dict) and type(details.get('cached_tokens', 0)) is int and
            details.get('cached_tokens', 0) == cached,
            'Usage and cache-frontier counts disagree')
    calls = number(timing, 'decode_calls', True)
    require(calls == output or (finish == 'stop' and calls == output+1),
            'Expected one completed AR call per output, plus an optional EOS check')
    require(number(timing, 'ssd_cached_tokens', True) == 0 and
            number(timing, 'mtp_drafted_tokens', True) == 0 and
            number(timing, 'mtp_accepted_tokens', True) == 0,
            'Unexpected SSD or speculative work')
    pp_ms, tg_ms = number(timing, 'prefill_ms'), number(timing, 'decode_ms')
    require((not prefill or pp_ms > 0) and (not output or tg_ms > 0),
            'Nonempty stage has no positive duration')
    return SimpleNamespace(prompt_tokens=prompt, cached_prompt_tokens=cached,
        completion_tokens=output, prefill_tokens=prefill, prefill_ms=pp_ms, decode_ms=tg_ms,
        finish_reason=finish, decode_calls=calls,
        prefill_tokens_per_second=prefill*1000/pp_ms if pp_ms else None,
        decode_tokens_per_second=output*1000/tg_ms if tg_ms else None,
        completion_sha256=hashlib.sha256(text.encode()).hexdigest())


def parse_reply(chunks, streamed):
    """Require complete, coherent single-choice output and a terminal marker."""
    usage = timing = None
    parts, finish, done = [], None, False
    for chunk in chunks:
        require(not done, 'Data after terminal marker')
        if chunk == '[DONE]':
            done = True
            continue
        require(isinstance(chunk, dict) and not chunk.get('error'), 'Invalid/error response chunk')
        if 'usage' in chunk and chunk['usage'] is not None:
            require(usage is None, 'Duplicate usage')
            usage = chunk['usage']
        if 'lie_timings' in chunk:
            require(timing is None, 'Duplicate stage timings')
            timing = chunk['lie_timings']
        choices = chunk.get('choices')
        require(isinstance(choices, list) and len(choices) <= 1, 'Expected a single choice')
        if not choices:
            continue
        choice = choices[0]
        require(isinstance(choice, dict) and choice.get('index') == 0, 'Wrong choice index')
        value = choice.get('delta' if streamed else 'message')
        require(isinstance(value, dict), 'Missing text response')
        require(not value.get('tool_calls') and not value.get('reasoning_content'),
                'Unexpected tools or reasoning output')
        content = value.get('content', '')
        require(content is None or isinstance(content, str), 'Invalid text content')
        require(not content or finish is None, 'Text after finish')
        parts.append(content or '')
        reason = choice.get('finish_reason')
        if reason is not None:
            require(finish is None and reason in ('stop', 'length'), 'Invalid/duplicate finish reason')
            finish = reason
    require((done or not streamed) and finish is not None, 'Truncated response')
    text = ''.join(parts)
    return observation(usage, timing, text, finish), text


def load_upstream(source):
    sys.dont_write_bytecode = True
    plan = json.loads((ROOT / 'config/q2-curve-parity-plan.json').read_text())
    for name, expected in plan['canonical_reference']['files_sha256'].items():
        require(hashlib.sha256((source/name).read_bytes()).hexdigest() == expected,
                'Canonical upstream source changed: ' + name)
    # Bind all imported Python dependencies, not only the prompt generator.
    manifest = json.loads((ROOT / 'config/q2-curve-source.json').read_text())
    for name, expected in manifest['variants']['ud']['files'].items():
        if name.startswith('tools/gufo/') and name.endswith('.py'):
            require(hashlib.sha256((source/name).read_bytes()).hexdigest() == expected,
                    'Canonical driver dependency changed: ' + name)
    sys.path.insert(0, str(source/'tools'))
    llm = importlib.import_module('gufo.model_bench.llm')
    serving = importlib.import_module('gufo.serving_bench')
    require(Path(llm.__file__).resolve() == (source/'tools/gufo/model_bench/llm.py').resolve(),
            'Unexpected imported canonical driver')
    return llm, serving


class Session:
    def __init__(self, serving, output, timeout):
        self.serving, self.output, self.timeout = serving, output, timeout
        self.tokenizer_calibration = {}
        self.requests = 0

    def call(self, base_url, messages, max_tokens, streamed, extra_body=None):
        # LIE accepts the OpenAI controls; Gufo-only top-k/min-p fields are
        # omitted. Greedy, neutral penalties and thinking-off are explicit.
        payload = dict(model='bench', messages=messages, max_tokens=max_tokens,
                       stream=streamed, chat_template_kwargs={'enable_thinking': False},
                       **self.serving.benchmark_sampling(0.0, 'openai'))
        if streamed:
            payload['stream_options'] = {'include_usage': True}
        require(not extra_body, 'Only the pinned AR prose workload is admitted')
        body = json.dumps(payload).encode()
        record = dict(index=self.requests, payload=payload,
                      payload_sha256=hashlib.sha256(body).hexdigest(),
                      started_ns=time.monotonic_ns())
        self.requests += 1
        path = self.output/f'request-{record["index"]:04d}.json'
        require(not path.exists(), 'Refusing to overwrite request evidence')
        chunks = []
        try:
            request = urllib.request.Request(base_url+'/v1/chat/completions', data=body,
                headers={'Content-Type': 'application/json', 'X-Client-ID': 'model-bench'}, method='POST')
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                require(response.status == 200, 'HTTP request failed')
                if streamed:
                    size = 0
                    for event in self.serving._sse_data(response):
                        size += len(event.encode())
                        require(size <= MAX_REPLY, 'Oversized response')
                        chunks.append(event if event == '[DONE]' else json.loads(event))
                else:
                    data = response.read(MAX_REPLY+1)
                    require(len(data) <= MAX_REPLY, 'Oversized response')
                    chunks.append(json.loads(data))
            sample, text = parse_reply(chunks, streamed)
            record['observation'] = vars(sample)
            return sample, text
        except Exception as error:
            record['error'] = str(error)
            raise
        finally:
            record.update(ended_ns=time.monotonic_ns(), response=chunks)
            path.write_text(json.dumps(record, indent=2)+'\n')

    def request(self, base_url, prompt, max_tokens, *, index=0, messages=None, extra_body=None):
        return self.call(base_url, messages or [{'role': 'user', 'content': prompt}],
                         max_tokens, True, extra_body)[0]

    def chat_text(self, base_url, messages, max_tokens, extra_body=None):
        return self.call(base_url, messages, max_tokens, False, extra_body)[1]


def loopback_url(value):
    url = urllib.parse.urlsplit(value)
    require(url.scheme == 'http' and url.hostname == '127.0.0.1' and
            url.port and not url.username and not url.password and
            not url.query and not url.fragment and url.path in ('', '/'),
            'Expected an owned loopback HTTP endpoint')
    return value.rstrip('/')


def check_backend(info, profile_ple=False, iq2_signs=False, ple_cache_first=False, profile_routes=False):
    require(sum(map(bool, (profile_ple, iq2_signs, ple_cache_first, profile_routes))) <= 1,
            'Instrumented, IQ2 and PLE cache-first curves are separate')
    require(isinstance(info, dict) and info.get('schema') == 'synapse-lie.llm.v1' and
            info.get('ready') is True, 'Model is not ready')
    backend = info.get('backend', {})
    require(backend.get('synthetic') is False and backend.get('mtp') is False and
            backend.get('vision') is False and backend.get('prefix_state') is True and
            backend.get('model') == 'bench' and backend.get('context_tokens') == 133760 and
            backend.get('build_id') == ('q2-canonical-curve-route-profile' if profile_routes else
                                        'q2-canonical-curve-ple-cache-first' if ple_cache_first else
                                        'q2-canonical-curve-iq2-signs' if iq2_signs else
                                        'q2-canonical-curve-ple-profile' if profile_ple else
                                        'q2-canonical-curve-experiment') and
            backend.get('source_pin') == 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
            'Endpoint is not the admitted C1 AR curve composition')
    require(number(info.get('cache', {}), 'budget_bytes', True) > 0,
            'RAM prefix cache is disabled')
    scheduler = info.get('scheduler', {})
    require(scheduler.get('queued') == 0 and scheduler.get('active') == 0 and
            scheduler.get('max_active') == 1,
            'Endpoint has other active requests')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--management-url', required=True)
    parser.add_argument('--gufo-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=('q2', 'ud'), required=True)
    composition = parser.add_mutually_exclusive_group()
    composition.add_argument('--profile-ple', action='store_true',
                        help='Diagnostic instrumentation; rates are not benchmark evidence')
    composition.add_argument('--profile-routes', action='store_true',
                        help='Diagnostic expert counts; rates are not benchmark evidence')
    composition.add_argument('--iq2-signs', action='store_true',
                        help='Measured ordered IQ2 vector-sign provider; same canonical workload')
    composition.add_argument('--ple-cache-first', action='store_true',
                        help='Host-qualified PLE reader with ordered IQ2 decode; same canonical workload')
    parser.add_argument('--depths', default=','.join(map(str, DEPTHS)))
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    require(not (args.iq2_signs or args.ple_cache_first or args.profile_routes) or args.variant == 'q2',
            'Provider experiment requires the Q2 model')
    base_url = loopback_url(args.base_url)
    management_url = loopback_url(args.management_url)
    require(math.isfinite(args.timeout) and 0 < args.timeout <= 1800, 'Invalid timeout')
    depths = [int(x) for x in args.depths.split(',')]
    # Restrict diagnostics to an ordered prefix, preserving calibration history.
    require(depths and depths == DEPTHS[:len(depths)], 'Depths must be an ordered prefix of the canonical grid')
    llm, serving = load_upstream(args.gufo_source.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='synapse-lie.canonical-http-curve.v1', variant=args.variant,
        state='RUNNING', timing_scope=TIMING_SCOPE, context_capacity=133760,
        instrumentation='routing-counts' if args.profile_routes else 'ple-forward' if args.profile_ple else None,
        provider_experiment='ple-cache-first-ordered' if args.ple_cache_first else
                            'iq2-signs-ordered' if args.iq2_signs else None,
        headline_eligible=not (args.profile_ple or args.profile_routes),
        new_prompt_target=2048, output_tokens=128, depths=depths,
        full_grid=depths == DEPTHS, rows=[], goal_met=False,
        comparison_scope='Pinned Gufo canonical workload over common C17 HTTP; LIE completed executor-call timings. Published Gufo scheduler rates remain historical, not an identical timer.',
        started_ns=time.monotonic_ns())
    def save():
        (args.output/'curve.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        with urllib.request.urlopen(management_url+'/actuator/llm', timeout=10) as response:
            data = response.read(MAX_REPLY+1)
            require(len(data) <= MAX_REPLY, 'Oversized backend response')
            report['backend_before'] = json.loads(data)
        check_backend(report['backend_before'], args.profile_ple, args.iq2_signs, args.ple_cache_first, args.profile_routes)
        session = Session(serving, args.output, args.timeout)
        tokenizer = llm.Tokenizer(session, base_url)
        session.request(base_url, llm.synthetic_text(8888, tokenizer.words_for(2048)), 16)
        report['initial_calibration'] = dict(overhead=tokenizer.overhead, ratio=tokenizer.ratio)
        for depth in depths:
            first_request = session.requests
            sample = llm._measure_depth(session, base_url, tokenizer, depth=depth,
                prompt_tokens=2048, output_tokens=128, fraction=.005, seed=1,
                repetition=0, task='prose')
            require(sample.prompt_tokens+sample.completion_tokens <= 133760, 'Context overflow')
            require(sample.decode_calls == 128, 'Measured tg128 includes an extra EOS call')
            row = dict(depth=depth, first_request=first_request,
                       accepted_request=session.requests-1, ratio=tokenizer.ratio, **vars(sample))
            report['rows'].append(row)
            save()
            print(json.dumps(row), flush=True)
        report['state'] = 'MEASURED_NOT_PARITY_OR_QUALITY_VERDICT'
    except Exception as error:
        report.update(state='FAILED', error=str(error))
        raise
    finally:
        report['ended_ns'] = time.monotonic_ns()
        save()


if __name__ == '__main__':
    main()
