#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect a finished private .161 benchmark with source hashes and fresh closure."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '/home/pop/workspace/synapse-lie'
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
       'pop@192.168.5.161']
SCP = ['scp', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
FILES = {
    'bench': ('manifest.json', 'runner.py', 'result.json', 'measurements.jsonl',
              'telemetry.jsonl', 'stdout.log', 'stderr.log'),
    'distrobox-bench': ('manifest.json', 'runner.py', 'result.json',
                       'measurements.jsonl', 'telemetry.jsonl', 'stdout.log',
                       'stderr.log', 'distrobox-create.log',
                       'distrobox.stdout.log', 'distrobox.stderr.log'),
    'diagnostic': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                   'stdout.log', 'stderr.log'),
    'image-build': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl',
                    'image-build.log'),
    'preflight': ('manifest.json', 'runner.py', 'result.json', 'telemetry.jsonl'),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('--kind', choices=tuple(FILES), default='bench')
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,48}', args.label): parser.error('Invalid label')
    local = ROOT/'evidence'/args.label
    if not (local/'plan.json').is_file(): parser.error('Unknown local campaign label')
    remote = BASE+'/'+args.label
    names = FILES[args.kind]
    program = '''import fcntl,hashlib,json,os,pathlib,subprocess
base=pathlib.Path('/home/pop/workspace/synapse-lie')
root=base/'''+repr(args.label)+'''
if root.resolve()!=root or root.stat().st_uid!=os.getuid():raise SystemExit('Unexpected run root')
result=json.loads((root/'result.json').read_text())
if not result.get('ended_at'):raise SystemExit('Campaign has not finished')
names='''+repr(names)+'''
files={}
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
    required = set(names)
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
