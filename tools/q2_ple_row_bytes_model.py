# SPDX-License-Identifier: MIT
"""Private full-prefill trial, retaining the saved client and original requests."""
import hashlib
import json
from pathlib import Path
import shutil
from q2_full_prefill128 import inputs as saved_inputs

MANIFEST = 'config/q2-ple-row-bytes-source.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_provider(root, source):
    manifest = json.loads((root/MANIFEST).read_text())
    actual = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    if manifest['schema'] != 'synapse-lie.q2-ple-row-bytes-source.v1' or actual != manifest['files']:
        raise ValueError('Row-byte provider inventory differs')
    for key in ('parent_manifest', 'patch', 'generator', 'fixture'):
        if sha(root/manifest[key]) != manifest[key+'_sha256']:
            raise ValueError('Row-byte provider binding differs: '+key)
    return manifest


def reuse_mmq(root):
    manifest = verify_provider(root, root/'source')
    pins = json.loads((root/'config/q2-curve128-binaries.json').read_text())['numerical_qualification']
    previous = root.parent/pins['label']
    receipt = previous/'results/result.json'
    if sha(receipt) != pins['receipt_sha256']:
        raise ValueError('Retained MMQ qualification differs')
    old_result = json.loads(receipt.read_text())
    if any(c['exit_code'] for c in old_result['commands']) or not old_result.get('finished_at'):
        raise ValueError('Retained MMQ qualification incomplete')
    parent = json.loads((root/manifest['parent_manifest']).read_text())['variants']['iq2-fixed-bounds']
    actual = {p.relative_to(previous/'source').as_posix(): sha(p)
              for p in (previous/'source').rglob('*') if p.is_file()}
    if actual != parent['files'] or set(actual) != set(manifest['files']):
        raise ValueError('Retained MMQ source differs')
    changed = {n for n in actual if actual[n] != manifest['files'][n]}
    expected = {'src/models/qwen38_flash_next/ngram.cpp'}
    if changed != expected:
        raise ValueError('Row-byte change extends outside the BF16 descriptor selection')
    # MMQ units do not include kernels.hpp. Bind the complete private source,
    # all untouched MMQ sources/headers, and the retained qualification binary.
    binary = previous/'build/hip/cmake/hip/q2_model'
    if sha(binary) != old_result['binary_sha256_after']:
        raise ValueError('Retained MMQ binary differs')
    archive = previous/'build/hip/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a'
    (root/'reuse').mkdir()
    copied = root/'reuse/libgufo_qwen38_flash_next_mmq.a'
    shutil.copyfile(archive, copied)
    if sha(copied) != sha(archive):
        raise ValueError('MMQ copy differs')
    return copied, dict(reference=str(previous), archive=str(archive), sha256=sha(copied), changed=sorted(changed),
                        files_verified=len(actual), source_manifest_sha256=sha(root/MANIFEST),
                        controls_rebuilt_or_rerun=False)


def verify_server(root):
    pins = json.loads((root/'config/q2-ple-row-bytes-binaries.json').read_text())
    if pins['schema'] != 'synapse-lie.q2-ple-row-bytes-binaries.v1' or pins['context_capacity'] != 133760:
        raise ValueError('Invalid row-byte binary contract')
    if sha(root/MANIFEST) != pins['source_manifest_sha256']:
        raise ValueError('Row-byte binary source manifest changed')
    previous = root.parent/pins['label']
    receipt_path = previous/'results/result.json'
    if sha(receipt_path) != pins['receipt_sha256']:
        raise ValueError('Row-byte build receipt changed')
    receipt = json.loads(receipt_path.read_text())
    if (not receipt.get('finished_at') or any(c['exit_code'] for c in receipt['commands']) or
            receipt['mode'] != 'q2-prefill-ple-row-bytes'):
        raise ValueError('Row-byte model qualification incomplete')
    binary = previous/pins['binary']
    if sha(binary) != pins['binary_sha256'] or receipt['binary_sha256_after'] != pins['binary_sha256']:
        raise ValueError('Row-byte server binary changed')
    for directory in (root, previous):
        verify_provider(directory, directory/'source')
    core = json.loads((root/'config/q2-curve128-source.json').read_text())['core_files']
    for directory in (root/'curve-core', previous/'curve-core'):
        if {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob('*') if p.is_file()} != core:
            raise ValueError('Row-byte core source differs')
    return binary, dict(pins, no_build=True)


