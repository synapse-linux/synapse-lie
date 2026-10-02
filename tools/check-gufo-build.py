#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify pinned source and private runtime archives; never open model weights."""
import hashlib
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    state_access=sys.argv[-1:] == ['--state-access']
    source,build=(p.resolve() for p in map(Path,sys.argv[1:-1] if state_access else sys.argv[1:]))
    if not source.is_relative_to(root/'.deps') or not build.is_relative_to(root/'build'):
        raise ValueError('sources and archives must stay inside this repository')
    manifest_path=root/'third_party/gufo-source.json'
    manifest=json.loads(manifest_path.read_text())
    receipt=json.loads((build/'BUILD-RECEIPT.json').read_text())
    if receipt['state']!='LIBRARIES_BUILT_NOT_EXECUTED_NOT_INFERENCE_QUALIFIED': raise ValueError('build not successful')
    if receipt['source_pin']!='f783fedb9bea2ec7de941f6da4e02f4a4596b29e' or receipt['source_manifest_sha256']!=sha(manifest_path): raise ValueError('source identity mismatch')
    files=manifest['files']
    if state_access:
        from gufo_state_source import expected as state_files
        files,_=state_files(root)
        if receipt.get('source_variant')!='lie-state-access-v1' or receipt.get('state_access_edits_sha256')!=sha(root/'adapters/gufo-state/access-edits.json') or receipt.get('variant_files')!=files:
            raise ValueError('state access variant mismatch')
    elif receipt.get('source_variant'):
        raise ValueError('modified provider requires explicit state access selection')
    for name,expected in files.items():
        p=source/name
        if p.is_symlink() or sha(p)!=expected: raise ValueError('source drift: '+name)
    expected_libraries={'libgufo_core.a','src/models/qwen38_flash_next/libgufo_qwen38_flash_next.a',
                        'src/models/qwen38_flash_next/libgufo_qwen38_flash_next_mmq.a'}
    if set(receipt['libraries'])!=expected_libraries or sha(build/'CMakeCache.txt')!=receipt['cmake_cache_sha256']:
        raise ValueError('build manifest/cache drift')
    if receipt.get('scope')=='lie-qwen-only-source-subset' and receipt['subset_cmake_sha256']!=sha(root/'cmake/gufo-runtime/CMakeLists.txt'):
        raise ValueError('subset recipe drift; create a new private build')
    for name,expected in receipt['libraries'].items():
        p=build/name
        if not p.resolve().is_relative_to(build.resolve()) or p.is_symlink() or sha(p)!=expected: raise ValueError('archive drift: '+name)
    print('Verified pinned Gufo sources and private archives; no hardware inference qualification')

if __name__=='__main__': main()
