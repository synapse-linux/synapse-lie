#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional development review of native HTTP steering captures, not a model judge.

The native C benchmark supplies requests, full SSE chunks and actual timings.
This independent checker separates arithmetic correctness, zero-scale parity
and a predeclared conciseness effect. HOST fixtures never qualify inference.
Original-weight execution additionally requires the campaign ownership protocol.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('steering_quality_files', HERE/'strix-point-steering-build-gate.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)
SCALES = (('minus1', -1), ('minus05', -.5), ('zero', 0),
          ('plus05', .5), ('plus1', 1), ('plus2', 2))
FIELDS = {'model_id', 'fingerprint', 'context', 'chunk', 'seed', 'output_tokens',
          'request_timeout_seconds', 'bank_sha256'}
WORDS = re.compile(r"\b\w+(?:['’-]\w+)*\b", re.UNICODE)


def strict(text):
    def nonfinite(_value):
        raise ValueError('Nonfinite JSON number')
    return json.loads(text, object_pairs_hook=files.strict_object, parse_constant=nonfinite)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def settings(value):
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError('Expected complete steering quality settings')
    for name, low, high in (('context', 512, 8192), ('chunk', 1, 8192),
                           ('seed', 0, 2**63-1), ('output_tokens', 64, 512),
                           ('request_timeout_seconds', 30, 1800)):
        if not integer(value[name], low, high):
            raise ValueError('Invalid steering quality bound: '+name)
    if value['chunk'] > value['context'] or value['output_tokens'] + 256 > value['context']:
        raise ValueError('Insufficient steering request capacity')
    for name in ('model_id', 'fingerprint'):
        if type(value[name]) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value[name]):
            raise ValueError('Invalid steering quality identity: '+name)
    if type(value['bank_sha256']) is not str or not re.fullmatch(r'[0-9a-f]{64}', value['bank_sha256']):
        raise ValueError('Invalid learned bank SHA256')
    return dict(value)


def corpus(value):
    keys = {'schema', 'target_instruction', 'contrast_instruction', 'training_questions', 'held_out'}
    if type(value) is not dict or set(value) != keys or value['schema'] != 'synapse-lie.steering-conciseness.v1':
        raise ValueError('Invalid steering corpus schema')
    train, held = value['training_questions'], value['held_out']
    if type(train) is not list or len(train) != 100 or type(held) is not list or len(held) != 10:
        raise ValueError('Expected 100 training pairs and 10 held-out questions')
    text = [value['target_instruction'], value['contrast_instruction'], *train]
    if any(type(s) is not str or not 1 <= len(s.encode('utf-8')) <= 4096 or
           any(c in s for c in ('\n', '\r', '\0')) or not s.strip() for s in text):
        raise ValueError('Invalid single-line training question or instruction')
    if value['target_instruction'] == value['contrast_instruction'] or len(set(train)) != 100:
        raise ValueError('Duplicate training question or indistinguishable contrast')
    seen = set(train)
    for row in held:
        if type(row) is not dict or set(row) != {'id', 'question', 'answer'}:
            raise ValueError('Invalid held-out question')
        if (type(row['id']) is not str or not re.fullmatch(r'held-[0-9]{2}', row['id']) or
                type(row['question']) is not str or not 1 <= len(row['question'].encode('utf-8')) <= 4096 or
                any(c in row['question'] for c in ('\n', '\r', '\0')) or
                type(row['answer']) is not str or not re.fullmatch(r'-?[0-9]{1,8}', row['answer'])):
            raise ValueError('Invalid held-out identity, question or exact answer')
        if row['question'] in seen or any(row['question'] in q or q in row['question'] for q in train):
            raise ValueError('Training and held-out questions overlap')
        seen.add(row['question'])
    if len({row['id'] for row in held}) != 10:
        raise ValueError('Duplicate held-out identity')
    return value


