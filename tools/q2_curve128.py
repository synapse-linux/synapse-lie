# SPDX-License-Identifier: MIT
"""Reuse an immutable retained server at the original 133760-token capacity."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def verify_server(root):
    pins = json.loads((root/'config/q2-curve128-binaries.json').read_text())
    if pins['schema'] != 'synapse-lie.q2-curve128-binaries.v1' or pins['context_capacity'] != 133760:
        raise ValueError('Invalid retained128 binary contract')
    manifest_path = root/pins['source_manifest']
    if sha(manifest_path) != pins['source_manifest_sha256']:
        raise ValueError('Retained128 source manifest changed')
    source = json.loads(manifest_path.read_text())
    server = pins['server']
    previous = root.parent/server['label']
    receipt_path = previous/'results/result.json'
    if sha(receipt_path) != server['receipt_sha256']:
        raise ValueError('Retained server build receipt changed')
    receipt = json.loads(receipt_path.read_text())
    if not receipt.get('finished_at') or [c['exit_code'] for c in receipt['commands']] != server['command_exits']:
        raise ValueError('Retained server build closure differs')
    binary = previous/server['binary']
    if sha(binary) != server['binary_sha256'] or receipt['binary_sha256_after'] != server['binary_sha256']:
        raise ValueError('Retained server binary changed')
    for directory, files in [('source', source['variants']['q2']['files']),
                             ('curve-core', source['core_files'])]:
        if inventory(previous/directory) != files or inventory(root/directory) != files:
            raise ValueError('Retained server source inventory changed: ' + directory)
    qualified = pins['numerical_qualification']
    qp = root.parent/qualified['label']/'results/result.json'
    if sha(qp) != qualified['receipt_sha256']:
        raise ValueError('Retained numerical qualification changed')
    qr = json.loads(qp.read_text())
    if not qr.get('finished_at') or any(c['exit_code'] for c in qr['commands']):
        raise ValueError('Retained numerical qualification is incomplete')
    return binary, dict(server, context_capacity=133760, numerical_qualification=qualified,
                        provider_files=len(source['variants']['q2']['files']),
                        core_files=len(source['core_files']), no_build=True)
