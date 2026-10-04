#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seal the independently built Gufo control beside the pinned Point LIE client."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


GUIFO_PIN = 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e'
ROCWMMA_PIN = '48b7db12a9ade97f0b7ab2ff9321ba0cbb4e5b77'
UPSTREAM_MANIFEST_SHA = '8891dc1d32fdebbeba4a0fe13e3a13c5a9d7cdb95483c6b0edec7897a074db51'
ROCWMMA_FILES_SHA = '76691eaf997ced3f6ff2f9f028f94c92a47c95fefeaaa3b3031ff5e378459654'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lie-bundle', type=Path, required=True)
    parser.add_argument('--gufo-build', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    base = args.lie_bundle.resolve(strict=True)
    build = args.gufo_build.resolve(strict=True)
    destination = args.destination.absolute()
    if destination.exists():
        raise ValueError('Refusing to replace an existing bundle')
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError('Bundle parent is not a directory')
    source = json.loads((base / 'BUNDLE.json').read_text())
    if (source.get('schema') != 'synapse-lie.point-bundle.v1' or
            source.get('source_commit') != '128f490cfff9713f84f658ad17118272a1cd4ad7'):
        raise ValueError('LIE bundle provenance mismatch')
    for relative, expected in source['artifacts'].items():
        if sha(base / relative) != expected:
            raise ValueError('LIE artifact drift: ' + relative)
    receipt_path = build / 'gufo-build-result.json'
    receipt = json.loads(receipt_path.read_text())
    binary = build / 'gufo-build' / 'gufo'
    patch = build / 'gufo-gfx1150-port.patch'
    if (receipt.get('schema') != 'synapse-lie.point-gufo-port-build.v1' or
            receipt.get('state') != 'BUILT_NOT_GPU_TESTED' or
            receipt.get('exit_code') != 0 or
            receipt.get('upstream_pin') != GUIFO_PIN or
            receipt.get('target') != 'gfx1150' or
            receipt.get('upstream_manifest_sha256') != UPSTREAM_MANIFEST_SHA or
            receipt.get('binary_sha256') != sha(binary) or
            receipt.get('port', {}).get('patch_sha256') != sha(patch)):
        raise ValueError('Gufo build provenance mismatch')
    control = {
        'upstream_pin': GUIFO_PIN,
        'upstream_manifest_sha256': UPSTREAM_MANIFEST_SHA,
        'port_patch_sha256': sha(patch),
        'port_build_result_sha256': sha(receipt_path),
        'rocwmma_pin': ROCWMMA_PIN,
        'rocwmma_files_sha256': ROCWMMA_FILES_SHA,
        'binary_sha256': sha(binary),
        'target': 'gfx1150',
    }
    staging = parent / (destination.name + '.staging')
    if staging.exists():
        raise ValueError('Refusing to replace an existing staging directory')
    try:
        shutil.copytree(base, staging, symlinks=False)
        target = staging / 'runtime/bin/gufo'
        shutil.copy2(binary, target)
        if sha(target) != control['binary_sha256']:
            raise ValueError('Gufo copy hash mismatch')
        source['artifacts']['runtime/bin/gufo'] = control['binary_sha256']
        source['gufo_control'] = control
        (staging / 'BUNDLE.json').write_text(json.dumps(source, indent=2) + '\n')
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({'bundle': str(destination), 'bundle_sha256': sha(destination / 'BUNDLE.json'),
                      'artifacts': source['artifacts'], 'gufo_control': control}, sort_keys=True))


if __name__ == '__main__':
    main()
