#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare or run isolated Point HTTP controls with server sessions equal to C."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
CASES = (('ar', 'prose', (1, 2, 4, 6, 8)),
         ('mtp', 'prose', (1, 2, 4, 6, 8)),
         ('mtp', 'repetition', (1, 2, 4, 6, 8)),
         ('ar', 'repetition', (1,)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_manifest(mode, case, impl):
    if mode == 'ar':
        name = ('point-http-multi-r6-' + impl + '-ar-c1' +
                ('-r2' if impl == 'lie' else '') + '/manifest.json')
    else:
        name = 'point-http-multi-r6-' + impl + '-mtp-c1-manifest.json'
    return json.loads((EVIDENCE / name).read_text())


def rows():
    first = EVIDENCE / 'point-http-fresh-r7-ar-prose-c1-lie-manifest.json'
    revision = (json.loads(first.read_text())['runner_commit'] if first.exists() else
                subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                        text=True).strip())
    helper_sha = sha(ROOT / 'tools/strix-point-http-multi-gate.py')
    for mode, case, levels in CASES:
        corpus_sha = sha(ROOT / 'config/bench/gufo-qwen38' / (case + '.jsonl'))
        for level_index, level in enumerate(levels):
            order = ('lie', 'gufo') if level_index % 2 == 0 else ('gufo', 'lie')
            for impl in order:
                label = f'point-http-fresh-r7-{mode}-{case}-c{level}-{impl}'
                manifest = base_manifest(mode, case, impl)
                manifest.update(http_users=str(level), http_case=case,
                                http_capacity_policy='fresh-per-level',
                                http_server_sessions=level,
                                http_multi_gate_sha256=helper_sha,
                                corpus_sha256=corpus_sha,
                                distrobox_name=f'lie-fresh-r7-{mode}-{case}-c{level}-{impl}',
                                purpose=f'Official Gufo-style fresh-server Point {mode.upper()} {case} C{level} {impl.upper()} control',
                                runner_commit=revision)
                yield label, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Execute each admitted window after preparing manifests')
    parser.add_argument('--start-at', help='Resume at this exact prepared label')
    args = parser.parse_args()
    plans = list(rows())
    labels = [label for label, _ in plans]
    if args.start_at and args.start_at not in labels:
        parser.error('Unknown resume label')
    for label, manifest in plans:
        path = EVIDENCE / (label + '-manifest.json')
        payload = json.dumps(manifest, indent=2) + '\n'
        if path.exists():
            if path.read_text() != payload:
                raise RuntimeError('Prepared manifest changed: ' + label)
        else:
            path.write_text(payload)
        print(json.dumps({'label': label, 'manifest_sha256': sha(path)}, sort_keys=True), flush=True)
    if not args.run:
        return 0
    begin = not args.start_at
    for label, _ in plans:
        if not begin and label == args.start_at:
            begin = True
        if not begin:
            continue
        runroot = EVIDENCE / label
        if runroot.exists():
            raise RuntimeError('Refusing to replay existing campaign: ' + label)
        manifest = EVIDENCE / (label + '-manifest.json')
        launch = subprocess.run([sys.executable, str(ROOT/'tools/strix-point-launch.py'),
                                 label, str(manifest)], cwd=ROOT, check=False)
        collect = subprocess.run([sys.executable, str(ROOT/'tools/strix-point-bench-collect.py'),
                                  label, '--kind', 'http-multi'], cwd=ROOT, check=False)
        print(json.dumps({'label': label, 'launch_exit_code': launch.returncode,
                          'collect_exit_code': collect.returncode}, sort_keys=True), flush=True)
        if launch.returncode or collect.returncode:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
