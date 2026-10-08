#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the model-owned serial prefill/reactive decode source capsule."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / '.deps/lie-ds4-walk-bench'
OUTPUT = ROOT / '.deps/lie-core-model-flow'
PARENT_MANIFEST = ROOT / 'config/ds4-walk-bench-source.json'
MANIFEST = ROOT / 'config/core-model-flow-source.json'
PATCH = ROOT / 'experiments/core-model-flow.patch'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = json.loads(PARENT_MANIFEST.read_text())
    manifest = json.loads(MANIFEST.read_text())
    assert manifest['parent_manifest_sha256'] == sha(PARENT_MANIFEST)
    assert manifest['patch_sha256'] == sha(PATCH)
    assert manifest['generator_sha256'] == sha(Path(__file__))
    for name, digest in parent['files'].items():
        assert sha(PARENT / name) == digest, f'Parent differs: {name}'
    if '--verify' not in sys.argv[1:]:
        if OUTPUT.exists():
            raise SystemExit('Preserve existing model-flow source capsule')
        subprocess.run(['cp', '-a', '--reflink=auto', str(PARENT), str(OUTPUT)], check=True)
        subprocess.run(['git', 'apply', str(PATCH)], cwd=OUTPUT, check=True)
    for name, digest in manifest['changed_files'].items():
        assert sha(OUTPUT / name) == digest, f'Model-flow source differs: {name}'
    print(json.dumps({'source': str(OUTPUT.relative_to(ROOT)),
                      'changed_files': len(manifest['changed_files']),
                      'verified': True}))


if __name__ == '__main__':
    main()
