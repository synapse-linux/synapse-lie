#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze exact saved binaries and original 32K requests for one .157 A/B."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    previous = ROOT/'config/q2-iq2-stage-layout-r2-window-release.json'
    receipt = read(previous)
    retained = read(ROOT/'config/q2-curve128-binaries.json')['server']
    candidate = read(ROOT/'evidence/q2-select-live-grid-model-r1/results/result.json')
    native = read(ROOT/'config/q2-curve128-binaries.json')['native_bench']
    original = ROOT/'evidence/q2-long-profile-r1/results/full-prefill.requests.jsonl'
    require = lambda condition, message: condition or (_ for _ in ()).throw(ValueError(message))
    require(sha(original) == '200e66bde770068819ce66451f66252acaf6eb021c129fdfed055e893681af58',
            'Original selected 32K request changed')
    cases = [json.loads(line) for line in original.read_text().splitlines()]
    require(len(cases) == 4 and cases[-1]['id'] == 'original-14-prefix-32768' and
            cases[-1]['expected_prompt_tokens'] == 32711,
            'Selected corpus does not end at the original complete 32K case')
    require(candidate['binary_sha256'] == candidate['binary_sha256_after'] and
            candidate['native_bench_binary_sha256'] == native['binary_sha256'] and
            retained['binary_sha256'] == '9993fdce3cf0dc12890ffe0af07f9b5eba23b5ce58321603f3ed238314c931b3',
            'Saved binary bindings differ')
    def binding(label, relative, digest):
        return dict(label=label, path=str(REMOTE/relative), sha256=digest)
    plan = dict(schema='synapse-lie.q2-select-live-grid-pair-plan.v1',
                previous_release=previous.name, previous_release_sha256=sha(previous),
                runner_sha256=sha(ROOT/'tools/q2-select-live-grid-pair.py'),
                order=['retained', 'live-grid', 'live-grid', 'retained'],
                capacity=133760, chunk=2048, prefix_tokens=32711,
                retained_server=binding('saved retained',
                    retained['label']+'/'+retained['binary'], retained['binary_sha256']),
                candidate_server=binding('saved live-grid',
                    'q2-select-live-grid-model-r1/build/hip/cmake/curve/core/synapse-lie-server',
                    candidate['binary_sha256']),
                client=binding('saved native C client',
                    native['label']+'/build/native-bench/synapse-lie-bench',
                    native['binary_sha256']),
                requests=binding('original preparation and complete 32K prefix',
                    'q2-select-live-grid-pair-requests.jsonl', sha(original)),
                model_stats=receipt['models'],
                previous_retired_identities=len(receipt['retired_identities']),
                previous_retired_groups=len(receipt['retired_groups']),
                no_rebuild=True, no_model_mutation=True, no_remote_cleanup=True,
                no_new_benchmark_tokens=True, no_cached_prefix=True,
                scope='Four original complete32K prefill requests in A-B-B-A order. '
                      'Each arm starts a fresh server and replays the original three '
                      'preparation requests plus the exact32711-token prefix using '
                      'the saved native C benchmark binary. Capacity133760, chunk2048, '
                      'C1 AR, eight output tokens, no prefix cache, original model bytes. '
                      'No GPU build, tuning, model conversion or broad curve. Collect '
                      'all artifacts before release; no remote cleanup.')
    target = ROOT/'config/q2-select-live-grid-pair-plan.json'
    require(not target.exists(), 'Plan already exists')
    with target.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(plan=str(target), sha256=sha(target),
                          previous_release_sha256=plan['previous_release_sha256'],
                          runner_sha256=plan['runner_sha256'])))


if __name__ == '__main__':
    main()
