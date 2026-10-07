#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional original-weight function transition gate; no product dependency."""
import json
from pathlib import Path

PROFILES = (
    ('greedy', {'temperature': 0, 'top_p': 1, 'top_k': 0, 'min_p': 0}),
    ('ds4', {'temperature': 1, 'top_p': 1, 'top_k': 0, 'min_p': .05}),
    ('filtered', {'temperature': .8, 'top_p': .9, 'top_k': 32, 'min_p': .02}),
)
CASES = {
    'auto-text': ('Do not call any function. Reply with only READY.', 'auto', True, (), False),
    'prose-call': ('First write the sentence Checking values. Then call get_value once with key alpha. Do not add more text.',
                   'auto', False, ('alpha',), True),
    'parallel': ('Call get_value exactly twice in this turn: once with key alpha and once with key beta. '
                 'Both calls are independent and must be issued together. Do not explain.',
                 'required', True, ('alpha', 'beta'), False),
    'single': ('Call get_value once with key alpha. Do not explain.',
               'required', False, ('alpha',), False),
}
CHECKS = frozenset(
    f'{profile}_{api}_{case}_{wire}' for profile, _ in PROFILES
    for api in ('chat', 'responses') for case in CASES for wire in ('json', 'sse')
) | frozenset(
    f'{profile}_{api}_correlated_results_{wire}' for profile, _ in PROFILES
    for api in ('chat', 'responses') for wire in ('json', 'sse')
) | frozenset(f'{profile}_responses_parallel_replay' for profile, _ in PROFILES) | frozenset(
    f'{api}_refusal_{case}' for api in ('chat', 'responses')
    for case in ('orphan', 'missing', 'duplicate', 'unknown')
)
FUNCTION = {
    'name': 'get_value', 'description': 'Get the independent integer value for the selected key.',
    'strict': True, 'parameters': {
        'type': 'object', 'properties': {'key': {'type': 'string', 'enum': ['alpha', 'beta']}},
        'required': ['key'], 'additionalProperties': False,
    },
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class ModelQualityError(RuntimeError):
    """A valid model response did not fulfill the predeclared question."""


def require_model(condition, message):
    if not condition:
        raise ModelQualityError(message)


def object_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON property')
            result[key] = value
        return result
    def constant(_):
        raise RuntimeError('Nonfinite JSON constant')
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (TypeError, ValueError) as error:
        raise RuntimeError('Malformed JSON object') from error
    require(type(value) is dict, 'JSON object required')
    return value


def normalized(value, responses):
    """Validate completed wire objects independently of product parsers."""
    require(type(value) is dict, 'Completion must be an object')
    if responses:
        require(value.get('status') == 'completed', 'Responses did not complete naturally')
        items = value.get('output')
        require(type(items) is list, 'Missing Responses items')
        text, calls, seen_call = '', [], False
        for item in items:
            require(type(item) is dict and item.get('status') == 'completed', 'Incomplete output item')
            if item.get('type') == 'function_call':
                seen_call = True
                calls.append({'id': item.get('call_id'), 'name': item.get('name'), 'arguments': item.get('arguments')})
            else:
                require(item.get('type') == 'message' and item.get('role') == 'assistant' and not seen_call,
                        'Unexpected output type/order')
                parts = item.get('content')
                require(type(parts) is list and parts, 'Missing output text parts')
                for part in parts:
                    require(part.get('type') == 'output_text' and type(part.get('text')) is str,
                            'Invalid output text part')
                    text += part['text']
        usage = value.get('usage', {})
        prompt, output = usage.get('input_tokens'), usage.get('output_tokens')
    else:
        choices = value.get('choices')
        require(type(choices) is list and len(choices) == 1 and
                type(choices[0].get('index')) is int and choices[0]['index'] == 0,
                'Expected one indexed Chat choice')
        choice = choices[0]
        message = choice.get('message', {})
        require(message.get('role') == 'assistant', 'Invalid assistant role')
        text = message.get('content')
        require(text is None or type(text) is str, 'Invalid Chat text')
        text = text or ''
        raw = message.get('tool_calls', [])
        require(type(raw) is list, 'Invalid Chat tool calls')
        calls = []
        for call in raw:
            require(call.get('type') == 'function', 'Invalid Chat tool type')
            fn = call.get('function', {})
            calls.append({'id': call.get('id'), 'name': fn.get('name'), 'arguments': fn.get('arguments')})
        require(choice.get('finish_reason') == ('tool_calls' if calls else 'stop'), 'Unexpected Chat finish')
        usage = value.get('usage', {})
        prompt, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
    require(type(prompt) is int and prompt > 0 and type(output) is int and 0 < output <= 512 and
            type(usage.get('total_tokens')) is int and usage['total_tokens'] == prompt + output,
            'Invalid completion token accounting')
    identities = set()
    for call in calls:
        require(type(call['id']) is str and call['id'] and call['id'] not in identities,
                'Missing/duplicate call identity')
        identities.add(call['id'])
        require(call['name'] == 'get_value' and type(call['arguments']) is str, 'Unexpected function identity')
        args = object_json(call['arguments'])
        require(set(args) == {'key'} and args['key'] in ('alpha', 'beta'), 'Invalid independent function arguments')
        call['parsed_arguments'] = args
    return {'text': text, 'calls': calls, 'prompt_tokens': prompt, 'output_tokens': output,
            'timings': value.get('lie_timings')}


def chat_stream(chunks):
    require(chunks and chunks[-1] == '[DONE]' and chunks.count('[DONE]') == 1, 'Chat sentinel mismatch')
    text, calls, finish, usage, timings = '', {}, None, None, None
    for chunk in chunks[:-1]:
        require(type(chunk) is dict and 'error' not in chunk, 'Chat stream error')
        if chunk.get('usage') is not None:
            require(usage is None, 'Duplicate Chat usage')
            usage = chunk['usage']
        if chunk.get('lie_timings') is not None:
            timings = chunk['lie_timings']
        for choice in chunk.get('choices', []):
            require(type(choice.get('index')) is int and choice['index'] == 0 and finish is None,
                    'Unknown choice/data after terminal')
            delta = choice.get('delta', {})
            piece = delta.get('content')
            require(piece is None or type(piece) is str, 'Invalid Chat text delta')
            require(not piece or not calls, 'Text arrived after function start')
            text += piece or ''
            for part in delta.get('tool_calls', []):
                index = part.get('index')
                require(type(index) is int and index >= 0, 'Invalid function index')
                fn = part.get('function', {})
                if 'id' in part:
                    require(index == len(calls) and part.get('type') == 'function' and index not in calls,
                            'Repeated/noncontiguous function start')
                    calls[index] = {'id': part['id'], 'type': 'function',
                                    'function': {'name': fn.get('name'), 'arguments': ''}}
                require(index in calls and ('name' not in fn or fn['name'] == calls[index]['function']['name']),
                        'Arguments preceded start/name changed')
                argument = fn.get('arguments', '')
                require(type(argument) is str, 'Invalid argument fragment')
                calls[index]['function']['arguments'] += argument
            if choice.get('finish_reason') is not None:
                finish = choice['finish_reason']
    require(finish is not None and usage is not None, 'Incomplete Chat SSE')
    return normalized({'choices': [{'index': 0, 'finish_reason': finish,
                       'message': {'role': 'assistant', 'content': text, 'tool_calls': list(calls.values())}}],
                       'usage': usage, 'lie_timings': timings}, False)


def response_stream(chunks):
    require(chunks and all(type(x) is dict for x in chunks), 'Malformed Responses SSE')
    require(all(type(x.get('sequence_number')) is int for x in chunks) and
            [x['sequence_number'] for x in chunks] == list(range(len(chunks))), 'Responses sequence mismatch')
    terminal = [x for x in chunks if x.get('type') in ('response.completed', 'response.incomplete', 'response.failed')]
    require(len(terminal) == 1 and terminal[0] is chunks[-1] and terminal[0]['type'] == 'response.completed',
            'Responses terminal mismatch')
    calls, text = {}, ''
    for item in chunks[:-1]:
        kind = item.get('type')
        if kind == 'response.output_item.added' and item['item'].get('type') == 'function_call':
            index, call = item.get('output_index'), item['item']
            require(type(index) is int and index >= 0 and index not in calls and
                    call.get('status') == 'in_progress' and call.get('arguments') == '', 'Invalid Responses call start')
            calls[index] = {'item': call, 'arguments': '', 'done': False, 'item_done': None}
        elif kind in ('response.function_call_arguments.delta', 'response.function_call_arguments.done'):
            index = item.get('output_index')
            require(type(index) is int and index in calls, 'Responses arguments preceded start')
            call = calls[index]
            require(item.get('item_id') == call['item']['id'] and not call['done'], 'Responses call changed/repeated done')
            if kind.endswith('.delta'):
                require(type(item.get('delta')) is str, 'Invalid Responses argument fragment')
                call['arguments'] += item['delta']
            else:
                require(item.get('arguments') == call['arguments'] and item.get('name') == call['item']['name'],
                        'Responses argument done differs from deltas')
                call['done'] = True
        elif kind == 'response.output_item.done' and item['item'].get('type') == 'function_call':
            index = item.get('output_index')
            require(type(index) is int and index in calls and calls[index]['done'] and
                    calls[index]['item_done'] is None, 'Invalid Responses item done')
            calls[index]['item_done'] = item['item']
        elif kind == 'response.output_text.delta':
            require(type(item.get('delta')) is str and (not item['delta'] or not calls), 'Text after Responses function')
            text += item['delta']
    final = chunks[-1]['response']
    result = normalized(final, True)
    require(text == result['text'] and len(calls) == len(result['calls']), 'Responses deltas/final differ')
    for index, call in calls.items():
        require(index < len(final['output']) and call['item_done'] == final['output'][index] and
                call['arguments'] == final['output'][index]['arguments'] and
                call['item']['id'] == final['output'][index]['id'] and
                call['item']['call_id'] == final['output'][index]['call_id'] and
                call['item']['name'] == final['output'][index]['name'], 'Responses item identity/final differs')
    return result, final


def semantic(result):
    return {'text': result['text'], 'calls': [(c['name'], c['parsed_arguments']) for c in result['calls']],
            'prompt_tokens': result['prompt_tokens'], 'output_tokens': result['output_tokens']}


def transitions_gate(api, model_id, exchange, events, root=Path('/work'), *, management, mode):
    require(mode in ('ar', 'mtp'), 'Explicit AR/MTP gate mode required')
    result = {'schema': 'synapse-lie.point-tool-transitions.v1', 'state': 'RUNNING', 'passed': [], 'witnesses': {},
              'scope': 'Original-weight selected HTTP function/text/result transitions; no independent probability or performance claim',
              'profiles': [dict(name=name, seed=123, **settings) for name, settings in PROFILES],
              'decode_mode': mode, 'refusals_before_forward_verified': False}
    def save():
        (root/'http-tool-transitions-result.json').write_text(json.dumps(result, indent=2)+'\n')
    def passed(name, witness):
        require(name in CHECKS and name not in result['passed'], 'Unknown/duplicate transition check')
        result['passed'].append(name); result['witnesses'][name] = witness; save()
    def send(responses, body, streaming=False, expected=200):
        body = dict(body, stream=streaming)
        if streaming and not responses: body['stream_options'] = {'include_usage': True}
        row = exchange(api, '/v1/responses' if responses else '/v1/chat/completions', body)
        require(row['status'] == expected, 'Unexpected transition HTTP status: '+str(row['status']))
        if expected != 200:
            value = object_json(row['body']); require(type(value.get('error')) is dict, 'Missing refusal error')
            return value, row
        if streaming:
            chunks = events(row['body'])
            return response_stream(chunks) + (row,) if responses else (chat_stream(chunks), None, row)
        value = object_json(row['body'])
        return normalized(value, responses), value, row
    def work():
        row = exchange(management, '/actuator/llm')
        require(row['status'] == 200, 'Missing executor observation')
        value = object_json(row['body'])
        scheduler = value.get('scheduler', {})
        executor = scheduler.get('executor', {})
        require(value.get('ready') is True and executor.get('phase') == 'none' and
                all(type(scheduler.get(k)) is int and scheduler[k] == 0 for k in ('active', 'queued')),
                'Refusal observation requires idle ready executor')
        fields = ('prefill_started', 'prefill_returned', 'decode_started', 'decode_returned',
                  'mtp_drafted_tokens', 'mtp_accepted_tokens')
        require(all(type(executor.get(k)) is int and executor[k] >= 0 for k in fields), 'Invalid executor counters')
        return {k: executor[k] for k in fields}
    save()
    try:
        for profile, controls in PROFILES:
            for api_name in ('chat', 'responses'):
                responses = api_name == 'responses'
                base = {'model': model_id, 'store': False, 'seed': 123, **controls}
                base['tools'] = [dict(FUNCTION, type='function')] if responses else [{'type': 'function', 'function': FUNCTION}]
                base['max_output_tokens' if responses else 'max_tokens'] = 512
                for case, (prompt, choice, parallel, keys, prose) in CASES.items():
                    body = dict(base, tool_choice=choice, parallel_tool_calls=parallel)
                    body['input' if responses else 'messages'] = prompt if responses else [{'role': 'user', 'content': prompt}]
                    expected = None
                    for wire in ('json', 'sse'):
                        result['current_check'] = f'{profile}_{api_name}_{case}_{wire}'; save()
                        selected = dict(body, store=responses and wire == 'sse' and case == 'parallel')
                        observed, final, row = send(responses, selected, wire == 'sse')
                        actual = [c['parsed_arguments']['key'] for c in observed['calls']]
                        require_model(sorted(actual) == sorted(keys), 'Model selected incorrect requested function keys: '+case)
                        require_model(not prose or observed['text'].strip(), 'Model omitted requested prose before function')
                        require_model(case != 'auto-text' or observed['text'].strip() == 'READY', 'Model failed explicit no-tool answer')
                        if expected is not None: require(semantic(observed) == expected, 'Seeded JSON/SSE transition drift')
                        expected = semantic(observed)
                        if not responses:
                            timings = observed['timings']
                            require(type(timings) is dict and timings.get('valid') is True and
                                    timings.get('decode_mode') == mode and
                                    all(type(timings.get(k)) is int and timings[k] >= 0 for k in
                                        ('mtp_drafted_tokens', 'mtp_accepted_tokens')) and
                                    timings['mtp_accepted_tokens'] <= timings['mtp_drafted_tokens'],
                                    'Missing actual selected decode-mode counters')
                        passed(f'{profile}_{api_name}_{case}_{wire}', observed)
                        if case != 'parallel': continue
                        outputs = [{'type': 'function_call_output', 'call_id': c['id'],
                                    'output': json.dumps({'value': 137 if c['parsed_arguments']['key'] == 'alpha' else 941})}
                                   for c in reversed(observed['calls'])]
                        instruction = 'Return only one JSON object mapping alpha and beta to their returned integer values. Do not call functions.'
                        follow = dict(base, tool_choice='none')
                        if responses:
                            follow['text'] = {'format': {'type': 'json_object'}}
                            history = [{'role': 'user', 'content': prompt}] + [
                                {'type': 'function_call', 'call_id': c['id'], 'name': c['name'], 'arguments': c['arguments']}
                                for c in observed['calls']]
                            if wire == 'sse':
                                replay = exchange(api, '/v1/responses/'+final['id']+'?stream=true')
                                require(replay['status'] == 200 and replay['body'] == row['body'], 'Function journal replay changed')
                                passed(f'{profile}_responses_parallel_replay', {'id': final['id'], 'exact_wire_replay': True})
                                follow['previous_response_id'] = final['id']; history = []
                            follow['input'] = history + outputs + [{'role': 'user', 'content': instruction}]
                        else:
                            follow['response_format'] = {'type': 'json_object'}
                            history = [{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': observed['text'] or None,
                                       'tool_calls': [{'id': c['id'], 'type': 'function', 'function': {
                                           'name': c['name'], 'arguments': c['arguments']}} for c in observed['calls']]}]
                            follow['messages'] = history + [{'role': 'tool', 'tool_call_id': x['call_id'], 'content': x['output']}
                                                          for x in outputs] + [{'role': 'user', 'content': instruction}]
                        result['current_check'] = f'{profile}_{api_name}_correlated_results_{wire}'; save()
                        reply, _, _ = send(responses, follow, wire == 'sse')
                        values = object_json(reply['text'])
                        require_model(not reply['calls'] and values == {'alpha': 137, 'beta': 941} and
                                all(type(x) is int for x in values.values()),
                                'Model confused correlated distinct/reversed function results')
                        passed(f'{profile}_{api_name}_correlated_results_{wire}', reply)
                # Invalid history must refuse before generation. Fixed identities
                # are client-supplied historical calls, never fabricated GPU output.
                calls = [{'id': 'history-alpha', 'type': 'function', 'function': {
                    'name': 'get_value', 'arguments': '{"key":"alpha"}'}},
                         {'id': 'history-beta', 'type': 'function', 'function': {
                    'name': 'get_value', 'arguments': '{"key":"beta"}'}}]
                if profile != 'greedy': continue
                for refusal in ('orphan', 'missing', 'duplicate', 'unknown'):
                    ids = {'orphan': ['orphan'], 'missing': ['history-alpha'],
                           'duplicate': ['history-alpha', 'history-alpha', 'history-beta'],
                           'unknown': ['history-alpha', 'unknown']}[refusal]
                    user = {'role': 'user', 'content': 'Return both values.'}
                    if responses:
                        history = [user] + ([] if refusal == 'orphan' else [
                            dict(type='function_call', call_id=c['id'], **c['function']) for c in calls])
                        history += [{'type': 'function_call_output', 'call_id': identity, 'output': '{"value":137}'} for identity in ids]
                    else:
                        history = [user] + ([] if refusal == 'orphan' else [{'role': 'assistant', 'content': None, 'tool_calls': calls}])
                        history += [{'role': 'tool', 'tool_call_id': identity, 'content': '{"value":137}'} for identity in ids]
                    invalid = dict(base, tool_choice='none')
                    invalid['input' if responses else 'messages'] = history + [user]
                    result['current_check'] = f'{api_name}_refusal_{refusal}'; save()
                    before = work()
                    error, _ = send(responses, invalid, expected=400)
                    after = work()
                    require(after == before, 'Invalid function history performed model work')
                    passed(f'{api_name}_refusal_{refusal}', {'http_status': 400, 'error': error['error'],
                                                          'executor_before': before, 'executor_after': after})
        require(set(result['passed']) == CHECKS and len(result['passed']) == len(CHECKS), 'Incomplete transition inventory')
        drafted = sum(w['timings']['mtp_drafted_tokens'] for w in result['witnesses'].values()
                      if type(w.get('timings')) is dict)
        require(mode != 'mtp' or drafted > 0, 'MTP-enabled gate observed no actual proposals')
        result['observed_chat_drafted_tokens'] = drafted
        result['refusals_before_forward_verified'] = True
        result['current_check'] = None
        result['state'] = 'PASSED'
    except BaseException as error:
        result.update(state='FAILED', error=repr(error), failure_kind=(
            'model_quality' if isinstance(error, ModelQualityError) else 'protocol_or_infrastructure'))
        raise
    finally:
        save()
    return result
