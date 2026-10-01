#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Checked HIP candidate overlay; production linkage remains forbidden."""
import datetime
import json
from pathlib import Path
import q2_port

ROOT = q2_port.ROOT
RECIPE = ROOT / 'adapters/gufo-q2/hip-edits.json'


def member(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or str(p) != name:
        raise ValueError('invalid Q2 HIP member')
    return p


def checked_variant(base, recipe, load_owned, host_sha):
    if (recipe['schema'] != 'synapse-lie.q2-hip-edits.v1' or
        recipe['upstream_pin'] != q2_port.PIN or
        recipe['host_recipe_sha256'] != host_sha or
        recipe['runtime_link_allowed'] is not False):
        raise ValueError('Q2 HIP recipe identity or admission mismatch')
    result = dict(base)
    for name, change in recipe['files'].items():
        member(name)
        if name not in base or q2_port.sha(base[name]) != change['before_sha256']:
            raise ValueError('Q2 HIP base drift: ' + name)
        data = q2_port.transform(base[name], change['edits'])
        if q2_port.sha(data) != change['after_sha256']:
            raise ValueError('Q2 HIP edit result drift: ' + name)
        result[name] = data
    for name, spec in recipe['owned_files'].items():
        member(name)
        origin = member(spec['path'])
        if name in base or origin.parts[:2] != ('adapters', 'gufo-q2'):
            raise ValueError('invalid Q2 owned-file destination/source')
        data = load_owned(spec['path'])
        if q2_port.sha(data) != spec['sha256'] or b'SPDX-License-Identifier: MIT' not in data:
            raise ValueError('Q2 owned source identity/license drift')
        result[name] = data
    return result


def read_regular(root, name):
    p = root / member(name)
    if any(x.is_symlink() for x in [p, *p.parents]) or not p.is_file():
        raise ValueError('nonregular Q2 source: ' + name)
    return p.read_bytes()


def prepare(destination):
    manifest_bytes = (ROOT / 'third_party/gufo-source.json').read_bytes()
    host_bytes = q2_port.RECIPE.read_bytes()
    hip_bytes = RECIPE.read_bytes()
    host = q2_port.checked_variant(json.loads(manifest_bytes), json.loads(host_bytes),
                                  lambda n: read_regular(ROOT / '.deps/gufo-f783fedb', n))
    hip = json.loads(hip_bytes)
    files = checked_variant(host, hip, lambda n: read_regular(ROOT, n), q2_port.sha(host_bytes))
    dst = Path(destination)
    if any(x.is_symlink() for x in [dst, *dst.parents]):
        raise ValueError('symlink Q2 HIP output')
    dst.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, data in files.items():
        p = dst / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as f:
            f.write(data)
        hashes[name] = q2_port.sha(data)
        if q2_port.sha(p.read_bytes()) != hashes[name]:
            raise ValueError('Q2 HIP materialization drift')
    receipt = {'schema': 'synapse-lie.q2-hip-source.v1',
               'state': 'HIP_CANDIDATE_NOT_GPU_QUALIFIED', 'upstream_pin': q2_port.PIN,
               'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'runtime_link_allowed': False, 'gpu_execution': False,
               'pristine_manifest_sha256': q2_port.sha(manifest_bytes),
               'host_recipe_sha256': q2_port.sha(host_bytes),
               'hip_recipe_sha256': q2_port.sha(hip_bytes),
               'preparer_sha256': q2_port.sha(Path(__file__).read_bytes()),
               'host_preparer_sha256': q2_port.sha(Path(q2_port.__file__).read_bytes()),
               'files': hashes}
    with (dst / 'LIE-Q2-HIP-SOURCE.json').open('x') as f:
        f.write(json.dumps(receipt, indent=2) + '\n')
    return receipt
