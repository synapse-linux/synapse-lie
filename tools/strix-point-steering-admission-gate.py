#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional real-model bank refusal and zero-scale equivalence qualification."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys

ROOT = Path('/work')
OUTPUT = 32
SUCCESS = ('absent', 'zero', 'recovery')
CASES = ('empty', 'truncated', 'oversized', 'nan-first', 'nan-last', 'snan-middle',
         'positive-infinity', 'negative-infinity', 'directory', 'symlink', 'fifo', 'missing')
GEOMETRY_ERROR = 'steering file does not match model geometry'
FINITE_ERROR = 'nonfinite steering direction'
OPEN_ERROR = 'cannot open steering bank'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def ids_digest(ids):
    return hashlib.sha256(b''.join(struct.pack('<i', item) for item in ids)).hexdigest()


def expected_error(case):
    if case in ('empty', 'truncated', 'oversized', 'directory', 'fifo'):
        return GEOMETRY_ERROR
    if case in ('symlink', 'missing'):
        return OPEN_ERROR
    if case in ('nan-first', 'nan-last', 'snan-middle', 'positive-infinity', 'negative-infinity'):
        return FINITE_ERROR
    raise RuntimeError('Unknown malformed bank case')


def parse_identity(rows, mode, requested, ffn, attention):
    identities = [row for row in rows if row.get('event') == 'identity']
    if len(identities) != 1:
        raise RuntimeError('Missing or duplicate native identity')
    identity = identities[0]
    expected = {'schema': 'synapse-lie.core-bench.v1', 'synthetic': False, 'mode': mode,
                'execution': 'shared-reactive-core', 'cache_policy': 'off', 'prefix_cache_bytes': 0,
                'input_kind': 'raw-text', 'context_capacity': 4096, 'prefill_chunk': 256,
                'users': 1, 'warmups': 0, 'repetitions': 1, 'eos_policy': 'ignore'}
    if (mode not in ('ar', 'mtp') or any(identity.get(key) != value for key, value in expected.items()) or
            identity.get('generation', {}).get('temperature') != 0):
        raise RuntimeError('Unexpected original-weight native identity')
    steering = identity.get('steering', {})
    if (steering.get('requested') is not requested or steering.get('ffn') != ffn or
            steering.get('attention') != attention or steering.get('schedule') != []):
        raise RuntimeError('Unexpected steering admission request')
    return identity


def parse_refusal(rows, actual_exit, mode, case):
    parse_identity(rows, mode, True, 1, 0.5)
    if (actual_exit != 1 or len(rows) != 2 or rows[-1] !=
            {'event': 'failed', 'exit_code': 1, 'error': 'core readiness failed: ' + expected_error(case)}):
        raise RuntimeError('Bank was not refused before core readiness with its exact diagnostic')
    return {'case': case, 'actual_native_exit_code': actual_exit,
            'diagnostic': rows[-1]['error'], 'core_ready': False, 'numerical_job': False}