def requests(data, config, phase):
    if phase not in ('absent', 'bank'):
        raise ValueError('Unknown steering control phase')
    result = []
    schema = {'type': 'object', 'properties': {'answer': {'type': 'string'},
               'explanation': {'type': 'string'}}, 'required': ['answer', 'explanation'],
               'additionalProperties': False}
    choices = [('absent', None)] if phase == 'absent' else SCALES
    for label, scale in choices:
        for row in data['held_out']:
            body = {'messages': [{'role': 'user', 'content': row['question'] +
                    ' Return only a JSON object with answer (the integer as a string) and '
                    'explanation (an explanation in your own words).'}],
                    'temperature': 0, 'seed': config['seed'], 'max_tokens': config['output_tokens'],
                    'store': True, 'response_format': {'type': 'json_schema',
                    'json_schema': {'name': 'arithmetic_explanation', 'strict': True, 'schema': schema}}}
            if scale is not None:
                body['dir_steering_plan'] = [{'position': 0, 'ffn': scale, 'attention': 0}]
            result.append({'id': label+'-'+row['id'], 'body': body})
    return result


def client_command(binary, config, port, directory):
    return [str(binary), '--suite', 'http', '--url', f'http://127.0.0.1:{port}/v1',
            '--model', config['model_id'], '--requests', str(directory/'input.jsonl'),
            '--context-capacity', str(config['context']), '--rope-scaling', 'native',
            '--tg', str(config['output_tokens']), '--warmups', '0', '--repetitions', '1',
            '--server-kv-cache', 'off', '--server-label', 'LIE',
            '--timeout', str(config['request_timeout_seconds']),
            '--output', str(directory/'measurements.jsonl'),
            '--export-requests', str(directory/'requests.jsonl')]


def wire(row, config):
    chunks = row.get('response_chunks')
    if row.get('stream_complete') is not True or type(chunks) is not list or not 1 <= len(chunks) <= 8192:
        raise RuntimeError('Incomplete bounded native SSE observation')
    identifier, content, finishes, usages, phases = None, '', [], [], []
    for chunk in chunks:
        if (type(chunk) is not dict or chunk.get('object') != 'chat.completion.chunk' or
                chunk.get('model') != config['model_id'] or chunk.get('system_fingerprint') != config['fingerprint'] or
                type(chunk.get('id')) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}', chunk['id']) or
                type(chunk.get('choices')) is not list or len(chunk['choices']) > 1):
            raise RuntimeError('Invalid SSE identity or choice count')
        if identifier is None:
            identifier = chunk['id']
        if chunk['id'] != identifier:
            raise RuntimeError('SSE completion identity changed')
        for choice in chunk['choices']:
            if finishes or usages or type(choice) is not dict or type(choice.get('index')) is not int or choice['index'] != 0:
                raise RuntimeError('Choice after terminal event or invalid choice')
            delta = choice.get('delta')
            if type(delta) is not dict or set(delta) - {'role', 'content'} or delta.get('role', 'assistant') != 'assistant':
                raise RuntimeError('Unexpected non-text assistant delta')
            piece = delta.get('content', '')
            if type(piece) is not str or len((content+piece).encode('utf-8')) > 65536:
                raise RuntimeError('Invalid bounded assistant text')
            content += piece
            if choice.get('finish_reason') is not None:
                finishes.append(choice['finish_reason'])
        if chunk.get('usage') is not None:
            if not finishes or chunk['choices']:
                raise RuntimeError('Usage before finish or mixed with choices')
            usages.append(chunk['usage'])
        if chunk.get('lie_timings') is not None:
            phases.append(chunk['lie_timings'])
    if len(finishes) != 1 or len(usages) != 1 or len(phases) != 1:
        raise RuntimeError('Missing or duplicate terminal SSE metadata')
    if type(usages[0]) is not dict or type(phases[0]) is not dict:
        raise RuntimeError('Invalid terminal SSE metadata types')
    if (finishes[0] != row.get('finish_reason') or usages[0] != row.get('usage') or
            phases[0] != row.get('server_timings') or row.get('assistant') != {'role': 'assistant', 'content': content}):
        raise RuntimeError('Saved wire differs from assembled native observation')
    pp, tg, phase = row.get('prompt_tokens'), row.get('output_tokens'), phases[0]
    if (not integer(pp, 1, config['context']-config['output_tokens']) or
            not integer(tg, 1, config['output_tokens']) or type(row.get('cached_tokens')) is not int or row['cached_tokens'] != 0 or
            type(phase) is not dict or phase.get('schema') != 'synapse-lie.request-timings.v1' or
            phase.get('valid') is not True or phase.get('decode_mode') != 'ar' or
            usages[0].get('prompt_tokens') != pp or usages[0].get('completion_tokens') != tg or
            usages[0].get('total_tokens') != pp+tg or
            phase.get('prefill_tokens') != pp or phase.get('decode_tokens') != tg or
            phase.get('output_token_limit') != config['output_tokens'] or
            phase.get('prefill_calls') != math.ceil(pp/config['chunk']) or
            phase.get('decode_calls') != tg+(finishes[0] == 'stop') or finishes[0] not in ('stop', 'length')):
        raise RuntimeError('Invalid physical input, output or execution phases')
    for key in ('cached_tokens', 'ssd_cached_tokens', 'mtp_drafted_tokens', 'mtp_accepted_tokens'):
        if type(phase.get(key)) is not int or phase[key] != 0:
            raise RuntimeError('Cache or speculative work violates the cold AR control')
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        if type(usages[0].get(key)) is not int:
            raise RuntimeError('Untyped physical usage')
    for key in ('prefill_tokens', 'decode_tokens', 'output_token_limit', 'prefill_calls', 'decode_calls'):
        if type(phase.get(key)) is not int:
            raise RuntimeError('Untyped executor count')
    for key in ('prefill_ms', 'decode_ms'):
        if type(phase.get(key)) not in (int, float) or not math.isfinite(phase[key]) or phase[key] <= 0:
            raise RuntimeError('Missing actual executor duration')
    return identifier, content


