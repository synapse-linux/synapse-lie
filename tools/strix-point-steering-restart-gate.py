#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional original-weight physical steering-index/SSD gate, never a product dependency."""
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path('/work')
PREFIX = 2048
BOUNDARY = 128
OUTPUT = 32
PHASES = ('calibration', 'fresh', 'saved', 'reference', 'divergent', 'compatible')
SCHEDULED = PHASES[3:]
QUESTION = '\n\nWhat is 2 + 2? Reply with only the digit.\n'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def ids_digest(ids):
    return hashlib.sha256(b''.join(struct.pack('<i', value) for value in ids)).hexdigest()


def geometry(stream):
    """Read only bounded GGUF metadata up to the two architecture dimensions."""
    consumed = 0

    def read(count):
        nonlocal consumed
        consumed += count
        if count < 0 or consumed > 1024 * 1024:
            raise RuntimeError('GGUF geometry metadata exceeds bound')
        raw = stream.read(count)
        if len(raw) != count:
            raise RuntimeError('Truncated GGUF geometry metadata')
        return raw

    def integer(fmt):
        return struct.unpack('<' + fmt, read(struct.calcsize('<' + fmt)))[0]

    def string():
        size = integer('Q')
        if size > 65536:
            raise RuntimeError('GGUF metadata string exceeds bound')
        return read(size).decode('utf-8')

    scalars = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i',
               6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}

    def value(kind, depth=0):
        if kind in scalars:
            return integer(scalars[kind])
        if kind == 8:
            return string()
        if kind == 9 and not depth:
            subtype, count = integer('I'), integer('Q')
            if count > 65536:
                raise RuntimeError('GGUF metadata array exceeds bound')
            for _ in range(count):
                value(subtype, 1)
            return None
        raise RuntimeError('Unsupported GGUF metadata type')

    if read(4) != b'GGUF' or integer('I') not in (2, 3):
        raise RuntimeError('Unsupported GGUF geometry header')
    integer('Q')  # tensor count; tensor descriptors/payload are never inspected.
    count = integer('Q')
    architecture = None
    dims = {}
    for _ in range(min(count, 1024)):
        key, item = string(), value(integer('I'))
        if key == 'general.architecture':
            if not isinstance(item, str) or not item or len(item) > 128:
                raise RuntimeError('Invalid GGUF architecture')
            architecture = item
        if key.endswith(('.block_count', '.embedding_length')):
            dims[key] = item
        if architecture and all(architecture + suffix in dims for suffix in ('.block_count', '.embedding_length')):
            layers, width = (dims[architecture + suffix] for suffix in ('.block_count', '.embedding_length'))
            if (type(layers) is not int or type(width) is not int or layers <= 0 or width <= 0 or
                    layers > 1024 or width > 65536 or layers * width * 4 > 16 * 1024 * 1024):
                raise RuntimeError('Invalid or oversized steering geometry')
            return architecture, layers, width
    raise RuntimeError('GGUF steering geometry not found within bound')


def bank_bytes(layers, width):
    bank = bytearray(layers * width * 4)
    for layer in range(layers):
        struct.pack_into('<f', bank, (layer * width + layer % width) * 4, 0.125)
    return bytes(bank)


def steps_for(count):
    if not BOUNDARY < count < PREFIX:
        raise RuntimeError('Fresh physical prompt cannot exercise steering boundaries')
    return [{'position': BOUNDARY, 'ffn': 0.5, 'attention': 0.0},
            {'position': count + 1, 'ffn': -0.5, 'attention': 0.25},
            {'position': count + 7, 'ffn': 0.0, 'attention': 0.0}]


