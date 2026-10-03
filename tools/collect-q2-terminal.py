#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect one completed Q2 task campaign, with exact export/job ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run'


def file_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collection_limit(mode):
    if mode not in ('q2-terminal-smoke', 'q2-terminal-full'):
        raise ValueError('Expected a scored Terminal-Bench campaign')
    return 2 * 1024**3 if mode == 'q2-terminal-full' else 256000000


def remote_script(label, mode):
    # Serialize data as literals once; no replacement inside inserted values.
    variables = f'BASE={REMOTE!r}\nLABEL={label!r}\nMODE={mode!r}\nMAX_BYTES={collection_limit(mode)}\n'
    return variables + '''import hashlib,io,json,sys,tarfile
from pathlib import Path
base=Path(BASE)
label=LABEL
r=json.loads((base/label/'results/result.json').read_text())
if r['state']!='TERMINAL_BENCH_COMMAND_COMPLETE_INSPECT_REWARDS' or not r.get('finished_at'):
 raise RuntimeError('Campaign is incomplete')
if r.get('mode')!=MODE: raise RuntimeError('Campaign mode changed')
b=base/'q2-terminal-bench/benchmark'
exports=[]
for p in (b/'results').rglob('summary.json'):
 j=json.loads(p.read_text())
 if j.get('tag')==label: exports.append(p.parent)
if len(exports)!=1: raise RuntimeError('Expected one exact-tag normalized export')
roots=[(exports[0],'export')]
for name in (label,label+'-attempt2'):
 p=b/'jobs'/name
 if p.exists(): roots.append((p,'jobs/'+name))
files={}
for root,prefix in roots:
 for p in sorted(root.rglob('*')):
  if p.is_symlink(): raise RuntimeError('Unexpected evidence symlink')
  if p.is_file(): files[prefix+'/'+str(p.relative_to(root))]=p
def file_sha256(path):
 with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
if sum(p.stat().st_size for p in files.values())>MAX_BYTES: raise RuntimeError('Campaign archive exceeds scope bound')
metadata={name:{'bytes':p.stat().st_size,'sha256':file_sha256(p)} for name,p in files.items()}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for name,p in files.items(): archive.add(p,arcname='terminal-benchmark/'+name,recursive=False)
 data=json.dumps({'label':label,'files':metadata},indent=2).encode()
 item=tarfile.TarInfo('terminal-benchmark/manifest.json');item.size=len(data)
 archive.addfile(item,io.BytesIO(data))
'''


def validate_archive(archive, limit):
    total, seen = 0, set()
    for member in archive.getmembers():
        path = Path(member.name)
        if (not path.parts or path.is_absolute() or '..' in path.parts
                or path.parts[0] != 'terminal-benchmark' or not member.isfile()
                or member.name in seen or member.size < 0):
            raise ValueError('Unsafe benchmark evidence')
        total += member.size
        seen.add(member.name)
    if total > limit + 1000000:
        raise ValueError('Oversized benchmark evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    args = parser.parse_args()
    if not re.fullmatch(r'q2-[a-z0-9-]{1,48}', args.label):
        parser.error('Invalid exclusive campaign label')
    out = ROOT / 'evidence' / args.label
    receipt = json.loads((out / 'results/result.json').read_text())
    if receipt['state'] != 'TERMINAL_BENCH_COMMAND_COMPLETE_INSPECT_REWARDS':
        raise ValueError('Collect the completed supervisor receipt first')
    limit = collection_limit(receipt.get('mode'))
    if (out / 'terminal-benchmark').exists():
        raise ValueError('Refusing to overwrite collected task evidence')
    script = remote_script(args.label, receipt['mode'])
    archive_path = out / 'terminal-benchmark.tar.gz'
    with archive_path.open('xb') as stream, (out / 'terminal-collection.stderr').open('xb') as error:
        result = subprocess.run(['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes',
                                 'paperboy@192.168.5.157', 'python3 -c ' + shlex.quote(script)],
                                stdout=stream, stderr=error)
    (out / 'terminal-collection.exit.json').write_text(json.dumps({'exit_code': result.returncode}) + '\n')
    if result.returncode:
        raise SystemExit(result.returncode)
    with tarfile.open(archive_path) as archive:
        validate_archive(archive, limit)
        archive.extractall(out, filter='data')
    manifest = json.loads((out / 'terminal-benchmark/manifest.json').read_text())
    if manifest['label'] != args.label:
        raise ValueError('Wrong campaign identity')
    for name, expected in manifest['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe manifest filename')
        data = out / 'terminal-benchmark' / path
        if data.stat().st_size != expected['bytes'] or file_sha256(data) != expected['sha256']:
            raise ValueError('Task evidence integrity mismatch')
    collection = {'archive_sha256': file_sha256(archive_path),
                  'verified_files': len(manifest['files']), 'label': args.label}
    (out / 'terminal-collection.json').write_text(json.dumps(collection, indent=2) + '\n')
    print(json.dumps(collection))


if __name__ == '__main__':
    main()
