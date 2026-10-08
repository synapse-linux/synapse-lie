#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify paired PLE host fixtures; no inference or throughput claim."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve_evidence', ROOT/'tools/analyze-q2-curve.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
require = common.require


def observations(text):
    rows = []
    for line in text.splitlines():
        begin = line.find('{"fixture":"ple-cache-first"')
        if begin >= 0:
            rows.append(json.loads(line[begin:]))
    keys = [(r['format'], r['strict']) for r in rows]
    require(len(rows) == 4 and set(keys) == {
        ('BF16', True), ('BF16', False), ('IQ4_NL', True), ('IQ4_NL', False)},
        'Missing, duplicated or unknown paired observations')
    for row in rows:
        require(type(row['strict']) is bool and row['exact_rows'] is True
                and type(row['pread_calls']) is int
                and type(row['resident_pread_calls']) is int
                and row['unique_cold_rows'] == 1024
                and row['resident_rows'] == 128 and row['pread_calls'] >= 1024
                and 0 <= row['resident_pread_calls'] <= 128
                and row['pread_calls'] == 1024 + row['resident_pread_calls'],
                'Incomplete fixture values or read accounting')
        if row['strict']:
            require(row['resident_pread_calls'] == 0, 'Candidate reread a resident row')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite a result')
    receipt = common.artifacts(args.cohort)
    require(receipt['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            receipt['mode'] == 'ple-cache-first-cpu' and not receipt['model_access'],
            'No successful PLE host cohort')
    require(len(receipt['commands']) == 6, 'Unexpected qualification command count')
    candidate = common.read(ROOT/'config/q2-ple-cache-first-source.json')
    parent = common.read(ROOT/'config/q2-curve-source.json')['variants']['q2']
    require(common.sha(ROOT/'config/q2-curve-source.json') == candidate['parent_manifest_sha256'],
            'Canonical parent changed')
    require(candidate['base'] == parent['source'] and
            candidate['files'].keys() == parent['files'].keys() and
            [k for k in candidate['files'] if candidate['files'][k] != parent['files'][k]] ==
            ['src/models/qwen38_flash_next/ngram.cpp'], 'Unexpected provider changes')
    with tarfile.open(args.cohort/'source.tar.gz') as archive:
        for prefix, expected in [('source', candidate['files']), ('ple-control-source', parent['files'])]:
            actual = {m.name[len(prefix)+1:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                      for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix+'/')}
            require(actual == expected, 'Paired source inventory changed: '+prefix)
        fixture_sha = hashlib.sha256(archive.extractfile('tests/q2_ple_cache_first.cpp').read()).hexdigest()
    profiles = {}
    for name, log in [('debug', '03.log'), ('asan_ubsan', '06.log')]:
        text = (args.cohort/'results'/log).read_text()
        require('100% tests passed out of 21' in text and 'q2_ple_cache_control' in text
                and 'q2_ple_cache_first' in text and 'ngram' in text,
                'Missing complete paired host suite')
        profiles[name] = observations(text)
    report = dict(schema='synapse-lie.q2-ple-cache-first-host.v1',
        scope='Private BF16/IQ4 row fixtures and original host checks; no model access or GPU performance',
        cohort=str(args.cohort), profiles=profiles,
        fixture_sha256=fixture_sha, reference_files_verified=len(parent['files']),
        candidate_files_verified=len(candidate['files']), artifacts=len(receipt['artifacts']),
        command_exits=[c['exit_code'] for c in receipt['commands']],
        control_collision_rereads_observed=all(r['resident_pread_calls'] > 0
            for rows in profiles.values() for r in rows if not r['strict']),
        candidate_resident_rereads=0, original_model_validated=False,
        performance_validated=False, promoted=False, goal_met=False)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