def parse(rows, mode, phase, bank, steps):
    if mode not in ('ar', 'mtp') or phase not in PHASES:
        raise RuntimeError('Unknown phase or mode')
    if not rows or rows[-1] != {'event': 'complete', 'exit_code': 0}:
        raise RuntimeError('Incomplete native process')
    found = {}
    for name in ('identity', 'core_ready', 'input', 'job', 'sample'):
        selected = [row for row in rows if row.get('event') == name]
        if len(selected) != 1:
            raise RuntimeError('Missing or duplicated native witness: ' + name)
        found[name] = selected[0]
    identity, ready, inputs, job, sample = (found[name] for name in found)
    scheduled = phase in SCHEDULED
    disk = phase in ('saved', 'divergent', 'compatible')
    expected = {'schema': 'synapse-lie.core-bench.v1', 'synthetic': False, 'mode': mode,
                'execution': 'shared-reactive-core', 'cache_policy': 'ssd' if disk else 'off',
                'input_kind': 'physical-tokens' if phase == 'saved' else 'raw-text',
                'eos_policy': 'ignore', 'prefix_cache_bytes': 0, 'context_capacity': 4096,
                'prefill_chunk': 256, 'users': 1, 'warmups': 0, 'repetitions': 1,
                'checkpoint_policy': 'ds4', 'cache_text_prefix': True,
                'cache_capture_finish': False, 'cache_cold_max_tokens': BOUNDARY,
                'cache_min_tokens': BOUNDARY, 'cache_continued_tokens': 0,
                'cache_trim_tokens': 0, 'cache_align_tokens': 1}
    if any(identity.get(key) != item for key, item in expected.items()) or identity.get('generation', {}).get('temperature') != 0:
        raise RuntimeError('Unexpected native identity')
    requested = identity.get('steering', {})
    admitted = ready.get('steering', {})
    if (requested.get('requested') is not True or requested.get('ffn') != 0 or requested.get('attention') != 0 or
            requested.get('schedule') != (steps if scheduled else []) or
            admitted.get('admitted') is not True or admitted.get('ffn') != 0 or admitted.get('attention') != 0 or
            admitted.get('bank_file_sha256') != bank['sha256'] or
            admitted.get('host_vector_bytes') != bank['bytes'] or admitted.get('device_vector_bytes') != bank['bytes']):
        raise RuntimeError('Steering bank or declared plan differs')
    ids, outputs = inputs.get('physical_ids'), job.get('output_ids')
    budget = OUTPUT if scheduled else 1
    if (not isinstance(ids, list) or not ids or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in ids) or
            inputs.get('prompt_tokens') != len(ids) or job.get('prompt_tokens') != len(ids) or
            inputs.get('physical_ids_sha256') != ids_digest(ids)):
        raise RuntimeError('Invalid physical input witness')
    if (not isinstance(outputs, list) or len(outputs) != budget or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in outputs) or
            job.get('output_tokens') != budget or sample.get('output_tokens') != budget or job.get('finish') != 'length'):
        raise RuntimeError('Incomplete confirmed output')
    cached = BOUNDARY if phase == 'compatible' else 0
    if (job.get('cached_tokens') != cached or job.get('ssd_cached_tokens') != cached or
            job.get('prefill_tokens') != len(ids) - cached or sample.get('ssd_hits') != (1 if cached else 0) or
            sample.get('ssd_errors') != 0):
        raise RuntimeError('Incorrect physical restore or prefill frontier')
    drained = [row for row in rows if row.get('event') == 'ssd_drained']
    if disk:
        if (len(drained) != 1 or drained[0].get('pending') != 0 or drained[0].get('errors') != 0 or
                drained[0].get('disk_bytes', 0) <= 0 or
                (phase != 'compatible' and drained[0].get('writes', 0) < 1)):
            raise RuntimeError('SSD state was not completely drained')
    elif drained:
        raise RuntimeError('Uncached process used SSD')
    if mode == 'ar' and (job.get('mtp_drafted_tokens') != 0 or job.get('mtp_accepted_tokens') != 0):
        raise RuntimeError('AR process entered MTP')
    if scheduled:
        actual = job.get('steering_schedule', {})
        if (actual.get('terminal') is not True or actual.get('completed') != len(steps) or
                actual.get('applied') != len(steps) or len(actual.get('steps', [])) != len(steps) or
                actual.get('final_ffn') != 0 or actual.get('final_attention') != 0 or
                actual.get('history_epochs', 0) < 3 or actual.get('completed_positions') != len(ids) + budget):
            raise RuntimeError('Incomplete steering history')
        for wanted, applied in zip(steps, actual['steps']):
            if (any(applied.get(key) != item for key, item in wanted.items()) or
                    applied.get('actual_position') != wanted['position'] or applied.get('attempted') is not True or
                    applied.get('applied') is not True or applied.get('status') != 0):
                raise RuntimeError('Steering crossed a physical token boundary')
        if mode == 'mtp' and (job.get('mtp_drafted_tokens', 0) <= 0 or job.get('mtp_accepted_tokens', 0) <= 0 or
                              job.get('max_decode_output_tokens', 0) <= 1):
            raise RuntimeError('Scheduled MTP did not exercise an accepted burst')
    return found


