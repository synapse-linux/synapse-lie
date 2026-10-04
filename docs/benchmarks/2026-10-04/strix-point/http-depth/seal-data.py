#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seal checked Point HTTP depth evidence into reproducible archives."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SIZES = (8192, 32768, 131072, 258794)
MODES = ('ar', 'mtp')
HISTORY = ('point-http-depth-r1-ar-p8192-lie',)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def files_for(evidence, label):
    root = evidence/label
    collection = root/'collection.json'
    record = json.loads(collection.read_text())
    if record.get('schema') != 'synapse-lie.point-run-collection.v1':
        raise ValueError(label+': collection schema drift')
    inventory = record['inventory']
    expected_exit = 1 if label in HISTORY else 0
    if (record.get('exit_code') != 0 or
            inventory.get('result_exit_code') != expected_exit or
            inventory.get('child_exit_code') != expected_exit or
            inventory.get('service_exit') != 0 or
            not inventory.get('lease_free') or
            not inventory.get('supervisor_absent') or
            not inventory.get('gpu_child_absent') or
            not inventory.get('owned_child_absent') or
            'ActiveState=active' not in inventory.get('service', '')):
        raise ValueError(label+': invalid exit or closure')
    if (inventory.get('result_state') != ('FAILED' if expected_exit else 'PASSED') or
            not inventory.get('model_stat_unchanged')):
        raise ValueError(label+': invalid model or result state')
    result = [(collection, f'evidence/{label}/collection.json')]
    for relative, info in sorted(inventory['files'].items()):
        if (Path(relative).is_absolute() or '..' in Path(relative).parts or
                relative == 'collection.json'):
            raise ValueError(label+': unsafe inventory path')
        path = root/relative
        if path.stat().st_size != info['bytes'] or sha(path) != info['sha256']:
            raise ValueError(label+': collected file drift: '+relative)
        result.append((path, f'evidence/{label}/{relative}'))
    return result, {'collection_sha256': sha(collection),
                    'remote_files': len(inventory['files']),
                    'exit_code': expected_exit}


def archive(destination, records):
    if destination.exists():
        raise ValueError('Refusing to replace archive: '+str(destination))
    with destination.open('xb') as raw, gzip.GzipFile(filename='', mode='wb',
                                                       fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as stream:
            for path, relative in sorted(records, key=lambda item: item[1]):
                payload = path.read_bytes()
                info = tarfile.TarInfo(relative)
                info.size = len(payload)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mode = 0o644
                stream.addfile(info, io.BytesIO(payload))
    return {'sha256': sha(destination), 'bytes': destination.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, default=ROOT/'evidence')
    args = parser.parse_args()
    output = HERE/'data'
    output.mkdir(exist_ok=True)
    groups = {mode: [f'point-http-depth-r2-{mode}-p{size}-{impl}'
                     for size in SIZES for impl in ('lie', 'gufo')]
              for mode in MODES}
    groups['history'] = HISTORY
    details = {}
    hashes = []
    for group, labels in groups.items():
        records, runs = [], {}
        for label in labels:
            files, runs[label] = files_for(args.evidence_root, label)
            records.extend(files)
        name = group+'.tar.gz'
        meta = archive(output/name, records)
        meta['runs'] = runs
        details[name] = meta
        hashes.append(meta['sha256']+'  '+name)
    (output/'archives.sha256').write_text('\n'.join(hashes)+'\n')
    (output/'inventory.json').write_text(json.dumps(
        {'schema': 'synapse-lie.point-http-depth-archive.v1',
         'groups': details}, indent=2)+'\n')
    print(json.dumps({name: {'bytes': item['bytes'], 'runs': len(item['runs'])}
                      for name, item in details.items()}, sort_keys=True))


if __name__ == '__main__':
    main()
