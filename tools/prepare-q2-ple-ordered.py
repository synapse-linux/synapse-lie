#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the qualified PLE reader with measured ordered IQ2 decode."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/ngram.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def main():
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    ple_path = ROOT/'config/q2-ple-cache-first-source.json'
    curve_path = ROOT/'config/q2-curve-source.json'
    parent, ple, curve = [json.loads(p.read_text()) for p in (parent_path, ple_path, curve_path)]
    base, donor = ROOT/parent['candidate'], ROOT/ple['candidate']
    original = curve['variants']['q2']['files']
    if inventory(base) != parent['files'] or inventory(donor) != ple['files']:
        raise ValueError('Measured parent or host-qualified PLE source changed')
    if ple['parent_manifest_sha256'] != sha(curve_path):
        raise ValueError('PLE parent identity changed')
    if original.keys() != parent['files'].keys() or original.keys() != ple['files'].keys():
        raise ValueError('Different source inventories')
    if [k for k in original if original[k] != ple['files'][k]] != [REL]:
        raise ValueError('PLE donor changes more than the reader')
    if [k for k in original if original[k] != parent['files'][k]] != [
            'src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp']:
        raise ValueError('Ordered decode parent changes more than the measured header')
    host_path = ROOT/'config/q2-ple-cache-first-host-results.json'
    host = json.loads(host_path.read_text())
    if host['command_exits'] != [0]*6 or host['candidate_resident_rereads'] != 0:
        raise ValueError('PLE reader lacks successful host qualification')
    out = ROOT/'.deps/gufo-q2-curve-ple-ordered'
    manifest = ROOT/'config/q2-ple-ordered-source.json'
    if out.exists() or manifest.exists():
        raise ValueError('Refusing to overwrite a composition')
    shutil.copytree(base, out)
    shutil.copyfile(donor/REL, out/REL)
    files = inventory(out)
    if files.keys() != parent['files'].keys() or [
            k for k in files if files[k] != parent['files'][k]] != [REL]:
        raise ValueError('Unexpected composed provider delta')
    report = dict(schema='synapse-lie.q2-ple-ordered-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=files,
        parent_manifest_sha256=sha(parent_path), ple_manifest_sha256=sha(ple_path),
        curve_manifest_sha256=sha(curve_path), host_result_sha256=sha(host_path),
        changed_files=[REL], unchanged_files=len(files)-1,
        ple_reader_sha256=files[REL],
        mechanism='Consume resident PLE rows before publishing misses; preserve ordered IQ2 decode, all numerical kernels and cache capacity.',
        canonical_runtime_validated=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('candidate', 'changed_files', 'unchanged_files')}))


if __name__ == '__main__':
    main()
