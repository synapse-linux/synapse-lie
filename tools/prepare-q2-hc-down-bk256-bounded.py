#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain the first HC port and prepare a bounded-unroll numerical sibling."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    parent_path = ROOT/'config/q2-hc-down-bk256-source.json'
    parent = json.loads(parent_path.read_text())
    source = ROOT/parent['candidate']
    if inventory(source) != parent['files']:
        raise ValueError('First HC port changed')
    candidate = ROOT/'.deps/gufo-q2-hc-down-bk256-bounded'
    patch_path = ROOT/'experiments/q2-hc-down-bk256-bounded.patch'
    manifest_path = ROOT/'config/q2-hc-down-bk256-bounded-source.json'
    if any(p.exists() for p in (candidate, patch_path, manifest_path)):
        raise ValueError('Refusing to overwrite a retained candidate')
    shutil.copytree(source, candidate)
    name = 'src/models/qwen38_flash_next/kernels/rocm/q2_hc_down_bk256.inc'
    include = candidate/name
    text = include.read_text()
    old = '#pragma unroll\n        for (int kk = 0; kk < BK; kk += 16) {'
    if text.count(old) != 1:
        raise ValueError('K16 unroll anchor changed')
    include.write_text(text.replace(old, '#pragma unroll 2\n        for (int kk = 0; kk < BK; kk += 16) {'))
    files = inventory(candidate)
    changed = [n for n, digest in files.items() if parent['files'].get(n) != digest]
    if changed != [name]:
        raise ValueError('Bounded sibling changes more than K16 unrolling')
    patch = '// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        (source/name).read_text().splitlines(keepends=True),
        include.read_text().splitlines(keepends=True), fromfile='a/'+name, tofile='b/'+name))
    with patch_path.open('x') as stream:
        stream.write(patch)
    report = dict(schema='synapse-lie.q2-hc-down-bk256-bounded-source.v1',
        base=parent['candidate'], candidate=str(candidate.relative_to(ROOT)),
        parent_manifest='config/'+parent_path.name, parent_manifest_sha256=sha(parent_path),
        measured_model_parent=parent['base'], public_origin=parent['public_origin'],
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path),
        files=files, changed_files=changed, unchanged_files=len(files)-1,
        geometry=parent['geometry'], compiler_change='Only K16 loop unroll factor16 to2',
        original_f16_weights=True, original_f16_activations=True, bf16_conversion=False,
        two_fp32_k16_chains=True, additional_device_allocations=0,
        new_gpu_run=False, new_model_forward=False, numerical_qualification=False,
        performance_qualification=False, goal_met=False)
    with manifest_path.open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(candidate=report['candidate'], files=len(files), changed=changed,
                         arithmetic_source_changed=False, gpu_run=False)))


if __name__ == '__main__':
    main()
