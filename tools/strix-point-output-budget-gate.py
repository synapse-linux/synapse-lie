#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional original-weight output-budget gate; no task-quality or speed claim."""
import json
from pathlib import Path

OUTPUT_BUDGET_CHECKS = frozenset({
    'models_context_output_limits', 'chat_automatic_output', 'responses_automatic_output',
})
TEXT = ' '.join(['alpha'] * 180)
SCHEMA = {'type': 'object', 'properties': {'value': {'type': 'string', 'enum': [TEXT]}},
          'required': ['value'], 'additionalProperties': False}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_completion(value, responses, context, ceiling):
    usage = value.get('usage', {})
    prompt = usage.get('input_tokens' if responses else 'prompt_tokens')
    output = usage.get('output_tokens' if responses else 'completion_tokens')
    require(type(prompt) is int and 0 < prompt < context and
            type(output) is int and 128 < output <= ceiling,
            'Automatic output must actually pass 128 tokens with typed usage')
    limit = min(context - prompt, ceiling)
    require(output <= limit, 'Automatic output exceeds available context')
    if responses:
        require(value.get('status') == 'completed', 'Automatic response was truncated')
        limit_observed = value.get('max_output_tokens')
        text = ''.join(part.get('text', '') for item in value.get('output', [])
                       if item.get('type') == 'message' for part in item.get('content', [])
                       if part.get('type') == 'output_text')
    else:
        choices = value.get('choices', [])
        require(len(choices) == 1 and choices[0].get('finish_reason') == 'stop',
                'Automatic Chat was truncated or returned unexpected choices')
        limit_observed = value.get('lie_timings', {}).get('output_token_limit')
        text = choices[0].get('message', {}).get('content')
    require(type(limit_observed) is int and limit_observed == limit,
            'Resolved automatic budget differs from the prepared context')
    require(isinstance(text, str), 'Long constrained output is missing')
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise RuntimeError('Long constrained output is malformed or incomplete') from exc
    require(parsed == {'value': TEXT}, 'Long constrained output is incomplete')
    return {'prompt_tokens': prompt, 'output_tokens': output,
            'output_token_limit': limit, 'text': text}


def output_budget_gate(api, model_id, exchange, events, root=Path('/work')):
    result = {'schema': 'synapse-lie.point-output-budget.v1', 'state': 'RUNNING',
              'passed': [], 'witnesses': {},
              'scope': 'Original-weight HTTP budgets, not independent task quality or performance'}
    def save():
        (root/'http-output-budget-result.json').write_text(json.dumps(result, indent=2)+'\n')
    def passed(name, witness):
        result['passed'].append(name)
        result['witnesses'][name] = witness
        save()
    def request(path, body=None):
        row = exchange(api, path, body)
        require(row['status'] == 200, 'Automatic output request failed: '+path)
        return json.loads(row['body'])
    save()
    try:
        models = request('/v1/models')['data']
        selected = [item for item in models if item.get('id') == model_id]
        require(len(selected) == 1, 'Automatic budget model identity missing')
        detail = request('/v1/models/'+model_id)
        context, ceiling = detail.get('context_length'), detail.get('max_output_tokens')
        require(type(context) is int and context == 16384 and
                type(ceiling) is int and ceiling == 4096 and
                selected[0].get('context_length') == context and
                selected[0].get('max_output_tokens') == ceiling,
                'Model list/detail limits differ from the declared server')
        passed('models_context_output_limits', {'context_length': context,
                                                'max_output_tokens': ceiling})
        prompt = 'Return the JSON object prescribed by the schema, exactly and without explanation.'
        for responses in (False, True):
            body = {'model': model_id, 'temperature': 0, 'store': False}
            if responses:
                body.update(input=prompt, text={'format': {'type': 'json_schema',
                            'name': 'long_budget', 'strict': True, 'schema': SCHEMA}})
                path, key, name = '/v1/responses', 'max_output_tokens', 'responses_automatic_output'
            else:
                body.update(messages=[{'role': 'user', 'content': prompt}],
                            response_format={'type': 'json_schema', 'json_schema': {
                            'name': 'long_budget', 'strict': True, 'schema': SCHEMA}})
                path, key, name = '/v1/chat/completions', 'max_tokens', 'chat_automatic_output'
            omitted = validate_completion(request(path, body), responses, context, ceiling)
            streamed = dict(body, stream=True, **{key: None})
            if not responses:
                streamed['stream_options'] = {'include_usage': True}
            row = exchange(api, path, streamed)
            require(row['status'] == 200, 'Null automatic output SSE refused')
            chunks = events(row['body'])
            if responses:
                require(chunks and chunks[-1].get('type') == 'response.completed',
                        'Automatic Responses SSE did not complete')
                value = chunks[-1]['response']
                deltas = ''.join(x.get('delta', '') for x in chunks
                                 if x.get('type') == 'response.output_text.delta')
            else:
                require(chunks and chunks[-1] == '[DONE]' and chunks.count('[DONE]') == 1,
                        'Automatic Chat SSE terminal mismatch')
                deltas, finishes, usage, timings = '', [], [], []
                for chunk in chunks[:-1]:
                    if chunk.get('usage') is not None:
                        usage.append(chunk['usage'])
                    if chunk.get('lie_timings') is not None:
                        timings.append(chunk['lie_timings'])
                    for choice in chunk.get('choices', []):
                        require(choice.get('index') == 0, 'Automatic Chat index mismatch')
                        deltas += choice.get('delta', {}).get('content') or ''
                        if choice.get('finish_reason') is not None:
                            finishes.append(choice['finish_reason'])
                require(finishes == ['stop'] and len(usage) == len(timings) == 1,
                        'Automatic Chat SSE usage/limit mismatch')
                value = {'choices': [{'finish_reason': 'stop', 'message': {'content': deltas}}],
                         'usage': usage[0], 'lie_timings': timings[0]}
            null = validate_completion(value, responses, context, ceiling)
            require(null == omitted and deltas == omitted['text'],
                    'Omitted JSON and null SSE automatic output differ')
            passed(name, {'omitted_json': omitted, 'null_sse': null})
        result['state'] = 'PASSED'
    except BaseException as exc:
        result.update(state='FAILED', error=repr(exc))
        raise
    finally:
        save()
    return result
