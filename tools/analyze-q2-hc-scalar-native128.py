#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the original 130925-token HC trial against its saved unprofiled control."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-hc-scalar-native128-r1'
CONTROL = ROOT / 'evidence/q2-full-prefill128-final-r1/results'
spec = importlib.util.spec_from_file_location(
    'hc_native128', ROOT / 'tools/q2-hc-scalar-native128-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def telemetry(path):
    """Descriptive active samples, never a frequency-normalized benchmark."""
    clocks, busy, cpus, gpus = [], [], [], []
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if 'sensors' in row:
            sensors = row['sensors']
            base = '/sys/class/drm/card1/device/'
            use = int(sensors[base + 'gpu_busy_percent'])
            clock = sensors[base + 'pp_dpm_sclk']
            gpu = next(t['temperature_mc'] for t in row['thermal']
                       if t['device'] == 'amdgpu')
            cpu = max(t['temperature_mc'] for t in row['thermal']
                      if t['device'] == 'k10temp')
        else:
            use, clock = int(row['gpu_busy']), row['gpu_clock']
            gpu, cpu = int(row['gpu_temp_mc']), row['cpu_temp_mc']
        cpus.append(cpu)
        gpus.append(gpu)
        if use >= 80:
            busy.append(use)
            clocks.append(int(re.search(r'(\d+)Mhz \*', clock).group(1)))
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
            'sample_count': len(rows), 'gpu_busy_ge80_samples': len(clocks),
            'active_clock_mean_mhz': statistics.mean(clocks),
            'active_clock_median_mhz': statistics.median(clocks),
            'active_gpu_busy_mean_percent': statistics.mean(busy),
            'sampled_peak_cpu_mc': max(cpus), 'sampled_peak_gpu_mc': max(gpus)}


def main():
    plan_path = ROOT / 'config/q2-hc-scalar-native128-plan.json'
    plan = read(plan_path)
    require(sha(EVIDENCE / 'plan.json') == sha(plan_path), 'Frozen plan differs')
    require(sha(ROOT / 'tools/q2-hc-scalar-native128-window.py') ==
            plan['runner_sha256'], 'Measured validator differs')
    artifacts = read(EVIDENCE / 'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected artifact differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged artifact differs: ' + name)
    for name, digest in plan['saved_reference_sha256'].items():
        require(sha(ROOT / name) == digest, 'Saved reference differs: ' + name)
    result, release = read(EVIDENCE / 'results/native-result.json'), read(EVIDENCE / 'release.json')
    require(result['state'] == 'COMPLETE' and len(result['arms']) == 1 and
            result['plan_sha256'] == sha(plan_path), 'Native result incomplete')
    require(release['pair_result_sha256'] == sha(EVIDENCE / 'results/native-result.json') and
            release['plan_sha256'] == sha(plan_path) and release['pair_state'] == 'COMPLETE' and
            release['kfd_empty'] and release['original_model_stats_unchanged'] and
            release['original_leases_free'] and not release['gpu_reserved'], 'Closure differs')
    for label in ('cpu-test', 'verify', 'run'):
        require(read(EVIDENCE / (label + '-command.json'))['exit_code'] == 0,
                'Command failed: ' + label)
    children = read(EVIDENCE / 'results/00-hc-scalar.children.json')
    require(children['server_exit_code'] == 0 and children['client_exit_code'] == 0,
            'Native child exit differs')
    cases = [json.loads(line) for line in (EVIDENCE / 'requests.jsonl').read_text().splitlines()]
    new = window.validate_output(EVIDENCE / 'results/00-hc-scalar.jsonl', cases)
    old = window.validate_output(CONTROL / 'full-prefill.jsonl', cases)
    require(result['arms'][0]['outputs'] == json.loads(json.dumps(new['outputs'])),
            'Persisted native output differs')
    require(sha(EVIDENCE / 'requests.jsonl') == sha(CONTROL / 'full-prefill.requests.jsonl'),
            'Saved request sequence differs')
    report = {'schema': 'synapse-lie.q2-hc-scalar-native128-results.v1',
              'source_commit': plan['source_commit'], 'plan_sha256': sha(plan_path),
              'server_sha256': plan['candidate_server']['sha256'],
              'client_sha256': plan['client']['sha256'],
              'request_sha256': plan['requests']['sha256'],
              'tokens': 130925, 'prefill_calls': 64, 'full_chunks': 63, 'tail_tokens': 1901,
              'cached_tokens': 0, 'output_tokens': 8, 'decode_calls': 8,
              'all_four_outputs_exact': old['outputs'] == new['outputs'],
              'new': {k: new[k] for k in ('prefill_ms', 'prefill_tps', 'decode_ms', 'decode_tps')},
              'saved_unprofiled': {
                  'path': str((CONTROL / 'full-prefill.jsonl').relative_to(ROOT)),
                  'sha256': sha(CONTROL / 'full-prefill.jsonl'),
                  **{k: old[k] for k in ('prefill_ms', 'prefill_tps', 'decode_ms', 'decode_tps')}},
              'prefill_change_percent': 100 * (new['prefill_tps'] / old['prefill_tps'] - 1),
              'decode_change_percent': 100 * (new['decode_tps'] / old['decode_tps'] - 1),
              'target_prefill_ms': 130925000 / 1500,
              'new_prefill_excess_ms': new['prefill_ms'] - 130925000 / 1500,
              'new_decode_ms_per_call': new['decode_ms'] / 8,
              'target_decode_ms_per_call': 1000 / 30,
              'new_telemetry': telemetry(EVIDENCE / 'results/00-hc-scalar.telemetry.jsonl'),
              'saved_telemetry': telemetry(CONTROL / 'telemetry.jsonl'),
              'server_exit_code': children['server_exit_code'],
              'client_exit_code': children['client_exit_code'], 'artifact_count': len(artifacts),
              'release_at': release['at'], 'release_sha256': sha(EVIDENCE / 'release.json'),
              'retired_identities': len(release['retired_identities']),
              'retired_groups': len(release['retired_groups']),
              'controls_rebuilt_or_rerun': False, 'candidate_rebuilt_for_depth': False,
              'new_precision_reduction': False, 'sustained_tg128_measured': False,
              'independent_parent_quality_qualified': False, 'goal_met': False,
              'limits': ['One new observation against a historical unprofiled control.',
                         'Eight native output calls are not sustained TG128.',
                         'Exact response replay does not qualify inherited task quality.',
                         'Active clock/busy samples describe correlation, not causality.',
                         'Prefill regresses; neither clocks nor cache capture correct its rate.']}
    output = ROOT / 'config/q2-hc-scalar-native128-results.json'
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
