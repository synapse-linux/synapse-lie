#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export exact physical DS4-walk frontiers for the shared-core flow test."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if (not rows or rows[0].get('suite') != 'ds4-walk' or
            rows[0].get('synthetic') or rows[-1] != {'event': 'complete', 'exit_code': 0}):
        raise SystemExit('Require a completed original-weight DS4 walk')
    expected = (2048, 4096, 6144, 8192)
    inputs = [row for row in rows if row.get('event') == 'input']
    if len(inputs) != len(expected):
        raise SystemExit('Expected exactly four input frontiers')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    previous = []
    for size, row in zip(expected, inputs):
        ids = row['physical_ids']
        if (row['prompt_tokens'] != size or len(ids) != size or
                any(type(value) is not int or value < 0 or value > 2147483647 for value in ids) or
                ids[:len(previous)] != previous):
            raise SystemExit(f'Invalid exact prefix at {size}')
        packed = b''.join(value.to_bytes(4, 'little', signed=True) for value in ids)
        if digest(packed) != row['physical_ids_sha256']:
            raise SystemExit(f'Physical ID hash differs at {size}')
        name = f'tokens-{size}.json'
        payload = (json.dumps(ids, separators=(',', ':')) + '\n').encode()
        with (args.output_dir / name).open('xb') as output:
            output.write(payload)
        entries.append({'tokens': size, 'file': name, 'physical_ids_sha256': digest(packed),
                        'file_sha256': digest(payload), 'bytes': len(payload)})
        previous = ids
    manifest = {'schema': 'synapse-lie.core-model-flow-inputs.v1',
                'source': str(args.source), 'source_sha256': digest(raw),
                'source_suite': 'ds4-walk', 'entries': entries}
    with (args.output_dir / 'manifest.json').open('x') as output:
        json.dump(manifest, output, indent=2)
        output.write('\n')
    print(json.dumps({'frontiers': len(entries), 'source_sha256': digest(raw)}))


if __name__ == '__main__':
    main()
