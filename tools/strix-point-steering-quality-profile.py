#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional campaign body for original-weight held-out steering qualification.

The existing campaign owns admission, the container, resource sampling and
retirement. This module binds a previously independently qualified 100-pair
bank to the corpus/model/runtime, supervises the native-client helper and
independently reviews its complete saved wire. It never enters a GPU lease.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

HELPERS = (
    'strix-point-steering-quality-profile.py', 'strix-point-steering-quality-run.py',
    'strix-point-steering-quality-gate.py', 'strix-point-steering-build-gate.py',
    'strix-point-http-recall-gate.py')
INPUTS = ('steering-quality-settings.json', 'corpus.json',
          'steering-training-receipt.json', 'direction.ffn.f32')
RECEIPT_STATE = 'ORIGINAL_CAPTURES_AND_DS4_FORMAT_BANKS_VERIFIED_COLLECTED_STRONGLY_CLOSED_QUALITY_UNQUALIFIED'
CLOSURE_STATE = 'WHOLE_CONTAINER_AND_EXACT_GPU_IDENTITIES_CLOSED_NO_STANDING_RESERVATION'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def content(value):
    if (type(value) is not dict or type(value.get('bytes')) is not int or value['bytes'] < 1 or
            type(value.get('sha256')) is not str or not re.fullmatch(r'[0-9a-f]{64}', value['sha256'])):
        raise ValueError('Invalid bounded artifact content identity')
    return {key: value[key] for key in ('bytes', 'sha256')}


