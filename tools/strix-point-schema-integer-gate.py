#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional original-weight bounded-integer wire gate; no performance claim."""
import json
from pathlib import Path
import re
import sys

# Bounds below are independently declared exact mathematical expectations;
# never obtain an oracle by invoking LIE or reusing its formatter.
BIG = int(1e100)
MAXIMUM = int(sys.float_info.max)
CASES = (
    ('positive-inclusive', {'minimum': 7, 'maximum': 7}, 7, 7),
    ('negative-inclusive', {'minimum': -7, 'maximum': -7}, -7, -7),
    ('positive-exclusive', {'exclusiveMinimum': 1, 'exclusiveMaximum': 3}, 2, 2),
    ('negative-exclusive', {'exclusiveMinimum': -3, 'exclusiveMaximum': -1}, -2, -2),
    ('positive-fractional', {'minimum': .5, 'maximum': 1.5}, 1, 1),
    ('negative-fractional', {'minimum': -1.5, 'maximum': -.5}, -1, -1),
    ('cross-zero', {'minimum': -.5, 'maximum': .5}, 0, 0),
    ('positive-prefix', {'minimum': 9, 'maximum': 11}, 9, 11),
    ('negative-prefix', {'minimum': -11, 'maximum': -9}, -11, -9),
    ('beyond-int64', {'minimum': 2**63, 'maximum': 2**63}, 2**63, 2**63),
    ('exact-binary64', {'minimum': 1000000000000000128, 'maximum': 1000000000000000128},
     1000000000000000128, 1000000000000000128),
    ('large-magnitude', {'minimum': 1e100, 'maximum': 1e100}, BIG, BIG),
    ('largest-magnitude', {'minimum': sys.float_info.max, 'maximum': sys.float_info.max},
     MAXIMUM, MAXIMUM),
    ('large-positive-exclusive', {'exclusiveMinimum': 1e18, 'maximum': 1e18 + 128},
     10**18 + 1, 10**18 + 128),
    ('large-negative-exclusive', {'minimum': -1e18 - 128, 'exclusiveMaximum': -1e18},
     -10**18 - 128, -10**18 - 1),
)
REFUSALS = (
    ('empty-interval', {'minimum': 2, 'maximum': 1}),
    ('exclusive-zero-empty', {'minimum': 0, 'exclusiveMaximum': 0}),
    ('invalid-minimum', {'minimum': 'invalid', 'maximum': 1}),
)
CHECKS = frozenset(
    f'{api}_{wire}_{name}' for api in ('chat', 'responses')
    for wire in ('json', 'sse') for name, *_ in CASES
) | frozenset(f'{api}_refusal_{name}' for api in ('chat', 'responses')
              for name, _ in REFUSALS)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_text(text, low, high):
    require(isinstance(text, str), 'Missing bounded integer text')
    lexemes = []
    def integer(raw):
        require(re.fullmatch(r'-?(?:0|[1-9][0-9]*)', raw), 'Noncanonical integer spelling')
        lexemes.append(raw)
        return int(raw)
    def noninteger(_raw):
        raise RuntimeError('Bounded integer must use integer JSON syntax')
    def object_pairs(pairs):
        require(len(pairs) == 1 and pairs[0][0] == 'value',
                'Unexpected, missing or duplicate bounded integer property')
        return dict(pairs)
    try:
        value = json.loads(text, parse_int=integer, parse_float=noninteger,
                           parse_constant=noninteger, object_pairs_hook=object_pairs)
    except ValueError as error:
        raise RuntimeError('Malformed bounded integer JSON') from error
    require(type(value) is dict and type(value.get('value')) is int and len(lexemes) == 1,
            'Bounded result must contain one integer')
    require(low <= value['value'] <= high, 'Generated integer is outside the independent interval')
    return {'text': text, 'value': value['value'], 'lexeme': lexemes[0],
            'low': low, 'high': high}


def completion(value, responses):
    require(type(value) is dict, 'Completion must be an object')
    if responses:
        require(value.get('status') == 'completed', 'Bounded response was truncated')
        items = [part.get('text') for item in value.get('output', [])
                 if item.get('type') == 'message' for part in item.get('content', [])
                 if part.get('type') == 'output_text']
        require(len(items) == 1 and isinstance(items[0], str), 'Bounded response text is missing')
        text = items[0]
    else:
        choices = value.get('choices', [])
        require(len(choices) == 1 and choices[0].get('finish_reason') == 'stop',
                'Bounded Chat was truncated or returned unexpected choices')
        text = choices[0].get('message', {}).get('content')
    usage = value.get('usage', {})
    output = usage.get('output_tokens' if responses else 'completion_tokens')
    prompt = usage.get('input_tokens' if responses else 'prompt_tokens')
    require(type(output) is int and 0 < output <= 512 and type(prompt) is int and prompt > 0,
            'Invalid bounded completion usage')
    return text, output, prompt