def compare(observations):
    seed = observations['calibration']['input']['physical_ids']
    fresh = observations['fresh']['input']['physical_ids']
    if len(seed) <= 1 or fresh[-len(seed[1:]):] != seed[1:]:
        raise RuntimeError('Question suffix tokenization differs')
    saved = [seed[0]] * PREFIX + seed[1:]
    if observations['saved']['input']['physical_ids'] != saved or len(fresh) >= len(saved):
        raise RuntimeError('Saved physical history is not the divergent text spelling')
    reference = observations['reference']['job']
    for phase in SCHEDULED:
        found = observations[phase]
        if found['input']['physical_ids'] != fresh:
            raise RuntimeError('SSD replaced declared physical steering indices')
        if found['job']['output_ids'] != reference['output_ids']:
            raise RuntimeError('Scheduled cold/SSD confirmed outputs differ')
        if found['job']['steering_schedule'] != reference['steering_schedule']:
            raise RuntimeError('Scheduled cold/SSD final policy histories differ')
    return {'fresh_physical_tokens': len(fresh), 'saved_physical_tokens': len(saved),
            'fresh_ids_sha256': ids_digest(fresh), 'saved_ids_sha256': ids_digest(saved),
            'scheduled_physical_ids_equal': True, 'scheduled_output_ids_equal': True,
            'scheduled_policy_histories_equal': True,
            'divergent_cached_tokens': observations['divergent']['job']['cached_tokens'],
            'compatible_cached_tokens': observations['compatible']['job']['cached_tokens'],
            'scheduled_positions': [step['position'] for step in reference['steering_schedule']['steps']]}