def inputs(root, depth=None):
    _, manifest, cases = saved_inputs(root, depth)
    if depth is not None:
        return list(zip(cases, manifest['cases']))
    selected = [(c,b) for c,b in zip(cases, manifest['cases'])
                if b['phase'] != 'prefix' or b['depth'] <= 32768]
    if len(selected) != 9 or [b['historical_index'] for _,b in selected] != [0,1,2,4,6,8,10,12,14]:
        raise ValueError('Original prefix history through32K differs')
    return selected


def client_argv(root, binary, output, depth=None):
    corpus = output.with_suffix('.requests.jsonl')
    # Write the original serialized records verbatim, retaining preparation,
    # both original8K attempts, request settings and natural final tails.
    original, _, _ = saved_inputs(root)
    selected = {c['id'] for c,_ in inputs(root, depth)}
    payload = b''.join(line for line in original.read_bytes().splitlines(keepends=True)
                       if json.loads(line)['id'] in selected)
    with corpus.open('xb') as stream:
        stream.write(payload)
    return [str(binary), '--suite', 'http', '--url', 'http://127.0.0.1:8000/v1',
        '--model', 'bench', '--output', str(output), '--server-label', 'ple-row-bytes-full-prefill'+str(depth//1024 if depth else 32),
        '--server-kv-cache', 'on', '--requests', str(corpus), '--context-capacity', '133760',
        '--rope-scaling', 'native', '--warmups', '0', '--repetitions', '1', '--timeout', '1800']


def validate_result(root, path, depth=None):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    samples = [e for e in events if e['event'] == 'sample']
    selected = inputs(root, depth)
    if events[-1].get('event') != 'complete' or events[-1].get('exit_code') != 0 or len(samples) != len(selected):
        raise ValueError('Row-byte original-prefix replay incomplete')
    prefixes = []
    for sample, (case,binding) in zip(samples, selected):
        strip = lambda obj: {k:v for k,v in obj.items() if k not in ('stream', 'stream_options')}
        timing = sample['server_timings']
        if (sample['case'] != case['id'] or strip(sample['request']) != strip(case['body']) or
                sample['usage']['prompt_tokens'] != binding['expected_prompt_tokens']):
            raise ValueError('Row-byte replay changed original input')
        if (timing['valid'] is not True or timing['scope'] != 'synchronous_executor_calls' or
                timing['decode_mode'] != 'ar' or timing['mtp_drafted_tokens'] or
                timing['mtp_accepted_tokens'] or timing['ssd_cached_tokens']):
            raise ValueError('Row-byte timing scope changed')
        if binding['phase'] == 'prefix':
            tokens = binding['expected_prompt_tokens']
            if (timing['cached_tokens'] != 0 or timing['prefill_tokens'] != tokens or
                    timing['prefill_calls'] != (tokens+2047)//2048 or timing['prefill_ms'] <= 0):
                raise ValueError('Expected complete uncached prefill with original2048 chunks')
            prefixes.append(dict(case=case['id'], depth=binding['depth'], tokens=tokens,
                calls=timing['prefill_calls'], prefill_ms=timing['prefill_ms'],
                prefill_tps=tokens*1000/timing['prefill_ms']))
    return dict(all_saved_inputs_exact=True, context_capacity=133760, chunk_size=2048,
                preparation_and_prefix_history_exact=True, samples=len(samples), full_prefixes=prefixes)
