#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare and optionally run bounded cold-prefill HTTP Point controls."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
SIZES = (8192, 32768, 131072, 258794)
MODES = ('ar', 'mtp')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows():
    first = EVIDENCE/'point-http-depth-r2-ar-p8192-lie-manifest.json'
    revision = (json.loads(first.read_text())['runner_commit'] if first.exists() else
                subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                        text=True).strip())
    helper_sha = sha(ROOT/'tools/strix-point-http-depth-gate.py')
    for mode in MODES:
        for index, size in enumerate(SIZES):
            order = ('lie', 'gufo') if index % 2 == 0 else ('gufo', 'lie')
            for impl in order:
                source = EVIDENCE/f'point-http-fresh-r7-{mode}-prose-c1-{impl}-manifest.json'
                manifest = json.loads(source.read_text())
                for key in ('http_case', 'http_users', 'http_warmups',
                            'http_multi_gate_sha256', 'corpus_sha256',
                            'http_capacity_policy', 'http_server_sessions'):
                    manifest.pop(key, None)
                label = f'point-http-depth-r2-{mode}-p{size}-{impl}'
                manifest.update(bench_profile='modern-http-depth',
                                http_size=size, http_repetitions=2,
                                http_depth_gate_sha256=helper_sha,
                                distrobox_name=f'lie-depth-r2-{mode}-p{size}-{impl}',
                                purpose=f'Cold HTTP C1 Point {mode.upper()} {size} {impl.upper()} original-weight control',
                                runner_commit=revision)
                yield label, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--start-at', help='Resume at exact prepared label')
    parser.add_argument('--stop-after', help='Stop at this label, inclusive')
    args = parser.parse_args()
    plans = list(rows())
    labels = [label for label, _ in plans]
    for value in (args.start_at, args.stop_after):
        if value and value not in labels:
            parser.error('Unknown campaign label: '+value)
    for label, manifest in plans:
        path = EVIDENCE/(label+'-manifest.json')
        payload = json.dumps(manifest, indent=2)+'\n'
        if path.exists():
            if path.read_text() != payload:
                raise RuntimeError('Prepared manifest changed: '+label)
        else:
            path.write_text(payload)
        print(json.dumps({'label': label, 'manifest_sha256': sha(path)}, sort_keys=True), flush=True)
    if not args.run:
        return 0
    begin = not args.start_at
    for label, _ in plans:
        if label == args.start_at:
            begin = True
        if not begin:
            continue
        if (EVIDENCE/label).exists():
            raise RuntimeError('Refusing to replay existing campaign: '+label)
        launch = subprocess.run([sys.executable, str(ROOT/'tools/strix-point-launch.py'),
                                 label, str(EVIDENCE/(label+'-manifest.json'))],
                                cwd=ROOT, check=False)
        collect = subprocess.run([sys.executable, str(ROOT/'tools/strix-point-bench-collect.py'),
                                  label, '--kind', 'http-depth'], cwd=ROOT, check=False)
        print(json.dumps({'label': label, 'launch_exit_code': launch.returncode,
                          'collect_exit_code': collect.returncode}, sort_keys=True), flush=True)
        if launch.returncode or collect.returncode:
            return 1
        if label == args.stop_after:
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
