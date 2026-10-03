#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a component-only 128-row tile for the existing scaled Q2 route."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-scaled-input'
OUT = ROOT / '.deps/gufo-q2-bench-scaled-tiles'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'config/q2-scaled-input-source.json').read_text())
    for entry in manifest['changed_files']:
        if digest(BASE / entry['path']) != entry['sha256']:
            raise ValueError('Scaled input base changed: ' + entry['path'])
    original = (BASE / REL).read_text()
    anchor = '    default:\n      return false;\n'
    if original.count(anchor) != 1:
        raise ValueError('Unexpected scaled dispatch anchor')
    changed = original.replace(anchor, '''  case 128:
    LaunchRoutedQ2Scaled<128>(w, x, inverse, tiles, n_tiles, bounds, slots, out,
                             m, k, stream);
    break;
''' + anchor)
    shutil.copytree(BASE, OUT)  # Refuse to overwrite prior experimental evidence.
    (OUT / REL).write_text(changed)
    subprocess.run(['clang-format', '-i', str(OUT / REL)], check=True)
    patch = ROOT / 'experiments/q2-scaled-tiles.patch'
    patch.write_text(''.join(difflib.unified_diff(
        original.splitlines(True), (OUT / REL).read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    files = sorted(p.relative_to(BASE) for p in BASE.rglob('*') if p.is_file())
    differences = [str(p) for p in files if digest(BASE / p) != digest(OUT / p)]
    if differences != [str(REL)]:
        raise ValueError('Unexpected source differences')
    report = {
        'scope': 'Component-only tile experiment; no measured benefit or numerical admission',
        'pin': manifest['pin'], 'base': str(BASE.relative_to(ROOT)),
        'candidate': str(OUT.relative_to(ROOT)),
        'changed_files': [{'path': str(REL), 'base_sha256': digest(BASE / REL),
                           'sha256': digest(OUT / REL)}],
        'patch_sha256': digest(patch), 'source_files': len(files),
        'base_files': {str(p): digest(BASE / p) for p in files},
        'model_dispatch_changed': False, 'qualified_source_changed': False,
        'tensor_allocation_bytes_added': 0,
        'contract': 'Same scaled F16 inputs, Q2 weight palette, ordered F32 WMMA sums and inverse scale; tile48 versus tile128',
        'limits': 'Existing scaled-input numerical failures remain; require exact tile replay and unchanged independent checks. GPU runtime pending.'}
    (ROOT / 'config/q2-scaled-tiles-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'base_files'}))


if __name__ == '__main__':
    main()
