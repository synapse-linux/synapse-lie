#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a common C17 HTTP core and state-capable Q2/UD source compositions."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CORE_COMMIT = '15c6082152c3df0cb1f40d89ba5329692f307d7b'
PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'
CORE = ROOT / '.deps/lie-q2-curve-core'
MANIFEST = ROOT / 'config/q2-curve-source.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Source contains a symlink: ' + str(p))
        if p.is_file():
            files[str(p.relative_to(root))] = digest(p)
    return files


def main():
    outputs = {key: ROOT / ('.deps/gufo-q2-curve-' + key) for key in ('q2', 'ud')}
    if any(p.exists() for p in (CORE, MANIFEST, *outputs.values())):
        raise ValueError('Refusing to overwrite an existing source composition')
    source = subprocess.check_output([
        'git', 'archive', CORE_COMMIT, 'CMakeLists.txt', 'LICENSE', 'AGENTS.md',
        'adapters', 'cmake', 'config', 'include', 'src', 'tests', 'third_party', 'tools'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(source)) as archive:
        for member in archive.getmembers():
            if (not (member.isfile() or member.isdir()) or
                    Path(member.name).is_absolute() or '..' in Path(member.name).parts):
                raise ValueError('Unsafe frozen core archive')
        archive.extractall(CORE, filter='data')
    core_files = inventory(CORE)
    pristine = json.loads((CORE / 'third_party/gufo-source.json').read_text())
    if pristine['commit'] != PIN:
        raise ValueError('Frozen core uses a different upstream pin')
    candidate = json.loads((ROOT / 'config/q2-hc-library-ragged-source.json').read_text())
    bases = {'q2': (ROOT / candidate['candidate'], candidate['source_file_hashes']),
             'ud': (ROOT / '.deps/gufo-base', pristine['files'])}
    edits = []
    manifests = {}
    for name in ('access-edits.json', 'sampling-edits.json'):
        p = CORE / 'adapters/gufo-state' / name
        r = json.loads(p.read_text())
        if r['source_pin'] != PIN:
            raise ValueError('State/sampling source pin differs')
        edits.extend(r['edits'])
        manifests[name] = digest(p)
    variants = {}
    for key, (base, expected) in bases.items():
        if inventory(base) != expected:
            raise ValueError('Measured provider source differs: ' + key)
        changed = {}
        for edit in edits:
            name = edit['path']
            text = changed.get(name, (base / name).read_text())
            if text.count(edit['old']) != 1:
                raise ValueError('Missing/ambiguous composition edit: ' + name)
            changed[name] = text.replace(edit['old'], edit['new'])
        shutil.copytree(base, outputs[key])
        for name, text in changed.items():
            (outputs[key] / name).write_text(text)
        files = inventory(outputs[key])
        delta = sorted(n for n in files if files[n] != expected[n])
        if delta != sorted(changed):
            raise ValueError('Unexpected provider delta')
        variants[key] = dict(source=str(outputs[key].relative_to(ROOT)),
                             parent=str(base.relative_to(ROOT)), files=files,
                             changed_files=delta, unchanged_files=len(files)-len(delta))
    report = dict(schema='synapse-lie.q2-curve-source.v1', source_pin=PIN,
                  core_commit=CORE_COMMIT, core_source=str(CORE.relative_to(ROOT)),
                  core_files=core_files, core_archive_sha256=hashlib.sha256(source).hexdigest(),
                  edit_manifests=manifests, variants=variants,
                  scope='Frozen common C17 HTTP/worker/state adapter; friend access and optional bias/reporting support on both providers; upstream greedy sampling with empty bias. No dense C17 sampler patch, KVC, SSD, MTP or vision admission.',
                  kernel_changes_from_parents=False, runtime_qualified=False,
                  canonical_curve_measured=False, promoted=False, goal_met=False)
    MANIFEST.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(core_files=len(core_files), variants={
        k: dict(changed_files=v['changed_files'], unchanged_files=v['unchanged_files'])
        for k, v in variants.items()}, runtime_qualified=False)))


if __name__ == '__main__':
    main()
