#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a distinct retry after the collected first-window port-check failure."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    first_plan = ROOT/'config/q2-select-live-grid-pair-plan.json'
    first_release = ROOT/'config/q2-select-live-grid-pair-window-release.json'
    base_release = ROOT/'config/q2-iq2-stage-layout-r2-window-release.json'
    old = read(first_plan)
    release = read(first_release)
    base = read(base_release)
    if (release['state'] != 'Q2_LIVE_GRID_PAIR_RELEASED' or
            release['pair_state'] != 'FAILED' or
            release['plan_sha256'] != sha(first_plan) or
            release['pair_result_sha256'] != sha(ROOT/'evidence/q2-select-live-grid-pair-r1/results/pair-result.json') or
            old['previous_release_sha256'] != sha(base_release) or
            old['model_stats'] != base['models']):
        raise ValueError('First window failure and full base release differ')
    plan = dict(old)
    plan.update(schema='synapse-lie.q2-select-live-grid-pair-plan.v2',
                previous_release=first_release.name,
                previous_release_sha256=sha(first_release),
                base_release=base_release.name,
                base_release_sha256=sha(base_release),
                runner_sha256=sha(ROOT/'tools/q2-select-live-grid-pair-r2.py'),
                prior_failed_window_result_sha256=release['pair_result_sha256'],
                prior_failed_window_release_sha256=sha(first_release),
                scope='Distinct A-B-B-A retry on the identical original32711-token '
                      'full prefill. The first window stopped after its retained '
                      'arm because a pre-server port check did not allow loopback '
                      'TIME_WAIT. Only that socket check changes; binaries, request, '
                      'capacity133760/chunk2048/C1 AR, cache policy and output '
                      'budget are unchanged. Four fresh servers, no GPU build, '
                      'tuning, conversion, broad curve, model mutation or cleanup. '
                      'Collect all artifacts before release.')
    target = ROOT/'config/q2-select-live-grid-pair-r2-plan.json'
    if target.exists():
        raise ValueError('Retry plan already exists')
    with target.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(plan=str(target), sha256=sha(target),
                          previous_release_sha256=plan['previous_release_sha256'],
                          runner_sha256=plan['runner_sha256'])))


if __name__ == '__main__':
    main()
