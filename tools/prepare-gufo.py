#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reconstruct official base/candidate from the recorded archive; never fetch implicitly."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--base', action='store_true')
    args = parser.parse_args()
    identity = json.loads((ROOT/'config/gufo-source.json').read_text())
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != identity['archive_sha256']:
        parser.error('Archive does not match the recorded official source')
    args.destination.mkdir(parents=True)
    with tarfile.open(args.archive) as archive:
        for member in archive:
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path')
            if member.issym():
                continue  # Upstream editor aliases; never materialize archive links.
            if not (member.isfile() or member.isdir()):
                raise ValueError('Unsupported archive entry')
            if len(path.parts) < 2:
                continue
            member.name = str(Path(*path.parts[1:]))
            archive.extract(member, args.destination, filter='data')
    if not args.base:
        subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(ROOT/'patches/gufo-q2.patch')],
                       cwd=args.destination,check=True)
    print('Prepared ' + ('official base' if args.base else 'Q2 candidate'))


if __name__ == '__main__':
    main()