def snapshot(value, identifier, scale):
    if (type(value) is not dict or value.get('object') != 'synapse-lie.steering' or
            value.get('id') != identifier or type(value.get('choice')) is not int or value['choice'] != 0 or
            value.get('pending') is not False):
        raise RuntimeError('Invalid actual stored steering snapshot')
    if scale is None:
        if value.get('schedule') is not None or value.get('policy') is not None:
            raise RuntimeError('Absent-bank control unexpectedly has a steering policy')
        return
    step = {'position': 0, 'ffn': scale, 'attention': 0, 'attempted': True,
            'applied': True, 'status': 0, 'actual_position': 0}
    schedule = value.get('schedule')
    if (type(schedule) is not dict or schedule != {'count': 1, 'completed': 1, 'applied': 1, 'terminal': True, 'steps': [step]} or
            schedule.get('terminal') is not True or
            any(type(schedule.get(k)) is not int for k in ('count', 'completed', 'applied')) or
            type(schedule['steps'][0].get('position')) is not int or type(schedule['steps'][0].get('status')) is not int or
            type(schedule['steps'][0].get('actual_position')) is not int):
        raise RuntimeError('Declared steering plan was not actually applied at position zero')
    actual_step = schedule['steps'][0]
    if (actual_step.get('attempted') is not True or actual_step.get('applied') is not True or
            any(type(actual_step.get(k)) not in (int, float) for k in ('ffn', 'attention'))):
        raise RuntimeError('Untyped applied steering step')
    policy = value.get('policy')
    if (type(policy) is not dict or type(policy.get('ffn')) not in (int, float) or policy['ffn'] != scale or
            type(policy.get('attention')) not in (int, float) or policy['attention'] != 0 or
            not integer(policy.get('completed_positions'), 1, 8192) or
            not integer(policy.get('history_epochs'), 0, 8192) or
            any(type(policy.get(k)) is not str or not re.fullmatch(r'[0-9a-f]{64}', policy[k])
                for k in ('combined_scope_sha256', 'image_scope_sha256'))):
        raise RuntimeError('Final actual steering policy differs from the applied schedule')


