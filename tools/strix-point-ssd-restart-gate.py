#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Two independent original-weight core processes sharing opt-in SSD KV state.

Invoked only inside an admitted Point GPU window. Never hashes KV payloads.
"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/work')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def one(rowset, mode, hot):
    if not rowsset_complete(rowset):
        raise RuntimeError('Incomplete core measurement')
    identity = next(row for row in rowset if row.get('event') == 'identity')
    inputs = [row for row in rowset if row.get('event') == 'input']
    jobs = [row for row in rowset if row.get('event') == 'job']
    samples = [row for row in rowset if row.get('event') == 'sample']
    if (identity.get('schema') != 'synapse-lie.core-bench.v1' or
            identity.get('mode') != mode or identity.get('synthetic') or
            identity.get('cache_policy') != 'ssd' or len(inputs) != 1 or
            len(jobs) != 1 or len(samples) != 1):
        raise RuntimeError('Unexpected core SSD process identity')
    job, sample = jobs[0], samples[0]
    if (job.get('prompt_tokens') != 8192 or job.get('output_tokens') != 32 or
            len(job.get('output_ids', [])) != 32 or sample.get('ssd_errors') != 0):
        raise RuntimeError('Incomplete SSD process output')
    if hot:
        if (job.get('cached_tokens') != 8192 or job.get('ssd_cached_tokens') != 8192 or
                job.get('prefill_tokens') != 0 or sample.get('ssd_hits', 0) < 1):
            raise RuntimeError('New process did not read the persisted SSD prefix')
    elif (job.get('cached_tokens') != 0 or job.get('prefill_tokens') != 8192 or
          sample.get('ssd_hits') != 0 or sample.get('ssd_writes', 0) < 1):
        raise RuntimeError('Cold process was not cold or did not persist SSD state')
    if mode == 'mtp' and (job.get('mtp_drafted_tokens', 0) < 1 or
                          job.get('mtp_accepted_tokens', 0) < 1):
        raise RuntimeError('MTP predictor did not accept a draft')
    if mode == 'ar' and (job.get('mtp_drafted_tokens') or job.get('mtp_accepted_tokens')):
        raise RuntimeError('AR process entered MTP')
    return inputs[0], job, sample


def rowsset_complete(rowsset):
    return bool(rowsset) and rowsset[-1] == {'event': 'complete', 'exit_code': 0}


def main():
    if len(sys.argv) not in (4, 5) or sys.argv[3] not in ('ar', 'mtp') or (len(sys.argv) == 5) != (sys.argv[3] == 'mtp'):
        raise SystemExit('Usage: ssd-restart-gate.py BENCH MODEL ar|mtp [PREDICTOR]')
    binary, model, mode = sys.argv[1:4]
    result = {'schema': 'synapse-lie.point-ssd-restart.v1', 'state': 'RUNNING',
              'mode': mode, 'started_at': now(), 'processes': []}
    kv = ROOT/'kv'
    if list(kv.iterdir()):
        raise SystemExit('Fresh private SSD directory required')
    base = [binary, '--suite', 'core', '--model', model,
            '--tokens-file', '/work/tokens.json', '--kv-cache-ram-mb', '0',
            '--kv-cache-policy', 'ds4', '--kv-disk-dir', '/work/kv',
            '--kv-disk-space-mb', '4096', '--kv-disk-staging-mb', '512',
            '--context', '16384', '--chunk', '2048', '--users', '1',
            '--tg', '32', '--warmups', '0', '--repetitions', '1',
            '--timeout-ms', '600000']
    if mode == 'mtp':
        base += ['--model-mtp', sys.argv[4], '--mtp-draft-tokens', '7']
    observations = []
    try:
        for phase in ('cold', 'hot'):
            command = base + ['--output', f'/work/measurements-{phase}.jsonl']
            log = ROOT/f'bench-{phase}.log'
            if phase == 'cold':
                (ROOT/'restart-started.marker').write_text(now() + '\n')
            with log.open('xb') as output:
                process = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                         timeout=660, check=False)
            result[phase+'_exit_code'] = process.returncode
            result['processes'].append({'phase': phase, 'argv': command,
                                        'exit_code': process.returncode})
            if process.returncode:
                raise RuntimeError(f'{phase} inference process exited {process.returncode}')
            measurements = ROOT/f'measurements-{phase}.jsonl'
            result[phase+'_measurements_sha256'] = sha(measurements)
            observations.append(one(rows(measurements), mode, phase == 'hot'))
            result[phase+'_kv_bytes'] = sum(p.stat().st_size for p in kv.iterdir() if p.is_file())
            result[phase+'_kv_files'] = sum(p.is_file() for p in kv.iterdir())
        cold, hot = observations
        if cold[0]['physical_ids_sha256'] != hot[0]['physical_ids_sha256'] or cold[1]['output_ids'] != hot[1]['output_ids']:
            raise RuntimeError('Cross-process physical input/output IDs differ')
        result.update(physical_ids_sha256=hot[0]['physical_ids_sha256'],
                      output_ids_equal=True, hot_cached_tokens=hot[1]['cached_tokens'],
                      hot_ssd_cached_tokens=hot[1]['ssd_cached_tokens'],
                      hot_prefill_tokens=hot[1]['prefill_tokens'],
                      hot_ssd_hits=hot[2]['ssd_hits'],
                      ssd_errors=cold[2]['ssd_errors']+hot[2]['ssd_errors'],
                      cold_mtp_accepted=cold[1]['mtp_accepted_tokens'],
                      hot_mtp_accepted=hot[1]['mtp_accepted_tokens'],
                      hot_decode_tps=hot[1]['output_tokens']*1e9/hot[1]['decode_ns'],
                      hot_complete_wall_tps=hot[2]['output_per_total_wall_tps'],
                      state='PASSED')
    except BaseException as error:
        result['state'] = 'FAILED'
        result['error'] = repr(error)
    finally:
        result['ended_at'] = now()
        (ROOT/'ssd-restart-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['state'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
