#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind new geometry/dispatch to unchanged measured numerical source."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = ROOT/'config/q2-iq2-short-tiles-source-v2.json'
    source = json.loads(manifest.read_text())['variants']['iq2-short-tiles']
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['iq2-raw-prefetch']
    for key in ('parent_manifest', 'measured_parent', 'routing_audit', 'patch'):
        if sha(ROOT/source[key]) != source[key+'_sha256']:
            raise ValueError('Source binding changed: '+key)
    inventory = {str(p.relative_to(ROOT/source['source'])):sha(p)
                 for p in sorted((ROOT/source['source']).rglob('*')) if p.is_file()}
    if inventory != source['files'] or len(inventory) != 1027:
        raise ValueError('Provider inventory changed')
    changes = sorted(k for k,v in inventory.items() if parent['files'].get(k) != v)
    if changes != source['changed_files'] or len(changes) != 5:
        raise ValueError('Unexpected source changes')
    unchanged = source['unchanged_numerical_sources']
    if len(unchanged) != 11 or any(parent['files'][k] != v for k,v in unchanged.items()):
        raise ValueError('Measured numerical source changed')
    for name,digest in source['c17_map_files'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('C17 map changed')
    prep = ROOT/'evidence/q2-iq2-short-tiles-preparation'
    labels = ('map-debug', 'map-asan-unrestricted', 'fixture-host', 'fixture-device',
              'executor-host-includes', 'launcher-guards', 'generation-v2')
    receipts = {}
    for label in labels:
        path = prep/(label+'-command.json')
        row = json.loads(path.read_text())
        if row['exit_code'] != 0:
            raise ValueError('Incomplete preparation: '+label)
        receipts[str(path.relative_to(ROOT))] = sha(path)
    rejected = {}
    for label in ('map-asan', 'executor-host'):
        path = prep/(label+'-command.json')
        row = json.loads(path.read_text())
        if row['exit_code'] != 1:
            raise ValueError('Preserved initial failure changed')
        rejected[str(path.relative_to(ROOT))] = sha(path)
    out = ROOT/'config/q2-iq2-short-tiles-static.json'
    with out.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-short-tiles-static.v1',
            source_manifest_sha256=sha(manifest), provider_files=1027,
            changed_files=changes, unchanged_numerical_sources=unchanged,
            host_map_coverage='Independent full-row coverage and original128/64 descriptor preservation',
            preparation_receipts=receipts, preserved_initial_failure_receipts=rejected,
            initial_failure_causes=['LeakSanitizer rejected sandbox ptrace; unrestricted same binary passes',
                                    'Standalone executor syntax command omitted existing MMQ include directory'],
            launcher_guard_tests=105, gpu_run=False, model_inference=False,
            numerical_acceptance=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, numerical_sources_unchanged=11,
                         changed_files=changes, gpu_run=False)))


if __name__ == '__main__':
    main()
