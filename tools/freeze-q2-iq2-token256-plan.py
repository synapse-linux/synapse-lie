#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the private IQ2 token256 component after the .157 host cohort."""

import hashlib
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'q2-iq2-token256'
PREVIOUS_SHA = 'c087ce07de0fc16d3b058223b3fde68383271da0be8333d85236c68fd5d94aca'
FIXTURES = (
    'CMakeLists.txt', 'cmake/hip/CMakeLists.txt',
    'experiments/iq2_token256_tiles.c',
    'experiments/iq2_token256_tiles.h',
    'experiments/q2-iq2-token256-probe.patch',
    'experiments/q2_iq2_tail16_routes.inc',
    'tests/q2_iq2_token256.hip',
    'tests/q2_iq2_token256_tiles.py',
    'tests/q2_remote_test.py',
    'tools/q2-remote.py', 'tools/q2-runner.py',
    'tools/q2_process.py', 'tools/q2_thermal.py',
    'tools/q2_window_registry.py',
    'tools/prepare-q2-iq2-token256-probe.py',
    'tools/analyze-q2-iq2-token256-probe.py',
    'config/q2-iq2-token256-probe-source.json',
    'config/q2-iq2-token256-probe-static.json',
    'config/q2-iq2-fixed-bounds-source.json',
    'config/q2-current-routing-v2-results.json',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    output = ROOT / 'config' / (PREFIX + '-plan.json')
    require(not output.exists(), 'Preserve existing plan')
    host = PREFIX + '-host-r1'
    directory = ROOT / 'evidence' / host
    result = json.loads((directory / 'results/result.json').read_text())
    collection = json.loads((directory / 'collection.json').read_text())
    require(result['mode'] == 'cpu' and
            result['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            result['finished_at'] and not result['model_access'] and
            len(result['commands']) == 6 and
            all(command['exit_code'] == 0 for command in result['commands']),
            'Current .157 host cohort did not pass')
    require(collection['verified_artifacts'] == 7 and
            collection['sha256'] == sha(directory / 'results.tar.gz'),
            'Host collection differs')
    for name in ('03.log', '06.log'):
        log = (directory / 'results' / name).read_text()
        require('100% tests passed out of 43' in log and
                'iq2_token256_tiles' in log and 'q2_remote' in log,
                'Current Debug/ASan launcher and map checks missing')
    fixtures = {name: sha(ROOT / name) for name in FIXTURES}
    with tarfile.open(directory / 'source.tar.gz') as archive:
        for name, digest in fixtures.items():
            member = archive.getmember(name)
            require(member.isfile() and
                    hashlib.sha256(archive.extractfile(member).read()).hexdigest() == digest,
                    'Tested host capsule differs: ' + name)
    previous = ROOT / 'config/q2-select-score-group4-window-release.json'
    require(sha(previous) == PREVIOUS_SHA, 'Previous release differs')
    plan = {
        'schema': 'synapse-lie.q2-iq2-token256-plan.v1',
        'previous_release': str(previous.relative_to(ROOT)),
        'previous_release_sha256': PREVIOUS_SHA,
        'host': host,
        'host_result_sha256': sha(directory / 'results/result.json'),
        'host_source_capsule_sha256': sha(directory / 'source.tar.gz'),
        'host_collection_sha256': sha(directory / 'results.tar.gz'),
        'host_test_counts': {'debug': 43, 'asan_ubsan': 43},
        'fixtures': fixtures,
        'components': [{'label': PREFIX + '-component-r1',
                        'mode': 'iq2-token256-check',
                        'variant': 'iq2-token256-probe'}],
        'arms': [],
        'admission_path': 'config/' + PREFIX + '-window-admission.json',
        'release_path': 'config/' + PREFIX + '-window-release.json',
        'window_helper': 'tools/' + PREFIX + '-window.py',
        'window_helper_sha256': sha(ROOT / ('tools/' + PREFIX + '-window.py')),
        'phase_helper': 'tools/' + PREFIX + '-phase.py',
        'phase_helper_sha256': sha(ROOT / ('tools/' + PREFIX + '-phase.py')),
        'preflight_helper': 'tools/' + PREFIX + '-preflight.py',
        'preflight_helper_sha256': sha(ROOT / ('tools/' + PREFIX + '-preflight.py')),
        'scope': 'One private gfx1151 IQ2 token256 gate/up component only. Check all '
                 'guarded outputs and immutable inputs against the retained 128/64-token '
                 'producer on edge and saved 2048-token routed counts. Three rotating '
                 'weight sets and interleaved completed timings. No original-weight '
                 'model inference, saved control rebuild, Q4, full curve, dependency '
                 'installation, host tuning or remote cleanup. Collect every result '
                 'and release the window before performance analysis.',
        'gpu_admitted': False,
        'model_inference': False,
        'production_dispatch_changed': False,
    }
    with output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'plan_sha256': sha(output), 'fixtures': len(fixtures),
                      'gpu_admitted': False}))


if __name__ == '__main__':
    main()