def validate(rows, cases, snapshots, config, data, actual_exits):
    config, data = settings(config), corpus(data)
    if actual_exits != {'absent': 0, 'bank': 0} or any(type(v) is not int for v in actual_exits.values()):
        raise RuntimeError('Both actual native benchmark exits must be zero')
    if set(rows) != {'absent', 'bank'} or set(cases) != {'absent', 'bank'}:
        raise RuntimeError('Missing matched control cohort')
    scores, zero_parity, completion_ids = {}, [], set()
    expected_snapshot_keys = []
    for phase in ('absent', 'bank'):
        wanted = requests(data, config, phase)
        observed = rows[phase]
        if cases[phase] != wanted or type(observed) is not list or len(observed) != len(wanted)+2:
            raise RuntimeError('Incomplete or changed predeclared native workload')
        identity = observed[0]
        expected = {'event': 'identity', 'schema': 'synapse-lie.http-bench.v1', 'model': config['model_id'],
                    'server_label': 'LIE', 'cache_policy': 'off', 'warmups': 0, 'repetitions': 1,
                    'request_options': {}, 'context_capacity_declared': config['context'],
                    'rope_scaling_declared': 'native', 'timeout_seconds': config['request_timeout_seconds'],
                    'target_prompt_tokens': None, 'corpus_seed': None}
        if type(identity) is not dict or any(identity.get(k) != v for k, v in expected.items()):
            raise RuntimeError('Native client identity differs from the matched workload')
        if any(type(identity.get(k)) is not int for k in ('warmups', 'repetitions', 'context_capacity_declared')):
            raise RuntimeError('Untyped native client count')
        if observed[-1] != {'event': 'complete', 'exit_code': 0} or type(observed[-1]['exit_code']) is not int:
            raise RuntimeError('Native cohort lacks a successful terminal event')
        for case, row in zip(wanted, observed[1:-1]):
            body = {'model': config['model_id'], **case['body'], 'stream': True, 'stream_options': {'include_usage': True}}
            if (type(row) is not dict or row.get('event') != 'sample' or row.get('case') != case['id'] or
                    type(row.get('turn')) is not int or row['turn'] != 0 or type(row.get('rep')) is not int or row['rep'] != 0 or
                    row.get('warmup') is not False or row.get('request') != body):
                raise RuntimeError('Actual request differs from the frozen held-out question or scale')
            actual = row['request']
            if (type(actual.get('temperature')) not in (int, float) or actual['temperature'] != 0 or
                    type(actual.get('seed')) is not int or type(actual.get('max_tokens')) is not int or
                    actual.get('store') is not True or actual.get('stream') is not True or
                    actual['stream_options'].get('include_usage') is not True):
                raise RuntimeError('Untyped actual generation control')
            identifier, content = wire(row, config)
            if identifier in completion_ids:
                raise RuntimeError('Duplicate actual completion identity')
            completion_ids.add(identifier)
            label, held_id = case['id'].split('-held-')
            held = next(h for h in data['held_out'] if h['id'] == 'held-'+held_id)
            scale = dict(SCALES).get(label)
            expected_snapshot_keys.append(case['id'])
            snapshot(snapshots.get(case['id']), identifier, scale)
            try:
                answer = strict(content)
            except (ValueError, RuntimeError):
                answer = None
            valid = (type(answer) is dict and set(answer) == {'answer', 'explanation'} and
                     type(answer['answer']) is str and answer['answer'] == held['answer'] and
                     type(answer['explanation']) is str and bool(WORDS.findall(answer['explanation'])) and '\0' not in answer['explanation'])
            natural = row['finish_reason'] == 'stop'
            words = len(WORDS.findall(answer['explanation'])) if valid else None
            scores[case['id']] = {'correct': bool(valid), 'natural_stop': natural,
                                 'explanation_words': words, 'content': content,
                                 'prompt_tokens': row['prompt_tokens'], 'output_tokens': row['output_tokens']}
    if type(snapshots) is not dict or set(snapshots) != set(expected_snapshot_keys):
        raise RuntimeError('Missing, extra or duplicate retained steering observations')
    for held in data['held_out']:
        a, z = (scores[label+'-'+held['id']] for label in ('absent', 'zero'))
        zero_parity.append(all(a[k] == z[k] for k in ('content', 'prompt_tokens', 'output_tokens', 'natural_stop')))
    correctness = all(s['correct'] for s in scores.values())
    natural_stops = all(s['natural_stop'] for s in scores.values())
    effect = {'evaluated': False, 'passed': False}
    if correctness and natural_stops and all(zero_parity):
        low, high = [], []
        for held in data['held_out']:
            baseline = scores['zero-'+held['id']]['explanation_words']
            if not baseline:
                raise RuntimeError('Correct explanation has no countable words')
            low.append(scores['minus1-'+held['id']]['explanation_words']/baseline)
            high.append(scores['plus2-'+held['id']]['explanation_words']/baseline)
        effect = {'evaluated': True, 'negative_ratio_median': statistics.median(low),
                  'positive_ratio_median': statistics.median(high),
                  'negative_shorter_cases': sum(v < 1 for v in low),
                  'positive_longer_cases': sum(v > 1 for v in high)}
        effect['passed'] = (effect['negative_ratio_median'] <= .8 and effect['positive_ratio_median'] >= 1.2 and
                            effect['negative_shorter_cases'] >= 8 and effect['positive_longer_cases'] >= 8)
    passed = correctness and natural_stops and all(zero_parity) and effect['passed']
    return {'state': 'PASSED' if passed else 'QUALITY_FAILED', 'samples': len(scores),
            'learned_bank_sha256': config['bank_sha256'],
            'correct_answers': sum(s['correct'] for s in scores.values()), 'natural_stops': natural_stops,
            'zero_parity_cases': sum(zero_parity), 'conciseness_effect': effect, 'scores': scores,
            'scope': 'Held-out arithmetic correctness and explanation length only; not general model quality, semantic explanation quality or performance.'}