def streaming(chunks, responses):
    require(isinstance(chunks, list) and chunks, 'Missing bounded SSE')
    if responses:
        require(all(type(x) is dict for x in chunks), 'Malformed Responses SSE')
        sequence = [x.get('sequence_number') for x in chunks]
        require(all(type(x) is int for x in sequence) and sequence == list(range(len(chunks))),
                'Bounded Responses sequence discontinuity')
        terminals = [x for x in chunks if x.get('type') in
                     ('response.completed', 'response.incomplete', 'response.failed')]
        require(len(terminals) == 1 and terminals[0] is chunks[-1] and
                terminals[0]['type'] == 'response.completed', 'Bounded Responses terminal mismatch')
        value = chunks[-1]['response']
        text, output, prompt = completion(value, True)
        delta = ''.join(x['delta'] for x in chunks if x.get('type') == 'response.output_text.delta')
        require(delta == text, 'Bounded Responses delta/final mismatch')
        return text, output, prompt
    require(chunks[-1] == '[DONE]' and chunks.count('[DONE]') == 1, 'Bounded Chat sentinel mismatch')
    text, finish, usage = '', [], []
    for chunk in chunks[:-1]:
        require(type(chunk) is dict, 'Malformed Chat SSE')
        if chunk.get('usage') is not None:
            usage.append(chunk['usage'])
        for choice in chunk.get('choices', []):
            require(choice.get('index') == 0 and not finish, 'Unknown or already finished bounded choice')
            delta = choice.get('delta', {}).get('content')
            require(delta is None or isinstance(delta, str), 'Invalid bounded text delta')
            text += delta or ''
            if choice.get('finish_reason') is not None:
                finish.append(choice['finish_reason'])
    require(finish == ['stop'] and len(usage) == 1, 'Incomplete bounded Chat or usage')
    return completion({'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                       'usage': usage[0]}, False)


def integer_gate(api, model_id, exchange, events, root=Path('/work')):
    result = {'schema': 'synapse-lie.point-schema-integer.v1', 'state': 'RUNNING',
              'scope': 'Selected original-weight bounded-integer wire/membership checks; '
                       'not independent logits, all branches, quality or performance qualification',
              'passed': [], 'witnesses': {}}
    def save():
        (root/'http-schema-integer-result.json').write_text(json.dumps(result, indent=2) + '\n')
    def body(bounds, responses, stream=False):
        schema = {'type': 'object', 'properties': {'value': {'type': 'integer', **bounds}},
                  'required': ['value'], 'additionalProperties': False}
        prompt = 'Return exactly the JSON object required by the schema, without explanation.'
        fmt = {'type': 'json_schema', 'name': 'bounded_integer', 'strict': True, 'schema': schema}
        request = {'model': model_id, 'temperature': 0, 'store': False, 'stream': stream}
        if responses:
            request.update(input=prompt, max_output_tokens=512, text={'format': fmt})
        else:
            request.update(messages=[{'role': 'user', 'content': prompt}], max_tokens=512,
                           response_format={'type': 'json_schema', 'json_schema': {
                               k: v for k, v in fmt.items() if k != 'type'}},
                           chat_template_kwargs={'enable_thinking': False})
            if stream:
                request['stream_options'] = {'include_usage': True}
        return request
    save()
    try:
        for responses in (False, True):
            prefix, path = ('responses', '/v1/responses') if responses else ('chat', '/v1/chat/completions')
            for name, bounds, low, high in CASES:
                previous_text = None
                for stream in (False, True):
                    row = exchange(api, path, body(bounds, responses, stream))
                    require(row['status'] == 200, 'Bounded integer request failed: ' + name)
                    text, output, prompt = (streaming(events(row['body']), responses) if stream else
                                            completion(json.loads(row['body']), responses))
                    witness = validate_text(text, low, high)
                    if stream:
                        require(text == previous_text, 'Bounded JSON/SSE deterministic replay differs')
                    previous_text = text
                    key = f'{prefix}_{"sse" if stream else "json"}_{name}'
                    witness.update(output_tokens=output, prompt_tokens=prompt, bounds=bounds)
                    result['witnesses'][key] = witness
                    result['passed'].append(key)
                    save()
            for name, bounds in REFUSALS:
                row = exchange(api, path, body(bounds, responses))
                require(row['status'] == 400, 'Invalid integer schema must refuse with HTTP400: ' + name)
                error = json.loads(row['body']).get('error', {})
                require(type(error) is dict and isinstance(error.get('message'), str) and error['message'],
                        'Integer schema refusal requires an error message')
                key = f'{prefix}_refusal_{name}'
                result['witnesses'][key] = {'status': 400, 'error': error, 'bounds': bounds}
                result['passed'].append(key)
                save()
        require(set(result['passed']) == CHECKS and len(result['passed']) == len(CHECKS),
                'Incomplete bounded integer controls')
        result['state'] = 'PASSED'
        return result
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
        raise
    finally:
        save()