def main():
    args = sys.argv[1:]
    if len(args) not in (3, 4) or args[2] not in ('ar', 'mtp') or (len(args) == 4) != (args[2] == 'mtp'):
        raise SystemExit('Usage: steering-restart-gate.py BENCH MODEL ar|mtp [PREDICTOR]')
    binary, model, mode = args[:3]
    result = {'schema': 'synapse-lie.point-steering-restart.v1', 'state': 'RUNNING', 'mode': mode,
              'started_at': now(), 'processes': [],
              'scope': 'Original model weights with an owned sparse nonzero direction fixture; '
                       'exact physical schedule/cache regression, not DS4 learned-vector quality or performance.'}
    observations, steps = {}, []
    try:
        kv = ROOT / 'kv'
        if not kv.is_dir() or list(kv.iterdir()):
            raise RuntimeError('Fresh private SSD directory required')
        with open(model, 'rb') as stream:
            architecture, layers, width = geometry(stream)
        raw_bank = bank_bytes(layers, width)
        with (ROOT / 'steering.f32').open('xb') as output:
            output.write(raw_bank)
        bank = {'architecture': architecture, 'layers': layers, 'width': width,
                'bytes': len(raw_bank), 'sha256': hashlib.sha256(raw_bank).hexdigest(),
                'nonzero_values': layers, 'fixture': 'one 0.125 binary32 coordinate per layer'}
        result['bank'] = bank
        for name, value in (('calibration.txt', 'a' + QUESTION), ('prompt.txt', 'a' * PREFIX + QUESTION)):
            with (ROOT / name).open('x') as output:
                output.write(value)
        base = [binary, '--suite', 'core', '--model', model, '--context', '4096', '--chunk', '256',
                '--users', '1', '--warmups', '0', '--repetitions', '1', '--ignore-eos',
                '--kv-cache-ram-mb', '0', '--kv-cache-policy', 'ds4', '--kv-cache-min-tokens', str(BOUNDARY),
                '--kv-cache-cold-max-tokens', str(BOUNDARY), '--kv-cache-boundary-trim-tokens', '0',
                '--kv-cache-boundary-align-tokens', '1', '--kv-cache-continued-interval-tokens', '0',
                '--kv-cache-capture-finish', 'off', '--timeout-ms', '600000',
                '--dir-steering-file', '/work/steering.f32', '--dir-steering-ffn', '0', '--dir-steering-attn', '0']
        if mode == 'mtp':
            base += ['--model-mtp', args[3], '--mtp-draft-tokens', '7']
        for phase in PHASES:
            command = base + ['--tg', str(OUTPUT if phase in SCHEDULED else 1),
                              '--output', f'/work/measurements-{phase}.jsonl']
            if phase == 'saved':
                seed = observations['calibration']['input']['physical_ids']
                with (ROOT / 'tokens.json').open('x') as output:
                    json.dump([seed[0]] * PREFIX + seed[1:], output)
                    output.write('\n')
                command += ['--tokens-file', '/work/tokens.json']
            else:
                command += ['--prompt-file', '/work/' + ('calibration.txt' if phase == 'calibration' else 'prompt.txt')]
            if phase in SCHEDULED:
                if phase == 'reference':
                    steps = steps_for(len(observations['fresh']['input']['physical_ids']))
                    with (ROOT / 'steering-plan.json').open('x') as output:
                        json.dump(steps, output)
                        output.write('\n')
                command += ['--dir-steering-plan', '/work/steering-plan.json']
            if phase in ('saved', 'divergent', 'compatible'):
                command += ['--kv-disk-dir', '/work/kv', '--kv-disk-space-mb', '4096', '--kv-disk-staging-mb', '512']
            (ROOT / 'steering-progress.json').write_text(json.dumps({'phase': phase, 'started_at': now(),
                                                                   'completed': list(observations)}) + '\n')
            if phase == 'calibration':
                with (ROOT / 'restart-started.marker').open('x') as marker:
                    marker.write(now() + '\n')
            with (ROOT / ('bench-' + phase + '.log')).open('xb') as log:
                child = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=660, check=False)
            result['processes'].append({'phase': phase, 'argv': command, 'exit_code': child.returncode})
            if child.returncode:
                raise RuntimeError(phase + ' native process failed: ' + str(child.returncode))
            raw = (ROOT / ('measurements-' + phase + '.jsonl')).read_bytes()
            result[phase + '_sha256'] = hashlib.sha256(raw).hexdigest()
            observations[phase] = parse([json.loads(line) for line in raw.splitlines()], mode, phase, bank, steps)
            if phase in ('calibration', 'fresh') and list(kv.iterdir()):
                raise RuntimeError('Calibration contaminated SSD state')
        result.update(compare(observations), state='PASSED', steps=steps)
        result['scheduled_jobs'] = {phase: observations[phase]['job'] for phase in SCHEDULED}
        result['kv_file_bytes'] = {path.name: path.stat().st_size for path in kv.iterdir() if path.is_file()}
    except BaseException as error:
        result.update(state='FAILED', error=repr(error))
    finally:
        result['ended_at'] = now()
        (ROOT / 'steering-restart-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if result['state'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
