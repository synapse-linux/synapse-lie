#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional bounded collection of a terminal .161 steering response campaign.

Preserves complete and partial native wire, actual child lifetimes and failures.
Uses the qualified streamed transfer primitives; never runs or hashes a model.
Collection does not establish response quality or whole-container retirement.
"""
import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'steering_streamed_collection', ROOT/'tools/strix-point-steering-build-collect.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
strict, artifact = transfer.strict, transfer.artifact


def inventory(root, expected_manifest):
    """Enumerate only fixed, bounded owned artifacts after actual lease release."""
    if (not root.is_absolute() or root.resolve() != root or
            not root.is_dir() or root.stat().st_uid != os.getuid()):
        raise RuntimeError('Unexpected private response collection root')
    payload, manifest_id = artifact(root/'manifest.json', 2**20, True)
    if manifest_id['sha256'] != expected_manifest:
        raise RuntimeError('Admitted response manifest differs')
    manifest = strict(payload)
    if (manifest.get('action') != 'bench' or
            manifest.get('bench_profile') != 'modern-steering-quality'):
        raise RuntimeError('Expected native steering response campaign')
    payload, result_id = artifact(root/'result.json', 2**20, True)
    result = strict(payload)
    if (result.get('manifest_sha256') != expected_manifest or
            result.get('state') not in ('PASSED', 'FAILED') or
            type(result.get('exit_code')) is not int or
            any(type(result.get(key)) is not str or not result[key]
                for key in ('ended_at', 'lease_released_at'))):
        raise RuntimeError('Response campaign is not terminal and released')
    files = {'manifest.json': manifest_id, 'result.json': result_id}
    roots = {
        'runner.py': 2**20, 'corpus.json': 2**20,
        'steering-quality-settings.json': 2**20,
        'steering-training-receipt.json': 2**20, 'direction.ffn.f32': 16*2**20,
        'strix-point-steering-quality-profile.py': 2**20,
        'strix-point-steering-quality-run.py': 2**20,
        'strix-point-steering-quality-gate.py': 2**20,
        'strix-point-steering-build-gate.py': 2**20,
        'strix-point-http-recall-gate.py': 2**20,
        'steering-quality-result.json': 4*2**20,
        'steering-quality-review.json': 8*2**20,
        'telemetry.jsonl': 64*2**20, 'http-started.marker': 4096,
        'stdout.log': 16*2**20, 'stderr.log': 16*2**20,
        'distrobox-create.log': 16*2**20,
        'distrobox.stdout.log': 16*2**20, 'distrobox.stderr.log': 16*2**20}
    for name, maximum in roots.items():
        path = root/name
        if path.exists() or path.is_symlink():
            files[name] = artifact(path, maximum)[1]
    bound = {'runner.py': manifest.get('runner_sha256'),
             'steering-quality-settings.json': manifest.get('steering_quality_settings_sha256'),
             'direction.ffn.f32': manifest.get('steering_quality', {}).get('bank_sha256')}
    helpers = manifest.get('steering_quality_helpers')
    expected_helpers = {name for name in roots if name.startswith('strix-point-')}
    if type(helpers) is not dict or set(helpers) != expected_helpers:
        raise RuntimeError('Incomplete response helper provenance')
    bound.update(helpers)
    for name, expected in bound.items():
        if (type(expected) is not str or not re.fullmatch(r'[0-9a-f]{64}', expected) or
                name not in files or files[name]['sha256'] != expected):
            raise RuntimeError('Frozen response source differs: '+name)
    for name, field in (('corpus.json', 'steering_quality_corpus'),
                        ('steering-training-receipt.json', 'steering_quality_training_receipt')):
        expected = manifest.get(field)
        if (type(expected) is not dict or name not in files or
                any(files[name][key] != expected.get(key) for key in ('bytes', 'sha256'))):
            raise RuntimeError('Frozen response input differs: '+name)
    native = root/'steering-quality'
    native_names = {'target-prompts.txt': 2**20, 'contrast-prompts.txt': 2**20,
                    'snapshots-raw.jsonl': 8*2**20, 'snapshots.json': 8*2**20,
                    'execution.json': 4*2**20}
    phase_names = {'input.jsonl': 2**20, 'requests.jsonl': 2**20,
                   'measurements.jsonl': 64*2**20, 'server.log': 16*2**20,
                   'client.stdout.log': 16*2**20, 'client.stderr.log': 16*2**20}
    if native.exists() or native.is_symlink():
        if (native.resolve() != native or not native.is_dir() or
                native.stat().st_uid != os.getuid()):
            raise RuntimeError('Unexpected response artifact directory')
        for path in sorted(native.iterdir()):
            if path.name in native_names:
                files['steering-quality/'+path.name] = artifact(path, native_names[path.name])[1]
            elif path.name in ('absent', 'bank'):
                if (path.resolve() != path or not path.is_dir() or
                        path.stat().st_uid != os.getuid()):
                    raise RuntimeError('Unexpected response phase directory')
                for child in sorted(path.iterdir()):
                    if child.name not in phase_names:
                        raise RuntimeError('Unexpected response phase artifact')
                    files['steering-quality/'+path.name+'/'+child.name] = artifact(
                        child, phase_names[child.name])[1]
            else:
                raise RuntimeError('Unexpected response artifact')
    required = {'manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                *bound, 'corpus.json', 'steering-training-receipt.json'}
    proof = result.get('steering_quality_result', {})
    complete = type(proof) is dict and proof.get('state') in ('PASSED', 'QUALITY_FAILED')
    if result['state'] == 'PASSED':
        if (result['exit_code'] != 0 or type(result.get('child_exit_code')) is not int or
                result['child_exit_code'] != 0 or not complete or proof['state'] != 'PASSED'):
            raise RuntimeError('Successful response campaign contradicts actual exits')
    if complete:
        required |= {'steering-quality-result.json', 'steering-quality-review.json',
                     'steering-quality/snapshots.json', 'steering-quality/snapshots-raw.jsonl',
                     'steering-quality/execution.json'}
        for phase in ('absent', 'bank'):
            required |= {'steering-quality/'+phase+'/'+name for name in phase_names}
    if not required.issubset(files):
        raise RuntimeError('Missing required response collection evidence')
    total = sum(row['bytes'] for row in files.values())
    if total > 256*2**20:
        raise RuntimeError('Response collection aggregate budget exceeded')
    return {'state': result['state'], 'actual_supervisor_exit_code': result['exit_code'],
            'actual_child_exit_code': result.get('child_exit_code'),
            'response_quality_state': proof.get('state') if type(proof) is dict else None,
            'model_stat_unchanged': result.get('model_stat_unchanged'),
            'files': files, 'total_bytes': total,
            'heavyweight_model_hash_or_GPU_operation': False,
            'response_quality_or_strong_closure_qualified': False}


def inventory_program(remote, expected):
    program = 'import hashlib,json,os,re,stat\nfrom pathlib import Path\n'
    program += '\n'.join(inspect.getsource(helper) for helper in (strict, artifact, inventory))
    return program+'\nprint(json.dumps(inventory(Path('+repr(remote)+'),'+repr(expected)+')))\n'


def contents(files):
    return {name: {key: value[key] for key in ('bytes', 'sha256')}
            for name, value in files.items()}


def copy_artifact(local, remote, name, expected, commands):
    # Validate the complete remote relative path before creating any local parent.
    if (type(name) is not str or not re.fullmatch(
            r'(?:steering-quality/(?:(?:absent|bank)/)?)?[a-z][a-z0-9.-]{0,63}', name)):
        raise ValueError('Invalid relative response artifact path')
    relative = Path(name)
    transfer.copy_artifact(local/relative.parent, remote+'/'+relative.parent.as_posix(),
                           relative.name, expected, commands)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('--record', default='collection.json')
    args = parser.parse_args()
    if (not re.fullmatch(r'[a-z0-9-]{1,48}', args.label) or
            not re.fullmatch(r'collection(?:-[a-z0-9-]{1,48})?\.json', args.record)):
        parser.error('Invalid campaign label or collection receipt name')
    local = ROOT/'evidence'/args.label
    if not local.is_dir() or local.resolve() != local or local.stat().st_uid != os.getuid():
        parser.error('Unknown canonical private response campaign')
    record = local/args.record
    if record.exists() or record.is_symlink():
        parser.error('Refusing to overwrite collection evidence')
    _payload, admitted = artifact(local/'manifest.json', 2**20)
    remote = transfer.BASE+'/'+args.label
    program = inventory_program(remote, admitted['sha256'])
    status = {'schema': 'synapse-lie.steering-quality-collection.v1',
              'label': args.label, 'remote_root': remote,
              'inventory_program_sha256': hashlib.sha256(program.encode()).hexdigest(),
              'commands': [], 'exit_code': 1,
              'response_quality_or_strong_closure_qualified': False}
    try:
        argv = transfer.SSH+['python3 -B -']
        command = {'argv': argv, 'exit_code': None}
        status['commands'].append(command)
        run = subprocess.run(argv, input=program, capture_output=True, text=True, timeout=120)
        command.update(exit_code=run.returncode, stderr=run.stderr)
        if run.returncode:
            status['stdout'] = run.stdout
            raise RuntimeError('Remote bounded response inventory failed')
        found = strict(run.stdout)
        status['inventory'] = found
        for name, expected in found['files'].items():
            copy_artifact(local, remote, name, expected, status['commands'])
        verified = inventory(local, admitted['sha256'])
        fields = ('state', 'actual_supervisor_exit_code', 'actual_child_exit_code',
                  'response_quality_state', 'model_stat_unchanged', 'total_bytes')
        if (contents(verified['files']) != contents(found['files']) or
                any(verified[key] != found[key] for key in fields)):
            raise RuntimeError('Complete local response inventory differs after collection')
        status['all_local_content_reverified'] = True
        status['exit_code'] = 0
    except Exception as failed:
        status['error'] = repr(failed)
    finally:
        with record.open('x') as stream:
            json.dump(status, stream, indent=2)
            stream.write('\n')
    print(json.dumps({'label': args.label, 'exit_code': status['exit_code'],
                     'state': status.get('inventory', {}).get('state'),
                     'files': len(status.get('inventory', {}).get('files', {})),
                     'total_bytes': status.get('inventory', {}).get('total_bytes'),
                     'error': status.get('error'), 'strong_closure_pending': True}))
    return status['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