def regular(path, maximum):
    """Bootstrap input hashing before importing any staged helper code."""
    if path.resolve() != path:
        raise RuntimeError('Qualification input must be canonical without symlinks')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                not 1 <= before.st_size <= maximum):
            raise RuntimeError('Invalid bounded regular qualification input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            payload = stream.read(maximum+1)
        after, named = os.fstat(fd), path.stat(follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (len(payload) != before.st_size or not stat.S_ISREG(named.st_mode) or
                any(getattr(before, key) != getattr(after, key) or
                    getattr(after, key) != getattr(named, key) for key in fields)):
            raise RuntimeError('Qualification input changed during stable read')
        return payload, {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    finally:
        os.close(fd)


def file_identity(reader, path, maximum):
    before = path.stat(follow_symlinks=False)
    payload, found = reader(path, maximum)
    after = path.stat(follow_symlinks=False)
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, key) != getattr(after, key) for key in fields):
        raise RuntimeError('Qualification input changed during identity review')
    return payload, {**found, 'device': after.st_dev, 'inode': after.st_ino,
                     'mtime_ns': after.st_mtime_ns, 'ctime_ns': after.st_ctime_ns}


def prompts(data):
    return {side+'-prompts.txt': {
        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        for side in ('target', 'contrast')
        for payload in [''.join(data[side+'_instruction']+' Question: '+question+'\n'
                    for question in data['training_questions']).encode('utf-8')]}


def bank_source(receipt, config, data, corpus_identity, bank, payload, manifest, quality):
    if (type(receipt) is not dict or
            receipt.get('schema') != 'synapse-lie.original-steering-capture-qualification.v1' or
            receipt.get('state') != RECEIPT_STATE or
            receipt.get('runtime_source_commit') != manifest['source_commit'] or
            receipt.get('runtime_build_id') != manifest['runtime_build_id'] or
            receipt.get('upstream_source_pin') != manifest['runtime_source_pin'] or
            receipt.get('bundle_manifest_sha256') != manifest['bundle_manifest_sha256'] or
            receipt.get('native_builder_sha256') != manifest['artifacts']['runtime/bin/lie-steering-build'] or
            receipt.get('source_model') != manifest['model_plan'] or
            content(receipt.get('training_corpus')) != content(corpus_identity)):
        raise RuntimeError('Learned bank model/runtime/corpus provenance differs')
    exits = receipt.get('actual_exits', {})
    if any(type(exits.get(name)) is not int or exits[name] != 0 for name in
           ('controller', 'supervisor', 'native_builder', 'collector', 'strong_closure', 'independent_review')):
        raise RuntimeError('Training requires actual successful native/review/control exits')
    capture = receipt.get('capture', {})
    if (capture.get('schema') != 'synapse-lie.point-steering-build.v1' or capture.get('state') != 'PASSED' or
            capture.get('classification') != 'ORIGINAL_ACTIVATION_CAPTURE_LEARNED_QUALITY_UNQUALIFIED' or
            type(capture.get('actual_native_exit_code')) is not int or capture['actual_native_exit_code'] != 0 or
            type(capture.get('pairs')) is not int or capture['pairs'] != 100 or
            capture.get('source_inputs') != prompts(data) or
            capture.get('model_generation_or_quality_tested') is not False):
        raise RuntimeError('Expected independently qualified original 100-pair learning')
    settings = capture.get('settings', {})
    if (settings.get('components') != 'ffn' or settings.get('rope') != 'native' or
            settings.get('prompt_format') != 'chat' or type(settings.get('context')) is not int or
            settings['context'] != config['context'] or type(settings.get('prefill_chunk')) is not int or
            settings['prefill_chunk'] != config['chunk']):
        raise RuntimeError('Bank learning selections differ from the frozen protocol')
    layers, width, branches = (capture.get(key) for key in ('layers', 'width', 'ffn_branches'))
    if (not quality.integer(layers, 1, 4096) or not quality.integer(width, 1, 131072) or
            not quality.integer(branches, 1, 1024) or len(payload) != layers*width*4 or
            type(capture.get('captured_rows')) is not int or capture['captured_rows'] != 200*layers or
            content(capture.get('raw'))['bytes'] != 200*layers*width*branches*4):
        raise RuntimeError('Original FFN capture/bank geometry is incomplete')
    native = capture.get('native_identity', {})
    if (native.get('synthetic') is not False or native.get('program') != 'lie-steering-build' or
            native.get('build_id') != manifest['runtime_build_id'] or
            native.get('source_pin') != manifest['runtime_source_pin'] or
            native.get('engine') != config['fingerprint']):
        raise RuntimeError('Original native capture identity differs')
    banks = capture.get('banks', {})
    if set(banks) != {'direction.ffn.f32'} or content(banks['direction.ffn.f32']) != content(bank):
        raise RuntimeError('Qualified FFN bank identity differs')
    for layer in range(layers):
        values = struct.unpack('<'+str(width)+'f', payload[layer*width*4:(layer+1)*width*4])
        if any(not math.isfinite(value) for value in values) or abs(math.hypot(*values)-1) > 1e-6:
            raise RuntimeError('Bank contains nonfinite or nonnormalized layer directions')
    closure = receipt.get('closure', {})
    roles = ('supervisor', 'Distrobox launcher', 'observed container init', 'observed native GPU owner')
    identities = closure.get('identities', [])
    if (closure.get('state') != CLOSURE_STATE or len(identities) != 4 or
            {row.get('role') for row in identities} != set(roles) or
            any(row.get('exact_identity_absent') is not True or
                not quality.integer(row.get('pid'), 1, 2**31-1) or
                not quality.integer(row.get('start_ticks'), 1, 2**63-1) for row in identities) or
            closure.get('model_stats_reverified_unchanged') is not True or
            closure.get('container_cgroup', {}).get('empty') is not True):
        raise RuntimeError('Original training window lacks complete exact-identity closure')
    scans = closure.get('whole_container_process_scans', [])
    lease = closure.get('original_lease', {})
    ownership = receipt.get('ownership', {})
    if (len(scans) != 2 or any(row.get('owned_cgroup_matches') != [] or row.get('unreadable') != [] or
            not quality.integer(row.get('processes_checked'), 1, 2**31-1) for row in scans) or
            lease.get('free_briefly') is not True or lease.get('released') is not True or
            ownership.get('all_four_specific_current_non_use') is not True or
            ownership.get('all_four_verified_release_notifications') is not True or
            ownership.get('standing_reservation_or_future_grant') is not False):
        raise RuntimeError('Original training collection/release proof is incomplete')
    return {'training_pairs': 100, 'layers': layers, 'width': width, 'ffn_branches': branches,
            'bank': content(bank), 'corpus': content(corpus_identity), 'quality_already_qualified': False}


def preflight(campaign):
    manifest, root = campaign.m, campaign.root
    if (manifest.get('action') != 'bench' or manifest.get('bench_profile') != 'modern-steering-quality' or
            manifest.get('stack') != 'rocm10-fedora43' or manifest.get('transport') != 'distrobox' or
            manifest.get('decode_mode') != 'ar' or any(key in manifest for key in ('predictor_plan', 'projector_plan'))):
        raise ValueError('Expected original-weight AR steering response qualification')
    for name in ('runtime_build_id', 'runtime_source_pin', 'source_commit', 'bundle_manifest_sha256'):
        if type(manifest.get(name)) is not str or not manifest[name]:
            raise ValueError('Missing explicit steering runtime identity')
    for name in ('synapse-lie-server', 'synapse-lie-bench', 'lie-steering-build'):
        if not re.fullmatch(r'[0-9a-f]{64}', manifest.get('artifacts', {}).get('runtime/bin/'+name, '')):
            raise ValueError('Missing qualified steering runtime artifact')
    if (not root.is_absolute() or root.resolve() != root or root.stat().st_uid != os.getuid() or
            any((root/name).exists() or (root/name).is_symlink()
                for name in ('steering-quality', 'steering-quality-result.json', 'steering-quality-review.json'))):
        raise RuntimeError('Refusing noncanonical steering directory or qualification replay')
    helpers = manifest.get('steering_quality_helpers')
    if type(helpers) is not dict or set(helpers) != set(HELPERS):
        raise ValueError('Expected the complete exact-filename steering helper set')
    # Reuse the stable-reader primitive without executing a staged helper first.
    reader = regular
    payloads, identities = {}, {}
    for name in (*HELPERS, *INPUTS):
        payloads[name], identities[name] = file_identity(reader, root/name, 16*2**20)
        if name in helpers and identities[name]['sha256'] != helpers[name]:
            raise RuntimeError('Steering helper content drift: '+name)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != helpers[Path(__file__).name]:
        raise RuntimeError('Executing profile differs from admitted source')
    supervisor = module('bound_steering_supervision', root/'strix-point-steering-quality-run.py')
    quality = supervisor.quality
    config = quality.settings(quality.strict(payloads['steering-quality-settings.json']))
    data = quality.corpus(quality.strict(payloads['corpus.json']))
    if (config != manifest.get('steering_quality') or
            identities['steering-quality-settings.json']['sha256'] != manifest.get('steering_quality_settings_sha256') or
            content(identities['corpus.json']) != content(manifest.get('steering_quality_corpus')) or
            content(identities['steering-training-receipt.json']) != content(manifest.get('steering_quality_training_receipt')) or
            identities['direction.ffn.f32']['sha256'] != config['bank_sha256']):
        raise RuntimeError('Frozen steering settings/corpus/training/bank differs')
    load = manifest.get('steering_quality_load_timeout_seconds')
    deadline = supervisor.container_timeout(config, load)
    receipt = quality.strict(payloads['steering-training-receipt.json'])
    source = bank_source(receipt, config, data, identities['corpus.json'], identities['direction.ffn.f32'],
                         payloads['direction.ffn.f32'], manifest, quality)
    return {'supervisor': supervisor, 'quality': quality, 'settings': config, 'corpus': data,
            'identities': identities, 'reader': reader, 'load_timeout': load, 'deadline': deadline,
            'bank_source': source}


def unchanged(root, prepared):
    for name, expected in prepared['identities'].items():
        _payload, actual = file_identity(prepared['reader'], root/name, 16*2**20)
        if actual != expected:
            raise RuntimeError('Qualification input identity changed: '+name)


def review(root, prepared, actual_container_exit):
    quality, supervisor = prepared['quality'], prepared['supervisor']
    config, data = prepared['settings'], prepared['corpus']
    result = quality.strict(quality.read(root/'steering-quality-result.json', 4*2**20)[0])
    directory = root/'steering-quality'
    rows, cases = {}, {}
    for phase in ('absent', 'bank'):
        rows[phase] = supervisor.lines(directory/phase/'measurements.jsonl', 64*2**20)[0]
        cases[phase] = supervisor.lines(directory/phase/'requests.jsonl', 2**20)[0]
    snapshots = quality.strict(quality.read(directory/'snapshots.json', 8*2**20)[0])
    execution = quality.strict(quality.read(directory/'execution.json', 4*2**20)[0])
    proof = quality.validate(rows, cases, snapshots, config, data, result.get('native_exit_codes'))
    expected_exit = 0 if proof['state'] == 'PASSED' else 1
    if (type(actual_container_exit) is not int or actual_container_exit != expected_exit or
            result.get('schema') != 'synapse-lie.point-steering-quality-run.v1' or
            result.get('state') != proof['state'] or result.get('quality_review') != proof or
            result.get('settings') != config or result.get('cleanup_errors') != [] or
            result.get('load_timeout_seconds') != prepared['load_timeout'] or
            result.get('container_timeout_seconds') != prepared['deadline'] or
            result.get('bank_before') != prepared['identities']['direction.ffn.f32'] or
            result.get('bank_after') != result['bank_before'] or result.get('bank_identity_unchanged') is not True or
            execution != {'native_exit_codes': result['native_exit_codes'], 'phases': result.get('phases')}):
        raise RuntimeError('Independent steering wire differs from actual supervised execution')
    if set(result.get('phases', {})) != {'absent', 'bank'}:
        raise RuntimeError('Missing serial steering lifetimes')
    for phase in ('absent', 'bank'):
        lifetime = result['phases'][phase]
        if (type(lifetime.get('client_exit_code')) is not int or lifetime['client_exit_code'] != 0 or
                type(lifetime.get('server_exit_code')) is not int or lifetime['server_exit_code'] not in (0, -15) or
                not all(type(lifetime.get(key)) is str and lifetime[key] for key in ('ready_at', 'retired_at'))):
            raise RuntimeError('Actual native/server lifetimes are incomplete')
        for role in ('client', 'server'):
            identity = lifetime.get(role+'_identity', {})
            if (not quality.integer(identity.get('pid'), 1, 2**31-1) or
                    not quality.integer(identity.get('start_ticks'), 1, 2**63-1) or
                    type(identity.get('cgroup')) is not str or not identity['cgroup']):
                raise RuntimeError('Missing actual supervised child identity')
    return proof


def run(campaign):
    prepared = preflight(campaign)
    root, manifest = campaign.root, campaign.m
    model, model_stats = campaign.verified_model()
    command = ['/usr/bin/python3', '-B', '/work/strix-point-steering-quality-run.py',
               '--directory', '/work', '--settings', '/work/steering-quality-settings.json',
               '--corpus', '/work/corpus.json', '--bank', '/work/direction.ffn.f32',
               '--model', '/model/'+manifest['model_plan']['files'][0]['name'],
               '--server', '/bundle/runtime/bin/synapse-lie-server',
               '--client', '/bundle/runtime/bin/synapse-lie-bench',
               '--load-timeout', str(prepared['load_timeout'])]
    campaign.r['steering_quality_command'] = command
    campaign.r['steering_quality_bank_source'] = prepared['bank_source']
    campaign.r['steering_quality_container_timeout_seconds'] = prepared['deadline']
    campaign.record()
    error = None
    try:
        try:
            campaign.run_container(command, manifest['bundle'], prepared['deadline'], model)
        except Exception as failed:
            error = failed
        proof = review(root, prepared, campaign.r.get('child_exit_code'))
        with (root/'steering-quality-review.json').open('x', encoding='utf-8') as stream:
            json.dump(proof, stream, indent=2)
            stream.write('\n')
        campaign.r['steering_quality_result'] = proof
        unchanged(root, prepared)
        if error is not None:
            raise RuntimeError('Actual container failed; independent steering observations retained') from error
        if proof['state'] != 'PASSED':
            raise RuntimeError('Held-out steering quality failed; complete observations retained')
        return proof
    finally:
        # Partial evidence and actual exits survive a launch, wire or quality failure.
        found, failures = {}, []
        for name, maximum in (('steering-quality-result.json', 4*2**20),
                ('steering-quality/snapshots.json', 8*2**20),
                ('steering-quality/absent/measurements.jsonl', 64*2**20),
                ('steering-quality/bank/measurements.jsonl', 64*2**20)):
            path = root/name
            if path.exists() or path.is_symlink():
                try:
                    found[name] = prepared['quality'].read(path, maximum)[1]
                except Exception as failed:
                    failures.append(name+': '+repr(failed))
        campaign.r['steering_quality_partial_artifacts'] = found
        campaign.r['steering_quality_partial_read_errors'] = failures
        try:
            campaign.check_model_after(model_stats)
        finally:
            campaign.record()
        if failures:
            raise RuntimeError('Partial steering observations refused; model postflight retained')
