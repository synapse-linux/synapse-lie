#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage task-owned sources and fixed qualification jobs on .157 only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
HOST = 'paperboy@192.168.5.157'
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['cpu', 'hip-build', 'operators', 'q2-smoke', 'q2-bench', 'q2-profile', 'ud-profile', 'ud-base', 'ud-patched', 'status', 'collect'])
    p.add_argument('label')
    args = p.parse_args()
    if not re.fullmatch(r'q2-[a-z0-9-]{1,48}', args.label):
        p.error('Label must start with q2- and contain lowercase letters/digits/hyphens')
    if args.mode == 'status':
        script = 'from pathlib import Path; import json; p=Path('+repr(REMOTE+args.label+'/results')+'); j=json.loads((p/"result.json").read_text()); print(json.dumps({k:j.get(k) for k in ["state","mode","pid","started_at","finished_at","commands","error","postflight_kfd"]},indent=2)); logs=sorted(p.glob("*.log")); print(logs[-1].read_text()[-3000:] if logs else "")'
        raise SystemExit(subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)]).returncode)
    if args.mode == 'collect':
        out = ROOT/'evidence'/args.label
        archive_path = out/'results.tar.gz'
        script = 'import tarfile,sys; a=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); a.add('+repr(REMOTE+args.label+'/results')+',arcname="results"); a.close()'
        with archive_path.open('xb') as stream:
            rc = subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)],stdout=stream).returncode
        if rc: raise SystemExit(rc)
        with tarfile.open(archive_path) as a:
            members=a.getmembers()
            if sum(m.size for m in members)>128000000: raise ValueError('Oversized collection')
            for m in members:
                pth=Path(m.name)
                if pth.is_absolute() or '..' in pth.parts or not (m.isdir() or m.isfile()): raise ValueError('Unsafe collection')
            a.extractall(out,filter='data')
        receipt=json.loads((out/'results/result.json').read_text())
        for name,meta in receipt.get('artifacts',{}).items():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('Unsafe artifact name')
            payload=(out/'results'/name).read_bytes()
            if len(payload)!=meta['bytes'] or hashlib.sha256(payload).hexdigest()!=meta['sha256']:
                raise ValueError('Artifact integrity mismatch')
        collected={'collected':str(archive_path),'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                   'verified_artifacts':len(receipt.get('artifacts',{}))}
        (out/'collection.json').write_text(json.dumps(collected,indent=2)+'\n')
        print(json.dumps(collected))
        return
    out = ROOT / 'evidence' / args.label
    out.mkdir()
    capsule = out / 'source.tar.gz'
    with tarfile.open(capsule, 'w:gz') as archive:
        for name in ['CMakeLists.txt', 'cmake', 'tests', 'config', 'tools/q2-runner.py', 'tools/q2_process.py', 'tools/analyze-q2-profile.py']:
            archive.add(ROOT / name, arcname=name)
        archive.add(ROOT / ('.deps/gufo-base' if args.mode in ('ud-base','ud-profile') else '.deps/gufo-q2'), arcname='source')
    dest = REMOTE + args.label
    # Exclusive destination and data-only extraction. No model or foreign path.
    script = '\n'.join([
        'import os,pathlib,sys,tarfile',
        'root=pathlib.Path(' + repr(dest) + ')',
        'root.mkdir()',
        'with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as archive:',
        ' for item in archive:',
        '  path=pathlib.PurePosixPath(item.name)',
        '  if path.is_absolute() or ".." in path.parts or not (item.isdir() or item.isfile()): raise ValueError("unsafe member")',
        '  if item.size>16000000: raise ValueError("oversized source file")',
        '  archive.extract(item,root,filter="data")',
        'os.execv(sys.executable,[sys.executable,str(root/"tools/q2-runner.py"),' + repr(args.mode) + '])',
    ])
    argv = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', HOST,
            'python3 -c ' + shlex.quote(script)]
    result = {'mode': args.mode, 'label': args.label, 'remote': dest,
              'capsule_sha256': hashlib.sha256(capsule.read_bytes()).hexdigest(),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with capsule.open('rb') as inp, (out/'remote.log').open('wb') as log:
        run = subprocess.run(argv, stdin=inp, stdout=log, stderr=subprocess.STDOUT)
    result['exit_code'] = run.returncode
    result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'transport.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result), flush=True)
    print((out/'remote.log').read_text()[-7000:], flush=True)
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