def read(path, limit=64*2**20):
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd()/path
    data, identity = files.regular(path, limit)
    return data, identity


def prepare(directory, data, config):
    corpus(data); settings(config)
    directory.mkdir(exist_ok=False)
    for side in ('target', 'contrast'):
        text = ''.join(data[side+'_instruction']+' Question: '+q+'\n' for q in data['training_questions'])
        (directory/(side+'-prompts.txt')).write_text(text, encoding='utf-8')
    for phase in ('absent', 'bank'):
        selected = directory/phase
        selected.mkdir()
        (selected/'input.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in requests(data, config, phase)), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'review'))
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--corpus', required=True, type=Path)
    parser.add_argument('--settings', required=True, type=Path)
    args = parser.parse_args()
    settings_data, settings_identity = read(args.settings, 65536)
    corpus_data, corpus_identity = read(args.corpus, 2**20)
    config = settings(strict(settings_data))
    data = corpus(strict(corpus_data))
    if args.operation == 'prepare':
        prepare(args.directory, data, config)
        return 0
    # execution.json comes from the own-child supervisor; its actual return codes
    # and identities must also be bound by the outer collection/closure receipt.
    exits = strict(read(args.directory/'execution.json', 2**20)[0])['native_exit_codes']
    rows, cases = {}, {}
    for phase in ('absent', 'bank'):
        root = args.directory/phase
        rows[phase] = [strict(line) for line in read(root/'measurements.jsonl')[0].splitlines()]
        cases[phase] = [strict(line) for line in read(root/'requests.jsonl', 2**20)[0].splitlines()]
    snapshots = strict(read(args.directory/'snapshots.json', 2**20)[0])
    proof = validate(rows, cases, snapshots, config, data, exits)
    proof['settings_identity'] = settings_identity
    proof['corpus_identity'] = corpus_identity
    with (args.directory/'quality-review.json').open('x') as output:
        output.write(json.dumps(proof, indent=2)+'\n')
    return 0 if proof['state'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
