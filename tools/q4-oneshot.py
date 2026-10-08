#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage/run/collect the owner's fixed Q4 one-shot; existing labels never rerun."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('stage', 'run', 'status', 'collect'):
        raise SystemExit('Usage: q4-oneshot.py stage|run|status|collect')
    phase = sys.argv[1]
    plan_path = ROOT/'config/q4-oneshot-plan.json'
    plan = json.loads(plan_path.read_text())
    remote = plan['remote_root']+'/'+plan['label']
    ssh = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o',
           'ConnectTimeout=10', plan['host']]
    if phase == 'stage':
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            for name, expected in plan['fixtures'].items():
                actual = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                if actual != expected:
                    raise RuntimeError('Frozen fixture changed: '+name)
                archive.add(ROOT/name, arcname=name, recursive=False)
            archive.add(plan_path, arcname='config/q4-oneshot-plan.json', recursive=False)
        payload = data.getvalue()
        source = ROOT/'evidence/q4-oneshot-preparation/source.tar.gz'
        with source.open('xb') as stream:
            stream.write(payload)
        code = """import hashlib,io,json,pathlib,sys,tarfile
root=pathlib.Path(REMOTE)
root.mkdir()
data=sys.stdin.buffer.read()
(root/'source.tar.gz').write_bytes(data)
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
 members=archive.getmembers()
 assert len(members)==7 and all(m.isfile() and not pathlib.Path(m.name).is_absolute() and '..' not in pathlib.Path(m.name).parts and m.size<1000000 for m in members)
 archive.extractall(root,filter='data')
sys.path.insert(0,str(root/'tools'))
import importlib.util
spec=importlib.util.spec_from_file_location('q4',root/'tools/q4-oneshot-runner.py')
q4=importlib.util.module_from_spec(spec);spec.loader.exec_module(q4)
plan=q4.read(root/'config/q4-oneshot-plan.json');q4.validate_plan(plan)
assert q4.stat_model(plan['model']['path'])==plan['model']
sources=q4.read(root/'config/q4-oneshot-sources.json')
arms={a['key']:q4.verify_arm(a,sources,dict(__import__('os').environ,LC_ALL='C'))[1] for a in plan['arms']}
report=dict(capsule_sha256=hashlib.sha256(data).hexdigest(),plan_sha256=q4.sha(root/'config/q4-oneshot-plan.json'),arms=arms,model_stat_exact=True,gpu_run=False,build_commands=0)
(root/'staging.json').write_text(json.dumps(report,indent=2)+'\\n')
print(json.dumps(report))
""".replace('REMOTE', repr(remote))
        result = subprocess.run(ssh+['python3 -B -c '+shlex.quote(code)], input=payload)
    elif phase == 'run':
        admission = ROOT/'config/q4-oneshot-window-admission.json'
        launch = dict(admission_sha256=hashlib.sha256(admission.read_bytes()).hexdigest(),
                      plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest())
        code = """import json,pathlib,subprocess,sys
root=pathlib.Path(REMOTE)
assert not (root/'results').exists()
with (root/'config/q4-oneshot-launch.json').open('x') as f:json.dump(json.loads(sys.stdin.buffer.read()),f,indent=2)
with (root/'runner-stdout.log').open('xb') as out:
 r=subprocess.run(['python3','-B',str(root/'tools/q4-oneshot-runner.py')],cwd=root,stdout=out,stderr=subprocess.STDOUT)
print((root/'runner-stdout.log').read_text()[-6000:])
sys.exit(r.returncode)
""".replace('REMOTE', repr(remote))
        result = subprocess.run(ssh+['python3 -B -c '+shlex.quote(code)],
                                input=json.dumps(launch).encode())
    elif phase == 'status':
        code = """import json,pathlib
root=pathlib.Path(REMOTE);p=root/'results/result.json'
if p.exists():
 d=json.loads(p.read_text());print(json.dumps({k:d.get(k) for k in ('state','pid','commands','error','finished_at')}))
else:print('Not started')
""".replace('REMOTE', repr(remote))
        result = subprocess.run(ssh+['python3 -B -c '+shlex.quote(code)])
    else:
        code = """import pathlib,sys,tarfile
root=pathlib.Path(REMOTE)
assert (root/'results/result.json').is_file()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for name in ('source.tar.gz','config','tools','staging.json','runner-stdout.log','results','arms'):archive.add(root/name,arcname=name)
""".replace('REMOTE', repr(remote))
        destination = ROOT/'evidence'/plan['label']
        destination.mkdir()
        archive_path = destination/'collection.tar.gz'
        with archive_path.open('xb') as out:
            result = subprocess.run(ssh+['python3 -B -c '+shlex.quote(code)], stdout=out)
        if result.returncode:
            raise SystemExit(result.returncode)
        with tarfile.open(archive_path) as archive:
            members = archive.getmembers()
            if (len(members) > 200 or sum(m.size for m in members) > 128000000 or
                    len({m.name for m in members}) != len(members) or
                    any(not (m.isdir() or m.isfile()) or Path(m.name).is_absolute() or
                        '..' in Path(m.name).parts for m in members)):
                raise RuntimeError('Unsafe or oversized collection')
            archive.extractall(destination, filter='data')
        receipt = json.loads((destination/'results/result.json').read_text())
        for name, expected in receipt['artifacts'].items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unsafe retained artifact name')
            data = (destination/path).read_bytes()
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise RuntimeError('Collection artifact changed')
        print(json.dumps(dict(state=receipt['state'], artifacts=len(receipt['artifacts']),
                              archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest())))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
