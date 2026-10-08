#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the exact first-party C17 benchmark/adapter behind the 26.049 baseline."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '7f85ef8090506c32998780a8249aa0e10cd9e091'
FILES = ('LICENSE', 'tools/executor-bench.c', 'include/lie/executor.h',
         'adapters/gufo.cpp', 'adapters/gufo_binding.c', 'adapters/gufo_device.cpp')


def main():
    previous = json.loads((ROOT/'config/q2-decode-baseline-static.json').read_text())['historical_baseline']
    evidence = Path(previous['main_worktree'])/'evidence/t0-c1-perf-r2'
    manifest = json.loads((evidence/'manifest.json').read_text())
    measurements = (evidence/'remote-results/measurements.jsonl').read_bytes()
    assert manifest['source_commit'] == COMMIT and manifest['source_worktree_clean']
    assert hashlib.sha256(measurements).hexdigest() == previous['measurement_sha256']
    destination = ROOT/'experiments/original-baseline'
    destination.mkdir()  # Never replace a frozen historical source.
    hashes = {}
    for name in FILES:
        raw = subprocess.check_output(['git', 'show', COMMIT+':'+name], cwd=ROOT)
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    report = dict(repository='synapse-lie', commit=COMMIT,
        source='experiments/original-baseline', files=hashes,
        historical_manifest_sha256=hashlib.sha256((evidence/'manifest.json').read_bytes()).hexdigest(),
        historical_measurement_sha256=previous['measurement_sha256'],
        historical_binary_sha256=manifest['files']['lie-executor-bench'],
        scope='Byte-exact first-party benchmark, ABI and adapter; independently pinned Gufo is linked afresh. No old numerical artifact or DS4 source imported.',
        runtime='Pending .157 after verified core handover; full MMQ build required',
        goal_met=False)
    (ROOT/'config/q2-original-baseline-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(commit=COMMIT, frozen_files=len(hashes), source=str(destination))))


if __name__ == '__main__':
    main()
