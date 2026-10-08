#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one native original-32K HC result, preserving every saved reference."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-hc-scalar-native32-r1'
spec = importlib.util.spec_from_file_location(
    'hc_native', ROOT / 'tools/q2-hc-scalar-native32-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    plan = read(ROOT / 'config/q2-hc-scalar-native32-plan.json')
    require(sha(EVIDENCE / 'plan.json') == sha(ROOT / 'config/q2-hc-scalar-native32-plan.json'),
            'Frozen plan differs')
    require(sha(ROOT / 'tools/q2-hc-scalar-native32-window.py') == plan['runner_sha256'],
            'Validator differs from measured runner')
    artifacts = read(EVIDENCE / 'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected evidence differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged evidence differs: ' + name)
    for name, digest in plan['saved_reference_sha256'].items():
        require(sha(ROOT / name) == digest, 'Historical reference differs: ' + name)
    result = read(EVIDENCE / 'results/native-result.json')
    release = read(EVIDENCE / 'release.json')
    require(result['state'] == 'COMPLETE' and len(result['arms']) == 1 and
            result['plan_sha256'] == sha(EVIDENCE / 'plan.json'), 'Native run incomplete')
    require(release['pair_result_sha256'] == sha(EVIDENCE / 'results/native-result.json') and
            release['plan_sha256'] == sha(EVIDENCE / 'plan.json') and
            release['pair_state'] == 'COMPLETE' and release['kfd_empty'] and
            release['original_model_stats_unchanged'] and release['original_leases_free'] and
            not release['gpu_reserved'], 'Closure differs')
    for label in ('cpu-test', 'verify'):
        require(read(EVIDENCE / (label + '-command.json'))['exit_code'] == 0,
                'Preliminary command failed')
    child = read(EVIDENCE / 'results/00-hc-scalar.children.json')
    require(child['server_exit_code'] == 0 and child['client_exit_code'] == 0,
            'Native child exit differs')
    cases = [json.loads(line) for line in (EVIDENCE / 'requests.jsonl').read_text().splitlines()]
    measured = window.validate_output(EVIDENCE / 'results/00-hc-scalar.jsonl', cases)
    # The runner serializes tuple token pieces as JSON arrays. Normalize only
    # the container representation; every piece/value must still compare equal.
    require(result['arms'][0]['outputs'] == json.loads(json.dumps(measured['outputs'])),
            'Native parsed outputs differ')
    refs = []
    for name in ('00-retained.jsonl', '03-retained.jsonl'):
        path = ROOT / 'evidence/q2-select-live-grid-pair-r2/results' / name
        original = window.validate_output(path, cases)
        refs.append({'name': name, 'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                     'prefill_tps': original['prefill_tps'], 'decode_tps': original['decode_tps'],
                     'all_four_outputs_exact': original['outputs'] == measured['outputs'],
                     'prefill_change_percent': 100 * (measured['prefill_tps'] /
                                                       original['prefill_tps'] - 1),
                     'decode_change_percent': 100 * (measured['decode_tps'] /
                                                      original['decode_tps'] - 1)})
    original_curve = next(r for r in read(ROOT / 'config/q2-full-prefill128-decode-results.json')['rows']
                          if r['tokens'] == 32711)
    historical = {'prefill_tps': original_curve['current_prefill_tps'],
                  'decode_tps': original_curve['current_decode_tps'],
                  'prefill_change_percent': 100 * (measured['prefill_tps'] /
                                                   original_curve['current_prefill_tps'] - 1),
                  'decode_change_percent': 100 * (measured['decode_tps'] /
                                                  original_curve['current_decode_tps'] - 1),
                  'same_request_different_preceding_sequence': True}
    telemetry = [json.loads(line) for line in
                 (EVIDENCE / 'results/00-hc-scalar.telemetry.jsonl').read_text().splitlines()]
    report = {'schema': 'synapse-lie.q2-hc-scalar-native32-results.v1',
              'source_commit': plan['source_commit'], 'plan_sha256': sha(EVIDENCE / 'plan.json'),
              'server_sha256': plan['candidate_server']['sha256'],
              'client_sha256': plan['client']['sha256'],
              'request_sha256': plan['requests']['sha256'],
              'tokens': 32711, 'prefill_calls': 16, 'full_chunks': 15, 'tail_tokens': 1991,
              'cached_tokens': 0, 'output_tokens': 8, 'decode_calls': 8,
              'new_prefill_ms': measured['prefill_ms'], 'new_prefill_tps': measured['prefill_tps'],
              'new_decode_ms': measured['decode_ms'], 'new_decode_tps': measured['decode_tps'],
              'original_full_curve_reference': historical, 'same_sequence_saved_controls': refs,
              'all_saved_outputs_exact': all(r['all_four_outputs_exact'] for r in refs),
              'sampled_peak_cpu_mc': max(r['cpu_temp_mc'] for r in telemetry),
              'sampled_peak_gpu_mc': max(int(r['gpu_temp_mc']) for r in telemetry),
              'server_exit_code': child['server_exit_code'], 'client_exit_code': child['client_exit_code'],
              'artifact_count': len(artifacts), 'release_at': release['at'],
              'release_sha256': sha(EVIDENCE / 'release.json'),
              'retired_identities': len(release['retired_identities']),
              'retired_groups': len(release['retired_groups']),
              'controls_rebuilt_or_rerun': False, 'new_precision_reduction': False,
              'sustained_tg128_measured': False, 'full_128k_measured': False,
              'independent_parent_quality_qualified': False, 'goal_met': False,
              'limits': ['One new observation; historical controls are not contemporaneous.',
                         'Same-sequence controls and earlier full-curve observation remain separate.',
                         'Eight native decode calls are not the direct fixed TG128 scope.',
                         'Streamed output equality does not qualify inherited task quality.']}
    (ROOT / 'config/q2-hc-scalar-native32-results.json').write_text(
        json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
