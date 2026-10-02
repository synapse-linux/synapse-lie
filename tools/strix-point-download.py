#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pinned original UD staging, invoked only inside the admitted .161 campaign."""
import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import urllib.request

BASE = Path('/home/pop/workspace/synapse-lie/models')
REVISION = '38bb39ee97821de2c9009abb7e93950eec396e66'
PREFIX = 'https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/resolve/'+REVISION+'/UD-Q4_K_XL/'
CHUNK = 8*1024*1024

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(path):
    s = path.stat()
    return {'path': str(path), 'bytes': s.st_size, 'device': s.st_dev, 'inode': s.st_ino,
            'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}
def save(path, value):
    tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps(value, indent=2)+'\n'); tmp.replace(path)
def transfer(stream, destination, expected_size, expected_sha, progress):
    """No retries/resume. Keep an incomplete .part as failure evidence."""
    digest = hashlib.sha256(); received = 0
    partial = destination.with_suffix(destination.suffix+'.part')
    if destination.exists(): raise FileExistsError(destination)
    with partial.open('xb') as output:
        while True:
            chunk = stream.read(min(CHUNK, expected_size-received+1))
            if not chunk: break
            received += len(chunk)
            if received > expected_size: raise ValueError('Payload exceeds pinned size')
            output.write(chunk); digest.update(chunk)
            progress(received)
        if received != expected_size: raise ValueError('Truncated payload')
        if digest.hexdigest() != expected_sha: raise ValueError('Payload SHA-256 mismatch')
        output.flush(); os.fsync(output.fileno())
    # A hard link publishes exclusively, so even an unexpected destination is
    # never overwritten. Incomplete/corrupt bytes keep only their .part name.
    os.link(partial, destination)
    partial.unlink()
    return {'sha256': digest.hexdigest(), **identity(destination)}

def fetch_range(url, start, end, total):
    request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity',
        'Range': f'bytes={start}-{end}', 'User-Agent': 'synapse-lie-qualification'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
            raise ValueError('Server did not honor the exact pinned range')
        data = response.read(end-start+2)
    if len(data) != end-start+1: raise ValueError('Truncated/oversized range')
    return data

def transfer_ranges(row, destination, workers, progress):
    """Bounded ordered prefetch. Resume only by hashing the entire saved prefix."""
    digest = hashlib.sha256(); received = 0
    partial = destination.with_suffix(destination.suffix+'.part')
    # A completed earlier shard is reverified, never blindly trusted or changed.
    existing = destination if destination.exists() else partial
    if existing.exists():
        fd = os.open(existing, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > row['bytes']:
                raise ValueError('Unsafe existing shard or partial')
            while chunk := source.read(CHUNK):
                digest.update(chunk); received += len(chunk); progress(received)
        if existing == destination:
            if received != row['bytes'] or digest.hexdigest() != row['sha256']:
                raise ValueError('Existing published shard changed')
            return {'sha256': digest.hexdigest(), 'reverified_existing': True, **identity(destination)}
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'ab') as output:
        if os.fstat(output.fileno()).st_size != received: raise ValueError('Partial changed before resume')
        segment = 16*1024*1024
        intervals = iter((start, min(start+segment, row['bytes'])-1) for start in range(received, row['bytes'], segment))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = deque()
            def enqueue():
                item = next(intervals, None)
                if item is not None: pending.append(pool.submit(fetch_range, row['url'], *item, row['bytes']))
            for _ in range(workers): enqueue()
            while pending:
                data = pending.popleft().result()
                output.write(data); digest.update(data); received += len(data); progress(received)
                enqueue()
        if received != row['bytes'] or digest.hexdigest() != row['sha256']:
            raise ValueError('Completed range payload identity mismatch')
        output.flush(); os.fsync(output.fileno())
    os.link(partial, destination); partial.unlink()
    return {'sha256': digest.hexdigest(), **identity(destination)}

def main():
    if len(sys.argv) != 2: raise SystemExit('Expected private run directory')
    root = Path(sys.argv[1]).resolve()
    if root.parent != BASE.parent or os.environ.get('LIE_ADMITTED_RUN') != str(root):
        raise SystemExit('Requires the admitted campaign supervisor')
    manifest = json.loads((root/'manifest.json').read_text())
    plan = manifest['model_plan']
    workers = manifest.get('transfer_workers', 1)
    if type(workers) is not int or not 1 <= workers <= 8: raise ValueError('Invalid transfer concurrency')
    destination = Path(plan['destination'])
    if plan['revision'] != REVISION or destination.parent != BASE or destination.resolve() != destination:
        raise ValueError('Unexpected pinned model destination')
    if len(plan['files']) != 4: raise ValueError('Expected all four trunk shards')
    for i, row in enumerate(plan['files'], 1):
        name = f'Qwen3.8-Flash-Next-UD-Q4_K_XL-{i:05}-of-00004.gguf'
        if row['name'] != name or row['url'] != PREFIX+name: raise ValueError('Unexpected shard identity')
    if sum(row['bytes'] for row in plan['files']) != plan['total_bytes']: raise ValueError('Size sum mismatch')
    BASE.mkdir(exist_ok=True)
    if BASE.resolve() != BASE or BASE.stat().st_uid != os.getuid(): raise ValueError('Unsafe model staging root')
    if shutil.disk_usage(BASE).free <= plan['total_bytes']: raise RuntimeError('Insufficient disk for pinned payloads')
    destination.mkdir(exist_ok=workers > 1)
    if (destination/'SOURCE.json').exists(): raise ValueError('Refusing replay of a completed model staging')
    result = {'at': now(), 'state': 'DOWNLOADING', 'revision': REVISION, 'files': []}
    started = time.monotonic(); completed = 0; last = 0
    try:
        for row in plan['files']:
            def progress(received):
                nonlocal last
                if time.monotonic()-last >= 2:
                    total = completed+received
                    value = {'at': now(), 'file': row['name'], 'file_bytes': received,
                             'completed_bytes': total, 'total_bytes': plan['total_bytes'],
                             'elapsed_s': time.monotonic()-started}
                    save(root/'download-progress.json', value)
                    last = time.monotonic()
            if workers > 1:
                file = transfer_ranges(row, destination/row['name'], workers, progress)
            else:
                request = urllib.request.Request(row['url'], headers={'Accept-Encoding': 'identity', 'User-Agent': 'synapse-lie-qualification'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 200 or int(response.headers.get('Content-Length', -1)) != row['bytes']:
                        raise ValueError('Unexpected payload response/length')
                    file = transfer(response, destination/row['name'], row['bytes'], row['sha256'], progress)
            completed += row['bytes']; result['files'].append(file)
            save(root/'download-result.json', result)
        result['state'] = 'VERIFIED'
        result['elapsed_s'] = time.monotonic()-started
        save(destination/'SOURCE.json', {'plan': plan, 'result': result})
        return 0
    except BaseException as ex:
        result.update(state='FAILED', error=repr(ex)); raise
    finally: save(root/'download-result.json', result)

if __name__ == '__main__': raise SystemExit(main())
