# SPDX-License-Identifier: MIT
"""Verify immutable source coverage before reusing an owned MMQ archive."""
import hashlib
from pathlib import Path

HC_KERNEL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'


def verify_sources(reference, candidate):
    def inventory(root):
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(Path(root).rglob('*')) if p.is_file()}
    old, new = inventory(reference), inventory(candidate)
    if not old or set(old) != set(new):
        raise RuntimeError('MMQ reuse requires identical source inventories')
    changed = [name for name in old if old[name] != new[name]]
    if any(name != HC_KERNEL for name in changed):
        raise RuntimeError('MMQ reuse source differs outside the HC kernel')
    return {'files_verified': len(old), 'changed': changed,
            'reference_manifest_sha256': hashlib.sha256(repr(sorted(old.items())).encode()).hexdigest(),
            'candidate_manifest_sha256': hashlib.sha256(repr(sorted(new.items())).encode()).hexdigest()}
