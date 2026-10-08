#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional bounded collection of a finished .161 steering-build campaign.

Collection verifies retained bytes, not learning, quality or strong closure.
Model files are never hashed or copied. Partial native artifacts survive failures.
"""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '/home/pop/workspace/synapse-lie'
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'pop@192.168.5.161']
SCP = ['scp', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']


def strict(payload):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate collection metadata key')
            result[key] = value
        return result
    def nonfinite(_value):
        raise ValueError('Nonfinite collection metadata')
    return json.loads(payload, object_pairs_hook=pairs, parse_constant=nonfinite)


def artifact(path, maximum, retain=False):
    """Hash in 1 MiB reads through one stable owned regular descriptor."""
    if path.resolve() != path:
        raise RuntimeError('Artifact path must be canonical without symlinks')
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                not 0 <= before.st_size <= maximum):
            raise RuntimeError('Invalid bounded regular collection artifact')
        digest, chunks, total = hashlib.sha256(), [], 0
        while True:
            data = os.read(fd, 2**20)
            if not data:
                break
            total += len(data)
            if total > maximum or total > before.st_size:
                raise RuntimeError('Collection artifact grew during read')
            digest.update(data)
            if retain:
                chunks.append(data)
        after, named = os.fstat(fd), path.stat(follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (total != before.st_size or not stat.S_ISREG(named.st_mode) or
                any(getattr(before, key) != getattr(after, key) or
                    getattr(after, key) != getattr(named, key) for key in fields)):
            raise RuntimeError('Collection artifact changed during read')
        identity = {'bytes': total, 'sha256': digest.hexdigest(), 'device': after.st_dev,
                    'inode': after.st_ino, 'mtime_ns': after.st_mtime_ns, 'ctime_ns': after.st_ctime_ns}
        return (b''.join(chunks) if retain else None), identity
    finally:
        os.close(fd)


def inventory(root, expected_manifest):
    if (not root.is_absolute() or root.resolve() != root or
            root.stat().st_uid != os.getuid() or not root.is_dir()):
        raise RuntimeError('Unexpected private collection root')
    manifest_bytes, manifest_id = artifact(root/'manifest.json', 2**20, True)
    if manifest_id['sha256'] != expected_manifest:
        raise RuntimeError('Admitted training manifest differs')
    manifest = strict(manifest_bytes)
    if manifest.get('action') != 'bench' or manifest.get('bench_profile') != 'modern-steering-build':
        raise RuntimeError('Expected native steering-build campaign')
    settings = manifest.get('steering_build', {})
    if (settings.get('components') not in ('ffn', 'attention', 'both') or
            type(settings.get('max_output_bytes')) is not int or
            not 8192 <= settings['max_output_bytes'] <= 512*2**20):
        raise RuntimeError('Unsupported bounded training output selection')
    result_bytes, result_id = artifact(root/'result.json', 2**20, True)
    result = strict(result_bytes)
    if (type(result.get('ended_at')) is not str or not result['ended_at'] or
            type(result.get('lease_released_at')) is not str or not result['lease_released_at'] or
            result.get('manifest_sha256') != expected_manifest or
            result.get('state') not in ('PASSED', 'FAILED') or
            type(result.get('exit_code')) is not int):
        raise RuntimeError('Training campaign is not terminal and released')
    files = {'manifest.json': manifest_id, 'result.json': result_id}
    roots = {'runner.py': 2**20, 'steering-build-gate.py': 2**20,
        'corpus.json': 2**20, 'target-prompts.txt': 32*2**20, 'contrast-prompts.txt': 32*2**20,
        'telemetry.jsonl': 64*2**20, 'steering-build-review.json': 8*2**20,
        'stdout.log': 16*2**20, 'stderr.log': 16*2**20, 'distrobox-create.log': 16*2**20,
        'distrobox.stdout.log': 16*2**20, 'distrobox.stderr.log': 16*2**20}
    for name, maximum in roots.items():
        path = root/name
        if path.exists() or path.is_symlink():
            files[name] = artifact(path, maximum)[1]
    native_names = {'build.jsonl': 64*2**20, 'activations.f32le': settings['max_output_bytes'],
        'target-prompts.txt': 32*2**20, 'contrast-prompts.txt': 32*2**20,
        'direction.ffn.f32': 16*2**20, 'direction.attention.f32': 16*2**20,
        'direction.ffn.f32.partial': 16*2**20, 'direction.attention.f32.partial': 16*2**20}
    native = root/'steering-build'
    if native.exists() or native.is_symlink():
        if native.resolve() != native or not native.is_dir() or native.stat().st_uid != os.getuid():
            raise RuntimeError('Unexpected native steering-build directory')
        for path in sorted(native.iterdir()):
            if path.name not in native_names:
                raise RuntimeError('Unexpected native steering-build artifact')
            files['steering-build/'+path.name] = artifact(path, native_names[path.name])[1]
    required = {'manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl'}
    if result['state'] == 'PASSED':
        if result['exit_code'] != 0 or type(result.get('child_exit_code')) is not int or result['child_exit_code'] != 0:
            raise RuntimeError('Successful training contradicts actual exits')
        required |= {'steering-build-gate.py', 'target-prompts.txt', 'contrast-prompts.txt',
                     'steering-build-review.json', 'steering-build/build.jsonl',
                     'steering-build/activations.f32le', 'steering-build/target-prompts.txt',
                     'steering-build/contrast-prompts.txt'}
        components = ('ffn', 'attention') if settings['components'] == 'both' else (settings['components'],)
        required |= {'steering-build/direction.'+component+'.f32' for component in components}
    if not required.issubset(files):
        raise RuntimeError('Missing required native training collection evidence')
    total = sum(identity['bytes'] for identity in files.values())
    if total > 640*2**20:
        raise RuntimeError('Training collection aggregate budget exceeded')
    return {'state': result['state'], 'actual_supervisor_exit_code': result['exit_code'],
        'actual_child_exit_code': result.get('child_exit_code'),
        'model_stat_unchanged': result.get('model_stat_unchanged'), 'files': files,
        'total_bytes': total, 'heavyweight_model_hash_or_GPU_operation': False,
        'learning_quality_or_strong_closure_qualified': False}


def copy_artifact(local, remote, name, expected, commands):
    """Publish verified copy without overwriting; retain failed owned staging."""
    if (type(name) is not str or not re.fullmatch(r'(?:steering-build/)?[a-z][a-z0-9.-]{0,63}', name) or
            type(expected) is not dict or type(expected.get('bytes')) is not int or
            not 0 <= expected['bytes'] <= 512*2**20 or
            type(expected.get('sha256')) is not str or not re.fullmatch(r'[0-9a-f]{64}', expected['sha256'])):
        raise ValueError('Invalid collection destination or content identity')
    dest = local/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.parent.resolve() != dest.parent or dest.parent.stat().st_uid != os.getuid():
        raise RuntimeError('Noncanonical local collection directory')
    if dest.exists() or dest.is_symlink():
        actual = artifact(dest, expected['bytes'])[1]
        if any(actual[key] != expected[key] for key in ('bytes', 'sha256')):
            raise RuntimeError('Existing local artifact differs: '+name)
        return
    fd, staged = tempfile.mkstemp(prefix='.collection-'+dest.name+'-', suffix='.partial', dir=dest.parent)
    os.close(fd)
    stage = Path(staged)
    argv = SCP+['pop@192.168.5.161:'+remote+'/'+name, str(stage)]
    command = {'argv': argv, 'exit_code': None}
    commands.append(command)
    copied = subprocess.run(argv, capture_output=True, text=True, timeout=240)
    command.update(exit_code=copied.returncode, stderr=copied.stderr)
    if copied.returncode:
        raise RuntimeError('SCP failed; partial staging retained: '+name)
    actual = artifact(stage, expected['bytes'])[1]
    if any(actual[key] != expected[key] for key in ('bytes', 'sha256')):
        raise RuntimeError('Copy/hash mismatch; partial staging retained: '+name)
    with stage.open('rb') as stream:
        os.fsync(stream.fileno())
    os.link(stage, dest, follow_symlinks=False)
    stage.unlink()
    directory = os.open(dest.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def inventory_program(remote, expected):
    program = 'import hashlib,json,os,re,stat\nfrom pathlib import Path\n'
    program += '\n'.join(inspect.getsource(helper) for helper in (strict, artifact, inventory))
    return program+'\nprint(json.dumps(inventory(Path('+repr(remote)+'),'+repr(expected)+')))\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('--record', default='collection.json', help='New local collection receipt filename')
    args = parser.parse_args()
    if (not re.fullmatch(r'[a-z0-9-]{1,48}', args.label) or
            not re.fullmatch(r'collection(?:-[a-z0-9-]{1,48})?\.json', args.record)):
        parser.error('Invalid campaign label or collection receipt name')
    local = ROOT/'evidence'/args.label
    if not local.is_dir() or local.resolve() != local or local.stat().st_uid != os.getuid():
        parser.error('Unknown canonical private local campaign')
    record = local/args.record
    if record.exists() or record.is_symlink():
        parser.error('Refusing to overwrite collection evidence')
    _payload, admitted = artifact(local/'manifest.json', 2**20)
    remote = BASE+'/'+args.label
    program = inventory_program(remote, admitted['sha256'])
    status = {'schema': 'synapse-lie.steering-build-collection.v1', 'label': args.label,
        'remote_root': remote, 'inventory_program_sha256': hashlib.sha256(program.encode()).hexdigest(),
        'commands': [], 'exit_code': 1, 'learning_quality_or_strong_closure_qualified': False}
    try:
        argv = SSH+['python3 -B -']
        command = {'argv': argv, 'exit_code': None}
        status['commands'].append(command)
        run = subprocess.run(argv, input=program, capture_output=True, text=True, timeout=120)
        command.update(exit_code=run.returncode, stderr=run.stderr)
        if run.returncode:
            status['stdout'] = run.stdout
            raise RuntimeError('Remote bounded training inventory failed')
        found = strict(run.stdout)
        status['inventory'] = found
        for name, expected in found['files'].items():
            copy_artifact(local, remote, name, expected, status['commands'])
        local_inventory = inventory(local, admitted['sha256'])
        def contents(files):
            return {name: {key: value[key] for key in ('bytes', 'sha256')} for name, value in files.items()}
        if (contents(local_inventory['files']) != contents(found['files']) or
                any(local_inventory[key] != found[key] for key in ('state', 'actual_supervisor_exit_code',
                    'actual_child_exit_code', 'model_stat_unchanged', 'total_bytes'))):
            raise RuntimeError('Complete local training inventory differs after collection')
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
        'total_bytes': status.get('inventory', {}).get('total_bytes'), 'error': status.get('error'),
        'strong_closure_pending': True}))
    return status['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
