#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the already downloaded 128K profiler archive with a bounded cap."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT/'evidence/q2-long-profile128-r1'
LIMIT = 512 * 1024 * 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    archive_path = DIRECTORY/'results.tar.gz'
    assert archive_path.is_file()
    assert not (DIRECTORY/'results').exists() and not (DIRECTORY/'collection.json').exists()
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        names = set()
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts or
                    path.parts[0] != 'results' or path in names or
                    member.size < 0 or not (member.isdir() or member.isfile())):
                raise ValueError('Unsafe collection member')
            names.add(path)
        if sum(member.size for member in members) > LIMIT:
            raise ValueError('Profiler collection exceeds fixed 512 MiB cap')
        receipts = [member for member in members if member.name == 'results/result.json']
        if len(receipts) != 1 or not receipts[0].isfile() or receipts[0].size > 1000000:
            raise ValueError('Missing or oversized collection receipt')
        receipt = json.load(archive.extractfile(receipts[0]))
        if (receipt.get('mode') != 'q2-prefill128' or
                receipt.get('state') != 'PREFIX128K_PROFILE_COMPLETE_NOT_BENCHMARK' or
                receipt.get('profile_prefix128k') is not True or
                receipt.get('model_access') is not True or
                not receipt.get('finished_at') or
                [row.get('exit_code') for row in receipt.get('commands', [])] != [0]*4):
            raise ValueError('Unexpected or incomplete model diagnostic')
        with tempfile.TemporaryDirectory(prefix='validated-', dir=DIRECTORY) as temporary:
            target = Path(temporary)
            archive.extractall(target, filter='data')
            for name, meta in receipt['artifacts'].items():
                path = Path(name)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe artifact name')
                artifact = target/'results'/name
                if artifact.stat().st_size != meta['bytes'] or sha(artifact) != meta['sha256']:
                    raise ValueError('Artifact integrity mismatch: '+name)
            (target/'results').rename(DIRECTORY/'results')
    report = dict(collected=str(archive_path), sha256=sha(archive_path),
                  verified_artifacts=len(receipt['artifacts']), existing_archive=True,
                  collection_cap_bytes=LIMIT,
                  default_collection_exit_code=1,
                  default_collection_failure='Oversized collection')
    (DIRECTORY/'collection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