def parse_success(rows, actual_exit, mode, phase, bank):
    if phase not in SUCCESS:
        raise RuntimeError('Unknown successful phase')
    parse_identity(rows, mode, phase != 'absent', 0, 0)
    if actual_exit != 0 or not rows or rows[-1] != {'event': 'complete', 'exit_code': 0}:
        raise RuntimeError('Incomplete successful original-weight process')
    found = {}
    for name in ('core_ready', 'input', 'job', 'sample'):
        selected = [row for row in rows if row.get('event') == name]
        if len(selected) != 1:
            raise RuntimeError('Missing or duplicate successful native witness: ' + name)
        found[name] = selected[0]
    if any(row.get('event') in ('failed', 'ssd_drained') for row in rows):
        raise RuntimeError('Unexpected failure or SSD in zero-scale qualification')
    admitted = found['core_ready'].get('steering', {})
    expected_bytes = bank['bytes'] if phase != 'absent' else 0
    if (admitted.get('admitted') is not (phase != 'absent') or admitted.get('ffn') != 0 or
            admitted.get('attention') != 0 or admitted.get('host_vector_bytes') != expected_bytes or
            admitted.get('device_vector_bytes') != expected_bytes or
            admitted.get('bank_file_sha256') != (bank['sha256'] if phase != 'absent' else '')):
        raise RuntimeError('Incorrect zero-scale or absent-bank admission')
    inputs, job, sample = (found[name] for name in ('input', 'job', 'sample'))
    ids, output = inputs.get('physical_ids'), job.get('output_ids')
    if (not isinstance(ids, list) or not ids or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in ids) or
            inputs.get('physical_ids_sha256') != ids_digest(ids) or inputs.get('prompt_tokens') != len(ids) or
            job.get('prompt_tokens') != len(ids) or job.get('prefill_tokens') != len(ids) or
            job.get('cached_tokens') != 0 or job.get('ssd_cached_tokens') != 0):
        raise RuntimeError('Incorrect physical input or hidden cache reuse')
    if (not isinstance(output, list) or len(output) != OUTPUT or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in output) or
            job.get('output_tokens') != OUTPUT or sample.get('output_tokens') != OUTPUT or
            job.get('finish') != 'length' or sample.get('ssd_hits') != 0 or sample.get('ssd_errors') != 0):
        raise RuntimeError('Incomplete successful output')
    if mode == 'ar' and (job.get('mtp_drafted_tokens') != 0 or job.get('mtp_accepted_tokens') != 0):
        raise RuntimeError('AR entered MTP')
    if mode == 'mtp':
        drafted, accepted = job.get('mtp_drafted_tokens'), job.get('mtp_accepted_tokens')
        if (type(drafted) is not int or type(accepted) is not int or
                drafted <= 0 or not 0 <= accepted <= drafted):
            raise RuntimeError('MTP baseline lacks real drafting or valid acceptance counters')
    return found


def compare(successes, refusals):
    if set(successes) != set(SUCCESS) or [row['case'] for row in refusals] != list(CASES):
        raise RuntimeError('Incomplete bank refusal/recovery campaign')
    reference = successes['absent']
    for phase in SUCCESS:
        row = successes[phase]
        if row['input']['physical_ids'] != reference['input']['physical_ids']:
            raise RuntimeError('Absent/zero/recovery physical inputs differ')
        if row['job']['output_ids'] != reference['job']['output_ids']:
            raise RuntimeError('Absent/zero/recovery confirmed output IDs differ')
    return {'physical_input_ids_equal': True, 'output_ids_equal': True,
            'prompt_tokens': reference['input']['prompt_tokens'],
            'output_tokens': OUTPUT, 'expected_refusals': len(refusals),
            'fresh_core_after_refusals': True}


def create_cases(directory, valid):
    directory.mkdir(mode=0o700)
    results = {}
    for case in CASES:
        path = directory / (case + '.f32')
        if case == 'directory':
            path.mkdir(mode=0o700)
        elif case == 'symlink':
            path.symlink_to(valid)
        elif case == 'fifo':
            os.mkfifo(path, 0o600)
        elif case == 'missing':
            pass
        else:
            raw = valid.read_bytes()
            if case == 'empty':
                raw = b''
            elif case == 'truncated':
                raw = raw[:-4]
            elif case == 'oversized':
                raw += b'\0' * 4
            else:
                offset = 0 if case in ('nan-first', 'positive-infinity') else len(raw) - 4
                bits = {'nan-first': 0x7fc00000, 'nan-last': 0x7fc00000,
                        'snan-middle': 0x7f800001, 'positive-infinity': 0x7f800000,
                        'negative-infinity': 0xff800000}[case]
                if case == 'snan-middle':
                    offset = len(raw) // 8 * 4
                changed = bytearray(raw)
                struct.pack_into('<I', changed, offset, bits)
                raw = bytes(changed)
            with path.open('xb') as output:
                output.write(raw)
        results[case] = path
    return results


