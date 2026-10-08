#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a clean, committed LIE native benchmark for matched Q2/UD runs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('commit')
    p.add_argument('qualification', type=Path, help='Retained core Debug/ASan receipt, inspected before freezing')
    args = p.parse_args()
    source = args.source.resolve()
    if not source.is_relative_to(PROJECT):
        raise ValueError('Native benchmark must come from the owned LIE project')
    def git(*command):
        return subprocess.check_output(['git', '-C', str(source), *command], text=True).strip()
    commit = git('rev-parse', '--verify', args.commit+'^{commit}')
    if git('rev-parse', 'HEAD') != commit or git('status', '--porcelain'):
        raise ValueError('Native benchmark requires a clean worktree at the qualified commit')
    qualification = json.loads(args.qualification.read_text())
    if not isinstance(qualification, dict):
        raise ValueError('Expected a structured core qualification receipt')
    out = ROOT/'.deps'/('lie-native-curve-bench-'+commit[:12])
    receipt = ROOT/'config/q2-native-bench-source.json'
    evidence = ROOT/'evidence'/('q2-native-bench-source-'+commit[:12])
    if any(p.exists() for p in (out, receipt, evidence)):
        raise ValueError('Refusing to overwrite frozen benchmark evidence')
    evidence.mkdir()
    archive = evidence/'source.tar'
    with archive.open('xb') as stream:
        subprocess.run(['git', '-C', str(source), 'archive', '--format=tar', commit],
                       stdout=stream, check=True)
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            name = Path(member.name)
            if (name.is_absolute() or '..' in name.parts or
                    not (member.isdir() or member.isfile()) or member.size > 16000000):
                raise ValueError('Unsupported source archive member')
        out.mkdir()
        bundle.extractall(out, filter='data')
    files = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file()}
    for name in ('tools/native/http_curve.c', 'tools/native/gufo_workload.c',
                 'tests/test_http_curve_native.c'):
        if name not in files:
            raise ValueError('Committed canonical C driver missing')
    copied = evidence/'core-qualification.json'
    copied.write_bytes(args.qualification.read_bytes())
    manifest = dict(schema='synapse-lie.q2-native-bench-source.v1', commit=commit,
        source=str(out.relative_to(ROOT)), files=files, origin=str(source),
        archive=str(archive.relative_to(ROOT)), archive_sha256=sha(archive),
        core_qualification=str(copied.relative_to(ROOT)), core_qualification_sha256=sha(copied),
        role='Native C canonical workload and report client; no embedded model runtime',
        server_source='Unchanged q2-curve-source.json frozen C17 server',
        server_changed=False, model_inference=False, promoted=False, goal_met=False)
    receipt.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(commit=commit, source=manifest['source'], files=len(files),
                         qualification_sha256=sha(copied))))


if __name__ == '__main__':
    main()
