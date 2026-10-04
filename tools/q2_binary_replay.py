# SPDX-License-Identifier: MIT
"""Replay a pinned, previously qualified counting binary; never rebuild it."""
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p)
            for p in Path(root).rglob('*') if p.is_file()}


def libraries(binary, env):
    result = subprocess.run(['ldd', str(binary)], env=env, capture_output=True,
                            text=True, timeout=30, check=True)
    if 'not found' in result.stdout:
        raise RuntimeError('Replay dependency missing')
    found = {}
    for line in result.stdout.splitlines():
        words = line.split()
        name = words[2] if len(words) > 2 and words[1] == '=>' else words[0] if words else ''
        if name.startswith('/'):
            path = Path(name).resolve(strict=True)
            found[str(path)] = sha(path)
    if not found:
        raise RuntimeError('Replay library inventory empty')
    return found


def verify_replay(root, label, mode, env, library_reader=libraries):
    manifest_path = root/'config/q2-fixed-binary-replay.json'
    manifest = json.loads(manifest_path.read_text())
    if label not in manifest['controls']:
        raise RuntimeError('Unqualified replay label')
    expected = manifest['controls'][label]
    if expected['mode'] != mode:
        raise RuntimeError('Replay mode changed')
    previous = root.parent/label
    receipt_path = previous/'results/result.json'
    if sha(receipt_path) != expected['receipt_sha256']:
        raise RuntimeError('Replay qualification receipt changed')
    receipt = json.loads(receipt_path.read_text())
    if (receipt['mode'] != mode or receipt['state'] != 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
            or not receipt.get('finished_at') or any(c['exit_code'] for c in receipt['commands'])):
        raise RuntimeError('Replay control was not qualified')
    binary = previous/'build/hip/cmake/hip/q2_model'
    digest = sha(binary)
    if digest != expected['binary_sha256'] or digest != receipt['binary_sha256_after']:
        raise RuntimeError('Replay binary changed')
    for source in (previous/'source', root/'source'):
        if inventory(source) != expected['source_files']:
            raise RuntimeError('Replay provider source changed')
    for directory in (previous, root):
        for name, key in [('experiments/counting-baseline/q2_model.cpp', 'fixture_sha256'),
                          ('tests/q2_profile_markers.hip', 'markers_sha256')]:
            if sha(directory/name) != expected[key]:
                raise RuntimeError('Replay counting fixture changed')
    runtime = library_reader(binary, env)
    if runtime != expected['libraries']:
        raise RuntimeError('Replay library identity changed')
    return binary, dict(reference=str(previous), manifest_sha256=sha(manifest_path),
                        receipt_sha256=expected['receipt_sha256'], binary_sha256=digest,
                        source_files_verified=len(expected['source_files']), libraries=runtime,
                        build_commands=0, original_build_unchanged=True,
                        historical_library_hashes_available=False,
                        library_scope='Installed libraries pinned immediately before this campaign; historical result did not hash libraries')