def case_metadata(cases):
    """Bind regular fixture bytes; never open the intentionally unsafe inputs."""
    result = {}
    for case, path in cases.items():
        row = {'path': str(path)}
        try:
            info = path.lstat()
        except FileNotFoundError:
            row['kind'] = 'missing'
        else:
            if stat.S_ISREG(info.st_mode):
                row.update(kind='regular', bytes=info.st_size,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            elif stat.S_ISLNK(info.st_mode):
                row.update(kind='symlink', target=os.readlink(path))
            elif stat.S_ISFIFO(info.st_mode):
                row['kind'] = 'fifo'
            elif stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
            else:
                raise RuntimeError('Unexpected fixture kind')
        result[case] = row
    return result


def main():
    args = sys.argv[1:]
    if len(args) not in (3, 4) or args[2] not in ('ar', 'mtp') or (len(args) == 4) != (args[2] == 'mtp'):
        raise SystemExit('Usage: steering-admission-gate.py BENCH MODEL ar|mtp [PREDICTOR]')
    binary, model, mode = args[:3]
    result = {'schema': 'synapse-lie.point-steering-admission.v1', 'state': 'RUNNING',
              'mode': mode, 'started_at': now(), 'processes': [],
              'scope': 'Real-model metadata refusal before readiness/inference, and original-weight absent/zero/fresh-core recovery equivalence. Not learned-vector quality, same-core reconfiguration, arbitrary fault injection or matched performance.'}
    successes, refusals = {}, []
    try:
        spec = importlib.util.spec_from_file_location('steering_fixture', ROOT / 'steering-restart-gate.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with open(model, 'rb') as stream:
            architecture, layers, width = fixture.geometry(stream)
        valid = ROOT / 'valid.f32'
        raw = fixture.bank_bytes(layers, width)
        with valid.open('xb') as output:
            output.write(raw)
        bank = {'architecture': architecture, 'layers': layers, 'width': width, 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(), 'nonzero_values': layers}
        result['bank'] = bank
        cases = create_cases(ROOT / 'banks', valid)
        result['case_inputs'] = case_metadata(cases)
        with (ROOT / 'prompt.txt').open('x') as output:
            output.write('a' * fixture.PREFIX + fixture.QUESTION)
        base = [binary, '--suite', 'core', '--model', model, '--context', '4096', '--chunk', '256',
                '--users', '1', '--warmups', '0', '--repetitions', '1', '--ignore-eos',
                '--kv-cache-ram-mb', '0', '--timeout-ms', '600000', '--prompt-file', '/work/prompt.txt']
        if mode == 'mtp':
            base += ['--model-mtp', args[3], '--mtp-draft-tokens', '7']
        for phase in ('absent', 'zero', *CASES, 'recovery'):
            negative = phase in CASES
            command = base + ['--tg', str(1 if negative else OUTPUT), '--output', f'/work/measurements-{phase}.jsonl']
            if phase != 'absent':
                command += ['--dir-steering-file', str(cases[phase] if negative else valid),
                            '--dir-steering-ffn', '1' if negative else '0',
                            '--dir-steering-attn', '0.5' if negative else '0']
            (ROOT / 'admission-progress.json').write_text(json.dumps({'phase': phase, 'started_at': now(),
                    'successes': list(successes), 'refusals': [item['case'] for item in refusals]}) + '\n')
            if phase == 'absent':
                with (ROOT / 'restart-started.marker').open('x') as output:
                    output.write(now() + '\n')
            with (ROOT / ('bench-' + phase + '.log')).open('xb') as output:
                child = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=660, check=False)
            result['processes'].append({'phase': phase, 'argv': command, 'exit_code': child.returncode})
            raw = (ROOT / ('measurements-' + phase + '.jsonl')).read_bytes()
            result[phase + '_sha256'] = hashlib.sha256(raw).hexdigest()
            rows = [json.loads(line) for line in raw.splitlines()]
            if negative:
                refusals.append(parse_refusal(rows, child.returncode, mode, phase))
            else:
                successes[phase] = parse_success(rows, child.returncode, mode, phase, bank)
        result.update(compare(successes, refusals), state='PASSED', refusals=refusals,
                      successful_jobs={phase: successes[phase]['job'] for phase in SUCCESS})
    except BaseException as error:
        result.update(state='FAILED', error=repr(error))
    finally:
        result['ended_at'] = now()
        (ROOT / 'steering-admission-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if result['state'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
