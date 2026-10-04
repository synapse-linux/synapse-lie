# SPDX-License-Identifier: MIT
"""Verify this workstream's retained Q8 arrays before staging and after replay."""
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(root, staged=False):
    root = Path(root)
    plan_path = root/'config/q2-shared-q8-oracle-replay-r2-plan.json'
    plan = json.loads(plan_path.read_text())
    expected = {'shared-q8-n'+str(n)+'-p'+str(p)+'-'+suffix
                for n,p in ((96,0),(97,1),(127,2),(129,0),(2048,0))
                for suffix in ('mixed-reference.bin','q8-reference.bin','independent-q8.bin')}
    if (plan['schema'] != 'synapse-lie.q2-shared-q8-oracle-replay-plan.v1' or
            set(plan['arrays']) != expected or plan['repetitions'] != 8 or
            plan['source_results'] != 'evidence/q2-shared-q8-producer-component-r3/results'):
        raise ValueError('Q8 oracle replay corpus or scope changed')
    for name, sha in plan['fixtures'].items():
        if digest(root/name) != sha:
            raise ValueError('Q8 oracle fixture changed: '+name)
    if not staged and digest(root/plan['source_results']/'result.json') != plan['origin_receipt_sha256']:
        raise ValueError('Q8 original R3 receipt changed')
    data = root/('oracle-replay-data' if staged else plan['source_results'])
    for name, row in plan['arrays'].items():
        path = data/name
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Retained Q8 array changed: '+name)
    return dict(plan_sha256=digest(plan_path), arrays=plan['arrays'],
                model_forward=False, production_kernels_launched=False)
