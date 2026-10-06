#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original-weight SSD text reconstruction regression in an admitted GPU window.

Optional qualification tooling, not a product dependency or performance runner.
Four independent core processes distinguish fresh BPE from persisted token history.
Only small input/output witnesses are hashed, never model or KV payloads.
"""
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path('/work')
PREFIX_TOKENS = 2048
OUTPUT_TOKENS = 32
PHASES = ('calibration', 'fresh', 'cold', 'hot')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest_ids(ids):
    return hashlib.sha256(b''.join(struct.pack('<i', item) for item in ids)).hexdigest()


def parse_phase(rows, mode, phase):
    """Refuse incomplete or internally inconsistent original-weight witnesses."""
    if mode not in ('ar', 'mtp') or phase not in PHASES:
        raise RuntimeError('Unknown mode or phase')
    if not rows or rows[-1] != {'event': 'complete', 'exit_code': 0}:
        raise RuntimeError('Incomplete core process')
    found = {}
    for event in ('identity', 'core_ready', 'input', 'job', 'sample'):
        matches = [row for row in rows if row.get('event') == event]
        if len(matches) != 1:
            raise RuntimeError('Incomplete or duplicate core witness: ' + event)
        found[event] = matches[0]
    identity, inputs, job, sample = (found[key] for key in ('identity', 'input', 'job', 'sample'))
    disk = phase in ('cold', 'hot')
    expected_kind = 'physical-tokens' if phase == 'cold' else 'raw-text'
    expected_output = OUTPUT_TOKENS if disk else 1
    if (identity.get('schema') != 'synapse-lie.core-bench.v1' or
            identity.get('synthetic') is not False or identity.get('mode') != mode or
            identity.get('input_kind') != expected_kind or
            identity.get('cache_policy') != ('ssd' if disk else 'off') or
            identity.get('execution') != 'shared-reactive-core' or
            identity.get('eos_policy') != 'ignore' or identity.get('prefix_cache_bytes') != 0 or
            identity.get('generation', {}).get('temperature') != 0 or
            identity.get('checkpoint_policy') != 'ds4' or identity.get('cache_text_prefix') is not True or
            identity.get('cache_capture_finish') is not False or identity.get('cache_continued_tokens') != 0 or
            identity.get('cache_trim_tokens') != 0 or identity.get('cache_align_tokens') != 1 or
            identity.get('prefill_chunk') != 256 or identity.get('context_capacity') != 4096 or
            identity.get('users') != 1 or identity.get('warmups') != 0 or
            identity.get('repetitions') != 1):
        raise RuntimeError('Unexpected core process identity')
    ids, outputs = inputs.get('physical_ids'), job.get('output_ids')
    if (not isinstance(ids, list) or not ids or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in ids) or
            inputs.get('prompt_tokens') != len(ids) or job.get('prompt_tokens') != len(ids) or
            inputs.get('physical_ids_sha256') != digest_ids(ids)):
        raise RuntimeError('Physical token witness mismatch')
    if (not isinstance(outputs, list) or len(outputs) != expected_output or
            any(type(item) is not int or not 0 <= item <= 2147483647 for item in outputs) or
            job.get('output_tokens') != expected_output or job.get('finish') != 'length' or
            sample.get('output_tokens') != expected_output or sample.get('ssd_errors') != 0):
        raise RuntimeError('Incomplete fixed-budget core output')
    cached = PREFIX_TOKENS if phase == 'hot' else 0
    if (job.get('cached_tokens') != cached or job.get('ssd_cached_tokens') != cached or
            job.get('prefill_tokens') != len(ids) - cached):
        raise RuntimeError('Incorrect restored or physically executed token count')
    if disk and len(ids) != PREFIX_TOKENS:
        raise RuntimeError('Persisted token history was not reconstructed')
    if sample.get('ssd_hits') != (1 if phase == 'hot' else 0):
        raise RuntimeError('Incorrect SSD hit witness')
    drained = [row for row in rows if row.get('event') == 'ssd_drained']
    if disk:
        if (len(drained) != 1 or drained[0].get('pending') != 0 or
                drained[0].get('errors') != 0 or drained[0].get('disk_bytes', 0) <= 0 or
                (phase == 'cold' and drained[0].get('writes', 0) < 1)):
            raise RuntimeError('SSD process did not completely drain its state')
    elif drained:
        raise RuntimeError('Uncached calibration process used SSD')
    if mode == 'ar' and (job.get('mtp_drafted_tokens') != 0 or job.get('mtp_accepted_tokens') != 0):
        raise RuntimeError('AR process entered MTP')
    if mode == 'mtp' and disk and (job.get('mtp_drafted_tokens', 0) < 1 or
                                  job.get('mtp_accepted_tokens', 0) < 1):
        raise RuntimeError('MTP cache process did not accept a draft')
    return found


def compare_phases(phases):
    calibration, fresh, cold, hot = (phases[key] for key in PHASES)
    seed = calibration['input']['physical_ids']
    if len(seed) != 1:
        raise RuntimeError('Calibration character is not one physical token')
    expected = seed * PREFIX_TOKENS
    if not 0 < len(fresh['input']['physical_ids']) < PREFIX_TOKENS:
        raise RuntimeError('Fresh BPE did not shorten the separated token history')
    if cold['input']['physical_ids'] != expected or hot['input']['physical_ids'] != expected:
        raise RuntimeError('Cross-process saved token history differs')
    if cold['job']['output_ids'] != hot['job']['output_ids']:
        raise RuntimeError('Cross-process confirmed output IDs differ')
    return {'calibration_token_id': seed[0],
            'fresh_bpe_tokens': len(fresh['input']['physical_ids']),
            'saved_physical_tokens': PREFIX_TOKENS,
            'fresh_bpe_ids_sha256': fresh['input']['physical_ids_sha256'],
            'saved_physical_ids_sha256': hot['input']['physical_ids_sha256'],
            'saved_history_longer_than_fresh_bpe': True,
            'physical_ids_equal': True, 'output_ids_equal': True,
            'hot_ssd_cached_tokens': hot['job']['ssd_cached_tokens'],
            'hot_prefill_tokens': hot['job']['prefill_tokens']}


def main():
    if (len(sys.argv) not in (4, 5) or sys.argv[3] not in ('ar', 'mtp') or
            (len(sys.argv) == 5) != (sys.argv[3] == 'mtp')):
        raise SystemExit('Usage: ssd-text-restart-gate.py BENCH MODEL ar|mtp [PREDICTOR]')
    binary, model, mode = sys.argv[1:4]
    result = {'schema': 'synapse-lie.point-ssd-text-restart.v1', 'state': 'RUNNING',
              'mode': mode, 'started_at': now(), 'processes': [],
              'scope': 'Shared reactive core; original-weight text/BPE SSD restart regression; '
                       'not HTTP, scheduled steering, quality or matched performance'}
    observations = {}
    try:
        kv = ROOT / 'kv'
        if not kv.is_dir() or list(kv.iterdir()):
            raise RuntimeError('Fresh private SSD directory required')
        with (ROOT / 'calibration.txt').open('x') as output:
            output.write('a')
        with (ROOT / 'prompt.txt').open('x') as output:
            output.write('a' * PREFIX_TOKENS)
        base = [binary, '--suite', 'core', '--model', model, '--kv-cache-ram-mb', '0',
                '--context', '4096', '--chunk', '256', '--users', '1', '--ignore-eos',
                '--warmups', '0', '--repetitions', '1', '--timeout-ms', '600000',
                '--kv-cache-policy', 'ds4', '--kv-cache-min-tokens', '512',
                '--kv-cache-boundary-trim-tokens', '0', '--kv-cache-boundary-align-tokens', '1',
                '--kv-cache-continued-interval-tokens', '0', '--kv-cache-capture-finish', 'off']
        if mode == 'mtp':
            base += ['--model-mtp', sys.argv[4], '--mtp-draft-tokens', '7']
        for phase in PHASES:
            disk = phase in ('cold', 'hot')
            input_name = 'calibration.txt' if phase == 'calibration' else 'prompt.txt'
            inputs = ['--prompt-file', '/work/' + input_name]
            if phase == 'cold':
                seed = observations['calibration']['input']['physical_ids']
                if len(seed) != 1:
                    raise RuntimeError('Calibration character is not one physical token')
                with (ROOT / 'tokens.json').open('x') as output:
                    json.dump(seed * PREFIX_TOKENS, output)
                    output.write('\n')
                inputs = ['--tokens-file', '/work/tokens.json']
            command = base + inputs + ['--tg', str(OUTPUT_TOKENS if disk else 1),
                                      '--output', f'/work/measurements-{phase}.jsonl']
            if disk:
                command += ['--kv-disk-dir', '/work/kv', '--kv-disk-space-mb', '4096',
                            '--kv-disk-staging-mb', '512']
            (ROOT / 'ssd-text-progress.json').write_text(json.dumps(
                {'phase': phase, 'started_at': now(), 'completed': list(observations)}) + '\n')
            with (ROOT / f'bench-{phase}.log').open('xb') as log:
                child = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=660, check=False)
            result['processes'].append({'phase': phase, 'argv': command, 'exit_code': child.returncode})
            result[phase + '_exit_code'] = child.returncode
            if child.returncode:
                raise RuntimeError(f'{phase} inference process exited {child.returncode}')
            raw = (ROOT / f'measurements-{phase}.jsonl').read_bytes()
            result[phase + '_measurements_sha256'] = hashlib.sha256(raw).hexdigest()
            observations[phase] = parse_phase([json.loads(line) for line in raw.splitlines()], mode, phase)
            if phase == 'calibration' and len(observations[phase]['input']['physical_ids']) != 1:
                raise RuntimeError('Calibration character is not one physical token')
            if phase == 'fresh' and not 0 < len(observations[phase]['input']['physical_ids']) < PREFIX_TOKENS:
                raise RuntimeError('Fresh BPE did not shorten the separated token history')
            if phase in ('calibration', 'fresh') and list(kv.iterdir()):
                raise RuntimeError('Calibration contaminated the private SSD directory')
        result.update(compare_phases(observations), state='PASSED')
        result['kv_file_bytes'] = {p.name: p.stat().st_size for p in kv.iterdir() if p.is_file()}
        result['cold_mtp_accepted'] = observations['cold']['job']['mtp_accepted_tokens']
        result['hot_mtp_accepted'] = observations['hot']['job']['mtp_accepted_tokens']
    except BaseException as error:
        result.update(state='FAILED', error=repr(error))
    finally:
        result['ended_at'] = now()
        (ROOT / 'ssd-text-restart-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['state'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
