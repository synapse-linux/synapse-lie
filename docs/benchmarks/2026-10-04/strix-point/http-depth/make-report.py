#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild Point HTTP depth tables from sealed evidence, offline."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New output directory')
    args = parser.parse_args()
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    inventory = json.loads((HERE/'data/inventory.json').read_text())
    if inventory.get('schema') != 'synapse-lie.point-http-depth-archive.v1':
        raise ValueError('Archive inventory schema drift')
    declared = {}
    for line in (HERE/'data/archives.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name in declared or name not in inventory['groups']:
            raise ValueError('Duplicate or unknown archive')
        declared[name] = digest
    if set(declared) != set(inventory['groups']):
        raise ValueError('Archive set drift')
    members = set()
    for name in sorted(declared):
        path = HERE/'data'/name
        if sha(path) != declared[name] or declared[name] != inventory['groups'][name]['sha256']:
            raise ValueError('Archive SHA-256 drift: '+name)
        with tarfile.open(path, 'r:gz') as archive:
            for item in archive:
                parts = Path(item.name).parts
                if (not item.isfile() or len(parts) != 3 or parts[0] != 'evidence' or
                        '..' in parts or item.name in members):
                    raise ValueError('Unsafe or duplicate archived member: '+item.name)
                members.add(item.name)
                destination = target/item.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(item) as source, destination.open('xb') as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
    spec = importlib.util.spec_from_file_location('point_http_depth_seal', HERE/'seal-data.py')
    seal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seal)
    checked = 0
    for group in inventory['groups'].values():
        for label, expected in group['runs'].items():
            files, actual = seal.files_for(target/'evidence', label)
            if actual != expected:
                raise ValueError('Archived run identity drift: '+label)
            checked += len(files)
    if checked != len(members):
        raise ValueError('Archived member count drift')
    report = [sys.executable, '-B', str(ROOT/'tools/strix-point-http-depth-report.py'),
              '--evidence-root', str(target/'evidence'), '--output', str(target/'generated')]
    result = subprocess.run(report, capture_output=True, text=True, check=False)
    receipt = {'schema': 'synapse-lie.point-http-depth-offline-report.v1',
               'archives': declared, 'archive_members': len(members),
               'report_source_sha256': sha(ROOT/'tools/strix-point-http-depth-report.py'),
               'report_command': ['python3', '-B', 'tools/strix-point-http-depth-report.py',
                                  '--evidence-root', 'NEW_OUTPUT/evidence',
                                  '--output', 'NEW_OUTPUT/generated'],
               'report_exit_code': result.returncode,
               'report_stdout': result.stdout, 'report_stderr': result.stderr}
    if result.returncode == 0:
        receipt['generated_sha256'] = {p.name: sha(p) for p in sorted((target/'generated').iterdir())
                                         if p.is_file()}
    (target/'verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'archive_members': len(members),
                      'report_exit_code': result.returncode,
                      'generated_files': len(receipt.get('generated_sha256', {}))}))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
