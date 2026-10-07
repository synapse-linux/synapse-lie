#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect a finished private .161 benchmark with source hashes and fresh closure."""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '/home/pop/workspace/synapse-lie'
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
       'pop@192.168.5.161']
SCP = ['scp', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
FILES = {
    'sampling-capture': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                         'stdout.log', 'stderr.log'),
    'steering-admission': ('manifest.json', 'runner.py', 'steering-admission-gate.py',
                           'steering-restart-gate.py', 'result.json', 'telemetry.jsonl'),
    'steering-restart': ('manifest.json', 'runner.py', 'steering-restart-gate.py',
                         'result.json', 'telemetry.jsonl'),
    'ssd-text-restart': ('manifest.json', 'runner.py', 'ssd-text-restart-gate.py',
                         'result.json', 'telemetry.jsonl'),
    'http': ('manifest.json', 'runner.py', 'http-gate.py', 'result.json', 'telemetry.jsonl'),
    'bench': ('manifest.json', 'runner.py', 'result.json', 'measurements.jsonl',
              'telemetry.jsonl', 'stdout.log', 'stderr.log'),
    'distrobox-bench': ('manifest.json', 'runner.py', 'result.json',
                       'measurements.jsonl', 'telemetry.jsonl', 'stdout.log',
                       'stderr.log', 'distrobox-create.log',
                       'distrobox.stdout.log', 'distrobox.stderr.log'),
    'http-multi': ('manifest.json', 'runner.py', 'http-multi-gate.py',
                   'corpus.jsonl', 'result.json', 'telemetry.jsonl'),
    'http-depth': ('manifest.json', 'runner.py', 'http-depth-gate.py',
                   'result.json', 'telemetry.jsonl'),
    'gufo-build': ('manifest.json', 'runner.py', 'gufo-build.py',
                   'result.json', 'telemetry.jsonl', 'stdout.log', 'stderr.log'),
    'diagnostic': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                   'stdout.log', 'stderr.log'),
    'image-build': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                    'image-build.log'),
    'preflight': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl'),
}
OPTIONAL = {
    'sampling-capture': ('capture-artifacts.json', 'distrobox-create.log',
                         'distrobox.stdout.log', 'distrobox.stderr.log'),
    'steering-admission': ('steering-admission-result.json', 'admission-progress.json',
                           'restart-started.marker', 'valid.f32', 'prompt.txt',
                           'stdout.log', 'stderr.log', 'distrobox-create.log',
                           'distrobox.stdout.log', 'distrobox.stderr.log') + tuple(
        prefix + phase + suffix
        for phase in ('absent', 'zero', 'empty', 'truncated', 'oversized', 'nan-first', 'nan-last',
                      'snan-middle', 'positive-infinity', 'negative-infinity', 'directory',
                      'symlink', 'fifo', 'missing', 'recovery')
        for prefix, suffix in (('measurements-', '.jsonl'), ('bench-', '.log'))),
    'steering-restart': ('steering-restart-result.json', 'steering-progress.json', 'restart-started.marker',
                         'steering.f32', 'steering-plan.json', 'calibration.txt', 'prompt.txt', 'tokens.json',
                         'measurements-calibration.jsonl', 'measurements-fresh.jsonl', 'measurements-saved.jsonl',
                         'measurements-reference.jsonl', 'measurements-divergent.jsonl', 'measurements-compatible.jsonl',
                         'bench-calibration.log', 'bench-fresh.log', 'bench-saved.log', 'bench-reference.log',
                         'bench-divergent.log', 'bench-compatible.log', 'stdout.log', 'stderr.log',
                         'distrobox-create.log', 'distrobox.stdout.log', 'distrobox.stderr.log'),
    'ssd-text-restart': ('ssd-text-restart-result.json', 'ssd-text-progress.json', 'restart-started.marker',
                         'calibration.txt', 'prompt.txt', 'tokens.json',
                         'measurements-calibration.jsonl', 'measurements-fresh.jsonl',
                         'measurements-cold.jsonl', 'measurements-hot.jsonl',
                         'bench-calibration.log', 'bench-fresh.log', 'bench-cold.log',
                         'bench-hot.log', 'stdout.log', 'stderr.log', 'distrobox-create.log',
                         'distrobox.stdout.log', 'distrobox.stderr.log'),
    'http': ('http-result.json', 'http-wire.jsonl', 'server.log', 'stdout.log',
             'stderr.log', 'distrobox-create.log', 'distrobox.stdout.log',
             'distrobox.stderr.log', 'http-controls.py', 'http-controls-result.json',
             'http-output-budget.py', 'http-output-budget-result.json',
             'http-schema-integer.py', 'http-schema-integer-result.json'),
    'distrobox-bench': ('tokens.json', 'image.png', 'prompt.txt'),
    'http-multi': ('http-multi-result.json', 'measurements.jsonl', 'server.log',
                   'client.stdout.log', 'client.stderr.log', 'stdout.log',
                   'stderr.log', 'distrobox-create.log',
                   'distrobox.stdout.log', 'distrobox.stderr.log'),
    'http-depth': ('http-depth-result.json', 'measurements.jsonl', 'requests.jsonl',
                   'gufo-options.json', 'server.log', 'client.stdout.log',
                   'client.stderr.log', 'stdout.log', 'stderr.log',
                   'distrobox-create.log', 'distrobox.stdout.log',
                   'distrobox.stderr.log'),
    'gufo-build': ('gufo-build-result.json', 'gufo-gfx1150-port.patch',
                   'gufo-configure.stdout.log', 'gufo-configure.stderr.log',
                   'gufo-link.stdout.log', 'gufo-link.stderr.log'),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def sampling_capture_inventory(root):
    """Collect bounded native data, including partial/uncommitted failed rows."""
    directory = root/'capture'
    if not directory.exists(): return {}
    if directory.resolve() != directory or directory.stat().st_uid != os.getuid():
        raise RuntimeError('Unexpected private capture directory')
    paths = sorted(directory.iterdir())
    if len(paths) > 770: raise RuntimeError('Too many native capture artifacts')
    result = {}
    for path in paths:
        if path.name == 'capture.jsonl': maximum = 8*2**20
        elif path.name == 'vocabulary.bin': maximum = 64*2**20
        else:
            match = re.fullmatch(r'profile-([0-5])-row-(0|[1-9][0-9]*)\.f32le', path.name)
            if not match or int(match[2]) >= 128:
                raise RuntimeError('Unexpected native capture artifact path')
            maximum = 4*1048576
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                    not 0 <= before.st_size <= maximum):
                raise RuntimeError('Invalid bounded native capture artifact')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                digest = hashlib.file_digest(stream,'sha256').hexdigest()
            after = os.fstat(fd); current = path.stat()
            fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
            if (any(getattr(before,k) != getattr(after,k) for k in fields) or
                    any(getattr(after,k) != getattr(current,k) for k in fields)):
                raise RuntimeError('Native capture artifact identity changed')
            result['capture/'+path.name] = {'bytes':before.st_size, 'sha256':digest}
        finally: os.close(fd)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('--kind', choices=tuple(FILES), default='bench')
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,48}', args.label): parser.error('Invalid label')
    local = ROOT/'evidence'/args.label
    if not (local/'plan.json').is_file(): parser.error('Unknown local campaign label')
    remote = BASE+'/'+args.label
    names = FILES[args.kind] + OPTIONAL.get(args.kind, ())
    program = 'import re,stat\n'+inspect.getsource(sampling_capture_inventory)+'\n'
    program += '''import fcntl,hashlib,json,os,pathlib,subprocess
base=pathlib.Path('/home/pop/workspace/synapse-lie')
root=base/'''+repr(args.label)+'''
if root.resolve()!=root or root.stat().st_uid!=os.getuid():raise SystemExit('Unexpected run root')
result=json.loads((root/'result.json').read_text())
if not result.get('ended_at'):raise SystemExit('Campaign has not finished')
names='''+repr(names)+'''
files=sampling_capture_inventory(root) if '''+repr(args.kind)+'''=='sampling-capture' else {}
for name in names:
 p=root/name
 if p.is_file():
  with p.open('rb') as source: digest=hashlib.file_digest(source,'sha256').hexdigest()
  files[name]={'bytes':p.stat().st_size,'sha256':digest}
service=subprocess.run(['systemctl','--user','show','llama-router.service','--property=ActiveState,MainPID'],capture_output=True,text=True)
lock=base/'campaign.lock';fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
try:
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);free=True
 except BlockingIOError:free=False
finally:os.close(fd)
out={'files':files,'result_state':result.get('state'),'result_exit_code':result.get('exit_code'),
     'child_exit_code':result.get('child_exit_code'),'model_stat_unchanged':result.get('model_stat_unchanged'),
     'supervisor_absent':not pathlib.Path('/proc/'+str(result['pid'])).exists(),
     'gpu_child_absent':not pathlib.Path('/proc/'+str(result.get('container_host_pid',-1))).exists(),
     'owned_child_absent':not pathlib.Path('/proc/'+str(result.get('child_pid',-1))).exists(),
     'lease_free':free,'service':service.stdout,'service_exit':service.returncode,
     'kernel_kfd':[p.name for p in pathlib.Path('/sys/class/kfd/kfd/proc').iterdir()]}
print(json.dumps(out))
'''
    commands = []
    status = {'schema': 'synapse-lie.point-run-collection.v1', 'label': args.label,
              'kind': args.kind,
              'remote_root': remote, 'commands': commands}
    p = subprocess.run(SSH+['python3 -'], input=program, capture_output=True, text=True, timeout=90)
    commands.append({'argv': SSH+['python3 -'], 'exit_code': p.returncode, 'stderr': p.stderr})
    if p.returncode:
        status['error'] = 'Remote inventory failed'; status['exit_code'] = p.returncode
        (local/'collection.json').write_text(json.dumps(status, indent=2)+'\n')
        return p.returncode
    inventory = json.loads(p.stdout)
    status['inventory'] = inventory
    for name, identity in inventory['files'].items():
        dest = local/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.stat().st_size != identity['bytes'] or sha(dest) != identity['sha256']:
                status['error'] = 'Staged source drift: '+name
                break
            continue
        cmd = SCP+[f'pop@192.168.5.161:{remote}/{name}', str(dest)]
        copied = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        commands.append({'argv': cmd, 'exit_code': copied.returncode, 'stderr': copied.stderr})
        if (copied.returncode or not dest.is_file() or dest.stat().st_size != identity['bytes'] or
            sha(dest) != identity['sha256']):
            status['error'] = 'Copy/hash mismatch: '+name
            break
    required = set(FILES[args.kind])
    if not status.get('error') and not required.issubset(inventory['files']):
        status['error'] = 'Missing required evidence files'
    status['exit_code'] = 0 if not status.get('error') else 1
    (local/'collection.json').write_text(json.dumps(status, indent=2)+'\n')
    print(json.dumps({'label': args.label, 'exit_code': status['exit_code'],
                      'state': inventory['result_state'], 'child_exit_code': inventory['child_exit_code'],
                      'files': len(inventory['files']), 'closure': {key: inventory[key] for key in
                      ('supervisor_absent', 'gpu_child_absent', 'owned_child_absent', 'lease_free')}}))
    return status['exit_code']


if __name__ == '__main__': raise SystemExit(main())
